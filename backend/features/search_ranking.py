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

import re
from dataclasses import dataclass, field

from features import ranking

# Filters that check a profile's text. A filter counts as met when the profile
# field contains the wanted text, ignoring capital letters.
TEXT_FILTERS = ("program", "year", "skills", "advice_topics")

# Result groups, in the order they are shown. Lower numbers come first.
YOUR_MATCHES = 0
OUTSIDE_CLOSE = 1          # Took the searched course (or no course was searched) but missed filters.
OUTSIDE_OTHER_COURSE = 2   # Took a different course in the same subject.


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


def course_subject(course_key):
    """Return the subject letters of a course key ("CSC510" -> "CSC"), or "" if there are none."""
    match = re.match(r"[A-Z]+", course_key or "")
    return match.group() if match else ""


def result_group(row, filters, missed):
    """Return which group the advisor belongs in, or None to leave them out of the results.

    Someone outside the searched subject is never shown. An advisor from a
    different course in the subject, or a near miss when no course was searched,
    must still meet at least one of the filters (if any were given).
    """
    meets_some_filters = not filters.text or len(missed) < len(filters.text)
    if not filters.course_key:
        if not missed:
            return YOUR_MATCHES
        return OUTSIDE_CLOSE if meets_some_filters else None
    if filters.course_key in row["course_keys"]:
        return OUTSIDE_CLOSE if missed else YOUR_MATCHES
    subject = course_subject(filters.course_key)
    same_subject = subject and any(course_subject(key) == subject for key in row["course_keys"])
    return OUTSIDE_OTHER_COURSE if same_subject and meets_some_filters else None


def rating_label(reputation):
    """Describe an advisor's reviews, for example "9.0/10 (20 reviews)" or "No reviews yet"."""
    count = reputation["rating_count"] or 0
    if count == 0:
        return "No reviews yet"
    return f"{reputation['average_rating']:.1f}/10 ({count} review{'' if count == 1 else 's'})"


def match_reasons(row, filters, group):
    """Short labels explaining an advisor's place in the results, built from the same data as the score.

    The searched course is not repeated for advisors who took it, since every
    such result shares it. Advisors from a different course say which one.
    """
    reasons = []
    if group == OUTSIDE_OTHER_COURSE:
        subject = course_subject(filters.course_key)
        taken = [code for code, key in zip(row["courses"], row["course_keys"]) if course_subject(key) == subject]
        reasons.append("Took " + ", ".join(dict.fromkeys(taken)))
    topic_words = ranking.matching_topic_words(filters.text.get("advice_topics"), row.get("advice_topics"))
    if topic_words:
        reasons.append("Advises on " + " ".join(topic_words))
    reasons.append(rating_label(row["reputation"]))
    if row["response_answered"] + row["response_unanswered"] > 0:
        reasons.append(f"Answers {row['reputation']['response_rate']}% of requests")
    return reasons
