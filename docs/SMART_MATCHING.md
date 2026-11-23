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
  "outside_filters": [ ...the best 15 advisors outside your filters... ],
  "total_matches": 4,
  "total_outside_filters": 1,
  "limit": 20,
  "offset": 0
}
```

`limit` and `offset` page through your matches only. The advisors outside your
filters are the same on every page (the best 15, with the full count in
`total_outside_filters`), so the page can show them in a row of their own.
Each advisor has the same fields as before, plus:

- `score`: the fit score from 0 to 1.
- `match_reasons`: short labels such as `"Advises on interview prep"`,
  `"9.0/10 (20 reviews)"`, `"No reviews yet"`, `"Answers 95% of requests"`,
  or `"Took CSC 540"` for advisors from a different course.
- `missed_filters`: the filters they do not meet, for example `["program"]`.

## Recommended for you

`GET /api/recommendations` suggests advisors for the courses the signed-in
student is taking now (their current courses, set under Edit Profile). It uses
the same scoring as search (`backend/features/recommendations.py`).

- Signed-out visitors get 401.
- No current courses gives an empty list.
- An advisor must have completed at least one current course; covering more of
  them ranks higher.
- Left out: the student, anyone blocked either way, anyone not taking requests
  right now, and anyone the student already has history with (a request either
  way that is waiting, accepted, completed, or declined). Cancelled and expired
  requests do not count as history.
- Up to 5 advisors, best fit first.

Response:

```json
{ "students": [ { "...": "same fields as search", "score": 0.91,
                  "match_reasons": ["Took CSC 510 and CSC 540", "9.0/10 (20 reviews)"] } ] }
```

## Ranking eval

`backend/scripts/ranking_eval.py` measures how often the advisor who accepted a
request was in the top 3 of the ranked search. For every accepted request it
rebuilds that search (the request's course and topic), ranks advisors using only
reviews and requests from before the request was sent, and checks where the
advisor who accepted landed. It also ranks the same cases the old way (advisors
who took the exact course, A-Z) as a baseline. It only reads.

PackConnect has no real history yet, so `backend/scripts/seed_ranking_eval.py`
creates a simulated semester in a dedicated local database: 21 fictional
advisors, 20 students, and 80 requests over 10 weeks. The students' behavior is
described at the top of that script; it does not use the app's scoring code.

```powershell
docker exec packconnect-test-db psql -U postgres -c "CREATE DATABASE packconnect_sim"
.\.venv\Scripts\python.exe backend/scripts/seed_ranking_eval.py --database-url "postgresql://postgres:postgres@127.0.0.1:5432/packconnect_sim?sslmode=disable"
.\.venv\Scripts\python.exe backend/scripts/ranking_eval.py --database-url "postgresql://postgres:postgres@127.0.0.1:5432/packconnect_sim?sslmode=disable"
```

Use any local PostgreSQL in place of the Docker container. The seed script
refuses non-local databases, so simulated history never mixes with real data.

Recorded result on the simulated semester (56 accepted requests):

| Order | Advisor who accepted was in the top 3 |
| --- | --- |
| New ranking | 42.9% (24 of 56) |
| Old A-Z order | 17.9% (10 of 56) |

These numbers come from simulated students, not real ones. They show the eval
works and how the ranking compares with the old order under realistic
conditions. Run the eval on the real database once there is enough history.

Limits:
- The database records when a request was sent, not when it was answered, so a
  request sent before a case counts with its final answer.
- Availability history is not stored, so the eval ignores availability.
- Profiles and courses are today's, not as they were at the time.

## Verification

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend -p "test_ranking.py" -v
.\.venv\Scripts\python.exe -m unittest discover -s backend -p "test_search_ranking.py" -v
```

These need no database. `backend/tests/test_search.py` and
`backend/tests/test_recommendations.py` check the rules end to end and need
`TEST_DATABASE_URL`, as described in [Supabase setup](SUPABASE.md).
