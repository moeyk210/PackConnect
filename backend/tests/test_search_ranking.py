"""Search grouping, ordering, reasons and paging. No database needed: rows are plain dicts."""

import unittest

from features import search_ranking
from features.search_ranking import SearchFilters


def row(**fields):
    """A search row with sensible defaults, overridden per test."""
    base = {
        "id": 1, "name": "Ada", "program": "MS Computer Science", "year": "Second Year",
        "skills": "Python", "advice_topics": "Projects", "course_keys": ["CSC510"], "courses": ["CSC 510"],
        "reputation": {"average_rating": None, "rating_count": 0, "helpful_percent": None,
                       "students_helped": 0, "response_rate": None},
        "response_answered": 0, "response_unanswered": 0,
    }
    base.update(fields)
    return base


class MissedFiltersTests(unittest.TestCase):
    def test_no_text_filters_means_nothing_missed(self):
        self.assertEqual(search_ranking.missed_filters(row(), SearchFilters()), [])

    def test_filters_match_by_contained_text_ignoring_case(self):
        filters = SearchFilters(text={"program": "computer", "skills": "PYTHON", "advice_topics": "project"})
        self.assertEqual(search_ranking.missed_filters(row(), filters), [])

    def test_lists_each_missed_filter_in_a_fixed_order(self):
        filters = SearchFilters(text={"advice_topics": "interview prep", "program": "Statistics", "year": "Second"})
        self.assertEqual(search_ranking.missed_filters(row(), filters), ["program", "advice_topics"])

    def test_empty_profile_field_misses_the_filter(self):
        filters = SearchFilters(text={"skills": "Java"})
        self.assertEqual(search_ranking.missed_filters(row(skills=None), filters), ["skills"])


class ResultGroupTests(unittest.TestCase):
    def group(self, advisor, filters):
        return search_ranking.result_group(advisor, filters, search_ranking.missed_filters(advisor, filters))

    def test_took_the_course_and_meets_every_filter_is_a_match(self):
        filters = SearchFilters(course_key="CSC510", text={"program": "computer"})
        self.assertEqual(self.group(row(), filters), search_ranking.YOUR_MATCHES)

    def test_took_the_course_but_missed_a_filter_is_outside_close(self):
        filters = SearchFilters(course_key="CSC510", text={"program": "Statistics"})
        self.assertEqual(self.group(row(), filters), search_ranking.OUTSIDE_CLOSE)

    def test_took_the_course_but_missed_every_filter_is_still_shown(self):
        filters = SearchFilters(course_key="CSC510", text={"program": "Statistics", "skills": "Java"})
        self.assertEqual(self.group(row(), filters), search_ranking.OUTSIDE_CLOSE)

    def test_other_course_in_the_subject_meeting_some_filters_is_outside_other_course(self):
        other = row(course_keys=["CSC540"], courses=["CSC 540"])
        filters = SearchFilters(course_key="CSC510", text={"program": "computer", "skills": "Java"})
        self.assertEqual(self.group(other, filters), search_ranking.OUTSIDE_OTHER_COURSE)

    def test_other_course_in_the_subject_with_no_filters_is_outside_other_course(self):
        other = row(course_keys=["CSC540"], courses=["CSC 540"])
        self.assertEqual(self.group(other, SearchFilters(course_key="CSC510")), search_ranking.OUTSIDE_OTHER_COURSE)

    def test_other_course_meeting_no_filters_is_left_out(self):
        other = row(course_keys=["CSC540"], courses=["CSC 540"])
        filters = SearchFilters(course_key="CSC510", text={"program": "Statistics"})
        self.assertIsNone(self.group(other, filters))

    def test_different_subject_is_always_left_out(self):
        other = row(course_keys=["MA305"], courses=["MA 305"])
        self.assertIsNone(self.group(other, SearchFilters(course_key="CSC510")))

    def test_course_with_no_subject_letters_only_matches_exactly(self):
        self.assertIsNone(self.group(row(course_keys=["511"]), SearchFilters(course_key="510")))

    def test_without_a_course_filters_decide_the_group(self):
        meets = SearchFilters(text={"program": "computer"})
        partly = SearchFilters(text={"program": "computer", "skills": "Java"})
        none = SearchFilters(text={"program": "Statistics"})
        self.assertEqual(self.group(row(), meets), search_ranking.YOUR_MATCHES)
        self.assertEqual(self.group(row(), partly), search_ranking.OUTSIDE_CLOSE)
        self.assertIsNone(self.group(row(), none))


def rated(average, count, answered=0, unanswered=0, response_rate=None):
    """Reputation fields for a row, in the shape the search route provides."""
    return {
        "reputation": {"average_rating": average, "rating_count": count, "helpful_percent": None,
                       "students_helped": 0, "response_rate": response_rate},
        "response_answered": answered, "response_unanswered": unanswered,
    }


class MatchReasonsTests(unittest.TestCase):
    def reasons(self, advisor, filters, group=search_ranking.YOUR_MATCHES):
        return search_ranking.match_reasons(advisor, filters, group)

    def test_new_advisor_shows_topic_and_no_reviews(self):
        advisor = row(advice_topics="Interview prep, resumes")
        filters = SearchFilters(course_key="CSC510", text={"advice_topics": "interview prep"})
        self.assertEqual(self.reasons(advisor, filters), ["Advises on interview prep", "No reviews yet"])

    def test_reviewed_advisor_shows_rating_and_response_rate(self):
        advisor = row(advice_topics="Interviews, projects", **rated(9.0, 20, answered=19, unanswered=1, response_rate=95))
        filters = SearchFilters(course_key="CSC510", text={"advice_topics": "interview prep"})
        self.assertEqual(self.reasons(advisor, filters),
                         ["Advises on interview", "9.0/10 (20 reviews)", "Answers 95% of requests"])

    def test_single_review_is_singular(self):
        self.assertEqual(self.reasons(row(**rated(7.0, 1)), SearchFilters()), ["7.0/10 (1 review)"])

    def test_no_topic_label_without_a_topic_match(self):
        advisor = row(advice_topics="Course workload", **rated(6.0, 5, answered=2, unanswered=2, response_rate=50))
        filters = SearchFilters(course_key="CSC510", text={"advice_topics": "interview prep"})
        self.assertEqual(self.reasons(advisor, filters), ["6.0/10 (5 reviews)", "Answers 50% of requests"])

    def test_other_course_advisor_says_which_course_they_took(self):
        advisor = row(course_keys=["CSC316", "CSC540", "MA305"], courses=["CSC 316", "CSC 540", "MA 305"])
        reasons = self.reasons(advisor, SearchFilters(course_key="CSC510"), search_ranking.OUTSIDE_OTHER_COURSE)
        self.assertEqual(reasons, ["Took CSC 316, CSC 540", "No reviews yet"])

    def test_searched_course_is_not_repeated_for_advisors_who_took_it(self):
        reasons = self.reasons(row(), SearchFilters(course_key="CSC510"))
        self.assertFalse(any("CSC 510" in reason for reason in reasons))


class RankSearchResultsTests(unittest.TestCase):
    def setUp(self):
        # Ana searches CSC 510 for interview prep in MS Computer Science.
        self.filters = SearchFilters(course_key="CSC510",
                                     text={"program": "MS Computer", "advice_topics": "interview prep"})
        self.rows = [
            row(id=1, name="Aaron", program="BS Computer Science", advice_topics="Course workload",
                **rated(6.0, 5, answered=2, unanswered=2, response_rate=50)),
            row(id=2, name="Maya", advice_topics="Interviews, projects",
                **rated(9.0, 20, answered=19, unanswered=1, response_rate=95)),
            row(id=3, name="Zoe", advice_topics="Interview prep, resumes"),
            row(id=4, name="Sam", advice_topics="Interview prep", course_keys=["CSC540"], courses=["CSC 540"]),
            row(id=5, name="Priya", advice_topics="Interview prep, exams",
                **rated(8.5, 12, answered=9, unanswered=1, response_rate=90)),
            row(id=6, name="Lee", course_keys=["MA305"], courses=["MA 305"], advice_topics="Interview prep"),
        ]

    def names(self, results):
        return [result.public["name"] for result in results]

    def test_matches_first_then_close_misses_then_other_courses(self):
        results = search_ranking.rank_search_results(self.rows, self.filters)
        # Zoe and Priya match everything. Maya misses the exact topic phrase; Aaron misses
        # the topic and the program. Sam took CSC 540 instead of CSC 510.
        self.assertEqual(self.names(results), ["Priya", "Zoe", "Maya", "Aaron", "Sam"])
        self.assertEqual([r.group for r in results], [0, 0, 1, 1, 2])

    def test_other_subjects_are_never_included(self):
        results = search_ranking.rank_search_results(self.rows, self.filters)
        self.assertNotIn("Lee", self.names(results))

    def test_unchecking_no_reviews_leaves_out_unrated_advisors(self):
        filters = SearchFilters(course_key="CSC510", text=self.filters.text, include_unrated=False)
        self.assertEqual(self.names(search_ranking.rank_search_results(self.rows, filters)), ["Priya", "Maya", "Aaron"])

    def test_public_data_adds_score_reasons_and_missed_filters_only(self):
        result = search_ranking.rank_search_results(self.rows, self.filters)[2]
        self.assertEqual(result.public["name"], "Maya")
        self.assertEqual(result.public["missed_filters"], ["advice_topics"])
        self.assertEqual(result.public["match_reasons"],
                         ["Advises on interview", "9.0/10 (20 reviews)", "Answers 95% of requests"])
        self.assertTrue(0 <= result.public["score"] <= 1)
        for internal in search_ranking.INTERNAL_FIELDS:
            self.assertNotIn(internal, result.public)

    def test_order_is_the_same_whatever_order_rows_arrive_in(self):
        forward = self.names(search_ranking.rank_search_results(self.rows, self.filters))
        backward = self.names(search_ranking.rank_search_results(list(reversed(self.rows)), self.filters))
        self.assertEqual(forward, backward)


class PageSettingsTests(unittest.TestCase):
    def test_defaults_to_twenty_from_the_start(self):
        self.assertEqual(search_ranking.page_settings({}), (20, 0))

    def test_reads_limit_and_offset(self):
        self.assertEqual(search_ranking.page_settings({"limit": "5", "offset": "10"}), (5, 10))

    def test_large_limits_are_lowered_to_the_maximum(self):
        self.assertEqual(search_ranking.page_settings({"limit": "10000"}), (50, 0))

    def test_invalid_values_are_rejected(self):
        for args in ({"limit": "abc"}, {"limit": "0"}, {"limit": "-3"}, {"offset": "-1"}, {"offset": "1.5"}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                search_ranking.page_settings(args)


class ResultsPageTests(unittest.TestCase):
    def setUp(self):
        # 3 matches followed by 2 advisors outside the filters, already in order.
        self.results = [search_ranking.RankedResult(group=0, public={"id": n}) for n in (1, 2, 3)]
        self.results += [search_ranking.RankedResult(group=1, public={"id": 4}),
                         search_ranking.RankedResult(group=2, public={"id": 5})]

    def match_ids(self, page):
        return [s["id"] for s in page["students"]]

    def test_page_splits_into_matches_and_outside_filters(self):
        page = search_ranking.results_page(self.results, 20, 0)
        self.assertEqual(self.match_ids(page), [1, 2, 3])
        self.assertEqual([s["id"] for s in page["outside_filters"]], [4, 5])
        self.assertEqual((page["total_matches"], page["total_outside_filters"]), (3, 2))

    def test_pages_move_through_matches_only_without_overlap(self):
        pages = [search_ranking.results_page(self.results, 2, offset) for offset in (0, 2)]
        self.assertEqual([self.match_ids(page) for page in pages], [[1, 2], [3]])

    def test_outside_filters_are_the_same_on_every_page(self):
        pages = [search_ranking.results_page(self.results, 2, offset) for offset in (0, 2, 99)]
        self.assertTrue(all([s["id"] for s in page["outside_filters"]] == [4, 5] for page in pages))

    def test_outside_filters_are_capped(self):
        many = [search_ranking.RankedResult(group=1, public={"id": n}) for n in range(40)]
        page = search_ranking.results_page(many, 20, 0)
        self.assertEqual(len(page["outside_filters"]), search_ranking.OUTSIDE_LIMIT)
        self.assertEqual(page["total_outside_filters"], 40)

    def test_totals_and_settings_are_reported(self):
        page = search_ranking.results_page(self.results, 2, 2)
        self.assertEqual((page["total_matches"], page["total_outside_filters"]), (3, 2))
        self.assertEqual((page["limit"], page["offset"]), (2, 2))

    def test_offset_past_the_end_gives_no_matches(self):
        page = search_ranking.results_page(self.results, 20, 99)
        self.assertEqual(page["students"], [])

if __name__ == "__main__":
    unittest.main()
