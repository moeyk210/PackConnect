"""Score how well an advisor fits a student's search, so results can be sorted best fit first.

The score is built from four factors. Each one answers a single question with a
number from 0 (worst) to 1 (best):

- course:   Did the advisor complete the courses the student asked about?
- topic:    Do the advisor's advice topics cover what the student asked about?
- rating:   How well do students rate this advisor's advice?
- response: How often does this advisor answer the requests they receive?

The final score is a weighted average of those four numbers, using RANKING_WEIGHTS.

Nothing in this module reads the database or the web request. Callers pass in
plain values, which keeps every rule here easy to test and easy to tune.
"""

import re
from dataclasses import dataclass, field

# How much each factor counts toward the final score. These are the only
# weights in the app: change them here and every ranked list follows.
# They do not need to add up to 1, because the final score divides by their total.
RANKING_WEIGHTS = {
    "course": 0.35,
    "topic": 0.30,
    "rating": 0.20,
    "response": 0.15,
}

# Ratings run from 1 to 10 (see the advice_feedback table).
LOWEST_RATING = 1
HIGHEST_RATING = 10

# New advisors have little or no history, so a single rating or a single answered
# request would swing their score wildly. Instead, every advisor starts with a few
# imaginary "typical" results, and their real results gradually outweigh them.
# This is known as a Bayesian average. Each pair below sets:
#   - the typical value an advisor is assumed to have before we know anything, and
#   - how many real results that assumption is worth.
RATING_STARTING_VALUE = 7.0
RATING_STARTING_WEIGHT = 3

RESPONSE_STARTING_RATE = 0.8
RESPONSE_STARTING_WEIGHT = 3


def course_match(wanted_courses, completed_courses):
    """Return the share of the wanted courses that the advisor has completed.

    Returns None when the student did not ask about any course, because the
    factor then says nothing about fit and should be left out of the score.
    Course codes must already be written the same way (for example "CSC 510");
    the caller cleans them up with the app's shared course-code helper.
    """
    wanted = set(wanted_courses)
    if not wanted:
        return None
    return len(wanted & set(completed_courses)) / len(wanted)


# Common words that carry no meaning on their own, so they never count as a match.
IGNORED_WORDS = {
    "a", "an", "and", "the", "for", "of", "to", "in", "on", "with", "my", "about", "help", "advice",
}


def _base_word(word):
    """Trim common plural endings so "interviews" matches "interview"."""
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 3 and word.endswith(("ches", "shes", "sses", "xes")):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _meaningful_words(text):
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {_base_word(word) for word in words if word not in IGNORED_WORDS}


def topic_match(asked_topic, advisor_topics):
    """Return the share of the student's topic words that the advisor's topics cover.

    Measuring coverage of the student's words (rather than overlap of both lists)
    means an advisor is not penalized for listing many topics.
    Returns None when the student did not ask about a topic.
    """
    asked = _meaningful_words(asked_topic)
    if not asked:
        return None
    return len(asked & _meaningful_words(advisor_topics)) / len(asked)


def _blend_with_starting_value(observed_total, observed_count, starting_value, starting_weight):
    """Average real results together with a few imaginary typical ones (a Bayesian average).

    With no real results this returns the starting value. As real results pile
    up, they outweigh the starting value and the average moves toward them.
    """
    return (starting_value * starting_weight + observed_total) / (starting_weight + observed_count)


def rating_score(average_rating, rating_count):
    """Return the advisor's rating as a number from 0 to 1, adjusted for how many ratings they have.

    Every rating counts, including low ones: they pull the score down as they
    should. But one rating is weak evidence, so a single 10 does not beat twenty 9s.
    An advisor with no ratings gets the starting value instead of zero.
    """
    count = rating_count or 0
    total = (average_rating or 0) * count
    blended = _blend_with_starting_value(total, count, RATING_STARTING_VALUE, RATING_STARTING_WEIGHT)
    return (blended - LOWEST_RATING) / (HIGHEST_RATING - LOWEST_RATING)


def response_score(answered_requests, unanswered_requests):
    """Return how reliably the advisor answers requests, from 0 to 1.

    Answered requests were accepted, declined, or completed. Unanswered ones
    expired without a reply. These counts follow the same rules as the advisor
    reputation stats. Like ratings, a short history is blended with the starting
    rate, so answering 1 of 1 requests does not beat answering 48 of 50.
    """
    answered = answered_requests or 0
    total = answered + (unanswered_requests or 0)
    return _blend_with_starting_value(answered, total, RESPONSE_STARTING_RATE, RESPONSE_STARTING_WEIGHT)


@dataclass(frozen=True)
class SearchRequest:
    """What the student is looking for."""

    courses: list = field(default_factory=list)
    topic: str = ""


@dataclass(frozen=True)
class AdvisorFacts:
    """What we know about one advisor, gathered by the caller."""

    id: int
    name: str
    completed_courses: list = field(default_factory=list)
    advice_topics: str = ""
    average_rating: float | None = None
    rating_count: int = 0
    answered_requests: int = 0
    unanswered_requests: int = 0


@dataclass(frozen=True)
class AdvisorScore:
    """An advisor's final score plus the per-factor numbers that produced it.

    The per-factor numbers are kept so the app can explain each ranking
    (for example "Completed CSC 510") from the same values used to score it.
    A factor set to None did not apply to this search and was left out.
    """

    advisor: AdvisorFacts
    score: float
    factors: dict


def score_advisor(search, advisor, weights=RANKING_WEIGHTS):
    """Combine the four factors into one score from 0 to 1 using a weighted average.

    Course and topic only count when the student asked about them. Rating and
    response always count, because they fall back to starting values.
    """
    factors = {
        "course": course_match(search.courses, advisor.completed_courses),
        "topic": topic_match(search.topic, advisor.advice_topics),
        "rating": rating_score(advisor.average_rating, advisor.rating_count),
        "response": response_score(advisor.answered_requests, advisor.unanswered_requests),
    }
    applicable = {name: value for name, value in factors.items() if value is not None}
    total_weight = sum(weights[name] for name in applicable)
    score = sum(weights[name] * value for name, value in applicable.items()) / total_weight
    return AdvisorScore(advisor=advisor, score=score, factors=factors)
