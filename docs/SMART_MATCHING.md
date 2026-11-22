# Smart matching and ranked search

Search results are ordered by how well each advisor fits the search, not by name.
This covers issue #3.

## How a score is worked out

Each advisor gets a score from 0 to 1, a weighted average of four factors
(`backend/features/ranking.py`):

| Factor | Question it answers | Weight |
| --- | --- | --- |
| Course | Did they complete the searched course? | 0.35 |
| Topic | How many of the student's topic words do their advice topics cover? | 0.30 |
| Rating | How well do students rate their advice? | 0.20 |
| Response | How often do they answer requests? | 0.15 |

- Course and topic only count when the student searched for them.
- Ratings and response rates use a Bayesian average: every advisor starts with a
  few imaginary typical results (7.0/10 rating, 80% response rate), and real
  results gradually outweigh them. One 10/10 rating does not beat twenty 9s, and
  advisors with no reviews get the starting value instead of zero.
- Topic words ignore capital letters, filler words, and simple plural endings,
  so "interviews" matches "interview".
- All weights and starting values are in one block at the top of `ranking.py`.

## Matches and "Outside your filters"

`backend/features/search_ranking.py` puts each advisor in a group:

1. **Your matches:** took the searched course and meets every filter
   (program, year, skills, advice topics).
2. **Outside your filters:** near misses, so a search is never a dead end.
   - First, advisors who took the searched course but miss some filters.
   - Then, advisors who took another course in the same subject (for example
     CSC 540 when searching CSC 510) and meet at least one filter, if any were given.

Advisors with no course in the searched subject are never shown. Without a
course, matches meet every filter and near misses meet at least one.
Inside each group, fewer missed filters come first, then higher scores, then
name and id, so the order is always the same for the same data.

## API

`GET /api/students/search`

| Parameter | Meaning | Default |
| --- | --- | --- |
| `course`, `program`, `year`, `skills`, `advice_topics` | Search and filters, as before | none |
| `available` | `false` also includes advisors who are paused, full, or not advising | `true` |
| `include_unrated` | `false` leaves out advisors with no reviews yet | `true` |
| `limit` | Results per page, at most 50 (larger values are lowered to 50) | 20 |
| `offset` | Results to skip, for later pages | 0 |

An invalid `limit` or `offset` returns 400.

Response:

```json
{
  "students": [ ...your matches on this page... ],
  "outside_filters": [ ...advisors outside your filters on this page... ],
  "total_matches": 4,
  "total_outside_filters": 1,
  "limit": 20,
  "offset": 0
}
```

Paging runs across both lists in order, so a page can end the matches and
start the advisors outside the filters. Each advisor has the same fields as
before, plus:

- `score`: the fit score from 0 to 1.
- `match_reasons`: short labels such as `"Advises on interview prep"`,
  `"9.0/10 (20 reviews)"`, `"No reviews yet"`, `"Answers 95% of requests"`,
  or `"Took CSC 540"` for advisors from a different course.
- `missed_filters`: the filters they do not meet, for example `["program"]`.

## Verification

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend -p "test_ranking.py" -v
.\.venv\Scripts\python.exe -m unittest discover -s backend -p "test_search_ranking.py" -v
```

These need no database. `backend/tests/test_search.py` checks the same rules end
to end and needs `TEST_DATABASE_URL`, as described in [Supabase setup](SUPABASE.md).
