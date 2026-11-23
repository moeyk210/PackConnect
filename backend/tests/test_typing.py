"""Typing signals reach only the other participant of an active, unblocked chat."""

import unittest
from unittest.mock import patch

import app as portal
import features.typing as typing_module
from core.realtime import socketio
from tests.postgres_test_support import PostgresTestCase, sign_in


class TypingTests(PostgresTestCase):
    def setUp(self):
        super().setUp()
        typing_module._last_relay.clear()
        self.addCleanup(typing_module._last_relay.clear)
        self.clock = [1000.0]
        self.enterContext(patch("features.typing.time.monotonic", lambda: self.clock[0]))
        hashed = portal.generate_password_hash("a long test password")
        self.ids, self.clients, self.sockets = [], [], []
        with portal.get_db() as db:
            for name in ("Alice", "Bob", "Carol"):
                student = db.execute(
                    "INSERT INTO students(name,program,year,willing_to_advise) VALUES(%s,'CS','1',true) RETURNING id",
                    (name,)).fetchone()["id"]
                db.execute("INSERT INTO accounts(student_id,email,password_hash) VALUES(%s,%s,%s)",
                           (student, name.lower() + "@example.test", hashed))
                self.ids.append(student)
        for student in self.ids:
            client = portal.app.test_client()
            sign_in(client, student)
            sock = socketio.test_client(portal.app, flask_test_client=client)
            self.addCleanup(lambda s=sock: s.is_connected() and s.disconnect())
            self.clients.append(client)
            self.sockets.append(sock)
        self.alice, self.bob, self.carol = self.clients
        response = self.alice.post("/api/requests", json={
            "recipient_id": self.ids[1], "course_code": "CSC 510", "advice_topic": "Projects",
            "message": "Help please"})
        self.request_id = response.get_json()["request"]["id"]
        self.bob.patch(f"/api/requests/{self.request_id}", json={"status": "accepted"})
        self.drain()

    def drain(self):
        for sock in self.sockets:
            sock.get_received()

    def typing(self, index):
        return [e["args"][0] for e in self.sockets[index].get_received() if e["name"] == "typing"]

    def type_as(self, index, payload=None):
        self.sockets[index].emit("typing", payload if payload is not None else {"request_id": self.request_id})
        self.clock[0] += 5  # past the relay interval

    def test_relays_only_to_the_other_participant(self):
        self.type_as(0)
        self.assertEqual(self.typing(1), [{"request_id": self.request_id, "user_id": self.ids[0]}])
        self.assertEqual(self.typing(0) + self.typing(2), [])
        self.type_as(1)
        self.assertEqual(self.typing(0), [{"request_id": self.request_id, "user_id": self.ids[1]}])

    def test_outsiders_and_bad_payloads_relay_nothing(self):
        self.type_as(2)
        for payload in ({}, {"request_id": "1"}, {"request_id": True}, {"request_id": 0}, ["x"], "x"):
            self.type_as(0, payload)
        self.type_as(0, {"request_id": 999999})
        self.assertEqual(self.typing(0) + self.typing(1) + self.typing(2), [])

    def test_only_accepted_unblocked_chats_relay(self):
        pending = self.carol.post("/api/requests", json={
            "recipient_id": self.ids[1], "course_code": "CSC 510", "advice_topic": "Tips", "message": "Hi"})
        self.type_as(2, {"request_id": pending.get_json()["request"]["id"]})
        self.assertEqual(self.typing(1), [])
        self.alice.patch(f"/api/requests/{self.request_id}", json={"status": "completed"})
        self.drain()
        self.type_as(0)
        self.assertEqual(self.typing(1), [])

    def test_blocked_pair_cannot_signal(self):
        with portal.get_db() as db:  # a block without closing, to isolate the check
            db.execute("INSERT INTO student_blocks(blocker_id,blocked_id) VALUES(%s,%s)", (self.ids[1], self.ids[0]))
        self.type_as(0)
        self.type_as(1)
        self.assertEqual(self.typing(0) + self.typing(1), [])

    def test_relay_is_rate_limited_per_tab(self):
        for _ in range(5):
            self.sockets[0].emit("typing", {"request_id": self.request_id})
        self.assertEqual(len(self.typing(1)), 1)
        self.clock[0] += typing_module.RELAY_INTERVAL_SECONDS
        self.sockets[0].emit("typing", {"request_id": self.request_id})
        self.assertEqual(len(self.typing(1)), 1)

    def test_invalidated_session_cannot_signal(self):
        with portal.get_db() as db:
            db.execute("UPDATE students SET session_version = session_version + 1 WHERE id = %s", (self.ids[0],))
        self.type_as(0)
        self.assertEqual(self.typing(1), [])


if __name__ == "__main__":
    unittest.main()
