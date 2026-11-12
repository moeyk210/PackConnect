"""Advisor reputation: aggregate feedback and responsiveness, never raw feedback.

Rules agreed for issue #2:
- Only the asking student's rating of the advisor counts. An advisor's rating
  of the student they helped never affects the advisor's own reputation.
- Students helped: distinct students whose request the advisor accepted
  (status accepted or completed).
- Response rate: answered requests (accepted, declined, completed) divided by
  answered plus unanswered (expired, or pending past its deadline). Requests
  still waiting for an answer, cancelled by the sender, or closed by a block
  are left out, so they neither help nor hurt.
"""

from flask import Blueprint, jsonify

FIELDS = ("average_rating", "rating_count", "helpful_percent", "students_helped", "response_rate")
PREFIX = "reputation_"


def reputation_join(alias="s"):
    # Callers supply a fixed SQL alias, never user input.
    return f"""LEFT JOIN LATERAL (
        SELECT count(f.id) AS rating_count,
               round(avg(f.rating)::numeric, 1)::float8 AS average_rating,
               round(100.0 * count(f.id) FILTER (WHERE f.helpful) / NULLIF(count(f.id), 0))::int AS helpful_percent
        FROM advice_feedback f JOIN advice_requests fr ON fr.id = f.request_id
        WHERE fr.recipient_id = {alias}.id AND f.rater_id = fr.sender_id
    ) rep_f ON true
    LEFT JOIN LATERAL (
        SELECT count(DISTINCT sender_id) FILTER (WHERE status IN ('accepted', 'completed')) AS students_helped,
               count(*) FILTER (WHERE status IN ('accepted', 'declined', 'completed')) AS answered,
               count(*) FILTER (WHERE status = 'expired'
                                OR (status = 'pending' AND expires_at <= CURRENT_TIMESTAMP)) AS unanswered
        FROM advice_requests WHERE recipient_id = {alias}.id
    ) rep_r ON true"""


def reputation_columns():
    return f"""rep_f.average_rating AS {PREFIX}average_rating,
        rep_f.rating_count AS {PREFIX}rating_count,
        rep_f.helpful_percent AS {PREFIX}helpful_percent,
        rep_r.students_helped AS {PREFIX}students_helped,
        round(100.0 * rep_r.answered / NULLIF(rep_r.answered + rep_r.unanswered, 0))::int AS {PREFIX}response_rate"""


def with_reputation(row):
    """Move the flat reputation_* columns of a result row into a nested object."""
    record = dict(row)
    record["reputation"] = {field: record.pop(PREFIX + field) for field in FIELDS}
    return record


def create_reputation_blueprint(get_db):
    api = Blueprint("reputation", __name__)

    @api.get("/api/students/<int:student_id>/reputation")
    def student_reputation(student_id):
        with get_db() as db:
            row = db.execute(
                f"SELECT {reputation_columns()} FROM students s {reputation_join()} WHERE s.id = %s",
                (student_id,),
            ).fetchone()
        if row is None:
            return jsonify(error="Student not found."), 404
        return jsonify(reputation=with_reputation(row)["reputation"])

    return api
