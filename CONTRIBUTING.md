# Contributing

Keep changes focused and easy to review. Link the relevant issue when one exists.

## Set up

Follow the [README](README.md) to set up Python, Node.js 24, and the backend and frontend dependencies:

```powershell
python -m pip install -r backend/requirements.txt
cd frontend
npm ci
```

Configure `backend/.env` using the [Supabase setup instructions](docs/SUPABASE.md). Backend tests need a dedicated localhost PostgreSQL database in `TEST_DATABASE_URL`, never your connected Supabase project.

Keep database URLs, Supabase keys, `FLASK_SECRET_KEY`, and SMTP settings in the ignored `backend/.env`. Never commit credentials or real student data. The example students are fictional.

## Make changes

Create a branch from `origin/dev`. Keep backend changes in the matching module: shared infrastructure in `backend/core/`, feature logic in `backend/features/`, command-line tasks in `backend/scripts/`, and tests in `backend/tests/`. Keep UI changes in `frontend/src/`.

For schema changes, add a new timestamped file to `supabase/migrations/` rather than editing an applied one. Apply it with `python backend/scripts/migrate.py` and preserve existing data.

For changes to authentication, profiles, requests, chat, notifications, blocks, or reports, test that the signed-in owner or participant can act and that everyone else is rejected. Check the 401, 403, and 400 responses, and verify that permission failures leave records unchanged. Do not expose emails, message content, or other private data in responses where they are not already shown.

Update existing documentation in the README or `docs/` when changes affect setup, configuration, API behavior, or features.

Prefer simple solutions over unnecessary abstractions, dependencies, or scaffolding. Follow existing patterns unless there is a clear reason to change them.

## Verify

Run the same checks as CI before opening a pull request. From the repository root:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend -p "test_*.py" -v
python -m compileall -q backend
cd frontend
npm.cmd test
npm.cmd run lint
npx prettier --check "src/**/*.{js,jsx,ts,tsx,css,json}"
npm.cmd run build
cd ..
git diff --check
```

See [continuous integration](docs/CONTINUOUS_INTEGRATION.md) for details. For changes to user-facing flows, also run the app locally and try the affected flow, using two accounts when requests or chat are involved. For database changes, run the opt-in Supabase integration tests described in [Supabase setup](docs/SUPABASE.md) when credentials are available.

Report checks actually performed, their results, and anything you could not verify. Distinguish automated tests from manual checks in the running app.

## Record AI use

Follow [AI usage](ai/AI_USAGE.md). For each significant AI-assisted change, add an artifact file in `ai/artifacts/` recording what the AI proposed, what a human changed, and how the result was checked. Review and test AI output yourself before committing it.

## Open a pull request

Target `dev` (`origin/dev`), never `main`. At the end of the project, `dev` is merged into `main` in a single pull request.

Keep PRs focused, use a descriptive title, and link the relevant issue when one exists.

Include:

- **What and why:** Explain the problem, what changed, and important design decisions.
- **Verification:** Report checks actually run and their results. Include screenshots or manual test steps for UI changes.
- **Limitations:** Note known issues, untested behavior, and anything requiring closer review.

Explain decisions rather than narrating the diff. Link to relevant code when useful, and keep descriptions proportional to the change.

Exclude build output (`frontend/dist/`), `node_modules/`, local database files, credentials, and unrelated changes from the diff.
