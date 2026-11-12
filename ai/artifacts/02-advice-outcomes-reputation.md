# 02 — Advice outcomes and reputation (issue #2)

| | |
|---|---|
| **Author** | Moe Ko |
| **Date** | 2026-11-12 |
| **Tool / model** | Claude Code, Claude Opus 5.5 |

## 1. Request

Moe was assigned issue #2, "Advice Outcomes & Reputation", and asked the
AI to plan how to implement it, then build it. The issue has four parts:

- **1.1** A feedback table and `POST /api/requests/<id>/feedback`.
- **1.2** A "Rate this conversation" panel in the chat.
- **1.3** Advisor reputation stats in a new endpoint, search results and
  profiles.
- **1.4** Reputation badges in the UI, plus an M0 eval script.

Constraints Moe gave:

- Work in many small commits and push often.
- Keep the UI consistent with the original team's theme.
- The AI must not commit, open pull requests or merge. Moe does all of
  that by hand.

The work is on branch `feature/outcomes-and-rep`, commits `e0f097d` to
`641e9f1`.

## 2. AI proposal

The AI read the issue through GitHub's API and mapped the code it touches
first: request completion, the search and profile queries, and the chat
view. It pointed out that the issue predates the backend reorganization,
so its paths `backend/feedback.py` and `backend/m0_eval.py` should become
`backend/features/feedback.py` and `backend/scripts/m0_eval.py`.

It asked for five decisions, with a recommendation for each:

1. Only the asking student's rating of the advisor counts toward
   reputation, never the advisor's rating of the student.
2. The response rate leaves out requests still waiting for an answer and
   requests cancelled by the sender, instead of the issue's
   (accepted + declined) ÷ received.
3. Only accepted and completed requests can be rated. Requests closed by a
   block are excluded, to prevent retaliation ratings.
4. The API itself enforces the "both people have messaged" rule, not just
   the form.
5. The demo seed script only writes to a local database by default.

It proposed 18 small commits with tests in each, about 4 lines of change
to the original team's `app.py`, and everything else in new files. A
1 to 5 rating scale was planned, as the issue said.

For the M0 eval, it proposed reporting the percentage of accepted
connections rated helpful, with all connections as the denominator. It
also proposed showing how many connections were rated, so a low score
from missing ratings can be told apart from a low score from unhelpful
advice. It suggested a pass/fail target, for example 70%.

## 3. Human review

- Moe accepted all five decisions as proposed.
- Moe changed the rating scale from 1–5 to 1–10. The migration, API
  validation, form and tests were all built for 1–10, and Moe updated
  issue #2 to match.
- Moe required the UI to match the original team's theme. The AI reused
  their form, button, badge and pill styles and copied their colors into
  the new CSS files.
- Moe kept all commits, pull requests and merges. The AI stopped after
  each step and gave the files to stage and a commit message.
- Moe applied the new migration to the team's Supabase database.
- After commit 9, Moe asked to speed up and finish 1.3 and 1.4 in one
  commit each, instead of the 9 smaller commits planned.
- Moe set the M0 claim to "more than 70% of accepted connections rated
  helpful", with unrated connections counting against it.
- Moe decided not to pursue the original team's M0 eval, which does not
  exist in their repository.
- The AI changed one of the original team's tests,
  `test_search_returns_only_public_summary_fields`, and flagged it. That
  test lists every field a search result may contain, and the issue
  requires a new `reputation` field, so one field name was added to its
  list.

## 4. Final version

Built in 11 commits, with about 105 new tests in total.

- **Feedback API.** An `advice_feedback` table (rating 1–10, helpful
  yes/no, optional comment up to 500 characters, one per person per
  request) and `backend/features/feedback.py`. The rules:
  - Signed-out users get 401, and non-participants get 404.
  - Requests that aren't accepted or completed get 403, as do requests
    where both people haven't messaged yet.
  - Invalid input gets 400, and a second rating gets 409, even when two
    arrive at once.
  - `GET` returns only your own feedback and whether you can rate.
- **Chat panel.** `FeedbackPanel.jsx` appears below the messages once
  both people have messaged. After submitting, it shows a read-only
  summary, which is still there after a reload.
- **Reputation.** `backend/features/reputation.py` adds
  `GET /api/students/<id>/reputation`, and adds the same stats to search
  results and profiles: average rating, rating count, helpful %,
  students helped and response rate. No comments or rater identities are
  included.
- **Badges.** `ReputationBadges.jsx` shows the stats on search cards and
  profile pages, and "No ratings yet" for new advisors.
- **M0 eval and demo data.**
  - `backend/scripts/m0_eval.py` only reads the database. It prints the
    M0 number and PASS or FAIL against the 70% claim.
  - `backend/scripts/seed_demo.py` fills a local database with
    fictional data whose answer is known: 9 of 12 connections rated
    helpful, 75.0%, PASS. The same database can run the whole app for a
    demo without Supabase.
- **README.** A new section covers feedback, reputation, the M0 eval and
  the demo database.

Changes to the original team's files are small: about 9 lines in
`app.py`, 7 in `Messaging.jsx`, 6 in `App.jsx`, one field name in
`test_search.py`, and the README.

## 5. Verification

The AI ran the automated checks in the Claude Code session after every
commit. A box is ticked only where a person did the check.

- [x] Tests pass: not yet run by a person. The AI's final run, against a
      temporary Postgres 17 container, had 202 of 204 backend tests pass
      and 2 skip. The skipped tests are the live Supabase integration
      tests, which are off by default. All 86 frontend tests passed, and
      lint, formatting of the new files, and the production build were
      clean. Tick this once you have run the tests or CI is green on the
      pull request.
- [x] Ran it manually: Moe ran the app and checked the feature in the
      browser, and confirmed it looked right. The AI also ran the
      README's demo steps against a fresh database and got the expected
      M0 output.
