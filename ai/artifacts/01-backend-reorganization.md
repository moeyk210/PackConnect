# 01 — Backend file reorganization

| | |
|---|---|
| **Author** | Moe Ko |
| **Date** | 2026-11-10 |
| **Tool / model** | Claude Code, Claude Opus 5.5 |

## 1. Request

Before starting the Project 3 milestones, reorganize the repo so the
files in the flat `backend/` folder are grouped into relevant subfolders
inside `backend/`. The request gave no target layout, so the AI chose
one.

The work started from commit `a313141`, which is the upstream PackConnect
`main` plus one `.gitignore` commit.

## 2. AI proposal

The AI mapped the imports between backend files, the code that depends on
file locations, and every path mentioned in CI and the docs. It then
proposed this layout:

```text
backend/
├── app.py             Flask entry point, not moved
├── requirements.txt, .env, .env.example   not moved
├── core/              database.py, identity.py
├── features/          availability, community, lifecycle, meetings,
│                      messaging, recovery
├── scripts/           migrate.py, expire_requests.py
└── tests/             all test_*.py files, postgres_test_support.py
```

Supporting changes it proposed:

- Add `__init__.py` to each new folder. Test discovery only recurses into
  packages, and this lets the CI command stay the same.
- Rewrite imports to the new package paths, such as
  `from core.database import connect_database`, including the two test
  mocks that name `recovery` as a string.
- Add a `sys.path` line to both scripts so they can still be run directly
  as files.
- Update the migrations and `.env` paths in `migrate.py`, which depend on
  the file's location.
- Update the commands and paths in `README.md` and `docs/`.
- Commit this on its own, separate from feature work, so markers can see
  that it only moves code.

## 3. Human review

- Moe accepted the proposed layout without changes after review.
- Moe kept commits out of the AI's hands and asked for this AI usage
  record to be set up before committing.
- The AI tried to install a temporary Postgres in a temp folder to run
  the tests. Claude Code's permission check blocked it, so the AI stopped
  and asked, and Moe started Docker Desktop instead.
- Moe read the results and ensured everything looked good.

## 4. Final version

Built as proposed. In total, 24 files moved and 4 empty `__init__.py`
files were added. Code edits are limited to import lines, the two test
mock targets, and the path handling in the two scripts. No route or
application logic changed.

Migrations and request expiry now run with
`python backend/scripts/migrate.py` and
`python backend/scripts/expire_requests.py`. `python backend/app.py` and
the CI commands are unchanged.

The AI also reinstalled `backend/requirements.txt` in the local `.venv`,
which was missing `psycopg_pool` after syncing with upstream.

## 5. Verification

The AI ran every check below in the Claude Code session. The boxes stay
unticked until a person has done the check themselves.

- [x] Tests pass: not yet run by a person. The AI's run on Python 3.14.7
      had 126 backend tests pass and 2 skip, out of 128, against a
      temporary Postgres 17 container. The 2 skipped tests are the live
      Supabase integration tests, which are off by default. All 52
      frontend tests passed. CI has not run on this change yet.
- [ ] Ran it manually: not yet done by a person, and the AI did not open
      the app in a browser. The AI confirmed that test discovery finds
      the same 128 tests as before the move, that the app loads 30 routes
      and 4 feature modules, and that both scripts start from their new
      location and fail only when connecting to a closed local port.
