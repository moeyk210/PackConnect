"""Advisor ranking rules. These tests need no database because ranking is plain calculation."""

import unittest

from features import ranking


class RankingSettingsTests(unittest.TestCase):
    def test_every_factor_has_a_positive_weight(self):
        self.assertEqual(set(ranking.RANKING_WEIGHTS), {"course", "topic", "rating", "response"})
        for factor, weight in ranking.RANKING_WEIGHTS.items():
            with self.subTest(factor=factor):
                self.assertGreater(weight, 0)

    def test_starting_values_are_inside_their_scales(self):
        self.assertTrue(ranking.LOWEST_RATING <= ranking.RATING_STARTING_VALUE <= ranking.HIGHEST_RATING)
        self.assertTrue(0 <= ranking.RESPONSE_STARTING_RATE <= 1)


if __name__ == "__main__":
    unittest.main()
