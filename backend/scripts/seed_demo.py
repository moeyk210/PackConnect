"""Fill a database with fictional demo data whose M0 result is known in advance.

    python backend/scripts/seed_demo.py --database-url "postgresql://postgres:postgres@127.0.0.1:54329/packconnect_demo?sslmode=disable"

For a local database the script first prepares it (Supabase stand-in roles and
auth table, then all migrations). It refuses any non-local database unless
--allow-remote is given, so demo data never lands in a shared project by
accident. All people and messages are fictional.

Expected M0 on this data: 9 of 12 accepted connections rated helpful = 75.0%.
"""

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
from werkzeug.security import generate_password_hash

# Direct runs put only scripts/ on the path; backend modules live one level up.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.database import connect_database
from scripts.migrate import apply_migrations

DEMO_DOMAIN = "demo.packconnect.test"
DEMO_PASSWORD = "packconnect-demo-2026"
LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1")

# key: (name, program, year, completed courses, advice topics or None if not advising)
STUDENTS = {
    "maya": ("Maya Okafor", "MS Computer Science", "Second Year", ["CSC 510", "CSC 540"], "Projects, interviews"),
    "jordan": ("Jordan Reyes", "BS Computer Science", "Senior", ["CSC 510", "CSC 316"], "Course workload"),
    "priya": ("Priya Natarajan", "MS Computer Science", "Second Year", ["CSC 510", "CSC 505"], "Exams, research"),
    "ana": ("Ana Kowalski", "MS Computer Science", "First Year", [], None),
    "ben": ("Ben Adeyemi", "BS Computer Science", "Junior", [], None),
    "chloe": ("Chloe Martin", "MS Computer Science", "First Year", [], None),
    "dev": ("Dev Patel", "BS Computer Science", "Junior", [], None),
    "elena": ("Elena Sousa", "MS Computer Science", "First Year", [], None),
    "farid": ("Farid Haddad", "BS Computer Science", "Sophomore", [], None),
    "grace": ("Grace Kim", "MS Computer Science", "First Year", [], None),
    "hugo": ("Hugo Lindqvist", "BS Computer Science", "Junior", [], None),
    "isla": ("Isla Brennan", "MS Computer Science", "First Year", [], None),
}

# Accepted connections: (asker, advisor, status, asker's feedback, advisor's feedback).
# Feedback is (rating 1-10, helpful, comment); None means not rated.
CONNECTIONS = [
    ("ana", "maya", "accepted", (9, True, "Clear plan for the project."), None),
    ("ben", "maya", "completed", (10, True, "Great interview tips."), (3, False, "Ignored by M0.")),
    ("chloe", "maya", "completed", (8, True, ""), None),
    ("dev", "maya", "completed", None, None),
    ("elena", "jordan", "accepted", (7, True, "Helpful workload advice."), None),
    ("farid", "jordan", "completed", (4, False, "Too general for my question."), None),
    ("ana", "jordan", "completed", (8, True, ""), (9, True, "Ignored by M0.")),
    ("ben", "jordan", "completed", (9, True, "Exactly what I needed."), None),
    ("grace", "priya", "accepted", (6, True, ""), None),
    ("hugo", "priya", "completed", (10, True, "Excellent exam strategy."), None),
    ("isla", "priya", "completed", None, None),
    ("chloe", "priya", "completed", (7, True, "Good research pointers."), None),
]

# Requests that never became connections, so M0 must ignore them.
OTHER_REQUESTS = [
    ("elena", "maya", "pending"),
    ("farid", "priya", "declined"),
    ("grace", "maya", "expired"),
    ("hugo", "jordan", "cancelled"),
]

EXPECTED_M0 = {"connections": 12, "rated": 10, "helpful": 9}


def is_local(database_url):
    return conninfo_to_dict(database_url).get("host") in LOCAL_HOSTS


def demo_present(db):
    return db.execute("SELECT EXISTS (SELECT 1 FROM accounts WHERE email LIKE %s) AS present",
                      (f"%@{DEMO_DOMAIN}",)).fetchone()["present"]


def seed_demo(db):
    """Insert the demo data through an open transaction; returns student IDs by key."""
    if demo_present(db):
        raise RuntimeError("Demo data is already present in this database.")
    password_hash = generate_password_hash(DEMO_PASSWORD)
    ids = {}
    for key, (name, program, year, courses, topics) in STUDENTS.items():
        ids[key] = db.execute("""
            INSERT INTO students (name, program, year, bio, advice_topics, willing_to_advise, max_open_requests)
            VALUES (%s, %s, %s, %s, %s, %s, NULL) RETURNING id
        """, (name, program, year, f"Fictional demo student ({program}).", topics or "",
              topics is not None)).fetchone()["id"]
        db.execute("INSERT INTO accounts (student_id, email, password_hash) VALUES (%s, %s, %s)",
                   (ids[key], f"{key}@{DEMO_DOMAIN}", password_hash))
        for course in courses:
            db.execute("INSERT INTO completed_courses (student_id, course_code) VALUES (%s, %s)", (ids[key], course))

    def add_request(asker, advisor, status, expires_at=None):
        return db.execute("""
            INSERT INTO advice_requests (sender_id, recipient_id, course_code, advice_topic, message, status, expires_at)
            VALUES (%s, %s, 'CSC 510', 'Projects', 'Could you share how you approached this course?', %s,
                    COALESCE(%s, now() + interval '7 days'))
            RETURNING id
        """, (ids[asker], ids[advisor], status, expires_at)).fetchone()["id"]

    def add_feedback(request_id, rater, feedback):
        rating, helpful, comment = feedback
        db.execute("INSERT INTO advice_feedback (request_id, rater_id, rating, helpful, comment) VALUES (%s, %s, %s, %s, %s)",
                   (request_id, ids[rater], rating, helpful, comment))

    for asker, advisor, status, asker_feedback, advisor_feedback in CONNECTIONS:
        request_id = add_request(asker, advisor, status)
        for sender, body in ((asker, "Thanks for accepting! Where should I start?"),
                             (advisor, "Happy to help. Start with the project milestones.")):
            db.execute("INSERT INTO chat_messages (request_id, sender_id, body) VALUES (%s, %s, %s)",
                       (request_id, ids[sender], body))
        if asker_feedback:
            add_feedback(request_id, asker, asker_feedback)
        if advisor_feedback:
            add_feedback(request_id, advisor, advisor_feedback)

    past = datetime.now(timezone.utc) - timedelta(days=1)
    for asker, advisor, status in OTHER_REQUESTS:
        add_request(asker, advisor, status, past if status == "expired" else None)
    return ids


def prepare_local(database_url):
    """Give a plain local PostgreSQL the Supabase objects the migrations expect."""
    with psycopg.connect(database_url, autocommit=True) as db:
        for role in ("anon", "authenticated", "service_role"):
            if not db.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,)).fetchone():
                db.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(role)))
        db.execute("CREATE SCHEMA IF NOT EXISTS auth")
        db.execute("CREATE TABLE IF NOT EXISTS auth.users (id uuid PRIMARY KEY, email text, email_confirmed_at timestamptz)")
    apply_migrations(database_url)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Seed fictional PackConnect demo data with a known M0 result.")
    parser.add_argument("--database-url", required=True, help="PostgreSQL connection string to seed")
    parser.add_argument("--allow-remote", action="store_true",
                        help="Allow a non-local database, such as a Supabase project (it must already be migrated)")
    args = parser.parse_args(argv)
    local = is_local(args.database_url)
    if not local and not args.allow_remote:
        print("Refusing to seed a non-local database. Pass --allow-remote if you really mean it.")
        return 2
    try:
        if local:
            prepare_local(args.database_url)
        with connect_database(args.database_url) as db:
            seed_demo(db)
    except RuntimeError as error:
        print(error)
        return 1
    except Exception as error:
        # Connection errors may contain user/host information; never echo a DSN.
        print(f"Seeding failed ({type(error).__name__}). Check the database URL and migrations.")
        return 1
    print(f"Seeded {len(STUDENTS)} fictional students, {len(CONNECTIONS)} accepted connections "
          f"and {len(OTHER_REQUESTS)} other requests.")
    print(f"Sign in as any of them, e.g. maya@{DEMO_DOMAIN}, with password {DEMO_PASSWORD}")
    print("Expected M0: 9 of 12 accepted connections rated helpful (75.0%).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
