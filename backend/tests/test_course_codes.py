"""Canonical course codes (story 3.2): helper, API behaviour and the data migration."""

import unittest
from pathlib import Path

import app as portal
from core.courses import normalize_code
from tests.postgres_test_support import PostgresTestCase, sign_in


MIGRATION = (Path(__file__).resolve().parents[2] / "supabase" / "migrations"
             / "20261115000200_canonical_course_codes.sql")


class NormalizeCodeTests(unittest.TestCase):
    def test_common_spellings_become_the_same_code(self):
        for raw in ("csc510", "CSC510", " CSC 510 ", "csc-510", "CSC   510", "Csc 510", "csc 510"):
            with self.subTest(raw=raw):
                self.assertEqual(normalize_code(raw), "CSC 510")

    def test_other_departments_and_trailing_letters(self):
        self.assertEqual(normalize_code("ece- 570"), "ECE 570")
        self.assertEqual(normalize_code("ma141"), "MA 141")
        self.assertEqual(normalize_code("csc116l"), "CSC 116L")

    def test_unrecognised_text_is_cleaned_but_kept(self):
        self.assertEqual(normalize_code(" csc 366/ece 366 "), "CSC 366/ECE 366")
        self.assertEqual(normalize_code("badcode"), "BADCODE")
        self.assertEqual(normalize_code("   "), "")

    def test_normalizing_twice_changes_nothing(self):
        for raw in ("csc510", " ece- 570 ", "CSC 366/ECE 366", "x"):
            with self.subTest(raw=raw):
                self.assertEqual(normalize_code(normalize_code(raw)), normalize_code(raw))


class CourseCodeRegressionTests(PostgresTestCase):
    def setUp(self):
        super().setUp()
        self.client = portal.app.test_client()

    def register(self, **overrides):
        payload = dict(name="Casey Smith", email="casey@example.edu", password="a long test password",
                       program="MS Computer Science", year="First Year", willing_to_advise=True,
                       completed_courses=["csc510"])
        payload.update(overrides)
        response = self.client.post("/api/auth/register", json=payload)
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()["student"]

    def sign_in(self, student_id):
        sign_in(self.client, student_id)

    def test_course_is_stored_and_found_the_same_way_however_it_is_typed(self):
        student = self.register(completed_courses=["csc510", " CSC 510 ", "CSC-540"])
        self.assertEqual(student["completed_courses"], ["CSC 510", "CSC 540"])
        with portal.get_db() as db:
            stored = [row["course_code"] for row in db.execute(
                "SELECT course_code FROM completed_courses WHERE student_id = %s ORDER BY course_code",
                (student["id"],)).fetchall()]
        self.assertEqual(stored, ["CSC 510", "CSC 540"])
        for query in ("CSC 510", "CSC510", "csc510", " CSC 510 ", "csc-510"):
            with self.subTest(query=query):
                response = self.client.get("/api/students/search", query_string={"course": query})
                self.assertIn(student["id"], [row["id"] for row in response.get_json()["students"]])

    def test_profile_edit_stores_canonical_codes_without_duplicates(self):
        student = self.register()
        self.sign_in(student["id"])
        response = self.client.put(f"/api/students/{student['id']}", json={
            "name": "Casey Smith", "program": "MS Computer Science", "year": "First Year",
            "completed_courses": ["csc510", "CSC 510", " csc-540 "],
            "current_courses": ["ece- 570", "ECE570"], "willing_to_advise": True,
        })
        self.assertEqual(response.status_code, 200, response.get_json())
        profile = response.get_json()["student"]
        self.assertEqual(profile["completed_courses"], ["CSC 510", "CSC 540"])
        self.assertEqual(profile["current_courses"], ["ECE 570"])

    def test_request_stores_the_canonical_course_code(self):
        with portal.get_db() as db:
            ids = {row["name"]: row["id"] for row in db.execute("SELECT id, name FROM students").fetchall()}
            for name in ("Jordan Lee", "Alex Morgan"):
                db.execute("INSERT INTO accounts (student_id, email, password_hash) VALUES (%s, %s, 'unused-test-hash')",
                           (ids[name], name.split()[0].lower() + "@example.test"))
        self.sign_in(ids["Jordan Lee"])
        response = self.client.post("/api/requests", json={
            "recipient_id": ids["Alex Morgan"], "course_code": " csc510 ",
            "advice_topic": "Workload", "message": "How heavy is this course?",
        })
        self.assertEqual(response.status_code, 201, response.get_json())
        self.assertEqual(response.get_json()["request"]["course_code"], "CSC 510")


class CanonicalizationMigrationTests(PostgresTestCase):
    def run_migration(self):
        text = MIGRATION.read_text(encoding="utf-8")
        text = "\n".join(line for line in text.splitlines() if line.strip() not in ("BEGIN;", "COMMIT;"))
        with portal.get_db() as db:
            db.execute(text.replace("public.", self.schema + "."), prepare=False)

    def student_ids(self, db):
        return {row["name"]: row["id"] for row in db.execute("SELECT id, name FROM students").fetchall()}

    def codes(self, db, table, student_id):
        return [row["course_code"] for row in db.execute(
            f"SELECT course_code FROM {table} WHERE student_id = %s ORDER BY course_code",
            (student_id,)).fetchall()]

    def test_existing_rows_are_normalized_without_duplicates(self):
        with portal.get_db() as db:
            ids = self.student_ids(db)
            alex, jordan, taylor = ids["Alex Morgan"], ids["Jordan Lee"], ids["Taylor Kim"]
            db.execute("DELETE FROM completed_courses WHERE student_id IN (%s, %s)", (alex, jordan))
            for code in ("csc510", "CSC 510", " CSC-510 ", "csc 540"):
                db.execute("INSERT INTO completed_courses (student_id, course_code) VALUES (%s, %s)", (alex, code))
            for code in ("ece570", "ECE 570"):
                db.execute("INSERT INTO current_courses (student_id, course_code) VALUES (%s, %s)", (alex, code))
            db.execute("INSERT INTO completed_courses (student_id, course_code) VALUES (%s, 'csc510')", (jordan,))
            db.execute("""INSERT INTO advice_requests (sender_id, recipient_id, course_code, advice_topic, message)
                          VALUES (%s, %s, ' csc510 ', 'Workload', 'Hello')""", (jordan, alex))
        for run in (1, 2):
            with self.subTest(run=run):
                self.run_migration()
                with portal.get_db() as db:
                    self.assertEqual(self.codes(db, "completed_courses", alex), ["CSC 510", "CSC 540"])
                    self.assertEqual(self.codes(db, "current_courses", alex), ["ECE 570"])
                    self.assertEqual(self.codes(db, "completed_courses", jordan), ["CSC 510"])
                    self.assertEqual(self.codes(db, "completed_courses", taylor), ["CSC 515", "CSC 540"])
                    self.assertEqual(db.execute("SELECT course_code FROM advice_requests").fetchone()["course_code"],
                                     "CSC 510")

    def test_migration_and_python_helper_agree(self):
        samples = [" csc510 ", "CSC510", "csc-510", "CSC   510", "ece- 570", "csc116l", "MA 141",
                   "csc 366/ece 366", "BADCODE", "x", "\tcsc\t510\n", "CSC 5 10", "123"]
        owners = {}
        with portal.get_db() as db:
            for index, raw in enumerate(samples):
                student_id = db.execute("INSERT INTO students (name, program, year) VALUES (%s, 'P', 'Y') RETURNING id",
                                        (f"Sample {index}",)).fetchone()["id"]
                db.execute("INSERT INTO completed_courses (student_id, course_code) VALUES (%s, %s)",
                           (student_id, raw))
                owners[student_id] = raw
        self.run_migration()
        with portal.get_db() as db:
            for student_id, raw in owners.items():
                with self.subTest(raw=raw):
                    self.assertEqual(self.codes(db, "completed_courses", student_id), [normalize_code(raw)])


if __name__ == "__main__":
    unittest.main()
