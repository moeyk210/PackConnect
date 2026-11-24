# 06 — Development seed data and end-to-end tests

| | |
|---|---|
| **Author** | Ethan Goodman |
| **Date** | 2026-11-23 |
| **Tool / model** | Claude Code (VS Code extension), Claude Opus 5.5 |

## 1. Request

While checking `dev` locally, I noticed that the only seed with search data
(the simulated semester for the ranking eval) puts 14 of its 21 advisors on
CSC 510, and every advisor has exactly one course. That makes it hard to try
search, filters and course pages on anything else.

On branch `test/expand-seed-data-and-coverage`, which I created, I asked the
AI to expand the seed data (more courses, topics, skills and so on) and to
build more tests covering each main flow and edge case. I asked it to first
understand the search logic, the filters, and what a student or advisor can
have, before writing any data or tests.

Working rules: the AI never commits or pushes, and nothing touches the
team's Supabase project.

## 2. AI proposal

The AI read the search route, `search_ranking.py`, `ranking.py`,
`advisor_candidates.py`, availability, reputation, recommendations, course
pages, the request rules, the existing seeds, and the existing tests. It
summarized how search works: SQL narrows candidates (registered, not blocked,
same subject, available), then Python groups and ranks them. It also listed the
five availability states and the course-page rule that ratings show only with
3 or more raters.

It proposed a new seed script instead of changing the existing two:

- `seed_demo.py` has a known M0 result (75%) written into the README and
  tests.
- `seed_ranking_eval.py` has eval numbers recorded in `docs/SMART_MATCHING.md`.

Changing either would break teammates' documented results. The new seed is
written out by hand (not random) so tests can check exact results:

- 22 advisors across 31 courses in four subjects (CSC, MA, ST, ECE), with 7
  programs and 6 years;
- every availability state: open, unlimited, paused, full, not advising;
- review histories that create a top advisor, a poorly rated one, a new one,
  and one who never answers;
- 8 students who are not advising, with current courses for recommendations;
- one profile without an account, and one block.

It worked out each expected search, ranking and course-page result by hand
from the ranking formulas before running any test.

Mistakes the AI made:

- Two expected results were wrong when first written. One assumed "interviews"
  would meet the "Interview prep" topic filter through the tests' stand-in
  model, but that model scores it below the threshold. The other assumed that
  turning off "Available only" never shows students who are not advising, but
  the README documents that it does. It caught both while checking its
  expectations and rewrote the tests.
- A third test failed on the first run for the same documented reason
  (registered students who completed CSC 510 but do not advise appear with
  `available=false`). The AI confirmed this from the failure output and
  corrected the expectation. It did not change app code.
- It first ran the tests from the wrong folder, so the command failed and had
  to be rerun.

## 3. Human review

- I chose the branch name and created the branch myself.
- I stopped the AI partway through the test run to confirm nothing had been
  committed or pushed. It had not, and it waited until I said to continue.
- I approved the remaining steps: fix the failing test, run the full suite,
  run the seed command itself, and add README instructions.
- I asked how the data reaches the site, whether pushing would share the data
  with teammates (it shares the script, not the data), and whether anything
  touched Supabase (nothing did: every database was a local Docker container).

## 4. Final version

- **`backend/scripts/seed_dev_data.py`**: the seed. It also loads the course
  catalog and creates topic fingerprints with the local model, unless
  `--skip-embeddings` is given. It refuses non-local databases and refuses to
  seed the same database twice.
- **`backend/tests/test_seed_dev_data.py`**: 58 tests covering seed contents,
  course search and ranking order, course-code spellings, near misses and
  subject rules, each filter alone and combined, availability states,
  reputation, recommendations, blocking, course pages and ratings,
  autocomplete, and the flow of search, request, accept, chat, rate, then
  seeing the new rating in search.
- **`README.md`**: a "Development seed data" section with setup steps, sign-in
  details, and searches to try.

The AI also found that the README's demo-seed command uses the `postgres:17`
image, which no longer works now that migrations need pgvector. This was left
unchanged for the team to fix.

## 5. Verification

- [x] Tests pass: the full backend suite passed against a local pgvector
      Postgres 17 (484 tests, 3 skipped: the live Supabase and real-model tests).
- [x] Ran it manually: the site was run on the seeded data and searches,
      filters, profiles and course pages were checked in the browser.

Other checks:

- The seed command against a fresh local database: it migrated, seeded, loaded
  162 catalog courses and created 22 fingerprints. A second run was refused,
  and so was a non-local URL.
- With the real topic model on the seeded data, "interviews" and "job hunting"
  found the two interview-prep advisors for CSC 510, and a seeded student
  could sign in.
