"""Ranking eval for issue #3: how often was the advisor who accepted a request in our top 3?

    python backend/scripts/ranking_eval.py                       # uses SUPABASE_DB_URL from backend/.env
    python backend/scripts/ranking_eval.py --database-url URL    # any other database

For every accepted or completed request, the eval rebuilds the search the
student would have made (the request's course and advice topic) and ranks the
advisors as search does today. It counts a hit when the advisor who accepted is
in the top 3. To keep the test fair, each case only uses reviews and requests
from before that request was sent.

The same cases are also ranked the old way (advisors who took the exact course,
in A-Z order), so the two numbers can be compared directly. The script only reads.
"""

import sys
from pathlib import Path

# Direct runs put only scripts/ on the path; backend modules live one level up.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from features import ranking

TOP_K = 3


def hits_in_top(positions, k=TOP_K):
    """Count cases whose advisor was within the first k places. Positions start at 0; None means not listed."""
    return sum(1 for position in positions if position is not None and position < k)


def percent(part, whole):
    return 100 * part / whole


def settings_lines(weights=ranking.RANKING_WEIGHTS):
    """Describe the weights and starting values used, so every result records its settings."""
    weight_text = ", ".join(f"{name} {value:g}" for name, value in weights.items())
    return [
        f"    Weights: {weight_text}",
        f"    Starting values: rating {ranking.RATING_STARTING_VALUE:g}/10 worth {ranking.RATING_STARTING_WEIGHT} ratings,"
        f" response {ranking.RESPONSE_STARTING_RATE:.0%} worth {ranking.RESPONSE_STARTING_WEIGHT} requests",
    ]


def ranking_eval_report(new_positions, old_positions, weights=ranking.RANKING_WEIGHTS):
    """Return the report text for the new ranking and the old A-Z order, measured on the same cases."""
    cases = len(new_positions)
    title = f"Ranking eval: was the advisor who accepted in the top {TOP_K}?"
    if cases == 0:
        return f"{title}\n    No accepted requests yet, so there is nothing to measure."
    new_hits, old_hits = hits_in_top(new_positions), hits_in_top(old_positions)
    lines = [
        title,
        f"    Cases: {cases} accepted requests",
        f"    New ranking:   {percent(new_hits, cases):.1f}% in the top {TOP_K} ({new_hits} of {cases})",
        f"    Old A-Z order: {percent(old_hits, cases):.1f}% in the top {TOP_K} ({old_hits} of {cases})",
        *settings_lines(weights),
        "    Each case only used reviews and requests from before that request was sent.",
    ]
    return "\n".join(lines)
