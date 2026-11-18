# Real-time messaging (issue #5)

## M0 baseline: polling (before)

Measured on the polling code before any real-time changes, with the backend
served in-process against a local PostgreSQL 17 database (Windows 11,
2026-11-18).

| Metric | 200 messages (seed 7) | 60 messages (seed 2) | 30 messages (seed 510) |
| --- | --- | --- | --- |
| Delivery latency p50 | **1444 ms** | 1225 ms | 1846 ms |
| Delivery latency p95 | **2941 ms** | 2641 ms | 3062 ms |
| Delivery latency max | 3099 ms | 2812 ms | 3110 ms |
| Chat requests/min (one receiver) | **19.8** | 20.1 | 20.5 |
| Browser requests/min, idle open chat (DevTools) | _to record_ | | |

The 200-message run is the reference: smaller samples vary by several hundred
milliseconds. Its median matches the expected ~1.5 s, half of the 3 s poll
cycle. These are localhost numbers. An earlier run through a backend connected
to Supabase measured a p50 of about 2.1 s and a p95 of about 3.5 s, because
each request crosses the network.

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
of 0.5–3.5 s so they land across the whole poll cycle.

## Reproduce the measurement

Use a local database only. The script registers fictional accounts and writes
messages. `--serve-local` refuses non-local database hosts and runs the backend
inside the script on a free port chosen by the operating system, so it cannot
reach another backend, such as one on port 5000 connected to Supabase. On
Windows two servers can bind port 5000 at once without an error.

```powershell
docker run -d --name packconnect-test-pg -e POSTGRES_PASSWORD=postgres -p 55432:5432 postgres:17
docker exec packconnect-test-pg psql -U postgres -c "CREATE DATABASE packconnect_bench"
docker exec packconnect-test-pg psql -U postgres -d packconnect_bench -c "DO `$`$ BEGIN CREATE ROLE anon NOLOGIN; CREATE ROLE authenticated NOLOGIN; CREATE ROLE service_role NOLOGIN; EXCEPTION WHEN duplicate_object THEN NULL; END `$`$; CREATE SCHEMA IF NOT EXISTS auth; CREATE TABLE IF NOT EXISTS auth.users (id uuid PRIMARY KEY, email text, email_confirmed_at timestamptz);"

$env:SUPABASE_DB_URL = "postgresql://postgres:postgres@127.0.0.1:55432/packconnect_bench?sslmode=disable"
.\backend\.venv\Scripts\python.exe backend\scripts\migrate.py
Remove-Item Env:SUPABASE_DB_URL

.\backend\.venv\Scripts\python.exe backend\scripts\benchmark_messaging.py --serve-local "postgresql://postgres:postgres@127.0.0.1:55432/packconnect_bench?sslmode=disable" --messages 200 --seed 7
```

### Browser request count

This needs a normal backend on port 5000. Stop any other backend first, and
point this one at the local database so test accounts stay out of Supabase.

1. In PowerShell, set `$env:SUPABASE_DB_URL` to the local URL above,
   `$env:SUPABASE_URL = ""`, and run `.\backend\.venv\Scripts\python.exe backend\app.py`.
2. Start the frontend with `npm run dev`, register two accounts, and accept a
   request so a chat is open.
3. In DevTools, open **Network**, filter to **Fetch/XHR**, and clear the log.
4. Leave the chat open and idle for 60 seconds, then record the request count.
