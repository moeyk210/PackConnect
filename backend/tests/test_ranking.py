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


def scaled_rating(rating):
    """Convert a 1-10 rating to the 0-1 scale the factors use."""
    return (rating - 1) / 9


class RatingScoreTests(unittest.TestCase):
    # These expected values assume a starting value of 7.0 worth 3 ratings.
    def setUp(self):
        self.assertEqual((ranking.RATING_STARTING_VALUE, ranking.RATING_STARTING_WEIGHT), (7.0, 3))

    def test_no_ratings_gets_the_starting_value_not_zero(self):
        self.assertAlmostEqual(ranking.rating_score(None, 0), scaled_rating(7.0))
        self.assertAlmostEqual(ranking.rating_score(None, None), scaled_rating(7.0))

    def test_known_average_is_blended_with_the_starting_value(self):
        # (7.0 * 3 + 8.75 * 20) / 23 = 8.52
        self.assertAlmostEqual(ranking.rating_score(8.75, 20), scaled_rating(196 / 23))

    def test_many_strong_ratings_beat_one_perfect_rating(self):
        self.assertGreater(ranking.rating_score(9.0, 20), ranking.rating_score(10.0, 1))

    def test_a_single_low_rating_still_lowers_the_score(self):
        # (7.0 * 3 + 1) / 4 = 5.5, below an advisor with no ratings.
        self.assertAlmostEqual(ranking.rating_score(1.0, 1), scaled_rating(5.5))
        self.assertLess(ranking.rating_score(1.0, 1), ranking.rating_score(None, 0))

    def test_many_low_ratings_rank_below_a_single_low_rating(self):
        self.assertLess(ranking.rating_score(3.0, 10), ranking.rating_score(1.0, 1))

    def test_higher_average_wins_when_counts_are_equal(self):
        self.assertGreater(ranking.rating_score(9.0, 5), ranking.rating_score(8.0, 5))

    def test_score_stays_between_zero_and_one(self):
        for average, count in ((1.0, 1000), (10.0, 1000)):
            with self.subTest(average=average):
                self.assertTrue(0 <= ranking.rating_score(average, count) <= 1)


class ResponseScoreTests(unittest.TestCase):
    # These expected values assume a starting rate of 0.8 worth 3 requests.
    def setUp(self):
        self.assertEqual((ranking.RESPONSE_STARTING_RATE, ranking.RESPONSE_STARTING_WEIGHT), (0.8, 3))

    def test_no_history_gets_the_starting_rate(self):
        self.assertAlmostEqual(ranking.response_score(0, 0), 0.8)
        self.assertAlmostEqual(ranking.response_score(None, None), 0.8)

    def test_known_history_is_blended_with_the_starting_rate(self):
        # (0.8 * 3 + 5) / (3 + 7) = 0.74
        self.assertAlmostEqual(ranking.response_score(5, 2), 0.74)

    def test_long_reliable_history_beats_one_answer(self):
        self.assertGreater(ranking.response_score(48, 2), ranking.response_score(1, 0))

    def test_ignoring_requests_lowers_the_score(self):
        self.assertLess(ranking.response_score(0, 4), ranking.response_score(0, 0))
        self.assertLess(ranking.response_score(2, 8), ranking.response_score(8, 2))


def advisor(advisor_id=1, name="Ada", **facts):
    return ranking.AdvisorFacts(id=advisor_id, name=name, **facts)


def only(factor):
    """Weights that count a single factor, so its effect can be tested alone."""
    return {name: (1 if name == factor else 0.0001) for name in ranking.RANKING_WEIGHTS}


class ScoreAdvisorTests(unittest.TestCase):
    def setUp(self):
        self.search = ranking.SearchRequest(courses=["CSC 510"], topic="interviews")

    def test_breakdown_contains_every_factor(self):
        result = ranking.score_advisor(self.search, advisor(completed_courses=["CSC 510"]))
        self.assertEqual(set(result.factors), {"course", "topic", "rating", "response"})
        self.assertEqual(result.factors["course"], 1.0)
        self.assertEqual(result.factors["topic"], 0.0)

    def test_score_is_the_weighted_average_of_the_factors(self):
        result = ranking.score_advisor(self.search, advisor(completed_courses=["CSC 510"], advice_topics="Interviews"))
        weights = ranking.RANKING_WEIGHTS
        expected = sum(weights[name] * value for name, value in result.factors.items()) / sum(weights.values())
        self.assertAlmostEqual(result.score, expected)

    def test_each_factor_changes_the_score_on_its_own(self):
        cases = {
            "course": ({"completed_courses": ["CSC 510"]}, {"completed_courses": ["CSC 540"]}),
            "topic": ({"advice_topics": "interviews"}, {"advice_topics": "workload"}),
            "rating": ({"average_rating": 9.5, "rating_count": 10}, {"average_rating": 4.0, "rating_count": 10}),
            "response": ({"answered_requests": 10}, {"unanswered_requests": 10}),
        }
        for factor, (better, worse) in cases.items():
            with self.subTest(factor=factor):
                weights = only(factor)
                self.assertGreater(
                    ranking.score_advisor(self.search, advisor(**better), weights).score,
                    ranking.score_advisor(self.search, advisor(**worse), weights).score,
                )

    def test_factors_the_student_did_not_ask_about_are_left_out(self):
        result = ranking.score_advisor(ranking.SearchRequest(), advisor())
        self.assertIsNone(result.factors["course"])
        self.assertIsNone(result.factors["topic"])
        weights = ranking.RANKING_WEIGHTS
        expected = (weights["rating"] * result.factors["rating"] + weights["response"] * result.factors["response"]) / (
            weights["rating"] + weights["response"]
        )
        self.assertAlmostEqual(result.score, expected)

    def test_advisor_with_no_history_is_not_scored_zero(self):
        result = ranking.score_advisor(self.search, advisor(completed_courses=["CSC 510"], advice_topics="interviews"))
        self.assertGreater(result.score, 0.8)

    def test_score_stays_between_zero_and_one(self):
        best = advisor(completed_courses=["CSC 510"], advice_topics="interviews",
                       average_rating=10.0, rating_count=500, answered_requests=500)
        worst = advisor(average_rating=1.0, rating_count=500, unanswered_requests=500)
        for facts in (best, worst):
            with self.subTest(advisor=facts):
                self.assertTrue(0 <= ranking.score_advisor(self.search, facts).score <= 1)


if __name__ == "__main__":
    unittest.main()
