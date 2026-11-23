"""Create topic fingerprints for students who have advice topics but no fingerprint yet.

    python backend/scripts/backfill_topic_embeddings.py --database-url URL
    python backend/scripts/backfill_topic_embeddings.py --database-url URL --all            # redo every one
    python backend/scripts/backfill_topic_embeddings.py --allow-remote                      # SUPABASE_DB_URL

New fingerprints are made whenever a profile is saved. This fills in profiles
saved before meaning-based matching existed, and redoes all of them after a
model change (--all). Only students.topic_embedding is written. It refuses any
non-local database unless --allow-remote is given, so the shared project is
never changed by accident.
"""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Direct runs put only scripts/ on the path; backend modules live one level up.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.database import connect_database
from core.embeddings import TopicEmbedder, vector_literal
from scripts.seed_demo import is_local

# How many profiles are sent to the model at once.
BATCH_SIZE = 64


def backfill_topic_embeddings(db, embedder, redo_all=False):
    """Fill in fingerprints through an open transaction. Returns how many were written."""
    missing_only = "" if redo_all else "AND topic_embedding IS NULL"
    rows = db.execute(f"""
        SELECT id, advice_topics FROM students
        WHERE btrim(coalesce(advice_topics, '')) <> '' {missing_only}
        ORDER BY id
    """).fetchall()
    for start in range(0, len(rows), BATCH_SIZE):
        batch = rows[start:start + BATCH_SIZE]
        vectors = embedder.embed([row["advice_topics"].strip() for row in batch])
        for row, vector in zip(batch, vectors):
            db.execute("UPDATE students SET topic_embedding = %s::extensions.vector WHERE id = %s",
                       (vector_literal(vector), row["id"]))
    return len(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Create missing topic fingerprints.")
    parser.add_argument("--database-url", help="PostgreSQL connection string (default: SUPABASE_DB_URL)")
    parser.add_argument("--all", action="store_true", help="redo every fingerprint, not only missing ones")
    parser.add_argument("--allow-remote", action="store_true",
                        help="allow a non-local database, such as the Supabase project")
    args = parser.parse_args(argv)
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    database_url = args.database_url or os.getenv("SUPABASE_DB_URL")
    if not database_url:
        print("Set SUPABASE_DB_URL in backend/.env or pass --database-url.")
        return 2
    if not is_local(database_url) and not args.allow_remote:
        print("Refusing to change a non-local database. Pass --allow-remote if you really mean it.")
        return 2
    try:
        with connect_database(database_url) as db:
            written = backfill_topic_embeddings(db, TopicEmbedder(), redo_all=args.all)
    except Exception as error:
        # Connection errors may contain user/host information; never echo a DSN.
        print(f"Backfill failed ({type(error).__name__}). Check the database URL and migrations.")
        return 1
    print(f"Created {written} topic fingerprint{'' if written == 1 else 's'}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
