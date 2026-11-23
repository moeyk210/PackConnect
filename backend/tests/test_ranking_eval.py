"""Ranking eval: known cases must produce known numbers."""

import unittest
from datetime import datetime, timedelta, timezone

import app as portal
from scripts.ranking_eval import evaluate, hits_in_top, ranking_eval_report
from tests.postgres_test_support import PostgresTestCase


class HitsInTopTests(unittest.TestCase):
    def test_counts_places_one_to_three(self):
        # Positions start at 0, so 0, 1 and 2 are the top 3.
        self.assertEqual(hits_in_top([0, 1, 2, 3, 9]), 3)

    def test_advisor_missing_from_the_list_is_a_miss(self):
        self.assertEqual(hits_in_top([None, 0]), 1)

    def test_no_cases(self):
        self.assertEqual(hits_in_top([]), 0)


class RankingEvalReportTests(unittest.TestCase):
    def test_report_compares_new_ranking_with_old_order(self):
        text = ranking_eval_report(new_positions=[0, 1, 2, 5], old_positions=[0, 4, 6, None])
        self.assertIn("Cases: 4 accepted requests", text)
        self.assertIn("New ranking:   75.0% in the top 3 (3 of 4)", text)
        self.assertIn("Old A-Z order: 25.0% in the top 3 (1 of 4)", text)

    def test_report_records_the_settings_used(self):
        text = ranking_eval_report([0], [0])
        self.assertIn("Weights: course 0.35, topic 0.3, rating 0.2, response 0.15", text)
        self.assertIn("Starting values: rating 7/10 worth 3 ratings, response 80% worth 3 requests", text)
        self.assertIn("from before that request was sent", text)

    def test_no_cases_says_there_is_nothing_to_measure(self):
        self.assertIn("nothing to measure", ranking_eval_report([], []))



class EvaluateTests(PostgresTestCase):
    """Small hand-made history in a real database, with known answers."""

    def setUp(self):
        super().setUp()
        self.ids = {}
        self.start = datetime(2026, 9, 1, tzinfo=timezone.utc)
        with portal.get_db() as db:
            db.execute("DELETE FROM accounts")
            db.execute("DELETE FROM completed_courses")
            db.execute("DELETE FROM students")
            self.student(db, "Ana", [], "")
            # Five CSC 510 advisors, A-Z: Aaron, Bea, Cal, Maya, Zed. One CSC 540 advisor.
            for name, topics in (("Aaron", "Workload"), ("Bea", "Workload"), ("Cal", "Workload"),
                                 ("Maya", "Projects"), ("Zed", "Interview prep")):
                self.student(db, name, ["CSC 510"], topics)
            self.student(db, "Kai", ["CSC 540"], "Interview prep")

    def student(self, db, name, courses, topics):
        self.ids[name] = db.execute("""
            INSERT INTO students (name, program, year, advice_topics, willing_to_advise)
            VALUES (%s, 'CS', '1', %s, true) RETURNING id
        """, (name, topics)).fetchone()["id"]
        db.execute("INSERT INTO accounts (student_id, email, password_hash) VALUES (%s, %s, 'unused')",
                   (self.ids[name], f"{name.lower()}@example.test"))
        for course in courses:
            db.execute("INSERT INTO completed_courses (student_id, course_code) VALUES (%s, %s)",
                       (self.ids[name], course))

    def request(self, advisor, topic, day, status="completed", course="CSC 510"):
        sent = self.start + timedelta(days=day)
        with portal.get_db() as db:
            return db.execute("""
                INSERT INTO advice_requests
                    (sender_id, recipient_id, course_code, advice_topic, message, status, created_at, expires_at)
                VALUES (%s, %s, %s, %s, 'Can you help?', %s, %s, %s) RETURNING id
            """, (self.ids["Ana"], self.ids[advisor], course, topic, status, sent, sent + timedelta(days=7))
            ).fetchone()["id"]

    def review(self, request_id, rating, day):
        with portal.get_db() as db:
            db.execute("""
                INSERT INTO advice_feedback (request_id, rater_id, rating, helpful, created_at)
                VALUES (%s, %s, %s, true, %s)
            """, (request_id, self.ids["Ana"], rating, self.start + timedelta(days=day)))

    def evaluate(self):
        with portal.get_db() as db:
            return evaluate(db)

    def test_topic_fit_puts_the_chosen_advisor_first_where_a_to_z_put_them_last(self):
        self.request("Zed", "interview prep", day=1)
        self.assertEqual(self.evaluate(), ([0], [4]))

    def test_advisors_from_another_course_count_for_the_new_ranking_only(self):
        self.request("Kai", "interview prep", day=1)
        # New ranking: the five CSC 510 advisors come first, then Kai. Old order never listed him.
        self.assertEqual(self.evaluate(), ([5], [None]))

    def test_reviews_written_after_a_request_do_not_affect_it(self):
        first = self.request("Zed", "workload", day=1)
        self.review(first, 10, day=3)
        self.request("Zed", "workload", day=10)
        new_positions, _ = self.evaluate()
        # Day 1: the three "Workload" advisors match. Maya and Zed don't, and with no history
        # they tie, so Maya comes first by name and Zed is 5th (position 4). If Zed's day-3
        # review leaked into day 1, he would already be 4th. Day 10: it now counts, so he is.
        self.assertEqual(new_positions, [4, 3])

    def test_declined_and_waiting_requests_are_not_cases(self):
        self.request("Zed", "interview prep", day=1, status="declined")
        self.request("Maya", "projects", day=2, status="pending")
        self.assertEqual(self.evaluate(), ([], []))


if __name__ == "__main__":
    unittest.main()
