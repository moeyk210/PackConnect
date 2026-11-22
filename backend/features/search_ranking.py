"""Turn advisor search rows into ranked, grouped, paged results.

Results come in two groups:

- "Your matches": advisors who took the searched course (when one was given)
  and meet every filter the student filled in.
- "Outside your filters": near misses, shown below the matches so a search is
  never a dead end. Advisors who took the searched course come first, then
  advisors who took another course in the same subject (for example CSC 540
  when searching CSC 510). Fewer missed filters rank higher.

Inside each group, advisors are ordered by their ranking score.
This module does no database work; the search route passes in plain rows.
"""

from dataclasses import dataclass, field

# Filters that check a profile's text. A filter counts as met when the profile
# field contains the wanted text, ignoring capital letters.
TEXT_FILTERS = ("program", "year", "skills", "advice_topics")


@dataclass(frozen=True)
class SearchFilters:
    """What the student searched for, already cleaned up by the route."""

    # Course code with spaces and hyphens removed, for example "CSC510". Empty if none.
    course_key: str = ""
    # Filled-in text filters only, for example {"program": "computer"}.
    text: dict = field(default_factory=dict)
    # When False, advisors with no reviews yet are left out entirely.
    include_unrated: bool = True


def missed_filters(row, filters):
    """Return the names of the text filters this advisor does not meet, in a fixed order."""
    return [
        name for name in TEXT_FILTERS
        if name in filters.text and filters.text[name].lower() not in (row.get(name) or "").lower()
    ]
