# AI Usage

How our team uses AI tools while extending PackConnect in Project 3, and
where to find the evidence. Every significant AI-assisted change has an
artifact file in [`artifacts/`](artifacts/) recording what the AI
proposed, what a human changed, and how the result was checked.

This log covers work done since the fork point. AI use by PackConnect's
original Project 2 team is not tracked here.

## Tools

| Tool | Model / version | Used by | Where it runs |
|---|---|---|---|
| Claude Code | Claude Opus 5.5 | Moe | VS Code extension |
| _TODO_ | | | |

## What we use AI for

- Assessing the inherited code and planning the Project 3 milestones
- Restructuring the backend without changing its behavior (see
  [01-backend-reorganization](artifacts/01-backend-reorganization.md))
- Planning and building a feature from a GitHub issue, with tests in each
  commit (see
  [02-advice-outcomes-reputation](artifacts/02-advice-outcomes-reputation.md))
- _TODO: add as the project goes (e.g. first drafts of tests, PR review)_

## What we do not use AI for

- _TODO: team to decide. Suggestions:_
  - _Deciding the outcome of student reports and blocks. These affect
    real people, so moderators decide them._
  - _Deciding what personal data is collected or shown, such as emails
    and course history. These rules are written and reviewed by people._
  - _Merging code no human has read._
  - _Writing M0 eval results or self-assessed rubric scores._

## How AI output is checked

1. Whoever uses AI output reviews it by hand and tests it before
   committing.
2. A different teammate reviews the pull request before it is merged.
3. The person who ran the session writes an artifact file from
   [`TEMPLATE.md`](artifacts/TEMPLATE.md).
4. CI runs the test suite on every push, so a regression is flagged
   before the merge.

## Artifact index

| # | Artifact | Author | Date |
|---|---|---|---|
| 01 | [Backend file reorganization](artifacts/01-backend-reorganization.md) | Moe Ko | 2026-11-10 |
| 02 | [Advice outcomes and reputation (issue #2)](artifacts/02-advice-outcomes-reputation.md) | Moe Ko | 2026-11-12 |
