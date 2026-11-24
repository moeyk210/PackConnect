"""Fill a local database with varied fictional students for trying search, filters and course pages.

    python backend/scripts/seed_dev_data.py --database-url "postgresql://postgres:postgres@127.0.0.1:54331/packconnect_dev?sslmode=disable"

The other seeds each answer one question: seed_demo.py has a known M0 result,
and seed_ranking_eval.py simulates a semester for the ranking eval. This one is
for exploring the app: 22 advisors across many CSC courses plus a few other
subjects, with different programs, years, skills, advice topics, availability
states and review histories, and 8 students who are not advising.

Every person is written out by hand, so tests can check exact search results
(tests/test_seed_dev_data.py). The script also loads the course catalog and,
unless --skip-embeddings is given, creates topic fingerprints with the local
model. It refuses non-local databases: the reviews here are made up and would
distort real reputations.
"""

import argparse
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from werkzeug.security import generate_password_hash

# Direct runs put only scripts/ on the path; backend modules live one level up.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.database import connect_database
from scripts.seed_demo import is_local, prepare_local

DEV_DOMAIN = "dev.packconnect.test"
DEV_PASSWORD = "packconnect-dev-2026"

# Availability settings. "open" is the registration default of 5 open requests.
OPEN, UNLIMITED, PAUSED, FULL = "open", "unlimited", "paused", "full"
MAX_OPEN_REQUESTS = {OPEN: 5, UNLIMITED: None, PAUSED: 5, FULL: 1}
PAUSE_DAYS = 30


@dataclass(frozen=True)
class Person:
    name: str
    program: str
    year: str
    completed: list
    current: list = field(default_factory=list)
    skills: str = ""
    # None means the person is not advising.
    topics: str | None = None
    availability: str = OPEN


ADVISORS = {
    "ava": Person("Ava Thompson", "MS Computer Science", "Second Year", ["CSC 510", "CSC 540", "CSC 316"],
                  skills="Python, Django, PostgreSQL", topics="Projects, team workflow, Git"),
    "marcus": Person("Marcus Bell", "BS Computer Science", "Senior", ["CSC 216", "CSC 316", "CSC 326"],
                     skills="Java, Spring, JUnit", topics="Exams, study plans"),
    "lena": Person("Lena Park", "MS Computer Science", "First Year", ["CSC 510", "CSC 517"],
                   skills="React, TypeScript, Node.js", topics="Interview prep, resumes"),
    "omar": Person("Omar Haddad", "PhD Computer Science", "Third Year", ["CSC 411", "CSC 505", "CSC 520", "CSC 522"],
                   skills="Machine learning, PyTorch, Python", topics="Research, reading papers"),
    "sofia": Person("Sofia Rossi", "MS Computer Science", "Second Year", ["CSC 431", "CSC 440", "CSC 540"],
                    skills="SQL, data modeling, Tableau", topics="Course workload, time management"),
    "kenji": Person("Kenji Watanabe", "BS Computer Science", "Junior", ["CSC 230", "CSC 236", "CSC 246"],
                    skills="C, Linux, assembly", topics="Debugging, office hours"),
    "priyanka": Person("Priyanka Rao", "MS Computer Science", "Second Year", ["CSC 401", "CSC 405", "CSC 515"],
                       skills="Security, networking, Wireshark", topics="Internships, career fairs"),
    "diego": Person("Diego Alvarez", "MS Computer Engineering", "Second Year", ["CSC 510", "CSC 547"],
                    skills="AWS, Docker, Kubernetes", topics="Projects, cloud deployment"),
    "hannah": Person("Hannah Schmidt", "BS Mathematics", "Senior", ["CSC 226", "CSC 333", "MA 305"],
                     skills="Discrete math, proofs, LaTeX", topics="Exams, problem sets"),
    "tariq": Person("Tariq Mensah", "MS Computer Science", "First Year", ["CSC 510"],
                    skills="Python, pandas", topics="Group work, communication"),
    "nora": Person("Nora Lindqvist", "MS Statistics", "Second Year", ["CSC 522", "ST 512"],
                   skills="R, regression, SAS", topics="Exams, study groups"),
    "wei": Person("Wei Zhang", "PhD Computer Science", "Second Year", ["CSC 501", "CSC 505", "CSC 512"],
                  skills="Compilers, LLVM, C++", topics="Research, grad school applications"),
    "fatima": Person("Fatima Diallo", "BS Computer Science", "Junior", ["CSC 216", "CSC 316"],
                     skills="Python, Flask", topics="Projects, interview prep", availability=FULL),
    "liam": Person("Liam O'Brien", "MS Computer Science", "Second Year", ["CSC 510", "CSC 547"],
                   skills="Go, distributed systems", topics="Projects, interviews", availability=PAUSED),
    "isabela": Person("Isabela Costa", "MS Computer Science", "First Year", ["CSC 510", "CSC 591"], ["CSC 522"],
                      skills="Unity, C#, game design", topics="Portfolio reviews, projects", availability=UNLIMITED),
    "aarav": Person("Aarav Shah", "BS Computer Science", "Sophomore", ["CSC 116", "CSC 216"],
                    skills="Java", topics="Study plans, course selection"),
    "zoe": Person("Zoe Martin", "MS Computer Science", "Second Year", ["CSC 421", "CSC 510", "CSC 520"],
                  skills="NLP, transformers, Python", topics="Research, interview prep"),
    "mateo": Person("Mateo Silva", "BS Computer Engineering", "Senior", ["CSC 453", "ECE 306"],
                    skills="Embedded C, IoT, Raspberry Pi", topics="Projects, lab reports"),
    "amara": Person("Amara Okeke", "MS Computer Science", "Second Year", ["CSC 510", "CSC 555"],
                    skills="Accessibility, UX research, Figma", topics="Resumes, portfolio reviews"),
    "jonas": Person("Jonas Weber", "MS Computer Science", "Second Year", ["CSC 510"],
                    skills="Python", topics="Projects"),
    "noemie": Person("Noémie Dubois", "MS Computer Science", "First Year", ["CSC 246", "CSC 501"],
                     skills="Rust, systems programming", topics="Debugging, exams"),
    # Took CSC 510 but has switched advising off.
    "chen": Person("Chen Wu", "MS Computer Science", "Second Year", ["CSC 510"], skills="Java"),
}

# Students who are not advising. Their current courses drive "Recommended for you".
STUDENTS = {
    "riley": Person("Riley Brooks", "BS Computer Science", "Sophomore", ["CSC 116"], ["CSC 216", "CSC 226"]),
    "sam": Person("Sam Okafor", "MS Computer Science", "First Year", [], ["CSC 510", "CSC 540"]),
    "jamie": Person("Jamie Lee", "MS Computer Science", "First Year", ["CSC 510"], ["CSC 520", "CSC 522"]),
    "taylor": Person("Taylor Nguyen", "BS Computer Science", "Junior", ["CSC 216"], ["CSC 230", "CSC 316"]),
    "alex": Person("Alex Romero", "MS Computer Science", "Second Year", ["CSC 316", "CSC 510"], ["CSC 547"]),
    "casey": Person("Casey Patel", "BS Computer Science", "Freshman", [], ["CSC 116"]),
    "drew": Person("Drew Kim", "MS Statistics", "First Year", [], ["CSC 522"]),
    "jordan": Person("Jordan Ellis", "BS Computer Science", "Senior", ["CSC 316", "CSC 326", "CSC 510"]),
}

# A profile with no login account. It must never appear in search or receive requests.
UNREGISTERED = Person("Robin Hayes", "MS Computer Science", "Second Year", ["CSC 510"],
                      skills="Python", topics="Projects")

# (blocker, blocked)
BLOCKS = [("taylor", "kenji")]

# Past requests: (asker, advisor, course, topic, status, feedback). Feedback is the
# asker's (rating 1-10, helpful, workload 1-5 or None, difficulty 1-5 or None), or None.
HISTORY = [
    ("alex", "ava", "CSC 510", "Projects", "completed", (10, True, 4, 4)),
    ("jamie", "ava", "CSC 510", "Projects", "completed", (9, True, 5, 4)),
    ("jordan", "ava", "CSC 510", "Team workflow", "completed", (9, True, 3, 3)),
    ("sam", "ava", "CSC 540", "Projects", "completed", (10, True, None, None)),
    ("jordan", "marcus", "CSC 316", "Exams", "completed", (8, True, 4, 5)),
    ("alex", "marcus", "CSC 316", "Exams", "completed", (7, True, 3, 4)),
    ("riley", "marcus", "CSC 216", "Study plans", "declined", None),
    ("sam", "lena", "CSC 510", "Interview prep", "completed", (8, True, None, None)),
    ("jamie", "lena", "CSC 517", "Resumes", "completed", (9, True, None, None)),
    ("jamie", "zoe", "CSC 520", "Research", "completed", (3, False, None, None)),
    ("sam", "zoe", "CSC 510", "Interview prep", "completed", (4, False, None, None)),
    ("alex", "zoe", "CSC 510", "Interview prep", "completed", (2, False, 2, 5)),
    ("jamie", "omar", "CSC 522", "Research", "completed", (10, True, None, None)),
    ("sam", "sofia", "CSC 540", "Course workload", "completed", (9, True, None, None)),
    ("alex", "sofia", "CSC 540", "Time management", "completed", (8, True, None, None)),
    ("jordan", "priyanka", "CSC 405", "Internships", "completed", (9, True, None, None)),
    # Jonas never answers: every request to him expired.
    ("riley", "jonas", "CSC 510", "Projects", "expired", None),
    ("casey", "jonas", "CSC 510", "Projects", "expired", None),
    ("drew", "jonas", "CSC 510", "Projects", "expired", None),
    ("taylor", "jonas", "CSC 510", "Projects", "expired", None),
    # Still open: Fatima's one accepted connection fills her limit of 1, and Diego has a request waiting.
    ("taylor", "fatima", "CSC 316", "Interview prep", "accepted", None),
    ("alex", "diego", "CSC 547", "Cloud deployment", "pending", None),
]

EXPECTED_COUNTS = {"advisors": len(ADVISORS), "students": len(STUDENTS), "requests": len(HISTORY),
                   "reviews": sum(feedback is not None for *_, feedback in HISTORY)}


def dev_data_present(db):
    return db.execute("SELECT EXISTS (SELECT 1 FROM accounts WHERE email LIKE %s) AS present",
                      (f"%@{DEV_DOMAIN}",)).fetchone()["present"]


def add_person(db, person, password_hash, key=None):
    """Insert one profile with its courses, and a login account when a key is given."""
    availability = MAX_OPEN_REQUESTS[person.availability]
    pause_until = date.today() + timedelta(days=PAUSE_DAYS) if person.availability == PAUSED else None
    student_id = db.execute("""
        INSERT INTO students (name, program, year, bio, skills, advice_topics, willing_to_advise,
                              max_open_requests, pause_until)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
    """, (person.name, person.program, person.year, f"Fictional student ({person.program}).", person.skills,
          person.topics or "", person.topics is not None, availability, pause_until)).fetchone()["id"]
    if key is not None:
        db.execute("INSERT INTO accounts (student_id, email, password_hash) VALUES (%s, %s, %s)",
                   (student_id, f"{key}@{DEV_DOMAIN}", password_hash))
    for table, courses in (("completed_courses", person.completed), ("current_courses", person.current)):
        for course in courses:
            db.execute(f"INSERT INTO {table} (student_id, course_code) VALUES (%s, %s)", (student_id, course))
    return student_id


def seed_dev_data(db):
    """Insert the data through an open transaction. Returns student IDs by key ("robin" is unregistered)."""
    if dev_data_present(db):
        raise RuntimeError("Development seed data is already present in this database.")
    password_hash = generate_password_hash(DEV_PASSWORD)
    ids = {key: add_person(db, person, password_hash, key) for key, person in {**ADVISORS, **STUDENTS}.items()}
    ids["robin"] = add_person(db, UNREGISTERED, password_hash)
    for blocker, blocked in BLOCKS:
        db.execute("INSERT INTO student_blocks (blocker_id, blocked_id) VALUES (%s, %s)", (ids[blocker], ids[blocked]))

    now = datetime.now(timezone.utc)
    for index, (asker, advisor, course, topic, status, feedback) in enumerate(HISTORY):
        sent = now - timedelta(days=60 - index)
        # Expired requests ran out a week after they were sent; open ones have time left.
        expires = sent + timedelta(days=7) if status == "expired" else now + timedelta(days=7)
        request_id = db.execute("""
            INSERT INTO advice_requests
                (sender_id, recipient_id, course_code, advice_topic, message, status, created_at, expires_at)
            VALUES (%s, %s, %s, %s, 'Could you share how you approached this course?', %s, %s, %s) RETURNING id
        """, (ids[asker], ids[advisor], course, topic, status, sent, expires)).fetchone()["id"]
        if status in ("accepted", "completed"):
            for sender, body in ((asker, "Thanks for accepting! Where should I start?"),
                                 (advisor, "Happy to help. Start with the first project milestone.")):
                db.execute("INSERT INTO chat_messages (request_id, sender_id, body, created_at) VALUES (%s, %s, %s, %s)",
                           (request_id, ids[sender], body, sent + timedelta(hours=2)))
        if feedback:
            rating, helpful, workload, difficulty = feedback
            db.execute("""
                INSERT INTO advice_feedback
                    (request_id, rater_id, rating, helpful, workload_rating, difficulty_rating, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (request_id, ids[asker], rating, helpful, workload, difficulty, sent + timedelta(days=3)))
    return ids


def main(argv=None):
    parser = argparse.ArgumentParser(description="Seed varied fictional PackConnect data for local development.")
    parser.add_argument("--database-url", required=True, help="Local PostgreSQL connection string to seed")
    parser.add_argument("--skip-embeddings", action="store_true",
                        help="Do not create topic fingerprints (topics then match by shared words only)")
    args = parser.parse_args(argv)
    if not is_local(args.database_url):
        print("Refusing to seed a non-local database. Use a dedicated local database for development data.")
        return 2
    try:
        prepare_local(args.database_url)
        with connect_database(args.database_url) as db:
            seed_dev_data(db)
            # Imported here so --help works without the catalog or model dependencies.
            from import_catalog import import_catalog
            catalog = import_catalog(db)
            fingerprints = None
            if not args.skip_embeddings:
                from core.embeddings import TopicEmbedder
                from scripts.backfill_topic_embeddings import backfill_topic_embeddings
                fingerprints = backfill_topic_embeddings(db, TopicEmbedder())
    except RuntimeError as error:
        print(error)
        return 1
    except Exception as error:
        # Connection errors may contain user/host information; never echo a DSN.
        print(f"Seeding failed ({type(error).__name__}). Check the database URL.")
        return 1
    print(f"Seeded {EXPECTED_COUNTS['advisors']} advisors, {EXPECTED_COUNTS['students']} students, "
          f"{EXPECTED_COUNTS['requests']} requests and {EXPECTED_COUNTS['reviews']} reviews.")
    print(f"Course catalog: {catalog['inserted'] + catalog['updated'] + catalog['unchanged']} courses.")
    if fingerprints is not None:
        print(f"Created {fingerprints} topic fingerprints.")
    print(f"Sign in as any of them, e.g. riley@{DEV_DOMAIN}, with password {DEV_PASSWORD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
