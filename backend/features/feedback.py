"""Post-advice feedback from the participants of an advice connection."""

from functools import wraps

from flask import Blueprint, jsonify, request, session
from core.identity import session_student_id

FEEDBACK_FIELDS = "id, request_id, rating, helpful, comment, created_at"
# Only connections that actually happened can be rated. Requests closed by a
# block are excluded so feedback cannot be used for retaliation.
RATEABLE_STATUSES = ("accepted", "completed")
MIN_RATING, MAX_RATING = 1, 10
MAX_COMMENT_LENGTH = 500


def feedback_payload(data):
    """Return (rating, helpful, comment) from a request body, or raise ValueError."""
    if not isinstance(data, dict):
        raise ValueError("Send a JSON object with your feedback.")
    rating = data.get("rating")
    # bool is a subclass of int in Python, so True would otherwise pass as 1.
    if isinstance(rating, bool) or not isinstance(rating, int) or not MIN_RATING <= rating <= MAX_RATING:
        raise ValueError(f"Rating must be a whole number from {MIN_RATING} to {MAX_RATING}.")
    helpful = data.get("helpful")
    if not isinstance(helpful, bool):
        raise ValueError("Say whether the advice was helpful (true or false).")
    comment = data.get("comment")
    if comment is None:
        comment = ""
    if not isinstance(comment, str):
        raise ValueError("Comment must be text.")
    comment = comment.strip()
    if len(comment) > MAX_COMMENT_LENGTH:
        raise ValueError(f"Comment must be at most {MAX_COMMENT_LENGTH} characters.")
    return rating, helpful, comment


def create_feedback_blueprint(get_db):
    api = Blueprint("feedback", __name__)

    def authenticated(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            with get_db() as db:
                user = session_student_id(db, session)
                if user is None:
                    return jsonify(error="Sign in to continue."), 401
                return function(db, user, *args, **kwargs)

        return wrapped

    def participant_request(db, user, request_id):
        # Unrelated users get the same 404 as a missing request, revealing nothing.
        return db.execute(
            "SELECT id, sender_id, recipient_id, status FROM advice_requests WHERE id = %s AND %s IN (sender_id, recipient_id)",
            (request_id, user),
        ).fetchone()

    @api.post("/api/requests/<int:request_id>/feedback")
    @authenticated
    def submit_feedback(db, user, request_id):
        advice = participant_request(db, user, request_id)
        if advice is None:
            return jsonify(error="Request not found."), 404
        if advice["status"] not in RATEABLE_STATUSES:
            return jsonify(error="Feedback opens once the request has been accepted."), 403
        try:
            rating, helpful, comment = feedback_payload(request.get_json(silent=True))
        except ValueError as error:
            return jsonify(error=str(error)), 400
        row = db.execute(
            f"""INSERT INTO advice_feedback (request_id, rater_id, rating, helpful, comment)
            VALUES (%s, %s, %s, %s, %s) RETURNING {FEEDBACK_FIELDS}""",
            (request_id, user, rating, helpful, comment),
        ).fetchone()
        return jsonify(feedback=dict(row)), 201

    return api
