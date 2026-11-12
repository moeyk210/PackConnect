"""Advisor reputation stats, computed from fixed fixture data with known answers.

Fixture for the "busy" advisor (each row is one request to them):

    sender    status            asker's rating   advisor's rating
    s1        accepted          9, helpful       -
    s2        completed         6, not helpful   3 (must be ignored)
    s2        completed         10, helpful      -
    s3        completed         4, helpful       -
    s4        declined          -                -
    s5        expired           -                -
    s6        pending, overdue  -                -
    s7        pending, fresh    -                -
    s8        cancelled         -                -
    s9        closed (blocked)  -                -

Expected:
    rating_count     = 4                        (asker ratings only)
    average_rating   = (9 + 6 + 10 + 4) / 4     = 7.25, rounded to 7.3
    helpful_percent  = 3 of 4                   = 75
    students_helped  = s1, s2, s3               = 3
    response_rate    = answered 5 (accepted, 3 completed, declined)
                       / (5 + unanswered 2: expired, overdue pending)
                       = 71.4%, rounded to 71
"""

import json
from datetime import datetime, timedelta, timezone

import app as portal
from tests.postgres_test_support import PostgresTestCase

EMPTY = {"average_rating": None, "rating_count": 0, "helpful_percent": None,
         "students_helped": 0, "response_rate": None}
SECRET_COMMENT = "Private remark that must never appear in reputation."


class ReputationTestCase(PostgresTestCase):
    def setUp(self):
        super().setUp()
        self.ids = {}
        with portal.get_db() as db:
            for name in ("busy", "single", "quiet", *(f"s{n}" for n in range(1, 10))):
                self.ids[name] = self.student(db, name)
            busy = [
                ("s1", "accepted", (9, True), None),
                ("s2", "completed", (6, False), 3),
                ("s2", "completed", (10, True), None),
                ("s3", "completed", (4, True), None),
                ("s4", "declined", None, None),
                ("s5", "expired", None, None),
                ("s6", "pending", None, None),
                ("s7", "pending", None, None),
                ("s8", "cancelled", None, None),
                ("s9", "closed", None, None),
            ]
            for sender, status, asker_rating, advisor_rating in busy:
                overdue = sender == "s6"
                request_id = self.request(db, sender, "busy", status, overdue=overdue)
                if asker_rating:
                    self.feedback(db, request_id, sender, *asker_rating)
                if advisor_rating:
                    self.feedback(db, request_id, "busy", advisor_rating, False)
            # One rating for "single", from s1, plus feedback "single" gave as an asker.
            request_id = self.request(db, "s1", "single", "completed")
            self.feedback(db, request_id, "s1", 7, True)
            request_id = self.request(db, "single", "quiet", "completed")
            self.feedback(db, request_id, "single", 2, False)

    def student(self, db, name):
        student_id = db.execute("""INSERT INTO students (name, program, year, willing_to_advise, max_open_requests)
            VALUES (%s, 'CS', '1', true, NULL) RETURNING id""", (name.title(),)).fetchone()["id"]
        db.execute("INSERT INTO accounts (student_id, email, password_hash) VALUES (%s, %s, 'unused')",
                   (student_id, f"{name}@example.test"))
        db.execute("INSERT INTO completed_courses (student_id, course_code) VALUES (%s, 'CSC 510')", (student_id,))
        return student_id

    def request(self, db, sender, recipient, status, overdue=False):
        expires = datetime.now(timezone.utc) + timedelta(days=-1 if overdue else 7)
        return db.execute("""
            INSERT INTO advice_requests (sender_id, recipient_id, course_code, advice_topic, message, status, expires_at)
            VALUES (%s, %s, 'CSC 510', 'Projects', 'Can you help?', %s, %s) RETURNING id
        """, (self.ids[sender], self.ids[recipient], status, expires)).fetchone()["id"]

    def feedback(self, db, request_id, rater, rating, helpful):
        db.execute("""INSERT INTO advice_feedback (request_id, rater_id, rating, helpful, comment)
            VALUES (%s, %s, %s, %s, %s)""", (request_id, self.ids[rater], rating, helpful, SECRET_COMMENT))

    def reputation(self, name):
        response = portal.app.test_client().get(f"/api/students/{self.ids[name]}/reputation")
        self.assertEqual(response.status_code, 200)
        return response.get_json()["reputation"]

    def search(self):
        response = portal.app.test_client().get("/api/students/search",
                                                query_string={"course": "CSC 510", "available": "false"})
        return {row["id"]: row for row in response.get_json()["students"]}

    def profile(self, name):
        return portal.app.test_client().get(f"/api/students/{self.ids[name]}").get_json()["student"]


class ReputationStatsTests(ReputationTestCase):
    def test_advisor_with_no_activity_has_empty_stats(self):
        self.assertEqual(self.reputation("s4"), EMPTY)

    def test_advisor_with_one_rating(self):
        self.assertEqual(self.reputation("single"), {
            "average_rating": 7.0, "rating_count": 1, "helpful_percent": 100,
            "students_helped": 1, "response_rate": 100,
        })

    def test_advisor_with_many_ratings_and_mixed_requests(self):
        self.assertEqual(self.reputation("busy"), {
            "average_rating": 7.3, "rating_count": 4, "helpful_percent": 75,
            "students_helped": 3, "response_rate": 71,
        })

    def test_advisor_ratings_of_askers_never_count_for_the_asker(self):
        # "single" rated "quiet" 2/10 as an asker; quiet is the advisor there, not single.
        self.assertEqual(self.reputation("quiet")["rating_count"], 1)
        self.assertEqual(self.reputation("quiet")["average_rating"], 2.0)
        self.assertEqual(self.reputation("single")["average_rating"], 7.0)

    def test_waiting_cancelled_and_closed_requests_do_not_affect_response_rate(self):
        # s5 has never received a request; give it only requests that are left out.
        with portal.get_db() as db:
            for sender, status in (("s1", "pending"), ("s2", "cancelled"), ("s3", "closed")):
                self.request(db, sender, "s5", status)
        reputation = self.reputation("s5")
        self.assertIsNone(reputation["response_rate"])
        self.assertEqual(reputation["students_helped"], 0)

    def test_unanswered_requests_lower_the_response_rate(self):
        with portal.get_db() as db:
            self.request(db, "s1", "s5", "declined")
            self.request(db, "s2", "s5", "expired")
            self.request(db, "s3", "s5", "pending", overdue=True)
            self.request(db, "s4", "s5", "accepted")
        # Answered 2 (declined, accepted) of 4 with an answer due.
        self.assertEqual(self.reputation("s5")["response_rate"], 50)

    def test_missing_student_gets_404(self):
        response = portal.app.test_client().get("/api/students/999999/reputation")
        self.assertEqual(response.status_code, 404)


class ReputationPrivacyTests(ReputationTestCase):
    def assert_private(self, payload):
        text = json.dumps(payload)
        self.assertNotIn(SECRET_COMMENT, text)
        self.assertNotIn("comment", text)
        self.assertNotIn("rater", text)

    def test_reputation_contains_only_aggregate_fields(self):
        reputation = self.reputation("busy")
        self.assertEqual(set(reputation), set(EMPTY))
        self.assert_private(reputation)

    def test_search_and_profile_expose_no_feedback_details(self):
        self.assert_private(self.search())
        self.assert_private(self.profile("busy"))


class ReputationInResponsesTests(ReputationTestCase):
    def test_search_results_include_the_same_stats(self):
        results = self.search()
        for name in ("busy", "single", "s4"):
            with self.subTest(name=name):
                self.assertEqual(results[self.ids[name]]["reputation"], self.reputation(name))

    def test_search_still_returns_each_advisor_once_with_original_fields(self):
        response = portal.app.test_client().get("/api/students/search",
                                                query_string={"course": "CSC 510", "available": "false"})
        rows = response.get_json()["students"]
        ids = [row["id"] for row in rows]
        self.assertEqual(len(ids), len(set(ids)))
        busy = next(row for row in rows if row["id"] == self.ids["busy"])
        for field in ("name", "program", "availability_status", "accepting_requests", "open_request_count"):
            self.assertIn(field, busy)
        self.assertFalse(any(key.startswith("reputation_") for key in busy))

    def test_profile_includes_the_same_stats(self):
        profile = self.profile("busy")
        self.assertEqual(profile["reputation"], self.reputation("busy"))
        self.assertEqual(profile["completed_courses"], ["CSC 510"])
        self.assertFalse(any(key.startswith("reputation_") for key in profile))

    def test_profile_of_new_student_has_empty_stats(self):
        self.assertEqual(self.profile("s4")["reputation"], EMPTY)

    def test_stats_update_after_new_feedback(self):
        with portal.get_db() as db:
            request_id = db.execute("SELECT id FROM advice_requests WHERE sender_id = %s AND recipient_id = %s",
                                    (self.ids["s1"], self.ids["busy"])).fetchone()["id"]
            self.feedback(db, request_id, "busy", 1, False)  # advisor's own rating: no change
        self.assertEqual(self.reputation("busy")["rating_count"], 4)
        with portal.get_db() as db:
            request_id = self.request(db, "s4", "single", "completed")
            self.feedback(db, request_id, "s4", 4, False)
        self.assertEqual(self.reputation("single"), {
            "average_rating": 5.5, "rating_count": 2, "helpful_percent": 50,
            "students_helped": 2, "response_rate": 100,
        })
