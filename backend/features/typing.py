"""Typing indicators: ephemeral, never stored, relayed only to the other participant."""

import threading
import time

from flask import request, session
from psycopg import OperationalError

from core.identity import session_student_id
from core.realtime import socketio, user_room
from features.lifecycle import blocked

# Clients send at most one signal per 2 s; the server relays at most one per
# second per tab and conversation, checked before any database work.
RELAY_INTERVAL_SECONDS = 1.0
_last_relay = {}
_lock = threading.Lock()


def _allowed(sid, request_id, now):
    with _lock:
        key = (sid, request_id)
        if now - _last_relay.get(key, float("-inf")) < RELAY_INTERVAL_SECONDS:
            return False
        _last_relay[key] = now
        if len(_last_relay) > 10_000:  # forget tabs that went quiet
            for stale in [k for k, seen in _last_relay.items() if now - seen > 60]:
                del _last_relay[stale]
        return True


def register_typing(get_db):
    @socketio.on("typing")
    def typing(data=None):
        request_id = data.get("request_id") if isinstance(data, dict) else None
        if type(request_id) is not int or request_id < 1:
            return
        if not _allowed(request.sid, request_id, time.monotonic()):
            return
        try:
            with get_db() as db:
                # Revoked sessions lose their sockets, but a signal can still race
                # the disconnect, so check the session on every event.
                student_id = session_student_id(db, session)
                if student_id is None:
                    return
                record = db.execute(
                    """SELECT sender_id, recipient_id, status FROM advice_requests
                    WHERE id = %s AND (sender_id = %s OR recipient_id = %s)""",
                    (request_id, student_id, student_id),
                ).fetchone()
                if (not record or record["status"] != "accepted"
                        or blocked(db, record["sender_id"], record["recipient_id"])):
                    return
        except OperationalError:
            return  # typing is best-effort
        peer = record["recipient_id"] if record["sender_id"] == student_id else record["sender_id"]
        socketio.emit("typing", {"request_id": request_id, "user_id": student_id}, to=user_room(peer))
