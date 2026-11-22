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


if __name__ == "__main__":
    unittest.main()
