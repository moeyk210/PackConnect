"""Ranking eval: known cases must produce known numbers."""

import unittest

from scripts.ranking_eval import hits_in_top, ranking_eval_report


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


if __name__ == "__main__":
    unittest.main()
