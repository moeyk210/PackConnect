"""Recognize existing Flask accounts and confirmed Supabase-linked profiles."""

import secrets


def registered_student_sql(alias="s"):
    # Callers supply a fixed SQL alias, never user input.
    return f"""(
        EXISTS (SELECT 1 FROM accounts a WHERE a.student_id = {alias}.id)
        OR EXISTS (
            SELECT 1 FROM auth.users u
            WHERE u.id = {alias}.auth_user_id AND u.email_confirmed_at IS NOT NULL
        )
    )"""


def create_auth_session(db, student_id):
    """Record a sign-in; the returned id goes into the signed session cookie."""
    # Revoked rows are never needed again; active ones live as long as their cookie.
    db.execute("DELETE FROM auth_sessions WHERE student_id = %s AND revoked_at IS NOT NULL", (student_id,))
    session_id = secrets.token_urlsafe(32)
    db.execute("INSERT INTO auth_sessions (id, student_id) VALUES (%s, %s)", (session_id, student_id))
    return session_id


def revoke_auth_session(db, session_id):
    db.execute("UPDATE auth_sessions SET revoked_at = now() WHERE id = %s AND revoked_at IS NULL",
               (session_id,))


def session_student_id(db, session):
    student_id = session.get("student_id")
    session_id = session.get("session_id")
    # Cookies without a server-side session (including pre-upgrade ones) are not trusted.
    if not student_id or not isinstance(session_id, str):
        return None
    if session.get("auth_user_id"):
        row = db.execute("""
            SELECT s.id, s.session_version FROM students s JOIN auth.users u ON u.id = s.auth_user_id
            WHERE s.id = %s AND u.id = %s AND u.email_confirmed_at IS NOT NULL
        """, (student_id, session["auth_user_id"])).fetchone()
    else:
        row = db.execute("SELECT s.id, s.session_version FROM accounts a JOIN students s ON s.id = a.student_id WHERE s.id = %s",
                         (student_id,)).fetchone()
    if not row or row["session_version"] != session.get("auth_version", 0):
        return None
    live = db.execute("SELECT 1 FROM auth_sessions WHERE id = %s AND student_id = %s AND revoked_at IS NULL",
                      (session_id, student_id)).fetchone()
    return row["id"] if live else None
