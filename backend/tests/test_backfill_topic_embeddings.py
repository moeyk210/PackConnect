"""Backfill script: fills missing topic fingerprints and refuses shared databases by default."""

import io
from contextlib import redirect_stdout

import app as portal
from scripts import backfill_topic_embeddings as backfill
from tests.fake_embedder import FakeEmbedder
from tests.postgres_test_support import PostgresTestCase


class BackfillTests(PostgresTestCase):
    def setUp(self):
        super().setUp()
        with portal.get_db() as db:
            for table in ("accounts", "completed_courses", "current_courses", "students"):
                db.execute(f"DELETE FROM {table}")
            self.ids = {}
            for name, topics in (("Ada", "Projects"), ("Blake", "  "), ("Casey", "Workload")):
                self.ids[name] = db.execute(
                    "INSERT INTO students (name, program, year, advice_topics) VALUES (%s, 'CS', '1', %s) RETURNING id",
                    (name, topics)).fetchone()["id"]

    def has_fingerprint(self, name):
        with portal.get_db() as db:
            return db.execute("SELECT topic_embedding IS NOT NULL AS present FROM students WHERE id = %s",
                              (self.ids[name],)).fetchone()["present"]

    def test_fills_students_with_topics_and_skips_blank_ones(self):
        with portal.get_db() as db:
            written = backfill.backfill_topic_embeddings(db, FakeEmbedder())
        self.assertEqual(written, 2)
        self.assertEqual([self.has_fingerprint(name) for name in ("Ada", "Blake", "Casey")], [True, False, True])

    def test_second_run_only_does_missing_ones_unless_asked_to_redo_all(self):
        embedder = FakeEmbedder()
        with portal.get_db() as db:
            backfill.backfill_topic_embeddings(db, embedder)
            self.assertEqual(backfill.backfill_topic_embeddings(db, embedder), 0)
            self.assertEqual(backfill.backfill_topic_embeddings(db, embedder, redo_all=True), 2)

    def test_refuses_a_non_local_database_by_default(self):
        output = io.StringIO()
        with redirect_stdout(output):
            status = backfill.main(["--database-url", "postgresql://user:pw@db.example.com:5432/postgres"])
        self.assertEqual(status, 2)
        self.assertIn("Refusing", output.getvalue())
        self.assertNotIn("pw", output.getvalue())
