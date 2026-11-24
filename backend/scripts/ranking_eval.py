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

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Direct runs put only scripts/ on the path; backend modules live one level up.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.identity import registered_student_sql
from features import ranking
from features.advisor_candidates import course_key_sql, fetch_advisor_rows, same_subject_condition
from features.search_ranking import SearchFilters, rank_search_results
from scripts.m0_eval import read_only_connection

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


# Every accepted connection is one case, oldest first.
CASES_SQL = f"""
    SELECT r.id, r.sender_id, r.recipient_id, r.advice_topic, r.created_at,
           {course_key_sql("r.course_code")} AS course_key
    FROM advice_requests r
    WHERE r.status IN ('accepted', 'completed')
    ORDER BY r.created_at, r.id
"""


def advisors_at_the_time(db, case):
    """Advisors the student could have found, with reputation as it stood when the request was sent.

    Availability history is not stored, so today's availability is ignored:
    every registered student with a course in the subject counts, except the asker.
    """
    subject_sql, subject_parameter = same_subject_condition(case["course_key"])
    conditions = [registered_student_sql(), "s.id <> %s", subject_sql]
    return fetch_advisor_rows(db, conditions, [case["sender_id"], subject_parameter], as_of=case["created_at"])


def position_of(advisor_id, ordered_ids):
    """Place of the advisor in an ordered list (0 is first), or None if they are not in it."""
    return ordered_ids.index(advisor_id) if advisor_id in ordered_ids else None


def new_ranking_position(case, rows):
    """Where today's search ranking puts the advisor who accepted: matches first, then outside the filters."""
    topic = (case["advice_topic"] or "").strip()
    filters = SearchFilters(course_key=case["course_key"], text={"advice_topics": topic} if topic else {})
    ordered = [result.public["id"] for result in rank_search_results(rows, filters)]
    return position_of(case["recipient_id"], ordered)


def old_order_position(case, rows):
    """Where the old search put them: only advisors who took the exact course, in A-Z order."""
    exact = [row for row in rows if case["course_key"] in row["course_keys"]]
    ordered = [row["id"] for row in sorted(exact, key=lambda row: (row["name"].lower(), row["id"]))]
    return position_of(case["recipient_id"], ordered)


def evaluate(db):
    """Return (new ranking positions, old order positions), one pair per accepted request."""
    new_positions, old_positions = [], []
    for case in db.execute(CASES_SQL).fetchall():
        rows = advisors_at_the_time(db, case)
        new_positions.append(new_ranking_position(case, rows))
        old_positions.append(old_order_position(case, rows))
    return new_positions, old_positions


def main(argv=None):
    parser = argparse.ArgumentParser(description="Report how often ranking puts the eventual advisor in the top 3.")
    parser.add_argument("--database-url", help="PostgreSQL connection string (default: SUPABASE_DB_URL)")
    args = parser.parse_args(argv)
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    database_url = args.database_url or os.getenv("SUPABASE_DB_URL")
    if not database_url:
        print("Set SUPABASE_DB_URL in backend/.env or pass --database-url.")
        return 2
    try:
        with read_only_connection(database_url) as db:
            new_positions, old_positions = evaluate(db)
    except Exception as error:
        # Connection errors may contain user/host information; never echo a DSN.
        print(f"Ranking eval failed ({type(error).__name__}). Check the database URL and migrations.")
        return 2
    print(ranking_eval_report(new_positions, old_positions))
    return 0


if __name__ == "__main__":
    sys.exit(main())
