"""Course pages and optional course ratings (story 3.4)."""

import json
from datetime import date, timedelta
from itertools import count
from urllib.parse import quote

import app as portal
from tests.postgres_test_support import PostgresTestCase

SECRET_COMMENT = "A private remark that must never appear on a course page."


class CoursePageTestCase(PostgresTestCase):
    """A two-course catalog, plus helpers to make advisors and course ratings."""

    def setUp(self):
        super().setUp()
        self.client = portal.app.test_client()
        self.numbers = count(1)
        with portal.get_db() as db:
            db.execute("""INSERT INTO courses (code, title, department, description) VALUES
                ('CSC 510', 'Software Engineering', 'CSC', 'Teams build a real product.'),
                ('CSC 540', 'Database Management Concepts and Systems', 'CSC', '')""")

    def student(self, name, courses=("CSC 510",), registered=True, willing=True, pause_until=None):
        with portal.get_db() as db:
            student_id = db.execute("""INSERT INTO students
                (name, program, year, willing_to_advise, max_open_requests, pause_until)
                VALUES (%s, 'CS', '1', %s, NULL, %s) RETURNING id""",
                                    (name, willing, pause_until)).fetchone()["id"]
            if registered:
                db.execute("INSERT INTO accounts (student_id, email, password_hash) VALUES (%s, %s, 'unused')",
                           (student_id, f"student{student_id}@example.test"))
            for course in courses:
                db.execute("INSERT INTO completed_courses (student_id, course_code) VALUES (%s, %s)",
                           (student_id, course))
        return student_id

    def rate(self, advisor, rating=8, workload=None, difficulty=None, course="CSC 510",
             asker=None, asker_courses=("CSC 510",)):
        """One completed conversation about `course`, rated by its asker.

        Askers have no account, so they are never listed as advisors themselves."""
        if asker is None:
            asker = self.student(f"Asker {next(self.numbers)}", courses=asker_courses, registered=False)
        with portal.get_db() as db:
            request_id = db.execute("""INSERT INTO advice_requests
                (sender_id, recipient_id, course_code, advice_topic, message, status)
                VALUES (%s, %s, %s, 'Workload', 'Can you help?', 'completed') RETURNING id""",
                                    (asker, advisor, course)).fetchone()["id"]
            db.execute("""INSERT INTO advice_feedback
                (request_id, rater_id, rating, helpful, comment, workload_rating, difficulty_rating)
                VALUES (%s, %s, %s, true, %s, %s, %s)""",
                       (request_id, asker, rating, SECRET_COMMENT, workload, difficulty))
        return asker

    def help_without_rating(self, advisor):
        asker = self.student(f"Asker {next(self.numbers)}", registered=False)
        with portal.get_db() as db:
            db.execute("""INSERT INTO advice_requests
                (sender_id, recipient_id, course_code, advice_topic, message, status)
                VALUES (%s, %s, 'CSC 510', 'Workload', 'Can you help?', 'completed')""",
                       (asker, advisor))

    def page(self, code="CSC 510", viewer=None):
        client = portal.app.test_client()
        if viewer:
            with client.session_transaction() as session:
                session["student_id"] = viewer
        return client.get(f"/api/courses/{quote(code, safe='')}")

    def body(self, code="CSC 510", viewer=None):
        response = self.page(code, viewer)
        self.assertEqual(response.status_code, 200)
        return response.get_json()

    def names(self, **kwargs):
        return [advisor["name"] for advisor in self.body(**kwargs)["advisors"]]


class CourseDetailsTests(CoursePageTestCase):
    def test_returns_the_title_and_description(self):
        self.assertEqual(self.body()["course"], {
            "code": "CSC 510", "title": "Software Engineering",
            "description": "Teams build a real product."})

    def test_a_blank_description_is_an_empty_string(self):
        self.assertEqual(self.body("CSC 540")["course"]["description"], "")

    def test_codes_are_normalized(self):
        for code in ("csc 510", "CSC510", "csc-510", "  Csc   510 "):
            with self.subTest(code=code):
                self.assertEqual(self.body(code)["course"]["code"], "CSC 510")

    def test_unknown_or_malformed_codes_return_404(self):
        for code in ("CSC 999", "XYZ", "!!!", "510", "A" * 40):
            with self.subTest(code=code):
                response = self.page(code)
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.get_json(), {"error": "Course not found."})

    def test_a_course_nobody_has_taken_has_no_advisors_or_ratings(self):
        body = self.body("CSC 540")
        self.assertEqual(body["advisors"], [])
        self.assertEqual(body["ratings"], {"min_ratings": 3, "workload": None, "difficulty": None})

    def test_no_sign_in_is_needed(self):
        self.assertEqual(self.page().status_code, 200)


class CourseAdvisorTests(CoursePageTestCase):
    def test_lists_only_available_registered_students_who_completed_the_course(self):
        self.student("Avail Anna")
        self.student("Paused Pat", pause_until=date.today() + timedelta(days=7))
        self.student("Retired Rae", willing=False)
        self.student("Ghost Gina", registered=False)
        self.student("Other Omar", courses=("CSC 540",))
        self.assertEqual(self.names(), ["Avail Anna"])
        self.assertEqual(self.names(code="CSC 540"), ["Other Omar"])

    def test_advisors_are_ranked_with_few_ratings_pulled_toward_the_middle(self):
        steady = self.student("Steady")
        lucky = self.student("Lucky")
        self.student("Newcomer")
        for _ in range(5):
            self.rate(steady, rating=9)   # (5 * 9 + 3 * 5.5) / 8 = 7.69
        self.rate(lucky, rating=10)       # (1 * 10 + 3 * 5.5) / 4 = 6.6
        self.assertEqual(self.names(), ["Steady", "Lucky", "Newcomer"])

    def test_equal_scores_go_to_whoever_helped_more_students_then_by_name(self):
        zed, amy, bob = self.student("Zed"), self.student("Amy"), self.student("Bob")
        for advisor in (zed, amy):
            self.rate(advisor, rating=8)
        for _ in range(2):
            self.help_without_rating(zed)
        # Same rating, but Zed has helped 3 students and Amy 1: Zed first despite
        # the later name. Bob has no ratings, so he comes last.
        self.assertEqual(self.names(), ["Zed", "Amy", "Bob"])

    def test_each_advisor_carries_the_same_reputation_stats_as_search(self):
        advisor = self.student("Rated")
        self.rate(advisor, rating=9)
        [listed] = self.body()["advisors"]
        self.assertEqual(listed["reputation"]["average_rating"], 9.0)
        self.assertEqual(listed["reputation"]["rating_count"], 1)
        self.assertEqual(listed["reputation"]["students_helped"], 1)

    def test_the_signed_in_student_is_not_listed_as_their_own_advisor(self):
        me = self.student("Me")
        self.student("Someone Else")
        self.assertEqual(self.names(viewer=me), ["Someone Else"])
        self.assertEqual(sorted(self.names()), ["Me", "Someone Else"])

    def test_no_private_feedback_details_are_exposed(self):
        advisor = self.student("Rated")
        self.rate(advisor, rating=9, workload=3, difficulty=4)
        text = json.dumps(self.body())
        self.assertNotIn(SECRET_COMMENT, text)
        self.assertNotIn("comment", text)
        self.assertNotIn("rater", text)


class CourseRatingTests(CoursePageTestCase):
    def setUp(self):
        super().setUp()
        self.advisor = self.student("Advisor")

    def ratings(self, code="CSC 510"):
        return self.body(code)["ratings"]

    def test_averages_stay_hidden_until_three_students_have_rated(self):
        self.rate(self.advisor, workload=2, difficulty=5)
        self.rate(self.advisor, workload=4, difficulty=5)
        self.assertEqual(self.ratings(), {"min_ratings": 3, "workload": None, "difficulty": None})
        self.rate(self.advisor, workload=3, difficulty=4)
        self.assertEqual(self.ratings(), {
            "min_ratings": 3,
            "workload": {"average": 3.0, "count": 3},
            "difficulty": {"average": 4.7, "count": 3}})

    def test_workload_and_difficulty_each_need_three_ratings(self):
        for workload, difficulty in ((2, 5), (4, 4), (3, None)):
            self.rate(self.advisor, workload=workload, difficulty=difficulty)
        ratings = self.ratings()
        self.assertEqual(ratings["workload"], {"average": 3.0, "count": 3})
        self.assertIsNone(ratings["difficulty"])

    def test_ratings_are_optional_so_feedback_without_them_adds_nothing(self):
        for _ in range(3):
            self.rate(self.advisor)
        self.assertEqual(self.ratings(), {"min_ratings": 3, "workload": None, "difficulty": None})

    def test_one_student_counts_once_however_many_conversations_they_rated(self):
        frequent = self.student("Frequent", registered=False)
        for _ in range(3):
            self.rate(self.advisor, workload=5, asker=frequent)
        self.rate(self.advisor, workload=1)
        self.assertIsNone(self.ratings()["workload"])      # only two students so far
        self.rate(self.advisor, workload=3)
        # Per-student averages 5, 1, 3 give 3.0; a plain average of the rows would give 3.8.
        self.assertEqual(self.ratings()["workload"], {"average": 3.0, "count": 3})

    def test_only_students_who_completed_the_course_count(self):
        for workload in (2, 4, 3):
            self.rate(self.advisor, workload=workload)
        self.rate(self.advisor, workload=5, asker_courses=())
        self.assertEqual(self.ratings()["workload"], {"average": 3.0, "count": 3})

    def test_ratings_for_other_courses_are_ignored(self):
        for workload in (2, 4, 3):
            self.rate(self.advisor, workload=workload)
        for _ in range(3):
            self.rate(self.advisor, workload=5, course="CSC 540", asker_courses=("CSC 510", "CSC 540"))
        self.assertEqual(self.ratings()["workload"], {"average": 3.0, "count": 3})
        self.assertEqual(self.ratings("CSC 540")["workload"], {"average": 5.0, "count": 3})


class CourseRatingFeedbackTests(PostgresTestCase):
    """The optional workload and difficulty ratings on the feedback form."""

    def setUp(self):
        super().setUp()
        self.ids = {}
        with portal.get_db() as db:
            for name in ("asker", "advisor"):
                self.ids[name] = db.execute("""INSERT INTO students (name, program, year, willing_to_advise)
                    VALUES (%s, 'CS', '1', true) RETURNING id""", (name.title(),)).fetchone()["id"]
                db.execute("INSERT INTO accounts (student_id, email, password_hash) VALUES (%s, %s, 'unused')",
                           (self.ids[name], f"{name}@example.test"))
            self.request_id = db.execute("""INSERT INTO advice_requests
                (sender_id, recipient_id, course_code, advice_topic, message, status)
                VALUES (%s, %s, 'CSC 510', 'Projects', 'Can you help?', 'accepted') RETURNING id""",
                                         (self.ids["asker"], self.ids["advisor"])).fetchone()["id"]
            for author in ("asker", "advisor"):
                db.execute("INSERT INTO chat_messages (request_id, sender_id, body) VALUES (%s, %s, 'Hello')",
                           (self.request_id, self.ids[author]))
        self.client = portal.app.test_client()
        with self.client.session_transaction() as session:
            session["student_id"] = self.ids["asker"]

    def submit(self, **fields):
        return self.client.post(f"/api/requests/{self.request_id}/feedback",
                                json={"rating": 8, "helpful": True, **fields})

    def stored(self):
        with portal.get_db() as db:
            return db.execute("SELECT * FROM advice_feedback ORDER BY id").fetchall()

    def test_course_ratings_are_stored_and_returned(self):
        response = self.submit(workload_rating=4, difficulty_rating=2)
        self.assertEqual(response.status_code, 201)
        feedback = response.get_json()["feedback"]
        self.assertEqual((feedback["workload_rating"], feedback["difficulty_rating"]), (4, 2))
        [row] = self.stored()
        self.assertEqual((row["workload_rating"], row["difficulty_rating"]), (4, 2))
        fetched = self.client.get(f"/api/requests/{self.request_id}/feedback").get_json()["feedback"]
        self.assertEqual((fetched["workload_rating"], fetched["difficulty_rating"]), (4, 2))

    def test_they_are_optional_and_independent(self):
        self.assertEqual(self.submit().status_code, 201)
        [row] = self.stored()
        self.assertEqual((row["workload_rating"], row["difficulty_rating"]), (None, None))
        with portal.get_db() as db:
            db.execute("DELETE FROM advice_feedback")
        self.assertEqual(self.submit(workload_rating=5, difficulty_rating=None).status_code, 201)
        [row] = self.stored()
        self.assertEqual((row["workload_rating"], row["difficulty_rating"]), (5, None))

    def test_boundaries_one_and_five_are_accepted(self):
        for value in (1, 5):
            with self.subTest(value=value):
                with portal.get_db() as db:
                    db.execute("DELETE FROM advice_feedback")
                self.assertEqual(self.submit(workload_rating=value, difficulty_rating=value).status_code, 201)

    def test_invalid_values_get_400_and_store_nothing(self):
        for field, label in (("workload_rating", "Workload"), ("difficulty_rating", "Difficulty")):
            for value in (0, 6, -1, 3.5, "3", True, [3]):
                with self.subTest(field=field, value=value):
                    response = self.submit(**{field: value})
                    self.assertEqual(response.status_code, 400)
                    self.assertIn(label, response.get_json()["error"])
        self.assertEqual(self.stored(), [])
