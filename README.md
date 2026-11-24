# PackConnect — Peer Advice Portal

[![Build](https://github.com/moeyk210/PackConnect/actions/workflows/build.yml/badge.svg?branch=main)](https://github.com/moeyk210/PackConnect/actions/workflows/build.yml?query=branch%3Amain)

[![Tests and Quality](https://img.shields.io/github/actions/workflow/status/moeyk210/PackConnect/ci.yml?branch=main&label=Tests%20%26%20Quality)](https://github.com/moeyk210/PackConnect/actions/workflows/ci.yml?query=branch%3Amain)

[![Coverage](https://codecov.io/gh/moeyk210/PackConnect/branch/main/graph/badge.svg)](https://app.codecov.io/gh/moeyk210/PackConnect/tree/main)


[![Code Style](https://img.shields.io/github/actions/workflow/status/moeyk210/PackConnect/style.yml?branch=main&label=Code%20Style)](https://github.com/moeyk210/PackConnect/actions/workflows/style.yml?query=branch%3Amain)



[![Formatter](https://img.shields.io/github/actions/workflow/status/moeyk210/PackConnect/formatter.yml?branch=main&label=Formatter)](https://github.com/moeyk210/PackConnect/actions/workflows/formatter.yml?query=branch%3Amain)


[![Syntax](https://img.shields.io/github/actions/workflow/status/moeyk210/PackConnect/syntax.yml?branch=main&label=Syntax)](https://github.com/moeyk210/PackConnect/actions/workflows/syntax.yml?query=branch%3Amain)



[![Original project DOI](https://img.shields.io/badge/Original%20project%20%28Project%202%29%20DOI-10.5281%2Fzenodo.23543676-blue)](https://doi.org/10.5281/zenodo.23543676)



https://github.com/user-attachments/assets/03d93b60-23e5-4d8d-a226-e6f5326d4a65



PackConnect is a student-to-student peer-advice discovery portal being developed for NC State University. Students can search by course code to find peers who have completed a course and volunteered to share advice.

> **Project status:** Early working prototype. The application includes account registration and persistent student profiles. Login uses password verification and session cookies. All application data persists in Supabase PostgreSQL; acceptance unlocks private two-person chat. Course histories remain self-reported.

See the [Step 1 baseline audit](docs/STEP_1_AUDIT.md) for verified behavior, limitations, and outstanding work.

## Project 3: what we changed

PackConnect started as another team's Project 2,
[KrishnaAttili10/PackConnect](https://github.com/KrishnaAttili10/PackConnect), by
Kireeti Attili, Atharva Tijare, saarinenemma and KrishnaAttili10. We forked it at
commit `5d635c1` (October 29, 2026), the last commit on their `main`. Everything
from `a313141` onward is our work:
[compare the fork point with our `main`](https://github.com/moeyk210/PackConnect/compare/5d635c1...main).

### What we inherited

Registration and sign-in, student profiles, course search with filters, advisor
availability limits, advice requests with cancellation and expiry, private chat
that refreshed every three seconds, in-app notifications, a conversation inbox,
block and report tools with moderation, password recovery, meeting proposals,
and course-code suggestions drawn from students' own course histories. It had
128 backend and 52 frontend tests, all passing in CI.

### What we added

| Milestone | Issue / PR | Lead | What works now that did not before |
| --- | --- | --- | --- |
| Advice outcomes and reputation | [#2](https://github.com/moeyk210/PackConnect/issues/2) / [#10](https://github.com/moeyk210/PackConnect/pull/10) | Moe Ko | Rate a conversation; advisor rating, students helped and response rate on search cards and profiles; the M0 eval and demo seed. See [feedback and reputation](#advice-feedback-reputation-and-m0-eval). |
| Smart matching and ranking | [#3](https://github.com/moeyk210/PackConnect/issues/3) / [#14](https://github.com/moeyk210/PackConnect/pull/14) | Morgan Simon | Search ranked by fit instead of A-Z, near misses under "Outside your filters", "Recommended for you", and advice topics matched by meaning with a local model and pgvector. See [smart matching](docs/SMART_MATCHING.md). |
| Course hub and catalog | [#4](https://github.com/moeyk210/PackConnect/issues/4) / [#15](https://github.com/moeyk210/PackConnect/pull/15) | Savanah Hendzel | A 162-course CSC catalog, one stored form for every course code, autocomplete by code or title, and course pages with ranked advisors and workload and difficulty ratings. See [course pages](docs/COURSE_PAGES.md). |
| Real-time messaging | [#5](https://github.com/moeyk210/PackConnect/issues/5) / [#11](https://github.com/moeyk210/PackConnect/pull/11), [#16](https://github.com/moeyk210/PackConnect/pull/16) | Ethan Goodman | Chat, notifications, requests, the inbox and meetings update over WebSockets instead of polling, with read receipts, typing indicators and server-side session revocation. See [real-time messaging](docs/REALTIME_MESSAGING.md). |

Supporting work: the backend reorganized into `core/`, `features/`, `scripts/`
and `tests/` ([#7](https://github.com/moeyk210/PackConnect/pull/7)), varied
development seed data and end-to-end tests
([#17](https://github.com/moeyk210/PackConnect/pull/17)), and fixes
([#8](https://github.com/moeyk210/PackConnect/pull/8),
[#9](https://github.com/moeyk210/PackConnect/pull/9),
[#12](https://github.com/moeyk210/PackConnect/pull/12),
[#13](https://github.com/moeyk210/PackConnect/pull/13)). AI use is logged in
[ai/AI_USAGE.md](ai/AI_USAGE.md).

### How we know the old parts still work

| Tests | At the fork (`5d635c1`) | Now |
| --- | --- | --- |
| Backend | 128 | 484 |
| Frontend | 52 | 164 |

Every inherited test file is still in the suite, and CI runs all of them on
every push. Most edits to inherited tests follow the backend reorganization
(import paths), real server-side sign-in, or new response fields. Five
inherited tests for course-code suggestions were replaced when suggestions moved
from students' course histories to the catalog
([#15](https://github.com/moeyk210/PackConnect/pull/15)); 13 tests in
`backend/tests/test_course_autocomplete.py` cover the new behavior.

### M0

The inherited project had no M0 eval; its own
[baseline audit](docs/STEP_1_AUDIT.md) lists the M0 instrument as missing. Our
claims and the instruments that measure them:

| Claim | Instrument | Result |
| --- | --- | --- |
| More than 70% of accepted connections are rated helpful | `backend/scripts/m0_eval.py` (`--check` exits 1 if the claim fails) | 75.0% (9 of 12) on the demo seed: pass |
| Ranked search puts the advisor who accepted in the top 3 more often than A-Z order | `backend/scripts/ranking_eval.py` | 42.9% vs 17.9% (24 vs 10 of 56) on a simulated semester |
| Meaning-based topic matching finds the right advisor more often than shared words | `backend/scripts/topic_match_eval.py` | 86.7% vs 46.7% (26 vs 14 of 30 hand-written cases) |
| Real-time push delivers chat faster than polling | `backend/scripts/benchmark_messaging.py` | Median 1444 ms to 50 ms; an idle open chat goes from about 45 requests a minute to 0 |

These results come from demo, simulated or hand-written data, not real
students. `m0_eval.py` and `ranking_eval.py` read whichever database they are
given, so they can measure real students once there is enough history.

## Current features

- Register an account with email, password, and a student profile. Passwords are hashed; emails remain private. Advising is optional.
- Create and edit profiles with completed/current courses, skills, and advice topics. Only the signed-in owner can edit their profile; the API rejects unauthenticated or non-owner updates.
- Set an open-request limit and pause new advice requests until a chosen date. Search and profiles show availability and capacity; the backend prevents concurrent overbooking. Complete accepted advice from Requests to free a slot and keep read-only message history. See [availability and migration instructions](docs/ADVISOR_AVAILABILITY.md).
- Search by course code (for example, `CSC 510`) and filter by program, year, skills, advice topics, and advising availability.
- Course search suggests up to ten matching codes from registered students' completed courses as you type. Select with the mouse or Arrow keys and Enter; Escape dismisses suggestions. Manual entry remains available, including when suggestions cannot load. Search treats `CSC510`, `csc 510`, and `CSC-510` alike. Suggestions reflect self-reported course histories, not an official university catalog; course titles are not yet stored. See [behavior and verification](docs/COURSE_AUTOCOMPLETE.md).
- Search lists registered students only, including confirmed Supabase Auth users linked through `students.auth_user_id` and accounts registered in this app. Profiles without a linked registered account are excluded from results. By default, results include students who opted in, are not paused, and have capacity; turning off the availability filter also includes registered students who are not currently advising.
- Send persistent advice requests, view incoming/outgoing requests, and accept or decline as the recipient.
- View a student's profile, including program, year, bio, interests, and completed courses (as returned by the API).
- Store accounts, profiles, courses, requests, chat, and notifications in Supabase PostgreSQL.
- Get in-app bell notifications for incoming requests, request decisions, and new chat messages. Read/unread state is saved per account.
- Chat privately after acceptance. Both participants can send messages of up to 2,000 characters, and conversations persist across visits. Messages, notifications, requests, the inbox, and meetings update in real time over WebSockets, with "Seen" read receipts and typing indicators. If the live connection drops, the app falls back to polling and catches up on reconnect. See [real-time messaging](docs/REALTIME_MESSAGING.md).
- Logging out ends that browser's session on the server, so a copied session cookie stops working. Other signed-in devices stay signed in.
- Rate a conversation from 1 to 10, say whether the advice was helpful, and add an optional comment, once both people have sent a message. Search cards and profiles show each advisor's average rating, students helped, and response rate. See [feedback, reputation, and the M0 eval](#advice-feedback-reputation-and-m0-eval).

New request and community tools include cancellation, seven-day expiration,
a conversation inbox, block/report controls with moderator review, password
recovery, and meeting proposals with calendar export. See [setup and behavior](docs/COMMUNITY_FEATURES.md),
including SMTP configuration and moderator assignment.

## Tech stack

| Layer | Technology |
| --- | --- |
| Frontend | React + Vite |
| Backend | Python + Flask + Flask-CORS |
| Database | Supabase PostgreSQL (Psycopg) |
| Development environment | PyCharm or any code editor |

## Project structure

```text
PackConnect/
├── backend/
│   ├── app.py             # Flask API entry point and database initialization
│   ├── requirements.txt
│   ├── core/              # Shared infrastructure: database connections, session identity
│   ├── features/          # Feature modules: messaging, availability, lifecycle,
│   │                      #   community, meetings, password recovery
│   ├── scripts/           # Command-line tasks: migrations, request expiry,
│   │                      #   demo seed data, M0 eval
│   └── tests/             # Backend test suite and shared test support
├── frontend/
│   ├── src/
│   │   ├── App.jsx        # Search and student profile UI
│   │   ├── App.css
│   │   └── index.css
│   ├── package.json
│   └── package-lock.json
├── .gitignore
└── README.md
```

## Prerequisites

Install:

- **Python 3.11 or later** (use a version supported by the project's Flask dependencies).
- **Node.js 24 LTS** (recommended for the current Vite/Rolldown setup) and npm.
- **Git** to clone the repository.

You do **not** need Visual Studio or Visual Studio Build Tools to run this prototype. PyCharm is optional.

Check your installed versions:

```powershell
python --version
node -v
npm -v
git --version
```

## Run locally (Windows / PowerShell)

### 1. Clone the repository

```powershell
git clone https://github.com/moeyk210/PackConnect.git
cd PackConnect
```

If you've already cloned it, open a terminal in the existing project folder instead.

### 2. Start the Flask backend

From the **repository root**, create and activate a Python virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install backend dependencies:

```powershell
python -m pip install -r backend/requirements.txt
```

Configure `backend/.env` using [the Supabase setup instructions](docs/SUPABASE.md).
`SUPABASE_DB_URL` must be a PostgreSQL connection string, not the HTTPS API URL.
Apply migrations, then start Flask:

```powershell
python backend/scripts/migrate.py
python backend/app.py
```

The backend should report:

```text
Running on http://127.0.0.1:5000
```

Flask connects to Supabase; it creates no local database or sample profiles. Leave this terminal running.

`backend/app.py` serves the API and the real-time Socket.IO channel through
Flask-SocketIO. After pulling changes, reinstall `backend/requirements.txt`,
apply migrations, and restart both Flask and Vite (Vite proxies `/socket.io`).
After the server-side session upgrade, everyone signs in again once.

> **PowerShell note:** If script execution is blocked when activating the virtual environment, you can skip activation and run `.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt` followed by `.\.venv\Scripts\python.exe backend/app.py`.

### 3. Start the React frontend

Open a **second terminal** in the repository root:

```powershell
cd frontend
npm ci
npm run dev
```

`npm ci` installs dependencies from `package-lock.json`. If the lockfile is missing, use `npm install` instead.

Vite should print a local URL, usually:

```text
http://localhost:5173/
```

Open that URL in your browser. **The frontend is the actual website; port 5000 serves only the API.**

### 4. Try the application

1. Search for `CSC 510`.
2. Results depend on registered advisors in your Supabase project. Create an advisor account with `CSC 510` in its completed courses to try the search.
3. Click **View Profile** to see a student's details.
4. Try `CSC 540` or `CSC 515` for other matches.
5. To try requests and chat, create two accounts, opt the recipient into advising, and sign into them in separate browser profiles or a normal/incognito window. Send a request from a registered student profile. Accept it in the recipient's **Requests ? Incoming** tab, then open chat from either account. Seed profiles have no accounts and cannot receive requests.

## API endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| GET | `/api/health` | Returns `{"status":"ok"}` |
| POST | `/api/auth/register` | Creates an account and student profile; returns 201, 400 for invalid input, or 409 for a duplicate email |
| GET | `/api/students/search?course=CSC%20510` | Ranks students who completed the course, best fit first, with near misses listed separately and 20 per page. See [smart matching](docs/SMART_MATCHING.md) |
| GET | `/api/recommendations` | Signed-in only: up to five advisors for your current courses, best fit first. See [smart matching](docs/SMART_MATCHING.md#recommended-for-you) |
| GET | `/api/courses?q=CSC` | Suggests up to ten distinct completed-course codes matching a prefix; case, spaces, and hyphens are ignored |
| GET | `/api/students/1` | Retrieves a student's full profile |
| GET / POST | `/api/requests` | List your requests or create one for another registered advisor |
| PATCH | `/api/requests/1` | Recipient accepts/declines a pending request |
| GET / POST | `/api/requests/1/messages` | Read/send messages after acceptance; participants only |
| GET / POST | `/api/requests/1/feedback` | Read your own feedback and whether you can rate; submit feedback once per request |
| GET | `/api/students/1/reputation` | An advisor's aggregate rating, helpful %, students helped, and response rate |

Quick browser checks:

- [Backend health](http://127.0.0.1:5000/api/health)
- [CSC 510 search](http://127.0.0.1:5000/api/students/search?course=CSC%20510)
- [Frontend](http://localhost:5173/)

### Account registration

Apply migrations with `python backend/scripts/migrate.py`, then restart the backend. Click **Create account** in the frontend header. Enter your name, email, a password of 12–128 characters, program, and year. Optional fields include bio, interests, and comma-separated completed courses. Opt in to advising to appear in searches for those courses.

The registration API accepts `name`, `email`, `password`, `program`, and `year`, plus optional `bio`, `interests`, `completed_courses` (an array of course codes), and `willing_to_advise` (a boolean, defaulting to false). Email uniqueness ignores case. Account and profile creation are transactional. After registration, sign in on the login page. Email verification is not yet implemented. Course completion is self-reported.

## Development notes

- The frontend uses same-origin `/api` requests. Vite proxies them to `http://127.0.0.1:5000`; restart Vite after updating its configuration. Production hosting must proxy `/api` to Flask as well.
- Vite usually runs on port **5173**. If that port is busy, use the URL printed by `npm run dev`.
- Flask runs in **debug mode** for local development. Do not deploy the development server to production.
- Supabase PostgreSQL is the only active storage backend. Existing SQLite files are ignored, left untouched, and never opened by the application. They are not imported automatically.
- The example students are fictional; no real student information is required for the prototype.
- Requests and chat use the signed-in account identity. Only the two participants can read requests/conversations, and only the recipient can accept or decline. Email/push notifications are not implemented.
- Backend checks require a dedicated localhost `TEST_DATABASE_URL`; see [verification instructions](docs/SUPABASE.md). Run frontend checks with `npm test`, `npm run lint`, and `npm run build` from `frontend`. See [frontend testing](frontend/README.md) for interaction-test scenarios.

## Common troubleshooting

**`python: can't open file 'backend/app.py'`**  
Make sure you're in the repository root (`PackConnect`) when running `python backend/app.py`.

**The frontend says it cannot connect to Flask**  
Start the backend in a separate terminal and check [the health endpoint](http://127.0.0.1:5000/api/health).

**`Cannot find native binding` (Rolldown)**  
Use a supported Node.js version (Node 24 LTS recommended), then from the `frontend` folder run:

```powershell
Remove-Item -Recurse -Force .\node_modules
npm ci --include=optional
npm run dev
```

If `npm ci` cannot run because the lockfile is missing, use `npm install --include=optional`.

**PowerShell says `Activate.ps1` cannot be loaded**  
Use the direct virtual-environment Python commands in the backend setup section instead.

## Working with Git

All work branches from `dev`, and pull requests target `dev`, never `main`. At the end of the project, `dev` is merged into `main` in a single pull request. See [CONTRIBUTING.md](CONTRIBUTING.md) for the full workflow, checks, and pull request expectations.

Before starting work, fetch the latest changes and create a feature branch from `origin/dev`:

```powershell
git fetch origin
git switch -c feature/short-description origin/dev
```

After making changes:

```powershell
git add .
git commit -m "Describe your change"
git push -u origin feature/short-description
```

Open a pull request into `dev` on GitHub. A teammate reviews it before it is merged.

## Planned improvements

- Email verification and login rate limiting (password recovery has its own rate limits).
- Course completion reporting and richer course discovery.
- Conversation management (archiving, message deletion) and settings to turn off read receipts or typing indicators.
- Improved testing, validation, privacy, and deployment configuration.

---

**Repository:** https://github.com/moeyk210/PackConnect

### Supabase connection setup

Set `SUPABASE_DB_URL` in `backend/.env` to the PostgreSQL **Session pooler**
connection string from Supabase's Connect panel, including the database password.
Run `python backend/scripts/migrate.py` before starting Flask. `SUPABASE_URL` and
`SUPABASE_SECRET_KEY` configure the optional SDK used by live integration tests;
they are separate from the database connection string.

All routes use Supabase PostgreSQL. There is no SQLite fallback and no automatic
sample seeding or local-data import. Existing `.db` files are left untouched as
unused backups. Keep credentials out of Git and the frontend. See
[Supabase setup, migrations, and verification](docs/SUPABASE.md).

### Automated checks

GitHub Actions runs backend tests, frontend interaction tests, ESLint, and the frontend production
build on every push and pull request. No private credentials are required. See
[CI instructions](docs/CONTINUOUS_INTEGRATION.md) for local commands and how to
inspect a run. The build badge links to the live workflow evidence.

### Login and public pages

Open the Vite URL to reach the login landing page. Create an account, then sign
in with its email and password to open `#/app`. Existing fictional seed students
have no login accounts. About, Privacy policy, and Terms & conditions are
available without signing in. These informational policy pages describe the
prototype and should be reviewed by the project team before public deployment.

Sessions use an HttpOnly, SameSite=Lax cookie and expire after eight hours.
Refresh restores a valid session; Sign out clears it. For stable sessions across
backend restarts, set `FLASK_SECRET_KEY` to a strong private value in `backend/.env`.
Without it, development uses a fresh random key per process. Use HTTPS and set
`COOKIE_SECURE=true` when deploying. The login gate controls frontend navigation;
Profile updates require the signed-in owner. Standalone profile creation is
retired (410); registration creates the account and its profile transactionally. Chat and advice requests require authentication
and participant access. Email verification and login rate
limiting remain planned. Password recovery is available after configuring SMTP; see [community setup](docs/COMMUNITY_FEATURES.md).

### Workspace pages

- `#/app`: Find peers with course search, collapsible advanced filters, and removable filter chips.
- `#/app/students/<id>`: A dedicated student profile, including an advice request form for registered advisors and chat links for existing connections.
- `#/app/profile`: Your own profile, with an Edit Profile button.
- `#/app/profile/edit`: Edit your own profile; Save persists changes and Cancel discards edits.
- `#/app/requests`: Incoming/Outgoing history, accept/decline, sender cancellation, expiration, and completion.
- `#/app/conversations`: Conversation previews and unread counts.
- `#/app/blocked`: Manage blocked students.
- `#/app/moderation`: Report review for assigned moderators.
- `#/forgot-password`: Request a password recovery email.

Shared navigation includes a mobile menu. Profile links support refresh and
browser Back/Forward. Profiles are created during registration; the search page
no longer offers duplicate profile creation. `PUT /api/students/<id>` returns
401 without a session, 403 for another user's profile, and 400 for invalid input.
Permission failures do not modify profile or course records.

### Persistent requests and private chat

Apply migrations before restarting Flask. Existing Supabase
profiles, accounts, and legacy messages are retained. Old unauthenticated
messages are not imported into private conversations because they lack verified
sender identities. The previous `/api/students/<id>/messages` endpoint now
returns 410; clients must use accepted-request conversations.

`#/app/chat/<request-id>` opens a conversation. Only its sender and recipient can
read or send messages, and only after acceptance. One pending/accepted connection
is allowed per student pair, including requests in the opposite direction.
Declined requests stay in history, and a new request may be sent. Accepted or
declined decisions cannot be reversed through the API. Either participant can mark accepted advice completed to release capacity and retain read-only history. Turning off future advice
availability does not delete existing connections or messages.

While the real-time connection is up, the Requests list, inbox, and open chats
update when something changes, without polling. If it drops, they fall back to
polling (requests and inbox every eight seconds, chats every three seconds) and
catch up on reconnect. History is fetched in batches of 100. Requests/messages
survive reloads and backend restarts; sign in again if a development restart
invalidates your session. See [messaging API and test instructions](docs/MESSAGING.md).

### Notifications

The header bell shows unread updates for new connection requests, accepted or
declined requests, and new chat messages. Open it to inspect updates. Selecting
an update marks it read and opens the relevant inbox, outgoing request, or chat.
**Mark all as read** clears the unread state for updates up to the latest loaded
notification, preserving newer arrivals. Read state persists across visits.

Read actions update the badge immediately, restore its prior state if saving
fails, and receive the remaining unread count directly from the save response.
They no longer wait for an additional notification fetch. The backend reuses a
small connection pool and shares one connection between messaging authentication
and its route. After pulling these changes, install `backend/requirements.txt`
and restart Flask. No additional database migration is needed for this
performance update. See [verification details](docs/NOTIFICATION_PERFORMANCE.md).

Notifications arrive in real time while the app is open, and are polled every
five seconds only if the live connection drops. No browser
permission is needed; these are in-app alerts, not email or operating-system
push notifications. Apply migrations before restarting Flask to prepare notification storage.
Existing pending requests and completed decisions are backfilled once without
resetting previously read updates. The panel shows the latest 50 events; the
badge counts all unread events. Chat message content is not included in the
notification preview. All notification APIs are scoped to the signed-in account.

### Existing Supabase Auth registrations

Students registered through Supabase Auth can use the same app login with their
existing email and password. The backend verifies those credentials with Supabase
and loads the existing profile by `students.auth_user_id`. It does not match by
name, copy passwords, or create a second profile. The email must be confirmed and
the profile must already have the matching Supabase user ID; missing links require
project-team review rather than automatic linking by email.

Set `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` (or `SUPABASE_ANON_KEY`) in
`backend/.env`. The server-only `SUPABASE_SECRET_KEY` is also supported as a
fallback. Supabase users are visible in search and can receive requests before
their first app login. After signing in, they can accept/decline, chat, edit their
own profile, and read notifications using the same Flask session flow. Existing
Flask accounts continue to work. No new database migration is needed.

### Advice feedback, reputation and M0 eval

Apply migrations before restarting Flask (`python backend/scripts/migrate.py`).

**Feedback.** Once a request is accepted and both people have sent at least one
message, the chat shows **Rate this conversation**: a rating from 1 to 10,
whether the advice was helpful, and an optional comment of up to 500
characters. Each participant can rate a request once and can't change it
afterwards; their own feedback is then shown read-only. Requests that are
pending, declined, cancelled, expired, or closed by a block can't be rated.

**Reputation.** Search cards and profiles show an advisor's average rating,
number of students helped, and response rate; profiles also show the helpful
percentage. Only the asking student's rating counts; an advisor's rating of a
student never affects the advisor's own score. The response rate divides
answered requests (accepted, declined, completed) by those that were due an
answer (adding expired requests and pending requests past their deadline).
Reputation never includes comments or who gave a rating. The rules are
documented in `backend/features/reputation.py`.

**M0 eval.** Our M0 claim for this feature: *more than 70% of accepted
connections are rated helpful by the student who asked.* Connections that were
never rated count against the claim. The eval only reads the database:

```powershell
python backend/scripts/m0_eval.py            # uses SUPABASE_DB_URL from backend/.env
python backend/scripts/m0_eval.py --check    # exit status 1 unless the claim is met
```

To see it on demo data with a known answer, seed a throwaway local database.
The seed script refuses non-local databases unless you pass `--allow-remote`,
so fictional data can't end up in your team's Supabase project by accident.

```powershell
docker run --rm -d --name packconnect-demo -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=packconnect_demo -p 127.0.0.1:54330:5432 postgres:17
$demo = "postgresql://postgres:postgres@127.0.0.1:54330/packconnect_demo?sslmode=disable"
python backend/scripts/seed_demo.py --database-url $demo
python backend/scripts/m0_eval.py --database-url $demo
```

Expected output:

```text
M0: 75.0% of accepted connections were rated helpful (9 of 12)
    Rated: 10 of 12 connections (83.3%); 9 of 10 ratings say helpful (90.0%)
    Claim: more than 70% of accepted connections rated helpful -> PASS
```

The same database can run the whole app with fictional students: set
`$env:SUPABASE_DB_URL = $demo` before `python backend/app.py`, then sign in as
`maya@demo.packconnect.test` (or any other seeded student) with the password
`packconnect-demo-2026`. Stop it with `docker stop packconnect-demo`, which also
deletes the demo data.

### Development seed data

To try search, filters, course pages and recommendations on varied data, seed a
throwaway local database with `backend/scripts/seed_dev_data.py`. It adds 22
fictional advisors across 31 courses in four subjects (CSC, MA, ST, ECE), with
different programs, years, skills, advice topics, availability (open, unlimited,
paused, full, not advising) and review histories, plus 8 students who are not
advising, one profile without an account, and one block. It also loads the
course catalog and creates topic fingerprints with the local model. It refuses
non-local databases.

```powershell
docker run --rm -d --name packconnect-dev -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=packconnect_dev -p 127.0.0.1:54331:5432 pgvector/pgvector:pg17
$dev = "postgresql://postgres:postgres@127.0.0.1:54331/packconnect_dev?sslmode=disable"
python backend/scripts/seed_dev_data.py --database-url $dev
```

Set `$env:SUPABASE_DB_URL = $dev` before `python backend/app.py`, then sign in as
`riley@dev.packconnect.test` (or any other seeded student) with the password
`packconnect-dev-2026`. Good searches to try: `CSC 510` with the topic
"interview prep", `CSC 522` (Isabela is only taking it, so she is not a match),
and `MA 305` (no catalog page). `backend/tests/test_seed_dev_data.py` lists the
expected result for each flow.
