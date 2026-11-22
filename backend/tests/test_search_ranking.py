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


if __name__ == "__main__":
    unittest.main()
