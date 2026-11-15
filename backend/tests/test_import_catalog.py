import tempfile
from pathlib import Path

import app as portal
from import_catalog import import_catalog
from tests.postgres_test_support import PostgresTestCase


FIXTURE = Path(__file__).parent / "fixtures" / "courses_fixture.csv"


class ImportCatalogTests(PostgresTestCase):
    def run_import(self, path=FIXTURE):
        with portal.get_db() as db:
            return import_catalog(db, path)

    def course_count(self):
        with portal.get_db() as db:
            return db.execute("SELECT COUNT(*) FROM courses").fetchone()["count"]

    def test_valid_rows_load_with_canonical_codes(self):
        summary = self.run_import()
        self.assertEqual(summary["inserted"], 3)
        self.assertEqual(self.course_count(), 3)
        with portal.get_db() as db:
            row = db.execute("SELECT title, department FROM courses WHERE code = 'CSC 540'").fetchone()
        self.assertEqual(row["title"], "Database Management Concepts")
        self.assertEqual(row["department"], "Computer Science")

    def test_malformed_rows_are_skipped_and_reported(self):
        summary = self.run_import()
        self.assertEqual([line for line, _ in summary["skipped"]], [5, 6, 7, 8, 9])
        reasons = " | ".join(reason for _, reason in summary["skipped"])
        for expected in ("duplicate course code", "invalid course code", "missing title",
                         "too few columns", "too many columns"):
            self.assertIn(expected, reasons)

    def test_running_twice_leaves_the_same_row_count(self):
        self.run_import()
        first = self.course_count()
        second_summary = self.run_import()
        self.assertEqual(self.course_count(), first)
        self.assertEqual(second_summary["inserted"], 0)
        self.assertEqual(second_summary["unchanged"], 3)

    def test_rerun_updates_changed_rows_without_duplicates(self):
        self.run_import()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "courses.csv"
            path.write_text("code,title,department,description\n"
                            "CSC 510,Software Engineering (Updated),Computer Science,New text\n",
                            encoding="utf-8")
            summary = self.run_import(path)
        self.assertEqual(summary["updated"], 1)
        self.assertEqual(self.course_count(), 3)
        with portal.get_db() as db:
            row = db.execute("SELECT title FROM courses WHERE code = 'CSC 510'").fetchone()
        self.assertEqual(row["title"], "Software Engineering (Updated)")

    def test_missing_columns_fail_before_any_insert(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad.csv"
            path.write_text("code,title\nCSC 510,Software Engineering\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing column"):
                self.run_import(path)
        self.assertEqual(self.course_count(), 0)