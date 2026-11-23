# 05 — Real-time messaging (issue #5)

| | |
|---|---|
| **Author** | Ethan Goodman |
| **Date** | 2026-11-18 |
| **Tool / model** | Claude Code (VS Code extension), Claude Opus 5.5 |

## 1. Request

Implement issue #5 on branch `feature/real-time-messaging`: replace the
inherited polling with push updates, then add read receipts and typing
indicators, and measure the result as our M0 claim.

Working rules:

- one task at a time, reported back before the next one started;
- the AI never commits or pushes, I commit each task myself;
- tests and benchmarks run only against a local database, never the
  team's shared Supabase project.

## 2. AI proposal

The AI first checked the issue against the code and found that two of its
items already existed: database connection pooling (`aefa83d`) and unread
counts. The issue was rewritten on 2026-11-18 to cover only the remaining
work:

1. A benchmark script that records a polling baseline first (latency and
   requests per minute).
2. An authenticated Socket.IO channel in Flask-SocketIO that checks the
   session cookie the same way the REST routes do.
3. Sending events only after the database transaction commits, so a
   rolled-back request sends nothing.
4. A frontend socket provider and hooks, with chat moved to push first.
5. The remaining polling (bell, requests, inbox, meetings) moved to push,
   with the old polling kept as a fallback while disconnected.
6. Read receipts, then typing indicators.
7. Docs with before/after results.

Two problems came up during the work and were fixed as extra tasks:

- **A.** Notifications could be sent across a block (`e352bd2`).
- **B.** Logout only cleared the cookie, so a socket could outlive the
  session. Sessions are now revoked on the server (`7a45003`), and a
  password reset disconnects all of that user's sockets (`bb417ba`).

## 3. Human review

- I chose in-process Flask-SocketIO fan-out over PostgreSQL LISTEN/NOTIFY,
  because it was simpler for a single server process. The trade-off is
  documented: several workers would need a message queue.
- I chose how to measure: a standalone benchmark script for latency, and
  requests per minute counted in the browser's DevTools.
- I chose to run tests and benchmarks against a local Docker Postgres 17
  container (`packconnect-test-pg`), not Supabase.
- I approved the server-side session migration, knowing it signs every
  user out once.
- I asked for the later UI changes: a messaging-style inbox, compact chat
  bubbles, a message menu, and Enter to send (`8a2aced`, `6d44818`).

## 4. Final version

15 commits on `feature/real-time-messaging` (`95b7960`..`6d44818`), merged
to `dev`. Main pieces:

- **Server:** `backend/core/realtime.py` (Socket.IO channel, after-commit
  events) and `backend/features/typing.py`. Read positions are stored in
  `conversation_reads`, and sessions in `auth_sessions`.
- **Client:** `frontend/src/realtime.js` and `RealtimeProvider.jsx`. Chat,
  the bell, requests, the inbox, and meetings refresh on events and fall
  back to polling while disconnected.
- **Benchmark:** `backend/scripts/benchmark_messaging.py`.
- **Docs:** `docs/REALTIME_MESSAGING.md`.
- **Tests:** 38 backend and 32 frontend tests added.

**M0 result** (200 messages, seed 7, local Postgres 17):

| Metric | Polling | Push |
|---|---|---|
| Delivery latency p50 | 1444 ms | 50 ms |
| Delivery latency p95 | 2941 ms | 81 ms |
| Requests/min, idle open chat | ~45 | 0 |

## 5. Verification

A box is ticked only where a person did the check.

- [x] Tests pass: I ran the test suite and it passed.
- [x] Ran it manually: I ran the app and checked the feature myself.
- [x] I reviewed each task's report, then committed and pushed it myself.

The AI ran the benchmark in both modes against the local container and
recorded the results above in `docs/REALTIME_MESSAGING.md`. It also
re-measured the fallback path, which matched the baseline (p50 1398 ms).
