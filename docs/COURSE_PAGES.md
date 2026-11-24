# Course pages

Every course in the catalog has a page at `#/app/courses/<code>` (for example
`#/app/courses/CSC%20510`). It shows:

- the course **title and description** from the `courses` table;
- the average **workload** and **difficulty**, when enough students have rated;
- the **available advisors** for the course, best rated first.

An unknown code, or one that is not in the catalog, shows a "Course not found"
page with a link back to Find peers.

Course codes link to the page from a student's profile (completed and current
courses) and from the search results, which link to the course that was
searched.

## API

`GET /api/courses/<code>` needs no sign-in. The code is normalized the same way
as everywhere else, so `csc-510` and `CSC510` find `CSC 510`. A code that is not
in the catalog returns `404 {"error": "Course not found."}`. Otherwise:

```json
{
  "course": {"code": "CSC 510", "title": "Software Engineering", "description": "..."},
  "advisors": [{"id": 2, "name": "Alex Morgan", "reputation": {"average_rating": 9.0, "...": "..."}}],
  "ratings": {
    "min_ratings": 3,
    "workload": {"average": 3.4, "count": 5},
    "difficulty": null
  }
}
```

### Workload and difficulty

These come from two optional 1-5 questions on the feedback form
("Course workload" and "Course difficulty"), stored in
`advice_feedback.workload_rating` and `difficulty_rating`. They describe the
course and never affect an advisor's reputation. The feedback API rejects
anything that is not a whole number from 1 to 5, and leaving them out is fine.

- A figure is shown **only when at least 3 students** gave that rating
  (`MIN_RATINGS`); otherwise it is `null`, so no single rating can be worked out.
  Workload and difficulty are counted separately.
- Only students who **completed the course** are counted.
- Each student counts **once**, however many conversations they rated: their
  own ratings are averaged first, and those per-student averages are averaged.
- Comments, who rated and individual ratings are never returned.

### Advisors

Registered students who completed the course and are currently available
(not paused, under their request limit, willing to advise). The signed-in
student, and anyone they have blocked or who has blocked them, is left out.

They are ranked by reputation rating, smoothed so that one perfect rating does
not outrank many excellent ones: the average is pulled toward the middle of the
1-10 scale as if the advisor had 3 more ratings of 5.5. For example, five
ratings of 9 score 7.7 and a single rating of 10 scores 6.6. Advisors with no
ratings come last. Ties go to the advisor who has helped more students, then to
the name. The weights are `SMOOTHING_WEIGHT` and `SCALE_MIDPOINT` in
`backend/features/courses.py`.

## Database

`supabase/migrations/20261122000100_course_ratings.sql` adds the two columns.
They are nullable with a `BETWEEN 1 AND 5` check, and the statement is safe to
run twice.

## Verification

Backend: `python -m unittest discover -s backend -p "test_course_pages.py" -v`.
Frontend, from `frontend/`: `npm test -- --run`, `npm run lint`,
`npm run build`, and `npx prettier --check "src/**/*.{js,jsx,css}"`.

Browser check:

1. Open `#/app/courses/CSC%20510`: title and description show, and advisors are
   listed best rated first.
2. Open `#/app/courses/CSC%20999`: "Course not found".
3. On a profile, click a course code: it opens that course's page.
4. On Find peers, click the "About CSC 510" link above the results.
5. Complete a conversation's feedback form with a workload and a difficulty
   rating. The averages stay hidden on the course page until 3 students who took
   the course have rated it.
