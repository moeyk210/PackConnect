"""Feedback API: who may rate an advice connection, and what they get back."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import app as portal
from tests.postgres_test_support import PostgresTestCase


class FeedbackApiTestCase(PostgresTestCase):
    """Shared setup: an asker, an advisor, an outsider, and one accepted request
    in which both participants have sent a message."""

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

    def create_request(self, db, status, sender="asker", recipient="advisor", messages=True):
        request_id = db.execute("""
            INSERT INTO advice_requests (sender_id, recipient_id, course_code, advice_topic, message, status)
            VALUES (%s, %s, 'CSC 510', 'Projects', 'Can you help?', %s) RETURNING id
        """, (self.ids[sender], self.ids[recipient], status)).fetchone()["id"]
        if messages:
            for author in (sender, recipient):
                self.send_message(db, request_id, author)
        return request_id

    def send_message(self, db, request_id, author):
        db.execute("INSERT INTO chat_messages (request_id, sender_id, body) VALUES (%s, %s, 'Hello')",
                   (request_id, self.ids[author]))

    def fetch(self, who="asker", request_id=None):
        return self.clients[who].get(f"/api/requests/{request_id or self.request_id}/feedback")

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


class FeedbackValidationTests(FeedbackApiTestCase):
    def assert_rejected(self, response, message_part):
        self.assertEqual(response.status_code, 400)
        self.assertIn(message_part, response.get_json()["error"])

    def test_rating_boundaries_one_and_ten_are_accepted(self):
        for rating in (1, 10):
            with self.subTest(rating=rating):
                with portal.get_db() as db:
                    db.execute("DELETE FROM advice_feedback")
                self.assertEqual(self.submit(rating=rating).status_code, 201)

    def test_invalid_ratings_get_400(self):
        for rating in (0, 11, -1, 7.5, "8", None, True, False, [8]):
            with self.subTest(rating=rating):
                self.assert_rejected(self.submit(rating=rating), "Rating")
        self.assertEqual(self.stored_feedback(), [])

    def test_missing_rating_gets_400(self):
        response = self.clients["asker"].post(f"/api/requests/{self.request_id}/feedback", json={"helpful": True})
        self.assert_rejected(response, "Rating")

    def test_helpful_must_be_true_or_false(self):
        for helpful in (None, "yes", 1, 0):
            with self.subTest(helpful=helpful):
                self.assert_rejected(self.submit(helpful=helpful), "helpful")

    def test_helpful_false_is_stored(self):
        response = self.submit(helpful=False, rating=3)
        self.assertEqual(response.status_code, 201)
        self.assertIs(response.get_json()["feedback"]["helpful"], False)

    def test_comment_must_be_text_of_at_most_500_characters(self):
        self.assert_rejected(self.submit(comment=42), "Comment")
        self.assert_rejected(self.submit(comment="x" * 501), "500")
        self.assertEqual(self.submit(comment="x" * 500).status_code, 201)

    def test_comment_whitespace_is_trimmed(self):
        response = self.submit(comment="   Helpful tips.  \n")
        self.assertEqual(response.get_json()["feedback"]["comment"], "Helpful tips.")

    def test_non_object_body_gets_400(self):
        for body in ([8, True], "great", 8):
            with self.subTest(body=body):
                response = self.clients["asker"].post(f"/api/requests/{self.request_id}/feedback", json=body)
                self.assert_rejected(response, "JSON object")
        response = self.clients["asker"].post(f"/api/requests/{self.request_id}/feedback",
                                              data="not json", content_type="text/plain")
        self.assert_rejected(response, "JSON object")

    def test_access_checks_run_before_validation(self):
        # A bad body must not reveal whether an outsider's target request exists.
        self.assertEqual(self.submit("outsider", rating=99).status_code, 404)


class FeedbackDuplicateTests(FeedbackApiTestCase):
    def test_second_submission_gets_409_and_keeps_the_first(self):
        self.assertEqual(self.submit(rating=9).status_code, 201)
        response = self.submit(rating=2, helpful=False)
        self.assertEqual(response.status_code, 409)
        self.assertIn("already", response.get_json()["error"])
        [row] = self.stored_feedback()
        self.assertEqual((row["rating"], row["helpful"]), (9, True))

    def test_each_participant_still_gets_one_submission(self):
        self.assertEqual(self.submit("asker").status_code, 201)
        self.assertEqual(self.submit("advisor").status_code, 201)
        self.assertEqual(self.submit("advisor").status_code, 409)
        self.assertEqual(len(self.stored_feedback()), 2)

    def test_rejected_submission_does_not_use_up_the_one_attempt(self):
        self.assertEqual(self.submit(rating=0).status_code, 400)
        self.assertEqual(self.submit(rating=7).status_code, 201)

    def test_new_request_with_same_advisor_can_be_rated_again(self):
        self.assertEqual(self.submit().status_code, 201)
        with portal.get_db() as db:
            db.execute("UPDATE advice_requests SET status = 'completed' WHERE id = %s", (self.request_id,))
            second = self.create_request(db, "accepted")
        self.assertEqual(self.submit(request_id=second).status_code, 201)

    def test_simultaneous_submissions_store_exactly_one(self):
        clients = []
        for _ in range(2):
            client = portal.app.test_client()
            with client.session_transaction() as session:
                session["student_id"] = self.ids["asker"]
            clients.append(client)
        barrier = Barrier(2)

        def send(client):
            barrier.wait(timeout=5)
            return client.post(f"/api/requests/{self.request_id}/feedback",
                               json={"rating": 8, "helpful": True}).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(send, clients))
        self.assertEqual(sorted(results), [201, 409])
        self.assertEqual(len(self.stored_feedback()), 1)


class FeedbackMessageRuleTests(FeedbackApiTestCase):
    def fresh_request(self, *authors):
        with portal.get_db() as db:
            # Only one active request per pair is allowed, so finish earlier ones first.
            db.execute("UPDATE advice_requests SET status = 'completed' WHERE status IN ('pending', 'accepted')")
            request_id = self.create_request(db, "accepted", messages=False)
            for author in authors:
                self.send_message(db, request_id, author)
        return request_id

    def test_no_messages_gets_403(self):
        response = self.submit(request_id=self.fresh_request())
        self.assertEqual(response.status_code, 403)
        self.assertIn("both sent a message", response.get_json()["error"])

    def test_only_one_side_messaging_gets_403_for_either_person(self):
        for author in ("asker", "advisor"):
            with self.subTest(author=author):
                request_id = self.fresh_request(author, author)
                self.assertEqual(self.submit("asker", request_id=request_id).status_code, 403)
                self.assertEqual(self.submit("advisor", request_id=request_id).status_code, 403)
        self.assertEqual(self.stored_feedback(), [])

    def test_rating_opens_once_both_have_messaged(self):
        request_id = self.fresh_request("asker", "advisor")
        self.assertEqual(self.submit(request_id=request_id).status_code, 201)


class FeedbackReadTests(FeedbackApiTestCase):
    def test_signed_out_user_gets_401(self):
        response = portal.app.test_client().get(f"/api/requests/{self.request_id}/feedback")
        self.assertEqual(response.status_code, 401)

    def test_non_participant_and_missing_request_get_404(self):
        self.assertEqual(self.fetch("outsider").status_code, 404)
        self.assertEqual(self.fetch(request_id=999999).status_code, 404)

    def test_before_rating_returns_no_feedback_and_can_rate(self):
        response = self.fetch()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"feedback": None, "can_rate": True})

    def test_after_rating_returns_own_feedback_and_cannot_rate(self):
        self.submit(rating=6, helpful=False, comment="Okay.")
        body = self.fetch().get_json()
        self.assertFalse(body["can_rate"])
        feedback = body["feedback"]
        self.assertEqual((feedback["rating"], feedback["helpful"], feedback["comment"]), (6, False, "Okay."))
        self.assertNotIn("rater_id", feedback)

    def test_other_participants_feedback_is_never_returned(self):
        self.submit("advisor", rating=3, comment="Private to the advisor.")
        self.assertEqual(self.fetch("asker").get_json(), {"feedback": None, "can_rate": True})

    def test_cannot_rate_before_both_have_messaged(self):
        with portal.get_db() as db:
            db.execute("DELETE FROM chat_messages WHERE sender_id = %s", (self.ids["advisor"],))
        self.assertFalse(self.fetch().get_json()["can_rate"])

    def test_closed_request_cannot_be_rated_but_existing_feedback_stays_visible(self):
        self.submit(rating=9)
        with portal.get_db() as db:
            db.execute("UPDATE advice_requests SET status = 'closed' WHERE id = %s", (self.request_id,))
        body = self.fetch().get_json()
        self.assertFalse(body["can_rate"])
        self.assertEqual(body["feedback"]["rating"], 9)
        with portal.get_db() as db:
            db.execute("DELETE FROM advice_feedback")
        self.assertEqual(self.fetch().get_json(), {"feedback": None, "can_rate": False})
