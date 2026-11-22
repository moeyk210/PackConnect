"""'Recommended for you': advisors for the courses a student is taking right now.

Rules agreed for issue #3:
- Only signed-in students get recommendations (401 otherwise).
- They are based on the student's current courses. No current courses means an
  empty list; what the page says in that case is decided with the UI.
"""

from flask import Blueprint, jsonify, session

from core.identity import session_student_id
from features.advisor_candidates import course_key_sql


def current_course_keys(db, student_id):
    """Return the student's current courses as keys (for example "CSC510"), without repeats."""
    rows = db.execute(
        f"SELECT DISTINCT {course_key_sql('course_code')} AS code FROM current_courses WHERE student_id = %s ORDER BY code",
        (student_id,),
    ).fetchall()
    return [row["code"] for row in rows]


def create_recommendations_blueprint(get_db):
    api = Blueprint("recommendations", __name__)

    @api.get("/api/recommendations")
    def recommendations():
        with get_db() as db:
            student_id = session_student_id(db, session)
            if student_id is None:
                return jsonify(error="Sign in to continue."), 401
            if not current_course_keys(db, student_id):
                return jsonify(students=[])
        return jsonify(students=[])

    return api
