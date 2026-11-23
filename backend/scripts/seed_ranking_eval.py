"""Fill a local database with a simulated semester of advice requests, for the ranking eval.

    python backend/scripts/seed_ranking_eval.py --database-url "postgresql://postgres:postgres@127.0.0.1:5432/packconnect_sim?sslmode=disable"
    python backend/scripts/ranking_eval.py --database-url "<the same URL>"

PackConnect does not have enough real history yet to measure ranking, so this
script makes up a realistic one. Everyone in it is fictional. A fixed random
seed means every run creates the same semester, so results can be checked again.

How the simulated students behave (written separately from the app's scoring,
and not adjusted after looking at eval results):
- Each advisor has two advice topics and two hidden traits: how helpful they
  really are, and how reliably they reply to requests.
- A student needing help with a course and topic picks among advisors who took
  that course. They lean towards advisors who list the topic and who are
  genuinely helpful, with plenty of randomness.
- The advisor replies if they are reliable enough this time; most replies are
  accepts. If the request expires or is declined, the student tries someone else.
- An accepted conversation usually gets a review a few days later, based on how
  helpful the advisor really is, plus noise.

This shows the eval working under realistic conditions. It is not evidence about
real students, so results from it should be labelled as simulated.
"""

import argparse
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from werkzeug.security import generate_password_hash

# Direct runs put only scripts/ on the path; backend modules live one level up.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.database import connect_database
from scripts.seed_demo import is_local, prepare_local

SIM_DOMAIN = "sim.packconnect.test"
SIM_PASSWORD = "packconnect-sim-2026"
RANDOM_SEED = 2026
SEMESTER_START = datetime(2026, 8, 24, tzinfo=timezone.utc)
SEMESTER_DAYS = 70
FIRST_REQUESTS = 60
TRIES_PER_NEED = 3

TOPICS = ["Projects", "Interview prep", "Exams", "Course workload",
          "Research", "Time management", "Resumes", "Group work"]

# (course taken, how many fictional advisors took it)
ADVISOR_COURSES = [("CSC 510", 14), ("CSC 540", 3), ("CSC 316", 2), ("MA 305", 2)]

# How often students need help with each course.
NEEDED_COURSES = [("CSC 510", 0.8), ("CSC 540", 0.15), ("CSC 316", 0.05)]

FIRST_NAMES = ["Avery", "Blair", "Cameron", "Dakota", "Emerson", "Finley", "Gray", "Harper", "Indigo",
               "Jules", "Kendall", "Logan", "Morgan", "Noel", "Oakley", "Parker", "Quinn", "Reese",
               "Sage", "Taylor", "Umi", "Vale", "Wren", "Xen", "Yael", "Zion"]
LAST_NAMES = ["Abbott", "Barros", "Chen", "Diallo", "Eriksen", "Fofana", "Garcia", "Hughes", "Ito",
              "Jensen", "Kowal", "Lopez", "Mensah", "Novak", "Okoro", "Patel", "Quint", "Rossi",
              "Silva", "Tanaka", "Ueda", "Varga", "Weber", "Xu", "Young", "Zhou"]
STUDENT_COUNT = 20


def fictional_names(rng, count):
    """Unique made-up full names."""
    pairs = [(first, last) for first in FIRST_NAMES for last in LAST_NAMES]
    return [f"{first} {last}" for first, last in rng.sample(pairs, count)]


def make_people(rng):
    """Return (advisors, students) as lists of dicts with their hidden traits."""
    advisor_count = sum(count for _, count in ADVISOR_COURSES)
    names = fictional_names(rng, advisor_count + STUDENT_COUNT)
    advisors = []
    for course, count in ADVISOR_COURSES:
        for _ in range(count):
            advisors.append({
                "name": names.pop(),
                "course": course,
                "topics": rng.sample(TOPICS, 2),
                "helpfulness": rng.uniform(0.3, 1.0),   # hidden: how good their advice really is
                "reliability": rng.uniform(0.4, 1.0),   # hidden: chance they reply to a request
            })
    students = [{"name": names.pop()} for _ in range(STUDENT_COUNT)]
    return advisors, students


def choice_weight(advisor, topic):
    """How attractive an advisor looks to a student needing help with this topic."""
    topic_fit = 2.0 if topic in advisor["topics"] else 0.5
    return topic_fit * (0.5 + advisor["helpfulness"])


def simulate_requests(rng, advisors, students):
    """Return the semester's requests in time order, each with its outcome and any review."""
    needs = sorted(rng.uniform(0, SEMESTER_DAYS - 10) for _ in range(FIRST_REQUESTS))
    courses, course_weights = zip(*NEEDED_COURSES)
    requests = []
    for day in needs:
        student = rng.choice(students)
        course = rng.choices(courses, course_weights)[0]
        topic = rng.choice(TOPICS)
        options = [advisor for advisor in advisors if advisor["course"] == course]
        for _ in range(TRIES_PER_NEED):
            if not options:
                break
            advisor = rng.choices(options, [choice_weight(option, topic) for option in options])[0]
            options.remove(advisor)
            request = {"student": student, "advisor": advisor, "course": course, "topic": topic, "day": day}
            requests.append(request)
            if rng.random() > advisor["reliability"]:
                request["status"] = "expired"
                day += 7
            elif rng.random() < 0.15:
                request["status"] = "declined"
                day += 1
            else:
                request["status"] = "completed"
                if rng.random() < 0.8:
                    rating = round(3 + 7 * advisor["helpfulness"] + rng.gauss(0, 1.2))
                    request["review"] = (min(10, max(1, rating)), day + 5)
                break
    return sorted(requests, key=lambda request: request["day"])


def sim_present(db):
    return db.execute("SELECT EXISTS (SELECT 1 FROM accounts WHERE email LIKE %s) AS present",
                      (f"%@{SIM_DOMAIN}",)).fetchone()["present"]


def seed_simulated_semester(db):
    """Insert the simulated semester through an open transaction. Returns counts of what was added."""
    if sim_present(db):
        raise RuntimeError("Simulated semester data is already present in this database.")
    rng = random.Random(RANDOM_SEED)
    advisors, students = make_people(rng)
    requests = simulate_requests(rng, advisors, students)
    password_hash = generate_password_hash(SIM_PASSWORD)

    def add_student(person, advising):
        topics = ", ".join(person["topics"]) if advising else ""
        person["id"] = db.execute("""
            INSERT INTO students (name, program, year, bio, advice_topics, willing_to_advise, max_open_requests)
            VALUES (%s, 'MS Computer Science', 'Second Year', 'Fictional simulated student.', %s, %s, NULL)
            RETURNING id
        """, (person["name"], topics, advising)).fetchone()["id"]
        email = person["name"].lower().replace(" ", ".") + "@" + SIM_DOMAIN
        db.execute("INSERT INTO accounts (student_id, email, password_hash) VALUES (%s, %s, %s)",
                   (person["id"], email, password_hash))

    for advisor in advisors:
        add_student(advisor, advising=True)
        db.execute("INSERT INTO completed_courses (student_id, course_code) VALUES (%s, %s)",
                   (advisor["id"], advisor["course"]))
    for student in students:
        add_student(student, advising=False)

    reviews = 0
    for request in requests:
        sent = SEMESTER_START + timedelta(days=request["day"])
        request_id = db.execute("""
            INSERT INTO advice_requests
                (sender_id, recipient_id, course_code, advice_topic, message, status, created_at, expires_at)
            VALUES (%s, %s, %s, %s, 'Could you help me with this course?', %s, %s, %s) RETURNING id
        """, (request["student"]["id"], request["advisor"]["id"], request["course"], request["topic"],
              request["status"], sent, sent + timedelta(days=7))).fetchone()["id"]
        if "review" in request:
            rating, day = request["review"]
            db.execute("""
                INSERT INTO advice_feedback (request_id, rater_id, rating, helpful, created_at)
                VALUES (%s, %s, %s, %s, %s)
            """, (request_id, request["student"]["id"], rating, rating >= 6, SEMESTER_START + timedelta(days=day)))
            reviews += 1
    accepted = sum(request["status"] == "completed" for request in requests)
    return {"advisors": len(advisors), "students": len(students), "requests": len(requests),
            "accepted": accepted, "reviews": reviews}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Seed a simulated semester for the ranking eval.")
    parser.add_argument("--database-url", required=True, help="PostgreSQL connection string to seed")
    args = parser.parse_args(argv)
    if not is_local(args.database_url):
        # Simulated history would mix with real data and distort real reputations.
        print("Refusing to seed a non-local database. Use a dedicated local database for the simulation.")
        return 2
    try:
        prepare_local(args.database_url)
        with connect_database(args.database_url) as db:
            counts = seed_simulated_semester(db)
    except RuntimeError as error:
        print(error)
        return 1
    except Exception as error:
        # Connection errors may contain user/host information; never echo a DSN.
        print(f"Seeding failed ({type(error).__name__}). Check the database URL.")
        return 1
    print(f"Simulated semester: {counts['advisors']} advisors, {counts['students']} students, "
          f"{counts['requests']} requests ({counts['accepted']} accepted), {counts['reviews']} reviews.")
    print("Run backend/scripts/ranking_eval.py with the same --database-url to measure ranking.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
