# 03 — Smart matching and ranking (issue #3)

| | |
|---|---|
| **Author** | Morgan Simon |
| **Date** | 2026-11-22 |
| **Tool / model** | Claude Code, Claude Opus 5.5 |

## 1. Request

Morgan was assigned issue #3, "Smart Matching & Ranking". Morgan used the AI
to review the repository, research standard approaches before each design
decision, and build the work in small, focused commits.

Constraints Morgan set:

- Follow single source of truth, separation of concerns and SOLID. Use
  plain-language comments.
- Commits are subject line only, and very small.
- Nothing is pushed, posted or opened as a PR until Morgan has approved it.

## 2. AI proposal

- **Ranking:** a pure scoring function from course, topic, rating and
  response rate, with the weights in one place. It compared rating methods
  (plain average, Bayesian average, Wilson score).
- **Topic matching:** it compared shared words, full-text search, fuzzy
  matching and embeddings, and suggested starting with shared words.
- **Search results:** one ranked list with per-card match explanations and
  match-strength labels.
- **Evaluation:** a replay eval that only uses data from before each
  request, run on a simulated semester because there isn't enough real
  history yet.
- **Embeddings:** fingerprints computed in memory, to avoid database and CI
  changes.

## 3. Human review

- **Ratings:** chose the Bayesian average, and added a filter to include or
  hide advisors with no reviews.
- **Results design:** redesigned the results, modeled on job and housing
  sites. Matches use page numbers, and near misses appear in a separate
  "Outside your filters" row, ordered with the exact course first and then
  related courses.
- **Labels:** removed the per-card explanations and the match-strength
  labels to keep cards uncluttered.
- **Filters:** chose the filter-pill design from three mockups.
- **Eval:** chose an A–Z baseline on the same cases, and kept the starting
  weights after comparing alternatives.
- **Embeddings:** chose pgvector so fingerprints are stored in the database.

## 4. Final version

Ranking module, ranked search with an "Outside your filters" group,
recommendations endpoint, meaning-based topic matching with pgvector, ranking
and topic evals, and the new search UI (Top match, page numbers, filter pills,
near-miss row). Branch `feature/smart-matching`; see
[`docs/SMART_MATCHING.md`](../../docs/SMART_MATCHING.md).

## 5. Verification

- [x] Tests pass: backend and frontend suites in CI on GitHub.
- [x] Ran it manually: Morgan used the search page with demo data and
  reviewed each UI change.
