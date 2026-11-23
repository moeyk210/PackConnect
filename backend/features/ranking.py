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


def _words(text):
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def _meaningful_words(text):
    return {_base_word(word) for word in _words(text) if word not in IGNORED_WORDS}


def matching_topic_words(asked_topic, advisor_topics):
    """Return the student's own topic words that the advisor's topics cover, in the order typed.

    Used to explain a match (for example "Advises on interview prep") with the
    same word rules that produce the topic score.
    """
    covered = _meaningful_words(advisor_topics)
    matched = []
    for word in _words(asked_topic):
        if word not in IGNORED_WORDS and _base_word(word) in covered and word not in matched:
            matched.append(word)
    return matched


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


# Meaning similarity between two topic fingerprints (see core/embeddings.py)
# bunches up: unrelated topics still score about 0.55 and the same idea about
# 0.80 or more. These two points stretch it to the 0-1 scale the factors use.
MEANING_NO_MATCH = 0.55
MEANING_STRONG_MATCH = 0.80

# A topic counts as meeting the student's topic filter when its stretched
# meaning match reaches this value, even without the exact words.
MEANING_FILTER_THRESHOLD = 0.5


def meaning_match(similarity):
    """Stretch a raw meaning similarity to 0-1. Returns None when there is no similarity."""
    if similarity is None:
        return None
    stretched = (similarity - MEANING_NO_MATCH) / (MEANING_STRONG_MATCH - MEANING_NO_MATCH)
    return min(1.0, max(0.0, stretched))


def combined_topic_match(asked_topic, advisor_topics, similarity=None):
    """Topic factor using both shared words and meaning: whichever is higher.

    Shared words catch exact terms; meaning catches different wording for the
    same idea ("interview prep" and "interviews"). Without a similarity (no
    fingerprints stored yet), this is the shared-words match alone.
    """
    words = topic_match(asked_topic, advisor_topics)
    if words is None:
        return None
    meaning = meaning_match(similarity)
    return words if meaning is None else max(words, meaning)


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
    # Meaning similarity between the advisor's topics and the searched topic,
    # or None when it is not known (see combined_topic_match).
    topic_similarity: float | None = None


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
        "topic": combined_topic_match(search.topic, advisor.advice_topics, advisor.topic_similarity),
        "rating": rating_score(advisor.average_rating, advisor.rating_count),
        "response": response_score(advisor.answered_requests, advisor.unanswered_requests),
    }
    applicable = {name: value for name, value in factors.items() if value is not None}
    total_weight = sum(weights[name] for name in applicable)
    score = sum(weights[name] * value for name, value in applicable.items()) / total_weight
    return AdvisorScore(advisor=advisor, score=score, factors=factors)


# Scores are rounded to this many decimal places before comparing, so two scores
# that are equal on paper but differ by a tiny computer rounding error still tie.
SCORE_PRECISION = 6


def best_fit_order(result):
    """Sort key for an AdvisorScore: highest score first, then name, then id.

    Ties are broken by name and then by id, so the order is always the same for
    the same data. Splitting results into pages relies on that: without a fixed
    order, one advisor could appear on two pages while another is skipped.
    """
    return (-round(result.score, SCORE_PRECISION), result.advisor.name.lower(), result.advisor.id)


def rank_advisors(search, advisors, weights=RANKING_WEIGHTS):
    """Score every advisor and return them best fit first (see best_fit_order)."""
    scored = [score_advisor(search, advisor, weights) for advisor in advisors]
    return sorted(scored, key=best_fit_order)
