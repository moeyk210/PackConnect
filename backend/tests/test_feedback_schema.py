"""Database rules for the advice_feedback table."""

from psycopg.errors import CheckViolation, ForeignKeyViolation, NotNullViolation, UniqueViolation

import app as portal
from tests.postgres_test_support import PostgresTestCase


class FeedbackSchemaTests(PostgresTestCase):
    def setUp(self):
        super().setUp()
        with portal.get_db() as db:
            self.asker, self.advisor = (db.execute(
                "INSERT INTO students (name, program, year) VALUES (%s, 'CS', '1') RETURNING id", (name,)
            ).fetchone()["id"] for name in ("Asker", "Advisor"))
            self.request_id = db.execute("""
                INSERT INTO advice_requests (sender_id, recipient_id, course_code, advice_topic, message, status)
                VALUES (%s, %s, 'CSC 510', 'Projects', 'Can you help?', 'accepted') RETURNING id
            """, (self.asker, self.advisor)).fetchone()["id"]

    def insert(self, db, rater=None, rating=8, helpful=True, **extra):
        columns = ["request_id", "rater_id", "rating", "helpful", *extra]
        values = [self.request_id, rater or self.asker, rating, helpful, *extra.values()]
        return db.execute(
            f"INSERT INTO advice_feedback ({', '.join(columns)}) VALUES ({', '.join(['%s'] * len(values))}) RETURNING *",
            values,
        ).fetchone()

    def test_valid_feedback_is_stored_with_defaults(self):
        with portal.get_db() as db:
            row = self.insert(db)
        self.assertEqual((row["rating"], row["helpful"], row["comment"]), (8, True, ""))
        self.assertIsNotNone(row["created_at"])

    def test_rating_bounds_are_one_to_ten(self):
        for rating in (1, 10):
            with self.subTest(rating=rating), portal.get_db() as db:
                self.insert(db, rating=rating)
                db.execute("DELETE FROM advice_feedback")
        for rating in (0, 11, -3):
            with self.subTest(rating=rating), self.assertRaises(CheckViolation), portal.get_db() as db:
                self.insert(db, rating=rating)

    def test_rating_and_helpful_are_required(self):
        for column in ("rating", "helpful"):
            with self.subTest(column=column), self.assertRaises(NotNullViolation), portal.get_db() as db:
                db.execute(f"""INSERT INTO advice_feedback (request_id, rater_id, {'helpful' if column == 'rating' else 'rating'})
                    VALUES (%s, %s, %s)""", (self.request_id, self.asker, True if column == "rating" else 5))

    def test_comment_is_limited_to_500_characters(self):
        with portal.get_db() as db:
            self.assertEqual(len(self.insert(db, comment="x" * 500)["comment"]), 500)
        with self.assertRaises(CheckViolation), portal.get_db() as db:
            self.insert(db, rater=self.advisor, comment="x" * 501)

    def test_each_person_rates_a_request_once(self):
        with portal.get_db() as db:
            self.insert(db)
            self.insert(db, rater=self.advisor)
        with self.assertRaises(UniqueViolation), portal.get_db() as db:
            self.insert(db, rating=3)

    def test_feedback_requires_existing_request_and_rater(self):
        with self.assertRaises(ForeignKeyViolation), portal.get_db() as db:
            self.insert(db, rater=999999)
        self.request_id = 999999
        with self.assertRaises(ForeignKeyViolation), portal.get_db() as db:
            self.insert(db)

    def test_browser_roles_have_no_feedback_privileges(self):
        with portal.get_db() as db:
            for role in ("anon", "authenticated"):
                for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE"):
                    allowed = db.execute("SELECT has_table_privilege(%s, %s, %s) AS allowed",
                                         (role, f"{self.schema}.advice_feedback", privilege)).fetchone()["allowed"]
                    self.assertFalse(allowed, (role, privilege))
