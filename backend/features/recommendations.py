"""'Recommended for you': advisors for the courses a student is taking right now.

Rules agreed for issue #3:
- Only signed-in students get recommendations (401 otherwise).
- They are based on the student's current courses. No current courses means an
  empty list; what the page says in that case is decided with the UI.
- An advisor must have completed at least one of those courses. Covering more of
  them ranks higher, using the same scoring as search (features/ranking.py).
- The student, anyone blocked either way, and anyone not taking requests right
  now (paused, full, or not advising) are left out.
"""

from flask import Blueprint, jsonify, session

from core.identity import registered_student_sql, session_student_id
from features import ranking
from features.advisor_candidates import NOT_BLOCKED_SQL, course_key_sql, fetch_advisor_rows
from features.availability import availability_status_sql
from features.search_ranking import INTERNAL_FIELDS, advisor_facts


def current_course_keys(db, student_id):
    """Return the student's current courses as keys (for example "CSC510"), without repeats."""
    rows = db.execute(
        f"SELECT DISTINCT {course_key_sql('course_code')} AS code FROM current_courses WHERE student_id = %s ORDER BY code",
        (student_id,),
    ).fetchall()
    return [row["code"] for row in rows]


def candidate_rows(db, student_id, course_keys):
    """Advisors who completed at least one of the given courses and could take a request now."""
    conditions = [
        registered_student_sql(),
        "s.id <> %s",
        NOT_BLOCKED_SQL,
        f"({availability_status_sql()}) = 'available'",
        f"""EXISTS (SELECT 1 FROM completed_courses c
            WHERE c.student_id = s.id AND {course_key_sql('c.course_code')} = ANY(%s))""",
    ]
    return fetch_advisor_rows(db, conditions, [student_id, student_id, student_id, course_keys])


def rank_recommendations(rows, course_keys):
    """Order advisor rows best fit first for the given courses and return their public data with scores."""
    rows_by_id = {row["id"]: row for row in rows}
    ranked = ranking.rank_advisors(ranking.SearchRequest(courses=course_keys), [advisor_facts(row) for row in rows])
    results = []
    for scored in ranked:
        public = {key: value for key, value in rows_by_id[scored.advisor.id].items() if key not in INTERNAL_FIELDS}
        public["score"] = round(scored.score, 3)
        results.append(public)
    return results


def create_recommendations_blueprint(get_db):
    api = Blueprint("recommendations", __name__)

    @api.get("/api/recommendations")
    def recommendations():
        with get_db() as db:
            student_id = session_student_id(db, session)
            if student_id is None:
                return jsonify(error="Sign in to continue."), 401
            course_keys = current_course_keys(db, student_id)
            if not course_keys:
                return jsonify(students=[])
            rows = candidate_rows(db, student_id, course_keys)
        return jsonify(students=rank_recommendations(rows, course_keys))

    return api
