"""Load the checked-in course catalog: python backend/import_catalog.py [file.csv].

Safe to re-run: rows are upserted by course code, so a second run adds nothing.
Malformed rows are skipped and reported with their line number.
"""

import csv
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

from core.database import connect_database


DEFAULT_CSV = Path(__file__).parent / "data" / "nc_state_courses.csv"
REQUIRED_COLUMNS = ("code", "title", "department", "description")
# Letters, optional space, three digits, optional letter: "csc510" -> "CSC 510".
# Story 3.2 will replace this with the shared normalize_code() helper.
CODE_PATTERN = re.compile(r"^([A-Z]{2,4})\s*([0-9]{3}[A-Z]?)$")

UPSERT = """
    INSERT INTO courses (code, title, department, description)
    VALUES (%(code)s, %(title)s, %(department)s, %(description)s)
    ON CONFLICT (code) DO UPDATE SET
        title = EXCLUDED.title,
        department = EXCLUDED.department,
        description = EXCLUDED.description,
        updated_at = now()
    WHERE (courses.title, courses.department, courses.description)
        IS DISTINCT FROM (EXCLUDED.title, EXCLUDED.department, EXCLUDED.description)
    RETURNING (xmax = 0) AS inserted
"""


def canonical_code(raw):
    match = CODE_PATTERN.match((raw or "").strip().upper())
    return f"{match.group(1)} {match.group(2)}" if match else None


def clean_row(row):
    """Return (course dict, None) for a good row or (None, reason) for a bad one."""
    if None in row:
        return None, "too many columns"
    if any(row[column] is None for column in REQUIRED_COLUMNS):
        return None, "too few columns"
    code = canonical_code(row["code"])
    if not code:
        return None, f"invalid course code {row['code']!r}"
    title = row["title"].strip()
    department = row["department"].strip()
    if not title:
        return None, "missing title"
    if not department:
        return None, "missing department"
    return {"code": code, "title": title, "department": department,
            "description": row["description"].strip()}, None


def import_catalog(db, csv_path=DEFAULT_CSV):
    """Upsert every valid row in one transaction; return counts and skipped rows."""
    summary = {"inserted": 0, "updated": 0, "unchanged": 0, "skipped": []}
    seen = set()
    with open(csv_path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        missing = [name for name in REQUIRED_COLUMNS if name not in (reader.fieldnames or [])]
        if missing:
            raise ValueError("CSV is missing column(s): " + ", ".join(missing))
        for row in reader:
            course, problem = clean_row(row)
            if course and course["code"] in seen:
                course, problem = None, f"duplicate course code {course['code']}"
            if problem:
                summary["skipped"].append((reader.line_num, problem))
                continue
            seen.add(course["code"])
            result = db.execute(UPSERT, course).fetchone()
            if result is None:
                summary["unchanged"] += 1
            elif result["inserted"]:
                summary["inserted"] += 1
            else:
                summary["updated"] += 1
    return summary


def main(argv):
    load_dotenv(Path(__file__).parent / ".env")
    path = Path(argv[1]) if len(argv) > 1 else DEFAULT_CSV
    try:
        with connect_database(os.getenv("SUPABASE_DB_URL")) as db:
            summary = import_catalog(db, path)
    except (OSError, ValueError) as exc:
        print(f"Import failed: {exc}")
        return 1
    except Exception as exc:
        # Connection errors may contain user/host information; never echo a DSN.
        print(f"Import failed ({type(exc).__name__}). Check configuration and run migrate.py first.")
        return 1
    print(f"Inserted {summary['inserted']}, updated {summary['updated']}, "
          f"unchanged {summary['unchanged']}, skipped {len(summary['skipped'])}.")
    for line, reason in summary["skipped"]:
        print(f"  skipped line {line}: {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))