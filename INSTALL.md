# Installing PackConnect

This guide sets up PackConnect on your machine: the Flask backend, the React
frontend, a database, and the test suites. Commands are for Windows PowerShell;
macOS and Linux equivalents are noted where they differ.

## 1. Requirements

| Tool | Version | Used for |
| --- | --- | --- |
| Python | 3.11 or later (CI uses 3.12) | Backend |
| Node.js and npm | Node 24 LTS (CI uses 24) | Frontend |
| Git | Any recent version | Cloning |
| Docker Desktop | Any recent version | Local database and backend tests (optional if you only use the team's Supabase project) |

Check what you have:

```powershell
python --version
node -v
npm -v
git --version
docker --version
```

## 2. Get the code

```powershell
git clone https://github.com/moeyk210/PackConnect.git
cd PackConnect
```

Run every command below from this repository root unless it says otherwise.

## 3. Install the backend

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
```

On macOS or Linux, activate with `source .venv/bin/activate`. If PowerShell
blocks `Activate.ps1`, skip activation and call `.\.venv\Scripts\python.exe`
wherever this guide says `python`.

The first search with an advice topic, or the first profile saved with advice
topics, downloads a small language model (about 65 MB) used for meaning-based
topic matching. It runs locally; no student text
leaves the server.

## 4. Choose a database

Create `backend/.env` from the example:

```powershell
Copy-Item backend/.env.example backend/.env
```

On macOS or Linux, use `cp backend/.env.example backend/.env`. Never commit
`backend/.env`; it is ignored by Git.

Then pick one option.

### Option A: the team's Supabase project

Use this to work with the shared, real data. Fill in `backend/.env` with the
values from the Supabase dashboard (ask a team member for access):

- `SUPABASE_DB_URL`: the **Connect → Session pooler** PostgreSQL connection
  string, including the database password. This is not the HTTPS project URL.
  Percent-encode special characters in the password.
- `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY`: needed for students who
  registered through Supabase Auth.
- `FLASK_SECRET_KEY`: any long private random value, so sign-ins survive a
  backend restart.

Apply any new migrations:

```powershell
python backend/scripts/migrate.py
```

The Supabase database is shared with the whole team. Only run migrations that
have been merged, and never point seed scripts or tests at it.

### Option B: a local database with fictional data

Use this to try the app without Supabase credentials. Start a PostgreSQL
container with pgvector, then fill it with fictional students, courses and
reviews:

```powershell
docker run --rm -d --name packconnect-dev -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=packconnect_dev -p 127.0.0.1:54331:5432 pgvector/pgvector:pg17
python backend/scripts/seed_dev_data.py --database-url "postgresql://postgres:postgres@127.0.0.1:54331/packconnect_dev?sslmode=disable"
```

The seed script applies the migrations itself, loads the course catalog, and
creates topic fingerprints. Then set these two lines in `backend/.env`:

```text
SUPABASE_DB_URL=postgresql://postgres:postgres@127.0.0.1:54331/packconnect_dev?sslmode=disable
SUPABASE_URL=
```

`SUPABASE_URL` must be blank (or have a real key next to it): the backend
refuses to start with the example's placeholder URL and no key.

Sign in as `riley@dev.packconnect.test` (or any other seeded student) with the
password `packconnect-dev-2026`. `docker stop packconnect-dev` deletes the
container and its data; run both commands again to start fresh. For a smaller
dataset with a known M0 result, see
[the demo seed](README.md#advice-feedback-reputation-and-m0-eval).

## 5. Start the backend

```powershell
python backend/app.py
```

It serves the API and the real-time channel on `http://127.0.0.1:5000`. Check
[the health endpoint](http://127.0.0.1:5000/api/health): it should return
`{"status":"ok"}`. Leave this terminal running.

## 6. Install and start the frontend

In a second terminal, from the repository root:

```powershell
cd frontend
npm ci
npm run dev
```

Open the URL Vite prints, usually `http://localhost:5173/`. That is the
website; port 5000 serves only the API. Vite forwards `/api` and `/socket.io`
to the backend.

## 7. Run the tests

### Backend

Backend tests need their own local PostgreSQL with pgvector. They create and
drop a temporary schema per test and refuse any non-local database.

```powershell
docker run -d --name packconnect-test-db -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=packconnect_test -p 127.0.0.1:5432:5432 pgvector/pgvector:pg17
$env:TEST_DATABASE_URL = "postgresql://postgres:postgres@127.0.0.1:5432/packconnect_test?sslmode=disable"
python -m unittest discover -s backend -p "test_*.py"
```

On macOS or Linux, set the variable with
`export TEST_DATABASE_URL="postgresql://..."`. Two live Supabase tests and one
real-model test are skipped unless you turn them on; see
[database verification](docs/SUPABASE.md).

### Frontend

From the `frontend` folder:

```powershell
npm test
npm run lint
npm run build
```

On Windows, use `npm.cmd` if PowerShell blocks `npm`. GitHub Actions runs all
of these on every push; see [continuous integration](docs/CONTINUOUS_INTEGRATION.md).

## 8. After pulling new changes

```powershell
python -m pip install -r backend/requirements.txt
python backend/scripts/migrate.py
cd frontend
npm ci
```

Then restart both the backend and Vite.

## Optional: benchmark tools

The real-time messaging benchmark needs one extra package:

```powershell
python -m pip install -r backend/requirements-dev.txt
```

See [real-time messaging](docs/REALTIME_MESSAGING.md) for how to run it.

## Troubleshooting

See [common troubleshooting](README.md#common-troubleshooting) in the README.
