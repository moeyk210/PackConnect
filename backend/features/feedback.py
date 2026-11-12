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

    def both_have_messaged(db, advice):
        # A rating should reflect a real exchange, not an accepted request nobody used.
        row = db.execute(
            "SELECT count(DISTINCT sender_id) AS senders FROM chat_messages WHERE request_id = %s AND sender_id IN (%s, %s)",
            (advice["id"], advice["sender_id"], advice["recipient_id"]),
        ).fetchone()
        return row["senders"] == 2

    def own_feedback(db, user, request_id):
        row = db.execute(
            f"SELECT {FEEDBACK_FIELDS} FROM advice_feedback WHERE request_id = %s AND rater_id = %s",
            (request_id, user),
        ).fetchone()
        return dict(row) if row else None

    @api.get("/api/requests/<int:request_id>/feedback")
    @authenticated
    def get_feedback(db, user, request_id):
        advice = participant_request(db, user, request_id)
        if advice is None:
            return jsonify(error="Request not found."), 404
        # Only the signed-in person's own feedback is returned, never the other participant's.
        mine = own_feedback(db, user, request_id)
        can_rate = (mine is None and advice["status"] in RATEABLE_STATUSES
                    and both_have_messaged(db, advice))
        return jsonify(feedback=mine, can_rate=can_rate)

    @api.post("/api/requests/<int:request_id>/feedback")
    @authenticated
    def submit_feedback(db, user, request_id):
        advice = participant_request(db, user, request_id)
        if advice is None:
            return jsonify(error="Request not found."), 404
        if advice["status"] not in RATEABLE_STATUSES:
            return jsonify(error="Feedback opens once the request has been accepted."), 403
        if not both_have_messaged(db, advice):
            return jsonify(error="Feedback opens after you have both sent a message."), 403
        try:
            rating, helpful, comment = feedback_payload(request.get_json(silent=True))
        except ValueError as error:
            return jsonify(error=str(error)), 400
        # The unique (request_id, rater_id) constraint decides races: of two
        # simultaneous submissions, exactly one inserts and the other gets 409.
        row = db.execute(
            f"""INSERT INTO advice_feedback (request_id, rater_id, rating, helpful, comment)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (request_id, rater_id) DO NOTHING
            RETURNING {FEEDBACK_FIELDS}""",
            (request_id, user, rating, helpful, comment),
        ).fetchone()
        if row is None:
            return jsonify(error="You have already given feedback for this conversation."), 409
        return jsonify(feedback=dict(row)), 201

    return api
