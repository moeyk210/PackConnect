"""Read positions: participant-only, monotonic, capped to real messages, pushed live."""

import unittest

import app as portal
from core.realtime import socketio
from tests.postgres_test_support import PostgresTestCase, sign_in


class ReadReceiptTests(PostgresTestCase):
    def setUp(self):
        super().setUp()
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
        self.sent = [self.alice.post(f"/api/requests/{self.request_id}/messages", json={"body": body})
                     .get_json()["message"]["id"] for body in ("one", "two")]
        self.drain()

    def drain(self):
        for sock in self.sockets:
            sock.get_received()

    def reads(self, index):
        return [event["args"][0] for event in self.sockets[index].get_received() if event["name"] == "read"]

    def read(self, client, through_id):
        return client.post(f"/api/requests/{self.request_id}/read", json={"through_id": through_id})

    def unread(self, client):
        return [c["unread_count"] for c in client.get("/api/conversations").get_json()["conversations"]]

    def test_marking_read_clears_unread_and_tells_both_participants(self):
        self.assertEqual(self.unread(self.bob), [2])
        response = self.read(self.bob, self.sent[1])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"last_read_id": self.sent[1]})
        self.assertEqual(self.unread(self.bob), [0])
        expected = [{"request_id": self.request_id, "reader_id": self.ids[1], "last_read_id": self.sent[1]}]
        self.assertEqual(self.reads(0), expected)  # Alice sees "Seen"
        self.assertEqual(self.reads(1), expected)  # Bob's other tabs update unread counts
        self.assertEqual(self.reads(2), [])

    def test_read_position_only_moves_forward_and_repeats_are_silent(self):
        self.read(self.bob, self.sent[1])
        self.drain()
        self.assertEqual(self.read(self.bob, self.sent[0]).get_json(), {"last_read_id": self.sent[1]})
        self.assertEqual(self.read(self.bob, self.sent[1]).get_json(), {"last_read_id": self.sent[1]})
        self.assertEqual(self.reads(0) + self.reads(1), [])

    def test_read_is_capped_to_messages_in_this_conversation(self):
        response = self.read(self.bob, 9_000_000)
        self.assertEqual(response.get_json(), {"last_read_id": self.sent[1]})
        self.drain()
        later = self.alice.post(f"/api/requests/{self.request_id}/messages", json={"body": "three"})
        self.assertEqual(self.unread(self.bob), [1])  # the later message is still unread
        self.assertGreater(later.get_json()["message"]["id"], self.sent[1])

    def test_validation_and_access(self):
        for body in (None, {}, {"through_id": "5"}, {"through_id": True}, {"through_id": 0}, {"through_id": -1}):
            with self.subTest(body=body):
                response = self.bob.post(f"/api/requests/{self.request_id}/read", json=body)
                self.assertEqual(response.status_code, 400)
        self.assertEqual(self.read(self.carol, self.sent[1]).status_code, 404)
        self.assertEqual(portal.app.test_client().post(
            f"/api/requests/{self.request_id}/read", json={"through_id": 1}).status_code, 401)
        pending = self.carol.post("/api/requests", json={
            "recipient_id": self.ids[1], "course_code": "CSC 510", "advice_topic": "Tips", "message": "Hi"})
        pending_id = pending.get_json()["request"]["id"]
        self.assertEqual(self.bob.post(f"/api/requests/{pending_id}/read", json={"through_id": 1}).status_code, 403)
        self.assertEqual(self.reads(0) + self.reads(2), [])

    def test_history_reports_the_peers_read_position_and_get_pushes_receipts(self):
        page = self.alice.get(f"/api/requests/{self.request_id}/messages").get_json()
        self.assertEqual(page["peer_last_read_id"], 0)
        self.bob.get(f"/api/requests/{self.request_id}/messages")  # opening the chat reads it
        self.assertEqual(self.reads(0)[-1]["last_read_id"], self.sent[1])
        page = self.alice.get(f"/api/requests/{self.request_id}/messages").get_json()
        self.assertEqual(page["peer_last_read_id"], self.sent[1])
        self.drain()
        self.bob.get(f"/api/requests/{self.request_id}/messages?after_id={self.sent[1]}")
        self.assertEqual(self.reads(0), [])  # nothing new was read

    def test_blocked_pair_does_not_learn_read_positions(self):
        self.bob.post(f"/api/students/{self.ids[0]}/block")
        self.drain()
        self.read(self.bob, self.sent[1])
        self.assertEqual(self.reads(0), [])
        self.assertEqual(len(self.reads(1)), 1)


if __name__ == "__main__":
    unittest.main()
