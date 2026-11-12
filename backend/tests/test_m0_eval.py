"""M0 instrument and demo seed: known data must produce a known M0 number."""

import io
from contextlib import contextmanager, redirect_stdout
from unittest import TestCase
from unittest.mock import patch

import app as portal
from scripts import m0_eval, seed_demo
from scripts.m0_eval import m0_counts, m0_report
from scripts.seed_demo import DEMO_DOMAIN, DEMO_PASSWORD, EXPECTED_M0, seed_demo as seed
from tests.postgres_test_support import PostgresTestCase

SEEDED_REPORT = (
    "M0: 75.0% of accepted connections were rated helpful (9 of 12)\n"
    "    Rated: 10 of 12 connections (83.3%); 9 of 10 ratings say helpful (90.0%)\n"
    "    Claim: more than 70% of accepted connections rated helpful -> PASS"
)


def run(main, *argv):
    output = io.StringIO()
    with redirect_stdout(output):
        status = main(list(argv))
    return status, output.getvalue().strip()


class M0ReportTests(TestCase):
    def test_report_lists_headline_and_supporting_numbers(self):
        text, met = m0_report({"connections": 12, "rated": 10, "helpful": 9})
        self.assertEqual(text, SEEDED_REPORT)
        self.assertTrue(met)

    def test_claim_needs_more_than_seventy_percent(self):
        self.assertFalse(m0_report({"connections": 10, "rated": 10, "helpful": 7})[1])
        self.assertTrue(m0_report({"connections": 100, "rated": 90, "helpful": 71})[1])

    def test_unrated_connections_count_against_the_claim(self):
        # 8 of 10 ratings are helpful, but only 8 of 20 connections are.
        text, met = m0_report({"connections": 20, "rated": 10, "helpful": 8})
        self.assertIn("40.0% of accepted connections", text)
        self.assertIn("8 of 10 ratings say helpful (80.0%)", text)
        self.assertFalse(met)
        self.assertTrue(text.endswith("-> FAIL"))

    def test_no_ratings_yet(self):
        text, met = m0_report({"connections": 3, "rated": 0, "helpful": 0})
        self.assertIn("0.0% of accepted connections were rated helpful (0 of 3)", text)
        self.assertIn("Rated: 0 of 3 connections (0.0%)\n", text)
        self.assertFalse(met)

    def test_no_connections_is_not_a_pass(self):
        text, met = m0_report({"connections": 0, "rated": 0, "helpful": 0})
        self.assertIn("nothing to measure", text)
        self.assertFalse(met)

    def test_custom_target(self):
        text, met = m0_report({"connections": 12, "rated": 10, "helpful": 9}, target=80)
        self.assertIn("more than 80%", text)
        self.assertFalse(met)


class SeedSafetyTests(TestCase):
    def test_only_local_hosts_count_as_local(self):
        self.assertTrue(seed_demo.is_local("postgresql://u:p@127.0.0.1:5432/demo"))
        self.assertTrue(seed_demo.is_local("postgresql://u:p@localhost/demo"))
        self.assertFalse(seed_demo.is_local("postgresql://u:p@aws-0-us-east-1.pooler.supabase.com:5432/postgres"))

    def test_remote_database_is_refused_without_flag_and_never_contacted(self):
        with patch.object(seed_demo, "connect_database") as connect, \
                patch.object(seed_demo, "prepare_local") as prepare:
            status, output = run(seed_demo.main, "--database-url", "postgresql://u:p@db.example.com/postgres")
        self.assertEqual(status, 2)
        self.assertIn("Refusing", output)
        connect.assert_not_called()
        prepare.assert_not_called()

    def test_m0_eval_needs_a_database_url(self):
        with patch.dict("os.environ", {"SUPABASE_DB_URL": ""}), patch.object(m0_eval, "load_dotenv"):
            status, output = run(m0_eval.main)
        self.assertEqual(status, 2)
        self.assertIn("SUPABASE_DB_URL", output)


class SeededM0Tests(PostgresTestCase):
    def setUp(self):
        super().setUp()
        with portal.get_db() as db:
            self.ids = seed(db)

    @contextmanager
    def local_connection(self, _url):
        with portal.get_db() as db:
            yield db

    def test_seeded_data_has_the_documented_counts(self):
        with portal.get_db() as db:
            self.assertEqual(m0_counts(db), EXPECTED_M0)

    def test_m0_eval_prints_the_number_on_seeded_data(self):
        with patch.object(m0_eval, "read_only_connection", self.local_connection):
            status, output = run(m0_eval.main, "--database-url", "postgresql://u@127.0.0.1/demo")
        self.assertEqual(status, 0)
        self.assertEqual(output, SEEDED_REPORT)

    def test_check_flag_sets_the_exit_status(self):
        with patch.object(m0_eval, "read_only_connection", self.local_connection):
            self.assertEqual(run(m0_eval.main, "--database-url", "x", "--check")[0], 0)
            self.assertEqual(run(m0_eval.main, "--database-url", "x", "--check", "--target", "80")[0], 1)

    def test_m0_ignores_advisor_feedback_and_unconnected_requests(self):
        with portal.get_db() as db:
            advisor_ratings = db.execute("""SELECT count(*) FROM advice_feedback f
                JOIN advice_requests r ON r.id = f.request_id WHERE f.rater_id = r.recipient_id""").fetchone()["count"]
            other = db.execute("SELECT count(*) FROM advice_requests WHERE status NOT IN ('accepted', 'completed')"
                               ).fetchone()["count"]
        self.assertEqual((advisor_ratings, other), (2, 4))
        with portal.get_db() as db:
            self.assertEqual(m0_counts(db), EXPECTED_M0)

    def test_new_feedback_moves_the_number(self):
        with portal.get_db() as db:
            unrated = db.execute("""SELECT r.id, r.sender_id FROM advice_requests r
                WHERE r.status IN ('accepted', 'completed') AND NOT EXISTS (
                    SELECT 1 FROM advice_feedback f WHERE f.request_id = r.id AND f.rater_id = r.sender_id)
                ORDER BY r.id LIMIT 1""").fetchone()
            db.execute("INSERT INTO advice_feedback (request_id, rater_id, rating, helpful) VALUES (%s, %s, 9, true)",
                       (unrated["id"], unrated["sender_id"]))
            self.assertEqual(m0_counts(db), {"connections": 12, "rated": 11, "helpful": 10})

    def test_seeding_twice_is_refused(self):
        with self.assertRaisesRegex(RuntimeError, "already present"), portal.get_db() as db:
            seed(db)

    def test_demo_accounts_can_sign_in(self):
        response = portal.app.test_client().post("/api/auth/login", json={
            "email": f"maya@{DEMO_DOMAIN}", "password": DEMO_PASSWORD})
        self.assertEqual(response.status_code, 200)

    def test_unrated_seeded_connection_is_open_for_rating(self):
        client = portal.app.test_client()
        with client.session_transaction() as session:
            session["student_id"] = self.ids["dev"]
        with portal.get_db() as db:
            request_id = db.execute("SELECT id FROM advice_requests WHERE sender_id = %s",
                                    (self.ids["dev"],)).fetchone()["id"]
        self.assertEqual(client.get(f"/api/requests/{request_id}/feedback").get_json(),
                         {"feedback": None, "can_rate": True})

    def test_seeded_reputation_matches_hand_calculation(self):
        # Maya: asker ratings 9, 10, 8 (all helpful); 4 students accepted;
        # answered 4 of 5 requests due an answer (Grace's expired).
        reputation = portal.app.test_client().get(f"/api/students/{self.ids['maya']}/reputation").get_json()["reputation"]
        self.assertEqual(reputation, {"average_rating": 9.0, "rating_count": 3, "helpful_percent": 100,
                                      "students_helped": 4, "response_rate": 80})
