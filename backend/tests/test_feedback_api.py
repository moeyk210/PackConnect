"""Feedback API: who may rate an advice connection, and what they get back."""

import app as portal
from tests.postgres_test_support import PostgresTestCase


class FeedbackApiTestCase(PostgresTestCase):
    """Shared setup: an asker, an advisor, an outsider, and one accepted request."""

    def setUp(self):
        super().setUp()
        self.ids = {}
        self.clients = {}
        with portal.get_db() as db:
            for name in ("asker", "advisor", "outsider"):
                student_id = db.execute("""INSERT INTO students (name, program, year, willing_to_advise)
                    VALUES (%s, 'CS', '1', true) RETURNING id""", (name.title(),)).fetchone()["id"]
                db.execute("INSERT INTO accounts (student_id, email, password_hash) VALUES (%s, %s, 'unused')",
                           (student_id, f"{name}@example.test"))
                self.ids[name] = student_id
            self.request_id = self.create_request(db, "accepted")
        for name, student_id in self.ids.items():
            client = portal.app.test_client()
            with client.session_transaction() as session:
                session["student_id"] = student_id
            self.clients[name] = client

    def create_request(self, db, status, sender="asker", recipient="advisor"):
        return db.execute("""
            INSERT INTO advice_requests (sender_id, recipient_id, course_code, advice_topic, message, status)
            VALUES (%s, %s, 'CSC 510', 'Projects', 'Can you help?', %s) RETURNING id
        """, (self.ids[sender], self.ids[recipient], status)).fetchone()["id"]

    def submit(self, who="asker", request_id=None, **fields):
        body = {"rating": 8, "helpful": True, "comment": "Clear and kind.", **fields}
        return self.clients[who].post(f"/api/requests/{request_id or self.request_id}/feedback", json=body)

    def stored_feedback(self):
        with portal.get_db() as db:
            return db.execute("SELECT * FROM advice_feedback ORDER BY id").fetchall()


class FeedbackAccessTests(FeedbackApiTestCase):
    def test_signed_out_user_gets_401(self):
        response = portal.app.test_client().post(f"/api/requests/{self.request_id}/feedback",
                                                 json={"rating": 8, "helpful": True})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.stored_feedback(), [])

    def test_non_participant_gets_404(self):
        response = self.submit("outsider")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.stored_feedback(), [])

    def test_missing_request_gets_404(self):
        self.assertEqual(self.submit(request_id=999999).status_code, 404)

    def test_asker_can_rate_the_advisor(self):
        response = self.submit(rating=9, helpful=True, comment="Very useful.")
        self.assertEqual(response.status_code, 201)
        feedback = response.get_json()["feedback"]
        self.assertEqual((feedback["request_id"], feedback["rating"], feedback["helpful"], feedback["comment"]),
                         (self.request_id, 9, True, "Very useful."))
        [row] = self.stored_feedback()
        self.assertEqual(row["rater_id"], self.ids["asker"])

    def test_advisor_can_rate_too(self):
        self.assertEqual(self.submit("advisor").status_code, 201)
        self.assertEqual([row["rater_id"] for row in self.stored_feedback()], [self.ids["advisor"]])

    def test_rater_identity_comes_from_the_session(self):
        response = self.submit(rater_id=self.ids["advisor"])
        self.assertEqual(response.status_code, 201)
        self.assertNotIn("rater_id", response.get_json()["feedback"])
        self.assertEqual(self.stored_feedback()[0]["rater_id"], self.ids["asker"])

    def test_comment_is_optional(self):
        response = self.submit(comment=None)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["feedback"]["comment"], "")


class FeedbackStatusTests(FeedbackApiTestCase):
    def request_with_status(self, status):
        # Reuse the shared request; only one active request per pair is allowed.
        with portal.get_db() as db:
            db.execute("UPDATE advice_requests SET status = %s WHERE id = %s", (status, self.request_id))
        return self.request_id

    def test_accepted_and_completed_requests_can_be_rated(self):
        for status in ("accepted", "completed"):
            with self.subTest(status=status):
                self.request_with_status(status)
                with portal.get_db() as db:
                    db.execute("DELETE FROM advice_feedback")
                self.assertEqual(self.submit().status_code, 201)

    def test_other_statuses_get_403_and_store_nothing(self):
        for status in ("pending", "declined", "cancelled", "expired", "closed"):
            with self.subTest(status=status):
                self.request_with_status(status)
                response = self.submit()
                self.assertEqual(response.status_code, 403)
                self.assertIn("accepted", response.get_json()["error"])
        self.assertEqual(self.stored_feedback(), [])

    def test_status_check_applies_to_the_advisor_too(self):
        self.request_with_status("pending")
        self.assertEqual(self.submit("advisor").status_code, 403)

    def test_outsider_gets_404_not_403_for_unrated_statuses(self):
        # The status of someone else's request must not leak through the error code.
        self.request_with_status("pending")
        self.assertEqual(self.submit("outsider").status_code, 404)
