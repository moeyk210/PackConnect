"""GET /api/courses: catalog autocomplete by course code or title (story 3.3)."""

import app as portal
from tests.postgres_test_support import PostgresTestCase


CATALOG = [
    ("CSC 510", "Software Engineering"),
    ("CSC 515", "Software Security"),
    ("CSC 540", "Database Management Concepts and Systems"),
    ("ECE 570", "Computer Networks"),
    ("ENG 200", "Writing for CSC Majors"),
    ("MA 141", "Calculus I"),
]


class CourseAutocompleteTests(PostgresTestCase):
    def setUp(self):
        super().setUp()
        self.client = portal.app.test_client()
        with portal.get_db() as db:
            for code, title in CATALOG:
                db.execute("INSERT INTO courses (code, title, department) VALUES (%s, %s, 'Test')",
                           (code, title))

    def suggest(self, query=None):
        response = self.client.get("/api/courses", query_string={} if query is None else {"q": query})
        self.assertEqual(response.status_code, 200)
        return response.get_json()["courses"]

    def codes(self, query):
        return [course["code"] for course in self.suggest(query)]

    def test_blank_or_missing_query_returns_an_empty_list(self):
        for query in (None, "", " ", "   ", "-", " - "):
            with self.subTest(query=query):
                self.assertEqual(self.suggest(query), [])

    def test_each_match_has_a_code_and_a_title(self):
        self.assertEqual(self.suggest("csc 510"),
                         [{"code": "CSC 510", "title": "Software Engineering"}])

    def test_code_prefix_ignores_case_spaces_and_hyphens(self):
        for query in ("csc5", "CSC 5", "csc-5", "  Csc   5 ", "\tCSC-5\n"):
            with self.subTest(query=query):
                self.assertEqual(self.codes(query), ["CSC 510", "CSC 515", "CSC 540"])
        self.assertEqual(self.codes("ece570"), ["ECE 570"])
        self.assertEqual(self.codes("ma 14"), ["MA 141"])

    def test_title_words_match_anywhere_in_the_title(self):
        self.assertEqual(self.codes("software"), ["CSC 510", "CSC 515"])
        self.assertEqual(self.codes("DATABASE management"), ["CSC 540"])
        self.assertEqual(self.codes("concepts and"), ["CSC 540"])
        self.assertEqual(self.codes("networks"), ["ECE 570"])

    def test_code_matches_come_before_title_matches(self):
        # "ENG 200" only matches because its title mentions CSC.
        self.assertEqual(self.codes("csc"), ["CSC 510", "CSC 515", "CSC 540", "ENG 200"])

    def test_titles_that_start_with_the_text_come_before_other_title_matches(self):
        with portal.get_db() as db:
            for code, title in (("CSC 316", "Data Structures and Algorithms"),
                                ("CSC 111", "Introduction to Data Science")):
                db.execute("INSERT INTO courses (code, title, department) VALUES (%s, %s, 'Test')", (code, title))
        for query in ("data", "DATA", " dAtA "):
            with self.subTest(query=query):
                self.assertEqual(self.codes(query), ["CSC 316", "CSC 540", "CSC 111"])

    def test_results_are_limited_to_ten(self):
        with portal.get_db() as db:
            for number in range(600, 615):
                db.execute("INSERT INTO courses (code, title, department) VALUES (%s, %s, 'Test')",
                           (f"CSC {number}", f"Special Topics {number}"))
        self.assertEqual(self.codes("csc 6"), [f"CSC {number}" for number in range(600, 610)])
        self.assertEqual(len(self.suggest("special topics")), 10)

    def test_queries_are_treated_as_literal_text(self):
        for query in ("%", "_", "%%", "' OR 1=1 --", "'; DROP TABLE courses; --", "NONEXISTENT"):
            with self.subTest(query=query):
                self.assertEqual(self.suggest(query), [])
        self.assertEqual(len(self.suggest("csc")), 4)

    def test_percent_sign_matches_only_a_literal_percent_sign(self):
        with portal.get_db() as db:
            db.execute("INSERT INTO courses (code, title, department) VALUES ('CSC 999', '100% Python', 'Test')")
        self.assertEqual(self.codes("%"), ["CSC 999"])
        self.assertEqual(self.codes("100%"), ["CSC 999"])
        self.assertEqual(self.suggest("_"), [])

    def test_overlong_query_returns_an_empty_list(self):
        self.assertEqual(self.suggest("a" * 101), [])

    def test_only_catalog_courses_are_suggested(self):
        with portal.get_db() as db:
            student_id = db.execute("SELECT id FROM students ORDER BY id LIMIT 1").fetchone()["id"]
            db.execute("INSERT INTO completed_courses (student_id, course_code) VALUES (%s, 'XYZ 999')",
                       (student_id,))
        self.assertEqual(self.suggest("xyz"), [])

    def test_empty_catalog_returns_an_empty_list(self):
        with portal.get_db() as db:
            db.execute("DELETE FROM courses")
        self.assertEqual(self.suggest("csc"), [])

    def test_a_bare_course_number_matches_the_number_part_of_the_code(self):
        self.assertEqual(self.codes("510"), ["CSC 510"])
        for query in ("51", " 51 ", "5-1"):
            with self.subTest(query=query):
                self.assertEqual(self.codes(query), ["CSC 510", "CSC 515"])
        self.assertEqual(self.codes("141"), ["MA 141"])