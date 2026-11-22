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


if __name__ == "__main__":
    unittest.main()
