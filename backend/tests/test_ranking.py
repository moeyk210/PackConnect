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


class CourseMatchTests(unittest.TestCase):
    def test_completed_course_is_a_full_match(self):
        self.assertEqual(ranking.course_match(["CSC 510"], ["CSC 510", "CSC 540"]), 1.0)

    def test_missing_course_is_no_match(self):
        self.assertEqual(ranking.course_match(["CSC 510"], ["CSC 540"]), 0.0)

    def test_partial_coverage_of_several_courses(self):
        self.assertAlmostEqual(ranking.course_match(["CSC 510", "CSC 540", "CSC 505"], ["CSC 510", "CSC 505"]), 2 / 3)

    def test_repeated_courses_count_once(self):
        self.assertEqual(ranking.course_match(["CSC 510", "CSC 510"], ["CSC 510"]), 1.0)

    def test_no_wanted_courses_leaves_the_factor_out(self):
        self.assertIsNone(ranking.course_match([], ["CSC 510"]))

    def test_advisor_with_no_courses_is_no_match(self):
        self.assertEqual(ranking.course_match(["CSC 510"], []), 0.0)


if __name__ == "__main__":
    unittest.main()
