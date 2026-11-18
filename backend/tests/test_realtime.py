import os
import unittest
from unittest.mock import patch

from psycopg import OperationalError

import app as portal
import core.realtime as core_realtime
from core.realtime import socketio, user_room
from tests.postgres_test_support import PostgresTestCase


class RealtimeConnectionTests(PostgresTestCase):
    def setUp(self):
        super().setUp()
        self.clients, self.ids = [], []
        for name in ("Alice", "Blake"):
            client = portal.app.test_client()
            credentials = {"email": name.lower() + "@example.edu", "password": "a long test password"}
            response = client.post("/api/auth/register", json={
                **credentials, "name": name, "program": "Computer Science", "year": "First Year",
            })
            self.ids.append(response.get_json()["student"]["id"])
            self.assertEqual(client.post("/api/auth/login", json=credentials).status_code, 200)
            self.clients.append(client)

    def socket(self, flask_client=None):
        sock = socketio.test_client(portal.app, flask_test_client=flask_client)
        self.addCleanup(lambda: sock.is_connected() and sock.disconnect())
        return sock

    def test_unauthenticated_socket_is_rejected(self):
        self.assertFalse(self.socket().is_connected())
        self.assertFalse(self.socket(portal.app.test_client()).is_connected())

    def test_signed_in_socket_joins_only_its_own_room(self):
        alice, blake = self.socket(self.clients[0]), self.socket(self.clients[1])
        self.assertTrue(alice.is_connected())
        self.assertTrue(blake.is_connected())
        with portal.app.app_context():
            socketio.emit("probe", {"for": "alice"}, to=user_room(self.ids[0]))
        self.assertEqual([e["args"] for e in alice.get_received()], [[{"for": "alice"}]])
        self.assertEqual(blake.get_received(), [])

    def test_logged_out_session_is_rejected(self):
        self.clients[0].post("/api/auth/logout")
        self.assertFalse(self.socket(self.clients[0]).is_connected())

    def test_invalidated_session_version_is_rejected(self):
        with portal.get_db() as db:
            db.execute("UPDATE students SET session_version = session_version + 1 WHERE id = %s", (self.ids[0],))
        self.assertFalse(self.socket(self.clients[0]).is_connected())
        self.assertTrue(self.socket(self.clients[1]).is_connected())

    def test_database_outage_refuses_connection(self):
        with patch("core.realtime.session_student_id", side_effect=OperationalError("down")):
            self.assertFalse(self.socket(self.clients[0]).is_connected())

    def reset_token(self):
        self.enterContext(patch.dict(os.environ, {"SMTP_HOST": "smtp.example.test",
                                                  "SMTP_FROM": "noreply@example.test",
                                                  "PUBLIC_APP_URL": "https://pack.example.test"}))
        mail = self.enterContext(patch("features.recovery.send_recovery_email"))
        response = portal.app.test_client().post("/api/auth/forgot-password", json={"email": "alice@example.edu"})
        self.assertEqual(response.status_code, 200, response.get_json())
        return mail.call_args.args[1].split("token=")[1]

    def test_password_reset_disconnects_every_tab_of_that_user_only(self):
        tabs = [self.socket(self.clients[0]), self.socket(self.clients[0])]
        blake = self.socket(self.clients[1])
        token = self.reset_token()
        new_password = "a brand new long password"
        response = portal.app.test_client().post("/api/auth/reset-password",
                                                 json={"token": token, "password": new_password})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([tab.is_connected() for tab in tabs], [False, False])
        self.assertTrue(blake.is_connected())
        self.assertFalse(self.socket(self.clients[0]).is_connected())  # the old cookie cannot reconnect
        fresh = portal.app.test_client()
        fresh.post("/api/auth/login", json={"email": "alice@example.edu", "password": new_password})
        self.assertTrue(self.socket(fresh).is_connected())

    def test_failed_reset_disconnects_nobody(self):
        alice = self.socket(self.clients[0])
        self.reset_token()
        response = portal.app.test_client().post("/api/auth/reset-password",
                                                 json={"token": "not-a-real-token", "password": "a brand new long password"})
        self.assertEqual(response.status_code, 400)
        self.assertTrue(alice.is_connected())

    def test_reset_during_connect_cannot_leave_a_stale_socket(self):
        real = core_realtime.session_student_id
        calls = []

        def reset_between_checks(db, session):
            result = real(db, session)
            calls.append(result)
            if len(calls) == 1:  # the reset commits right after the first check passes
                with portal.get_db() as other:
                    other.execute("UPDATE students SET session_version = session_version + 1 WHERE id = %s",
                                  (self.ids[0],))
            return result

        with patch("core.realtime.session_student_id", side_effect=reset_between_checks):
            sock = self.socket(self.clients[0])
        self.assertEqual(calls, [self.ids[0], None])
        self.assertFalse(sock.is_connected())
        room = list(socketio.server.manager.get_participants("/", user_room(self.ids[0])))
        self.assertEqual(room, [])


if __name__ == "__main__":
    unittest.main()
