"""Course pages: catalog details, ranked advisors and course-level ratings.

Rules:
- Advisors are registered students who completed the course and are currently
  available. The signed-in student is left out of their own list, and so is
  anyone they have blocked or who has blocked them.
- Advisors are ranked by their reputation rating, smoothed so that one perfect
  rating does not outrank many excellent ones: each advisor's average is pulled
  toward the middle of the 1-10 scale as if they had SMOOTHING_WEIGHT extra
  ratings of SCALE_MIDPOINT. Advisors without ratings come last. Ties go to the
  advisor who has helped more students, then to the name.
- Workload and difficulty averages come from the optional 1-5 course ratings on
  advice feedback. Only students who completed the course are counted, and each
  student counts once however many conversations they rated. An average is shown
  only when at least MIN_RATINGS students gave that rating; otherwise it is
  null, so that no individual rating can be worked out from the page.
"""

import re

from flask import Blueprint, jsonify, session

from core.courses import normalize_code
from core.identity import registered_student_sql, session_student_id
from features.availability import availability_columns, availability_status_sql, workload_join
from features.reputation import reputation_columns, reputation_join, with_reputation

MIN_RATINGS = 3
SMOOTHING_WEIGHT = 3
SCALE_MIDPOINT = 5.5
MAX_CODE_LENGTH = 30

# Compare codes ignoring case, spaces and hyphens, as search does.
CODE_KEY = "regexp_replace(upper({column}), '[[:space:]-]+', '', 'g')"


def code_key(value):
    return re.sub(r"[\s-]+", "", value).upper()


def ranking_score(reputation):
    count = reputation["rating_count"]
    if not count:
        return None
    return (count * reputation["average_rating"] + SMOOTHING_WEIGHT * SCALE_MIDPOINT) / (count + SMOOTHING_WEIGHT)


def rank_advisors(advisors):
    def order(advisor):
        reputation = advisor["reputation"]
        score = ranking_score(reputation)
        return (score is None, -(score or 0), -(reputation["students_helped"] or 0),
                advisor["name"].lower(), advisor["id"])

    return sorted(advisors, key=order)


def create_courses_blueprint(get_db):
    api = Blueprint("courses", __name__)

    def rating_summary(row, name):
        count = row[f"{name}_count"]
        if count < MIN_RATINGS:
            return None
        return {"average": row[f"{name}_average"], "count": count}

    @api.get("/api/courses/<code>")
    def course_page(code):
        code = normalize_code(code)
        key = code_key(code)
        if not key or len(code) > MAX_CODE_LENGTH:
            return jsonify(error="Course not found."), 404
        with get_db() as db:
            course = db.execute("SELECT code, title, description FROM courses WHERE code = %s",
                                (code,)).fetchone()
            if course is None:
                return jsonify(error="Course not found."), 404

            viewer = session_student_id(db, session) if session.get("student_id") else None
            parameters = [key]
            viewer_clause = ""
            if viewer:
                viewer_clause = """
                  AND s.id <> %s
                  AND NOT EXISTS (SELECT 1 FROM student_blocks b
                                  WHERE (b.blocker_id = %s AND b.blocked_id = s.id)
                                     OR (b.blocker_id = s.id AND b.blocked_id = %s))"""
                parameters += [viewer, viewer, viewer]
            advisors = db.execute(f"""
                SELECT s.id, s.name, s.program, s.year, s.advice_topics, s.willing_to_advise,
                       {availability_columns()}, {reputation_columns()}
                FROM students s {workload_join()} {reputation_join()}
                WHERE {registered_student_sql()}
                  AND ({availability_status_sql()}) = 'available'
                  AND EXISTS (SELECT 1 FROM completed_courses c
                              WHERE c.student_id = s.id
                                AND {CODE_KEY.format(column="c.course_code")} = %s){viewer_clause}
            """, parameters).fetchall()

            ratings = db.execute(f"""
                SELECT count(workload) AS workload_count,
                       round(avg(workload)::numeric, 1)::float8 AS workload_average,
                       count(difficulty) AS difficulty_count,
                       round(avg(difficulty)::numeric, 1)::float8 AS difficulty_average
                FROM (
                    SELECT f.rater_id,
                           avg(f.workload_rating) AS workload,
                           avg(f.difficulty_rating) AS difficulty
                    FROM advice_feedback f
                    JOIN advice_requests r ON r.id = f.request_id
                    WHERE {CODE_KEY.format(column="r.course_code")} = %s
                      AND EXISTS (SELECT 1 FROM completed_courses c
                                  WHERE c.student_id = f.rater_id
                                    AND {CODE_KEY.format(column="c.course_code")} = %s)
                    GROUP BY f.rater_id
                ) per_rater
            """, (key, key)).fetchone()

        return jsonify(
            course={"code": course["code"], "title": course["title"],
                    "description": course["description"] or ""},
            advisors=rank_advisors([with_reputation(row) for row in advisors]),
            ratings={"min_ratings": MIN_RATINGS,
                     "workload": rating_summary(ratings, "workload"),
                     "difficulty": rating_summary(ratings, "difficulty")},
        )

    return api
