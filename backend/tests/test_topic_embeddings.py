"""Saving a profile keeps the student's topic fingerprint up to date."""

import app as portal
from core.embeddings import vector_literal
from tests.fake_embedder import FakeEmbedder
from tests.postgres_test_support import PostgresTestCase, sign_in


class BrokenEmbedder:
    def embed(self, texts):
        raise RuntimeError("model unavailable")


class TopicFingerprintOnSaveTests(PostgresTestCase):
    def setUp(self):
        super().setUp()
        with portal.get_db() as db:
            self.student_id = db.execute("""
                INSERT INTO students (name, program, year, willing_to_advise)
                VALUES ('Ada', 'CS', 'Second Year', true) RETURNING id
            """).fetchone()["id"]
            db.execute("INSERT INTO accounts (student_id, email, password_hash) VALUES (%s, 'ada@example.test', 'x')",
                       (self.student_id,))
        self.client = portal.app.test_client()
        sign_in(self.client, self.student_id)

    def save(self, topics):
        response = self.client.put(f"/api/students/{self.student_id}", json={
            "name": "Ada", "program": "CS", "year": "Second Year", "advice_topics": topics,
            "completed_courses": ["CSC 510"], "willing_to_advise": True,
        })
        self.assertEqual(response.status_code, 200, response.get_json())

    def stored(self):
        with portal.get_db() as db:
            return db.execute("SELECT topic_embedding::text AS value FROM students WHERE id = %s",
                              (self.student_id,)).fetchone()["value"]

    def test_saving_topics_stores_their_fingerprint(self):
        self.save("Interview prep, resumes")
        expected = vector_literal(FakeEmbedder().embed(["Interview prep, resumes"])[0])
        stored = [float(value) for value in self.stored().strip("[]").split(",")]
        wanted = [float(value) for value in expected.strip("[]").split(",")]
        self.assertEqual(len(stored), 384)
        for got, want in zip(stored, wanted):
            self.assertAlmostEqual(got, want, places=5)

    def test_clearing_topics_removes_the_fingerprint(self):
        self.save("Projects")
        self.save("   ")
        self.assertIsNone(self.stored())

    def test_profile_still_saves_when_the_model_fails(self):
        portal.app.config["TOPIC_EMBEDDER"] = BrokenEmbedder()
        with self.assertLogs("features.topic_embeddings", level="WARNING") as logs:
            self.save("Projects")
        self.assertIsNone(self.stored())
        # The student's own topic text is never written to the logs.
        self.assertNotIn("Projects", " ".join(logs.output))
