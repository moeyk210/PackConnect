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


class TopicMatchTests(unittest.TestCase):
    def test_exact_topic_is_a_full_match(self):
        self.assertEqual(ranking.topic_match("interviews", "Projects, interviews"), 1.0)

    def test_plural_and_singular_match(self):
        self.assertEqual(ranking.topic_match("interview", "Projects, interviews"), 1.0)
        self.assertEqual(ranking.topic_match("study strategies", "study strategy"), 1.0)

    def test_case_and_punctuation_are_ignored(self):
        self.assertEqual(ranking.topic_match("Course-Workload", "course workload"), 1.0)

    def test_partial_match_counts_the_covered_share(self):
        self.assertEqual(ranking.topic_match("interview prep", "Projects, interviews"), 0.5)

    def test_listing_many_topics_is_not_penalized(self):
        many = "Exams, research, interview prep, resumes, networking, grad school"
        self.assertEqual(ranking.topic_match("interview prep", many), 1.0)

    def test_filler_words_never_count_as_a_match(self):
        self.assertEqual(ranking.topic_match("help with the exams", "help with the projects"), 0.0)

    def test_unrelated_topics_are_no_match(self):
        self.assertEqual(ranking.topic_match("interviews", "Course workload"), 0.0)

    def test_no_asked_topic_leaves_the_factor_out(self):
        for asked in ("", "   ", None, "the and of"):
            with self.subTest(asked=asked):
                self.assertIsNone(ranking.topic_match(asked, "Projects"))

    def test_advisor_with_no_topics_is_no_match(self):
        self.assertEqual(ranking.topic_match("interviews", None), 0.0)


if __name__ == "__main__":
    unittest.main()
