import unittest
from unittest.mock import patch

from psycopg import OperationalError

import app as portal
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


if __name__ == "__main__":
    unittest.main()
