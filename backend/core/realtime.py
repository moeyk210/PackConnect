"""Socket.IO channel authenticated by the existing Flask session cookie."""

import logging

from flask import json as flask_json, session
from flask_socketio import ConnectionRefusedError, SocketIO, join_room
from psycopg import OperationalError

from core.identity import session_student_id

logger = logging.getLogger(__name__)

# One in-process server. Same-origin only (the Flask-SocketIO default); Vite
# proxies /socket.io in development so the browser origin matches. Flask's
# JSON provider keeps payloads (including datetimes) identical to REST responses.
socketio = SocketIO(async_mode="threading", json=flask_json)


def user_room(student_id):
    return f"user:{student_id}"


def publish(db, user_ids, event, data):
    """Queue an event for these users; it is sent only after `db` commits."""
    rooms = [user_room(user_id) for user_id in dict.fromkeys(user_ids) if user_id is not None]
    if not rooms:
        return  # emit(to=[]) would broadcast to every client
    db.after_commit.append(lambda: _emit(event, data, rooms))


def _emit(event, data, rooms):
    try:
        socketio.emit(event, data, to=rooms)
    except Exception:
        # The data is committed; clients still see it on their next fetch.
        logger.exception("Realtime %s event could not be sent.", event)


def session_room(session_id):
    return f"session:{session_id}"


def disconnect_user(db, student_id):
    """Close every socket of this user once `db` commits (e.g. password reset)."""
    db.after_commit.append(lambda: _disconnect_room(user_room(student_id)))


def disconnect_session(db, session_id):
    """Close the sockets of one signed-in browser once `db` commits (logout)."""
    db.after_commit.append(lambda: _disconnect_room(session_room(session_id)))


def _disconnect_room(room):
    try:
        sids = [sid for sid, _ in socketio.server.manager.get_participants("/", room)]
        for sid in sids:
            socketio.server.disconnect(sid, namespace="/")
    except Exception:
        logger.exception("Realtime sockets could not be disconnected.")


def register_realtime(app, get_db):
    socketio.init_app(app)

    def verified_student():
        try:
            with get_db() as db:
                return session_student_id(db, session)
        except OperationalError:
            raise ConnectionRefusedError("unavailable") from None

    # Accept `auth` explicitly: Flask-SocketIO retries handlers that raise
    # TypeError without arguments, which would hide real errors.
    @socketio.on("connect")
    def connect(auth=None):
        student_id = verified_student()
        if student_id is None:
            raise ConnectionRefusedError("unauthorized")
        join_room(user_room(student_id))
        join_room(session_room(session["session_id"]))  # verified above
        # Check again after joining. A password reset or logout committing
        # between the first check and the joins would otherwise miss this
        # socket in its disconnect sweep. Refusal removes it from every room.
        if verified_student() != student_id:
            raise ConnectionRefusedError("unauthorized")
