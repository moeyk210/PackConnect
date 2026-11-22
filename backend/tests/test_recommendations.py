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
