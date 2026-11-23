# Real-time messaging (issue #5)

Chat, notifications, requests, the inbox, and meeting proposals update over a
WebSocket channel instead of timers. Students also see "Seen" read receipts and
typing indicators. If the connection drops, the app falls back to the previous
polling and catches up when it reconnects.

## Results (M0)

Both rows use the same benchmark, setup, and send pattern: 200 messages, seed 7,
backend served in-process against a local PostgreSQL 17 database (Windows 11,
2026-11-18).

| Metric | Before: polling | After: real-time push |
| --- | --- | --- |
| Delivery latency p50 | 1444 ms | 50 ms |
| Delivery latency p95 | 2941 ms | 81 ms |
| Delivery latency max | 3099 ms | 119 ms |
| Chat requests/min (one receiver) | 19.8 | 0 |
| Requests/min, idle open chat (all panels) | ~45 (calculated) | 0 |

The idle figure for polling is calculated from the frontend's intervals with an
open chat: chat 19.8 (measured), bell ~12, requests list 7.5, meeting panel ~6.
With a live connection, an idle chat makes no requests; only actual changes
trigger a fetch. Median delivery latency fell 96.5% (p95: 97.2%), and idle
requests fell 100%. Latency includes the sender's own POST round trip.

The fallback path was re-measured on the current code and is unchanged from the
baseline: p50 1398 ms, p95 2932 ms, 19.8 chat requests/min.

These are localhost numbers. Through Supabase each request is slower. An early
polling run through a Supabase-backed backend measured a p50 of about 2.1 s.

## How it works

**Server.** Flask-SocketIO runs in-process (threading mode, `simple-websocket`)
next to the REST API, started by `socketio.run` in `backend/app.py`
(`backend/core/realtime.py`). The browser connects through the Vite proxy at
`/socket.io`; only same-origin connections are accepted.

**Authentication.** A socket is accepted only if the session cookie passes the
same check as every REST route (`session_student_id`): a registered account,
the current `session_version`, and a live server-side session row
(`auth_sessions`). The socket then joins `user:<id>` and `session:<id>` rooms
and is checked once more, so a logout or password reset that lands mid-connect
cannot leave a stale socket behind. A password reset disconnects all of that
user's sockets. Logout disconnects only that browser's sockets.

**Events.** Every event is queued during the request and sent only after its
database transaction commits. A rolled-back request sends nothing, and clients
that refetch always see the committed data.

| Event | Sent when | Recipients |
| --- | --- | --- |
| `chat_message` | a message is sent (full row, same format as REST) | both participants |
| `request` | a request is created, decided, cancelled, completed, expired, or closed by a block | both participants (blocker only for blocks) |
| `meeting` | a meeting is proposed or decided, or advice completes | both participants |
| `notifications` | a notification row is created, or the user marks some read | that user |
| `read` | a participant's read position moves forward | both participants |
| `typing` | a participant types (relayed, never stored) | the other participant |

Blocked pairs never receive each other's events or notifications. Events other
than `chat_message` carry only IDs; clients refetch through the existing REST
routes, so all REST authorization still applies.

**Clients.** `frontend/src/realtime.js` keeps one socket per tab while a user
is signed in (`RealtimeProvider`). While connected, components refresh only on
events. While disconnected, they poll at the previous intervals: chat 3 s, bell
5 s, requests and inbox 8 s, meetings 10 s. Each (re)connect triggers one
catch-up fetch. Chat history only advances its cursor from fetched rows, so a
message missed while offline is always fetched. When the server refuses or
ends a connection, which socket.io-client does not retry, the hook retries
after 2, 5, 15, then 30 s.

**Read receipts.** `POST /api/requests/<id>/read` and history fetches move the
reader's position in `conversation_reads`, forward only and capped to real
messages. "Seen" shows under the student's latest own message once the peer has
read it. Pushed messages are marked read only while the tab is visible.

**Typing.** Clients send at most one signal per 2 s, and only while connected.
The server relays at most one per second per tab, after re-checking the
session, participation, an accepted status, and blocks. The indicator hides
5 s after the last signal or when the message arrives.

## Running it

```powershell
.\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\backend\.venv\Scripts\python.exe backend\scripts\migrate.py
.\backend\.venv\Scripts\python.exe backend\app.py
```

Restart Vite after pulling, because its proxy now includes `/socket.io`. The
server-side session migration (`20261118000100_auth_sessions.sql`) signs
everyone out once, since older cookies have no server-side session.

`socketio.run` uses the Werkzeug development server with
`allow_unsafe_werkzeug=True`. Flask-SocketIO otherwise refuses to start when
stdin is not a terminal, such as from IDE run buttons. Do not deploy the
development server.

## Limits and notes

- **One server process.** Events are delivered in-process. Running several
  workers or servers needs a Flask-SocketIO message queue (for example, Redis),
  and the typing rate limit would then be per process.
- **Scheduled expiry** (`backend/scripts/expire_requests.py`) runs in its own
  process, so its changes are not pushed live. Clients see them on their next
  fetch or reconnect. Expirations triggered while students use the app are pushed.
- **Development log line.** With the Werkzeug server, a closing socket may log
  `400 Bad request syntax ('\x81…')`. These are the client's closing frames,
  read as HTTP after the WebSocket ended. No data is lost.
- **Always on.** Read receipts and typing indicators have no opt-out yet.
- While disconnected, fallback polling marks fetched messages read even in a
  hidden tab, as before. Only the live path waits for the tab to be visible.

## Reproduce the measurement

Use a local database only. The script registers fictional accounts and writes
messages. `--serve-local` refuses non-local database hosts and runs the backend
inside the script on a free port chosen by the operating system, so it cannot
reach another backend, such as one on port 5000 connected to Supabase. On
Windows two servers can bind port 5000 at once without an error.

```powershell
docker run -d --name packconnect-test-pg -e POSTGRES_PASSWORD=postgres -p 55432:5432 pgvector/pgvector:pg17
docker exec packconnect-test-pg psql -U postgres -c "CREATE DATABASE packconnect_bench"
docker exec packconnect-test-pg psql -U postgres -d packconnect_bench -c "DO `$`$ BEGIN CREATE ROLE anon NOLOGIN; CREATE ROLE authenticated NOLOGIN; CREATE ROLE service_role NOLOGIN; EXCEPTION WHEN duplicate_object THEN NULL; END `$`$; CREATE SCHEMA IF NOT EXISTS auth; CREATE TABLE IF NOT EXISTS auth.users (id uuid PRIMARY KEY, email text, email_confirmed_at timestamptz);"

$env:SUPABASE_DB_URL = "postgresql://postgres:postgres@127.0.0.1:55432/packconnect_bench?sslmode=disable"
.\backend\.venv\Scripts\python.exe backend\scripts\migrate.py
Remove-Item Env:SUPABASE_DB_URL

.\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
$db = "postgresql://postgres:postgres@127.0.0.1:55432/packconnect_bench?sslmode=disable"
.\backend\.venv\Scripts\python.exe backend\scripts\benchmark_messaging.py --serve-local $db --mode push --messages 200 --seed 7
.\backend\.venv\Scripts\python.exe backend\scripts\benchmark_messaging.py --serve-local $db --mode poll --messages 200 --seed 7
```

`--serve-local` sets the database URL and clears the Supabase settings inside
Python. Do not try to clear them with `$env:SUPABASE_URL = ""`: in Windows
PowerShell 5.1 that deletes the variable, and `backend/.env` then fills it in again.
