# Real-time messaging (issue #5)

## M0 baseline: polling (before)

Measured on `feature/real-time-messaging` before any real-time code, against a
local PostgreSQL 17 database and a local Flask backend (Windows 11, 2026-11-18).

| Metric | Run 1 (30 msgs) | Run 2 (60 msgs) |
| --- | --- | --- |
| Delivery latency p50 | 2045 ms | 2143 ms |
| Delivery latency p95 | 3395 ms | 3584 ms |
| Delivery latency max | 3419 ms | 3663 ms |
| Chat requests/min (one receiver) | 18.5 | 18.3 |
| Browser requests/min, idle open chat (DevTools) | _to record_ | |

Polling intervals in the current frontend, while a chat is open:

| Loop | File | Interval |
| --- | --- | --- |
| Chat messages | `Messaging.jsx` | 3 s after each response |
| Notification bell | `NotificationBell.jsx` | 5 s after each response |
| Requests list | `useRequests.js` | every 8 s |
| Meeting panel | `MeetingPanel.jsx` | 10 s after each response |
| Inbox (Conversations page only) | `Community.jsx` | 8 s after each response |

Latency is measured from just before the sender's POST until the receiver's
poll response containing the message arrives. Messages are sent at random gaps
of 0.5–3.5 s so they land uniformly across the poll cycle.

## Reproduce the measurement

Use a local database only. The script registers fictional accounts and writes
messages. Never run it against the shared Supabase project.

```powershell
docker run -d --name packconnect-test-pg -e POSTGRES_PASSWORD=postgres -p 55432:5432 postgres:17
docker exec packconnect-test-pg psql -U postgres -c "CREATE DATABASE packconnect_bench"
docker exec packconnect-test-pg psql -U postgres -d packconnect_bench -c "DO `$`$ BEGIN CREATE ROLE anon NOLOGIN; CREATE ROLE authenticated NOLOGIN; CREATE ROLE service_role NOLOGIN; EXCEPTION WHEN duplicate_object THEN NULL; END `$`$; CREATE SCHEMA IF NOT EXISTS auth; CREATE TABLE IF NOT EXISTS auth.users (id uuid PRIMARY KEY, email text, email_confirmed_at timestamptz);"

$env:SUPABASE_DB_URL = "postgresql://postgres:postgres@127.0.0.1:55432/packconnect_bench?sslmode=disable"
$env:SUPABASE_URL = ""
$env:SUPABASE_SECRET_KEY = ""
.\backend\.venv\Scripts\python.exe backend\scripts\migrate.py
.\backend\.venv\Scripts\python.exe backend\app.py
```

In a second terminal:

```powershell
.\backend\.venv\Scripts\python.exe backend\scripts\benchmark_messaging.py --messages 60 --seed 2
```

Environment variables that are already set take precedence over
`backend/.env`, so the backend uses the local database and skips Supabase Auth.

### Browser request count

1. Start the backend as above and the frontend with `npm run dev`.
2. Register two accounts and accept a request so a chat is open.
3. In DevTools, open **Network**, filter to **Fetch/XHR**, and clear the log.
4. Leave the chat open and idle for 60 seconds, then record the request count.
