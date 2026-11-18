"""Server push events: right recipients, only after commit, never across blocks."""

import unittest
from datetime import datetime, timedelta, timezone

import psycopg

import app as portal
from core.realtime import publish, socketio
from features.lifecycle import notify
from tests.postgres_test_support import PostgresTestCase, sign_in


class RealtimeEventTests(PostgresTestCase):
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
            self.assertTrue(sock.is_connected())
            self.addCleanup(lambda s=sock: s.is_connected() and s.disconnect())
            self.clients.append(client)
            self.sockets.append(sock)
        self.alice, self.bob, self.carol = self.clients

    def events(self, index):
        return [(event["name"], event["args"][0]) for event in self.sockets[index].get_received()]

    def drain(self):
        for sock in self.sockets:
            sock.get_received()

    def request(self, accepted=False):
        response = self.alice.post("/api/requests", json={
            "recipient_id": self.ids[1], "course_code": "CSC 510",
            "advice_topic": "Projects", "message": "Help please"})
        self.assertEqual(response.status_code, 201, response.get_json())
        request_id = response.get_json()["request"]["id"]
        if accepted:
            self.assertEqual(self.bob.patch(f"/api/requests/{request_id}", json={"status": "accepted"}).status_code, 200)
        self.drain()
        return request_id

    def test_new_request_and_decision_reach_both_participants_only(self):
        response = self.alice.post("/api/requests", json={
            "recipient_id": self.ids[1], "course_code": "CSC 510",
            "advice_topic": "Projects", "message": "Help please"})
        request_id = response.get_json()["request"]["id"]
        self.assertEqual(self.events(0), [("request", {"request_id": request_id})])
        self.assertCountEqual(self.events(1), [("notifications", {}), ("request", {"request_id": request_id})])
        self.assertEqual(self.events(2), [])
        self.bob.patch(f"/api/requests/{request_id}", json={"status": "accepted"})
        self.assertCountEqual(self.events(0), [("notifications", {}), ("request", {"request_id": request_id})])
        self.assertEqual(self.events(1), [("request", {"request_id": request_id})])
        self.assertEqual(self.events(2), [])
        # A repeated decision changes nothing, so nothing is pushed.
        self.bob.patch(f"/api/requests/{request_id}", json={"status": "accepted"})
        self.assertEqual(self.events(0) + self.events(1), [])

    def test_message_push_matches_rest_payload_and_skips_outsiders(self):
        request_id = self.request(accepted=True)
        sent = self.alice.post(f"/api/requests/{request_id}/messages", json={"body": " Hi Bob "})
        self.assertEqual(sent.status_code, 201)
        rest_row = self.bob.get(f"/api/requests/{request_id}/messages").get_json()["messages"][0]
        expected = ("chat_message", {"request_id": request_id, "message": rest_row})
        self.assertIn(expected, self.events(0))  # sender's other tabs
        self.assertCountEqual(self.events(1), [expected, ("notifications", {})])
        self.assertEqual(self.events(2), [])

    def test_rejected_message_pushes_nothing(self):
        request_id = self.request(accepted=True)
        self.assertEqual(self.alice.post(f"/api/requests/{request_id}/messages", json={"body": " "}).status_code, 400)
        self.assertEqual(self.carol.post(f"/api/requests/{request_id}/messages", json={"body": "x"}).status_code, 404)
        self.assertEqual(self.events(0) + self.events(1) + self.events(2), [])

    def test_events_wait_for_commit_and_are_dropped_on_rollback(self):
        seen = []
        with portal.get_db() as db:
            db.execute("UPDATE students SET bio='committed' WHERE id=%s", (self.ids[0],))

            def check_visible():
                # A fresh connection only sees the row if the transaction committed.
                with psycopg.connect(portal.app.config["SUPABASE_DB_URL"]) as other:
                    other.execute(f'SET search_path TO "{portal.app.config["TEST_DB_SCHEMA"]}"')
                    seen.append(other.execute("SELECT bio FROM students WHERE id=%s", (self.ids[0],)).fetchone()[0])

            db.after_commit.append(check_visible)
            self.assertEqual(seen, [])
        self.assertEqual(seen, ["committed"])
        with self.assertRaises(RuntimeError):
            with portal.get_db() as db:
                publish(db, [self.ids[1]], "request", {"request_id": 1})
                raise RuntimeError("roll back")
        self.assertEqual(self.events(1), [])

    def test_pooled_connections_do_not_carry_callbacks(self):
        with portal.get_db() as db:
            first = db
            publish(db, [self.ids[0]], "probe", {})
        self.assertIsNone(first.after_commit)
        with portal.get_db() as db:
            self.assertEqual(db.after_commit, [])

    def test_empty_recipient_list_never_broadcasts(self):
        with portal.get_db() as db:
            publish(db, [], "probe", {})
            publish(db, [None], "probe", {})
            self.assertEqual(db.after_commit, [])
        self.assertEqual(self.events(0) + self.events(1) + self.events(2), [])

    def test_blocked_pair_gets_no_events_from_each_other(self):
        request_id = self.request(accepted=True)
        self.assertEqual(self.bob.post(f"/api/students/{self.ids[0]}/block").status_code, 200)
        self.assertCountEqual(self.events(1), [("request", {"request_id": request_id}),
                                               ("meeting", {"request_id": request_id})])
        self.assertEqual(self.events(0), [])
        with portal.get_db() as db:  # e.g. a late meeting cancellation by the blocked student
            notify(db, self.ids[1], self.ids[0], request_id, "meeting", "meeting:late:cancelled")
            stored = db.execute("SELECT 1 FROM notifications WHERE event_key='meeting:late:cancelled'").fetchone()
        self.assertIsNone(stored)
        self.assertEqual(self.events(1), [])

    def test_meeting_changes_reach_both_participants(self):
        request_id = self.request(accepted=True)
        start = datetime.now(timezone.utc) + timedelta(days=1)
        created = self.alice.post(f"/api/requests/{request_id}/meetings", json={
            "starts_at": start.isoformat(), "ends_at": (start + timedelta(minutes=30)).isoformat(),
            "location": "Library"})
        self.assertEqual(created.status_code, 201)
        meeting = ("meeting", {"request_id": request_id})
        self.assertEqual(self.events(0), [meeting])
        self.assertCountEqual(self.events(1), [meeting, ("notifications", {})])
        self.bob.patch(f"/api/requests/{request_id}/meetings/{created.get_json()['meeting']['id']}",
                       json={"status": "accepted"})
        self.assertCountEqual(self.events(0), [meeting, ("notifications", {})])
        self.assertEqual(self.events(1), [meeting])
        self.assertEqual(self.events(2), [])

    def test_completion_and_cancellation_push_request_events(self):
        request_id = self.request(accepted=True)
        self.alice.patch(f"/api/requests/{request_id}", json={"status": "completed"})
        both = [("request", {"request_id": request_id}), ("meeting", {"request_id": request_id})]
        self.assertCountEqual(self.events(0), both)
        self.assertCountEqual(self.events(1), both)
        self.alice.patch(f"/api/requests/{request_id}", json={"status": "completed"})  # idempotent
        self.assertEqual(self.events(0) + self.events(1), [])
        self.carol.post("/api/requests", json={"recipient_id": self.ids[1], "course_code": "CSC 510",
                                               "advice_topic": "Tips", "message": "Hello"})
        pending = self.bob.get("/api/requests").get_json()["requests"][0]["id"]
        self.drain()
        self.carol.patch(f"/api/requests/{pending}", json={"status": "cancelled"})
        self.assertEqual(self.events(2), [("request", {"request_id": pending})])
        self.assertCountEqual(self.events(1), [("request", {"request_id": pending}), ("notifications", {})])
        self.assertEqual(self.events(0), [])

    def test_expiration_pushes_to_both_participants(self):
        request_id = self.request()
        with portal.get_db() as db:
            db.execute("UPDATE advice_requests SET expires_at = now() - interval '1 minute' WHERE id=%s", (request_id,))
        self.alice.get("/api/requests")
        for index in (0, 1):
            self.assertCountEqual(self.events(index), [("request", {"request_id": request_id}), ("notifications", {})])
        self.assertEqual(self.events(2), [])

    def test_reading_notifications_syncs_only_own_tabs(self):
        self.request()
        notification = self.bob.get("/api/notifications").get_json()["notifications"][0]["id"]
        self.bob.post(f"/api/notifications/{notification}/read")
        self.assertEqual(self.events(1), [("notifications", {})])
        self.bob.post("/api/notifications/read", json={"through_id": notification})
        self.assertEqual(self.events(1), [("notifications", {})])
        self.assertEqual(self.events(0) + self.events(2), [])


if __name__ == "__main__":
    unittest.main()
