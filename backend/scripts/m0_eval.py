"""M0 instrument for advice outcomes: how many accepted connections were rated helpful.

    python backend/scripts/m0_eval.py                       # uses SUPABASE_DB_URL from backend/.env
    python backend/scripts/m0_eval.py --database-url URL    # any other database
    python backend/scripts/m0_eval.py --check               # exit 1 unless the claim is met

Claim: more than 70% of accepted connections are rated helpful by the student
who asked. Connections are requests with status accepted or completed; only
the asking student's feedback counts. Unrated connections count against the
claim, so the headline number is deliberately strict. The script only reads.
"""

import argparse
import os
import sys
from contextlib import contextmanager
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row

TARGET_PERCENT = 70

M0_SQL = """
    SELECT count(*) AS connections,
           count(f.id) AS rated,
           count(f.id) FILTER (WHERE f.helpful) AS helpful
    FROM advice_requests r
    LEFT JOIN advice_feedback f ON f.request_id = r.id AND f.rater_id = r.sender_id
    WHERE r.status IN ('accepted', 'completed')
"""


def m0_counts(db):
    return dict(db.execute(M0_SQL).fetchone())


def percent(part, whole):
    return 100 * part / whole


def m0_report(counts, target=TARGET_PERCENT):
    """Return (report text, whether the claim is met) for counts from m0_counts."""
    connections, rated, helpful = counts["connections"], counts["rated"], counts["helpful"]
    claim = f"Claim: more than {target}% of accepted connections rated helpful"
    if connections == 0:
        return f"M0: no accepted connections yet, so there is nothing to measure.\n    {claim} -> NOT MET", False
    score = percent(helpful, connections)
    met = score > target
    lines = [
        f"M0: {score:.1f}% of accepted connections were rated helpful ({helpful} of {connections})",
        f"    Rated: {rated} of {connections} connections ({percent(rated, connections):.1f}%)"
        + (f"; {helpful} of {rated} ratings say helpful ({percent(helpful, rated):.1f}%)" if rated else ""),
        f"    {claim} -> {'PASS' if met else 'FAIL'}",
    ]
    return "\n".join(lines), met


@contextmanager
def read_only_connection(database_url):
    parameters = conninfo_to_dict(database_url)
    parameters.setdefault("sslmode", "require")
    parameters.setdefault("connect_timeout", "10")
    with psycopg.connect(**parameters, row_factory=dict_row) as db:
        db.read_only = True
        yield db


def main(argv=None):
    parser = argparse.ArgumentParser(description="Report the advice-outcomes M0 number.")
    parser.add_argument("--database-url", help="PostgreSQL connection string (default: SUPABASE_DB_URL)")
    parser.add_argument("--target", type=float, default=TARGET_PERCENT, help="claim threshold in percent")
    parser.add_argument("--check", action="store_true", help="exit with status 1 unless the claim is met")
    args = parser.parse_args(argv)
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    database_url = args.database_url or os.getenv("SUPABASE_DB_URL")
    if not database_url:
        print("Set SUPABASE_DB_URL in backend/.env or pass --database-url.")
        return 2
    try:
        with read_only_connection(database_url) as db:
            counts = m0_counts(db)
    except Exception as error:
        # Connection errors may contain user/host information; never echo a DSN.
        print(f"M0 eval failed ({type(error).__name__}). Check the database URL and migrations.")
        return 2
    target = int(args.target) if args.target.is_integer() else args.target
    report, met = m0_report(counts, target)
    print(report)
    return 1 if args.check and not met else 0


if __name__ == "__main__":
    sys.exit(main())
