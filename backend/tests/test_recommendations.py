"""'Recommended for you' rules, against fictional profiles in PostgreSQL."""

import app as portal
from tests.postgres_test_support import PostgresTestCase, sign_in


class RecommendationsTestCase(PostgresTestCase):
    """Ana is taking CSC 510 and CSC 540. Advisors are added per test."""

    def setUp(self):
        super().setUp()
        self.ids = {}
        with portal.get_db() as db:
            db.execute("DELETE FROM accounts")
            db.execute("DELETE FROM completed_courses")
            db.execute("DELETE FROM students")
            self.ids["Ana"] = self.student(db, "Ana", completed=[], willing=False)
            for course in ("CSC 510", "csc-540"):
                db.execute("INSERT INTO current_courses (student_id, course_code) VALUES (%s, %s)",
                           (self.ids["Ana"], course))
        self.client = portal.app.test_client()
        sign_in(self.client, self.ids["Ana"])

    def student(self, db, name, completed, willing=True, topics="Projects"):
        student_id = db.execute("""
            INSERT INTO students (name, program, year, advice_topics, willing_to_advise)
            VALUES (%s, 'MS Computer Science', 'Second Year', %s, %s) RETURNING id
        """, (name, topics, willing)).fetchone()["id"]
        db.execute("INSERT INTO accounts (student_id, email, password_hash) VALUES (%s, %s, 'unused')",
                   (student_id, f"{name.lower()}@example.test"))
        for course in completed:
            db.execute("INSERT INTO completed_courses (student_id, course_code) VALUES (%s, %s)", (student_id, course))
        return student_id

    def add_advisor(self, name, completed, **options):
        with portal.get_db() as db:
            self.ids[name] = self.student(db, name, completed, **options)

    def recommended(self, client=None):
        response = (client or self.client).get("/api/recommendations")
        self.assertEqual(response.status_code, 200, response.get_json())
        return [row["name"] for row in response.get_json()["students"]]


class RecommendationAccessTests(RecommendationsTestCase):
    def test_signed_out_visitors_get_401(self):
        response = portal.app.test_client().get("/api/recommendations")
        self.assertEqual(response.status_code, 401)

    def test_no_current_courses_gives_an_empty_list(self):
        self.add_advisor("Maya", ["CSC 510"])
        with portal.get_db() as db:
            db.execute("DELETE FROM current_courses WHERE student_id = %s", (self.ids["Ana"],))
        self.assertEqual(self.recommended(), [])


class RecommendationRankingTests(RecommendationsTestCase):
    def test_covering_more_current_courses_ranks_higher(self):
        self.add_advisor("Zoe", ["CSC 510"])
        self.add_advisor("Maya", ["CSC-510", "csc 540"])
        self.add_advisor("Kai", ["CSC 540"])
        self.assertEqual(self.recommended(), ["Maya", "Kai", "Zoe"])

    def test_advisors_who_took_none_of_the_current_courses_are_left_out(self):
        self.add_advisor("Ben", ["CSC 316"])
        self.add_advisor("Zoe", ["CSC 510"])
        self.assertEqual(self.recommended(), ["Zoe"])

    def test_the_student_is_never_recommended_to_themselves(self):
        with portal.get_db() as db:
            db.execute("UPDATE students SET willing_to_advise = true WHERE id = %s", (self.ids["Ana"],))
            db.execute("INSERT INTO completed_courses (student_id, course_code) VALUES (%s, 'CSC 510')",
                       (self.ids["Ana"],))
        self.add_advisor("Zoe", ["CSC 510"])
        self.assertEqual(self.recommended(), ["Zoe"])

    def test_advisors_not_taking_requests_are_left_out(self):
        self.add_advisor("Lee", ["CSC 510"])
        self.add_advisor("Dev", ["CSC 510"], willing=False)
        self.add_advisor("Zoe", ["CSC 510"])
        with portal.get_db() as db:
            db.execute("UPDATE students SET pause_until = CURRENT_DATE + 30 WHERE id = %s", (self.ids["Lee"],))
        self.assertEqual(self.recommended(), ["Zoe"])

    def test_blocked_advisors_are_left_out_in_both_directions(self):
        for name in ("Blocked", "Blocker", "Zoe"):
            self.add_advisor(name, ["CSC 510"])
        with portal.get_db() as db:
            db.execute("INSERT INTO student_blocks (blocker_id, blocked_id) VALUES (%s, %s), (%s, %s)",
                       (self.ids["Ana"], self.ids["Blocked"], self.ids["Blocker"], self.ids["Ana"]))
        self.assertEqual(self.recommended(), ["Zoe"])

    def test_results_carry_a_score_and_no_internal_fields(self):
        self.add_advisor("Zoe", ["CSC 510"])
        row = self.client.get("/api/recommendations").get_json()["students"][0]
        self.assertTrue(0 <= row["score"] <= 1)
        for internal in ("course_keys", "courses", "response_answered", "response_unanswered"):
            self.assertNotIn(internal, row)


class PastConnectionTests(RecommendationsTestCase):
    def request(self, sender, recipient, status, overdue=False):
        with portal.get_db() as db:
            db.execute("""
                INSERT INTO advice_requests (sender_id, recipient_id, course_code, advice_topic, message, status, expires_at)
                VALUES (%s, %s, 'CSC 510', 'Projects', 'Can you help?', %s,
                        CURRENT_TIMESTAMP + (CASE WHEN %s THEN interval '-1 day' ELSE interval '7 days' END))
            """, (self.ids[sender], self.ids[recipient], status, overdue))

    def test_history_hides_an_advisor_but_never_connecting_does_not(self):
        cases = {"pending": False, "accepted": False, "completed": False, "declined": False,
                 "cancelled": True, "expired": True}
        for status, still_recommended in cases.items():
            with self.subTest(status=status):
                name = f"Advisor {status}"
                self.add_advisor(name, ["CSC 510"])
                self.request("Ana", name, status)
                self.assertEqual(name in self.recommended(), still_recommended)

    def test_history_counts_whichever_student_sent_the_request(self):
        self.add_advisor("Jordan", ["CSC 510"])
        self.request("Jordan", "Ana", "completed")
        self.assertEqual(self.recommended(), [])

    def test_waiting_request_past_its_deadline_counts_as_expired(self):
        self.add_advisor("Priya", ["CSC 510"])
        self.request("Ana", "Priya", "pending", overdue=True)
        self.assertEqual(self.recommended(), ["Priya"])
