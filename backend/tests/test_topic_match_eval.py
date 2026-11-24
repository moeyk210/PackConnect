"""Topic matching eval: scoring logic, without the real model."""

import unittest

from scripts.topic_match_cases import ADVISOR_TOPICS, CASES
from scripts.topic_match_eval import evaluate_topic_matching, is_clear_winner, topic_eval_report
from tests.fake_embedder import FakeEmbedder


class IsClearWinnerTests(unittest.TestCase):
    def test_right_option_must_score_strictly_highest(self):
        self.assertTrue(is_clear_winner([0.2, 0.9, 0.1], 1))
        self.assertFalse(is_clear_winner([0.9, 0.9, 0.1], 1))
        self.assertFalse(is_clear_winner([0.0, 0.0], 0))


class EvaluateTopicMatchingTests(unittest.TestCase):
    def test_exact_word_cases_are_hits_for_both_methods(self):
        cases = [("time management", 2), ("debugging", 6)]
        self.assertEqual(evaluate_topic_matching(FakeEmbedder(), cases), (2, 2, 2))

    def test_different_wording_misses_with_shared_words_alone(self):
        words_hits, _, cases = evaluate_topic_matching(FakeEmbedder(), [("job hunting", 1)])
        self.assertEqual((words_hits, cases), (0, 1))

    def test_test_set_points_at_real_advisor_topics(self):
        self.assertEqual(len(CASES), 30)
        self.assertTrue(all(0 <= index < len(ADVISOR_TOPICS) for _, index in CASES))

    def test_report_compares_both_methods(self):
        report = topic_eval_report(14, 26, 30)
        self.assertIn("Shared words only:           46.7% (14 of 30)", report)
        self.assertIn("Shared words and meaning:    86.7% (26 of 30)", report)


if __name__ == "__main__":
    unittest.main()
