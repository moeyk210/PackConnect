# Notification read performance

Marking all notifications read now clears the badge and visible unread markers
immediately. A failed save restores the previous state and displays an error;
the action can be retried. Duplicate clicks cannot create duplicate writes.

The save response includes the remaining unread count. There is no immediate
follow-up GET or refresh triggered by the busy flag. Regular polling continues
after the action finishes. Outstanding refreshes are cancelled and stale results
are ignored so they cannot restore old unread badges.

Bulk reads still use the latest loaded notification ID as a cutoff. Notifications
newer than that ID remain unread, appear in the returned unread count, and are
loaded by the next normal poll. This also clears older unread notifications
outside the latest-50 panel. Account scoping and authorization are unchanged.

The backend uses one database connection for messaging authentication and route
queries. A lazy pool reuses up to four connections per process and database.
Each checkout commits or rolls back its transaction before returning the
connection; test schema selection uses SET LOCAL to avoid leaking between
checkouts. Pool usage follows the [Psycopg connection-pool documentation](https://www.psycopg.org/psycopg3/docs/advanced/pool.html).

Install the updated requirements and restart the backend:

```sh
.venv/bin/python -m pip install -r backend/requirements.txt
```

Use the Python executable for the virtual environment running Flask, such as
`backend/.venv/bin/python`. No SQL migration is needed for this update.

Verification covers immediate feedback, failed-save rollback and retry, stale
refreshes, duplicate clicks, and newer notifications during a pending save.
Backend tests check read counts and one checkout per read request, plus physical
connection reuse, transaction rollback, and schema isolation. Existing messaging
and permission tests run against the same pooled code.

A read-only SELECT 1 comparison against the configured Supabase database measured
three fresh connections at 752–844 ms versus three warmed pool checkouts at
232–290 ms. These samples measure connection and query overhead, not complete
notification-action latency, and will vary with network conditions.

Local verification passed 43 frontend tests and 111 backend tests, with two live
integration tests intentionally skipped, plus lint, formatting, and the
production build. Chrome verified the built app against isolated PostgreSQL:
with a delayed save response, the badge cleared before the response, only one
write and no immediate follow-up fetch were sent, and the saved unread count
was zero. No JavaScript exceptions were reported.

## Update: real-time notifications (issue #5)

Regular polling is now only a fallback. While the real-time channel is
connected, the bell refreshes when the server pushes a `notifications` event,
and polls every five seconds only while disconnected. A newer refresh cancels
any in flight, and at most one poll is ever scheduled, so a stale response
cannot restore an old badge. Read actions also push a `notifications` event to
the reader's other tabs. The tab that performed the action receives it too and
refreshes once; if the save is still pending it waits five seconds. See
[real-time messaging](REALTIME_MESSAGING.md).
