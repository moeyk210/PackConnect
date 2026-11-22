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
