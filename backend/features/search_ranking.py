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

# Paging: results per page when none is asked for, and the most allowed at once.
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50

# The most advisors sent for the "Outside your filters" row.
OUTSIDE_LIMIT = 15

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


def meets_filter(row, name, wanted):
    """Whether the advisor meets one text filter.

    Every filter is met when the profile field contains the wanted text. The
    advice topics filter is also met when the topics are close enough in
    meaning (for example "interview prep" and "Projects, interviews").
    """
    if wanted.lower() in (row.get(name) or "").lower():
        return True
    if name == "advice_topics":
        meaning = ranking.meaning_match(row.get("topic_similarity"))
        return meaning is not None and meaning >= ranking.MEANING_FILTER_THRESHOLD
    return False


def missed_filters(row, filters):
    """Return the names of the text filters this advisor does not meet, in a fixed order."""
    return [
        name for name in TEXT_FILTERS
        if name in filters.text and not meets_filter(row, name, filters.text[name])
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


def reputation_reasons(row):
    """The review label, plus the response rate once the advisor has had at least one request.

    A brand-new advisor shows no response rate rather than a made-up number.
    """
    reasons = [rating_label(row["reputation"])]
    if row["response_answered"] + row["response_unanswered"] > 0:
        reasons.append(f"Answers {row['reputation']['response_rate']}% of requests")
    return reasons


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
    asked_topic = filters.text.get("advice_topics")
    topic_words = ranking.matching_topic_words(asked_topic, row.get("advice_topics"))
    if topic_words:
        reasons.append("Advises on " + " ".join(topic_words))
    elif asked_topic and meets_filter(row, "advice_topics", asked_topic):
        reasons.append("Advises on related topics")
    return reasons + reputation_reasons(row)


# Columns the route selects only so results can be ranked. They are removed
# before results are sent, so responses keep their original public fields.
INTERNAL_FIELDS = ("course_keys", "courses", "response_answered", "response_unanswered", "topic_similarity")


@dataclass(frozen=True)
class RankedResult:
    """One advisor's place in the results and the public data sent for them."""

    group: int
    public: dict


def advisor_facts(row):
    """Convert an advisor row (from features/advisor_candidates.py) into the facts ranking scores."""
    return ranking.AdvisorFacts(
        id=row["id"],
        name=row["name"],
        completed_courses=row["course_keys"],
        advice_topics=row.get("advice_topics") or "",
        average_rating=row["reputation"]["average_rating"],
        rating_count=row["reputation"]["rating_count"] or 0,
        answered_requests=row["response_answered"],
        unanswered_requests=row["response_unanswered"],
        topic_similarity=row.get("topic_similarity"),
    )


def rank_search_results(rows, filters):
    """Group, score and order search rows. Returns RankedResults, matches first.

    Order: group, then fewest missed filters, then best fit (score, name, id).
    """
    search = ranking.SearchRequest(
        courses=[filters.course_key] if filters.course_key else [],
        topic=filters.text.get("advice_topics", ""),
    )
    placed = []
    for row in rows:
        if not filters.include_unrated and not row["reputation"]["rating_count"]:
            continue
        missed = missed_filters(row, filters)
        group = result_group(row, filters, missed)
        if group is None:
            continue
        scored = ranking.score_advisor(search, advisor_facts(row))
        public = {key: value for key, value in row.items() if key not in INTERNAL_FIELDS}
        public.update(
            score=round(scored.score, 3),
            match_reasons=match_reasons(row, filters, group),
            missed_filters=missed,
        )
        order = (group, len(missed), *ranking.best_fit_order(scored))
        placed.append((order, RankedResult(group=group, public=public)))
    return [result for _, result in sorted(placed, key=lambda pair: pair[0])]


def _whole_number(value, name):
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a whole number.") from None


def page_settings(args):
    """Read limit and offset from the query string. Raises ValueError for invalid values.

    A limit above MAX_PAGE_SIZE is lowered to it rather than rejected.
    """
    limit = _whole_number(args.get("limit", DEFAULT_PAGE_SIZE), "Limit")
    offset = _whole_number(args.get("offset", 0), "Offset")
    if limit < 1:
        raise ValueError("Limit must be at least 1.")
    if offset < 0:
        raise ValueError("Offset cannot be negative.")
    return min(limit, MAX_PAGE_SIZE), offset


def results_page(results, limit, offset):
    """Cut one page of matches and attach the near misses.

    Page numbers only move through "Your matches". The advisors outside the
    filters come as their own short list (the best OUTSIDE_LIMIT of them), the
    same on every page, so the page can show them in a row of their own.
    """
    matches = [result.public for result in results if result.group == YOUR_MATCHES]
    outside = [result.public for result in results if result.group != YOUR_MATCHES]
    return {
        "students": matches[offset:offset + limit],
        "outside_filters": outside[:OUTSIDE_LIMIT],
        "total_matches": len(matches),
        "total_outside_filters": len(outside),
        "limit": limit,
        "offset": offset,
    }
