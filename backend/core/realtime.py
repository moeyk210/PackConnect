"""Socket.IO channel authenticated by the existing Flask session cookie."""

from flask import session
from flask_socketio import ConnectionRefusedError, SocketIO, join_room
from psycopg import OperationalError

from core.identity import session_student_id

# One in-process server. Same-origin only (the Flask-SocketIO default); Vite
# proxies /socket.io in development so the browser origin matches.
socketio = SocketIO(async_mode="threading")


def user_room(student_id):
    return f"user:{student_id}"


def register_realtime(app, get_db):
    socketio.init_app(app)

    # Accept `auth` explicitly: Flask-SocketIO retries handlers that raise
    # TypeError without arguments, which would hide real errors.
    @socketio.on("connect")
    def connect(auth=None):
        try:
            with get_db() as db:
                student_id = session_student_id(db, session)
        except OperationalError:
            raise ConnectionRefusedError("unavailable") from None
        if student_id is None:
            raise ConnectionRefusedError("unauthorized")
        join_room(user_room(student_id))
