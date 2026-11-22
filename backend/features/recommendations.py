"""'Recommended for you': advisors for the courses a student is taking right now.

Rules agreed for issue #3:
- Only signed-in students get recommendations (401 otherwise).
- They are based on the student's current courses. No current courses means an
  empty list; what the page says in that case is decided with the UI.
- An advisor must have completed at least one of those courses. Covering more of
  them ranks higher, using the same scoring as search (features/ranking.py).
- The student, anyone blocked either way, and anyone not taking requests right
  now (paused, full, or not advising) are left out.
- Anyone the student already has history with is left out, since the list is
  for finding someone new: a request either way that is waiting, accepted,
  completed, or declined. Cancelled and expired requests never connected the
  two students, so they do not hide an advisor.
"""

from flask import Blueprint, jsonify, session

from core.identity import registered_student_sql, session_student_id
from features import ranking
from features.advisor_candidates import NOT_BLOCKED_SQL, course_key_sql, fetch_advisor_rows
from features.availability import availability_status_sql
from features.search_ranking import INTERNAL_FIELDS, advisor_facts, reputation_reasons

# The most advisors shown at once. Students can search a course for the full list.
RECOMMENDATION_LIMIT = 5


def current_course_keys(db, student_id):
    """Return the student's current courses as keys (for example "CSC510"), without repeats."""
    rows = db.execute(
        f"SELECT DISTINCT {course_key_sql('course_code')} AS code FROM current_courses WHERE student_id = %s ORDER BY code",
        (student_id,),
    ).fetchall()
    return [row["code"] for row in rows]


# Leaves out advisors with existing history with the student, in either direction.
# A waiting request past its deadline counts as expired, as it does everywhere else.
# Takes the student's id twice.
NO_PAST_CONNECTION_SQL = """NOT EXISTS (SELECT 1 FROM advice_requests r
    WHERE ((r.sender_id = %s AND r.recipient_id = s.id) OR (r.sender_id = s.id AND r.recipient_id = %s))
      AND (r.status IN ('accepted', 'completed', 'declined')
           OR (r.status = 'pending' AND r.expires_at > CURRENT_TIMESTAMP)))"""


def candidate_rows(db, student_id, course_keys):
    """Advisors who completed at least one of the given courses and could take a request now."""
    conditions = [
        registered_student_sql(),
        "s.id <> %s",
        NOT_BLOCKED_SQL,
        NO_PAST_CONNECTION_SQL,
        f"({availability_status_sql()}) = 'available'",
        f"""EXISTS (SELECT 1 FROM completed_courses c
            WHERE c.student_id = s.id AND {course_key_sql('c.course_code')} = ANY(%s))""",
    ]
    parameters = [student_id, student_id, student_id, student_id, student_id, course_keys]
    return fetch_advisor_rows(db, conditions, parameters)


def joined(items):
    """Join labels as plain English: "A", "A and B", "A, B and C"."""
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def recommendation_reasons(row, course_keys):
    """Explain a recommendation: which of the student's current courses the advisor took, then reviews.

    Course codes are shown as the advisor saved them, once each.
    """
    taken = [code for code, key in zip(row["courses"], row["course_keys"]) if key in course_keys]
    return ["Took " + joined(list(dict.fromkeys(taken)))] + reputation_reasons(row)


def rank_recommendations(rows, course_keys):
    """Return up to RECOMMENDATION_LIMIT advisors, best fit first, with scores and reasons."""
    rows_by_id = {row["id"]: row for row in rows}
    ranked = ranking.rank_advisors(ranking.SearchRequest(courses=course_keys), [advisor_facts(row) for row in rows])
    results = []
    for scored in ranked[:RECOMMENDATION_LIMIT]:
        row = rows_by_id[scored.advisor.id]
        public = {key: value for key, value in row.items() if key not in INTERNAL_FIELDS}
        public["score"] = round(scored.score, 3)
        public["match_reasons"] = recommendation_reasons(row, course_keys)
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
