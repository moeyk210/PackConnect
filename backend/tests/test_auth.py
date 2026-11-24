import unittest

import app as portal
from tests.postgres_test_support import PostgresTestCase


class AuthenticationTests(PostgresTestCase):
    def setUp(self):
        super().setUp()
        self.client = portal.app.test_client()
        self.credentials = {"email": "casey@example.edu", "password": "a long test password"}
        response = self.client.post("/api/auth/register", json={
            **self.credentials, "name": "Casey", "program": "Computer Science",
            "year": "First Year",
        })
        self.student_id = response.get_json()["student"]["id"]

    def test_login_restores_session_and_logout_clears_it(self):
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)
        response = self.client.post("/api/auth/login", json={
            **self.credentials, "email": " CASEY@EXAMPLE.EDU ",
        })
        self.assertEqual(response.status_code, 200)
        student = response.get_json()["student"]
        self.assertEqual(student["id"], self.student_id)
        self.assertNotIn("email", student)
        self.assertNotIn("password_hash", student)
        self.assertIn("HttpOnly", response.headers["Set-Cookie"])
        self.assertIn("SameSite=Lax", response.headers["Set-Cookie"])
        self.assertEqual(self.client.get("/api/auth/me").get_json()["student"]["id"], self.student_id)
        self.assertEqual(self.client.post("/api/auth/logout").status_code, 200)
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)

    def test_wrong_password_and_unknown_email_do_not_authenticate(self):
        for payload in [
            {**self.credentials, "password": "incorrect password"},
            {**self.credentials, "email": "unknown@example.edu"},
        ]:
            with self.subTest(payload=payload):
                response = self.client.post("/api/auth/login", json=payload)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.get_json()["error"], "Email or password is incorrect.")
                self.assertEqual(self.client.get("/api/auth/me").status_code, 401)

    def test_invalid_login_payloads(self):
        for payload in [None, [], {}, {"email": [], "password": 123},
                        {**self.credentials, "password": "x" * 129}]:
            with self.subTest(payload=payload):
                self.assertEqual(self.client.post("/api/auth/login", json=payload).status_code, 400)

    def test_separate_browser_does_not_share_session(self):
        self.client.post("/api/auth/login", json=self.credentials)
        other_client = portal.app.test_client()
        self.assertEqual(other_client.get("/api/auth/me").status_code, 401)

    def test_copied_cookie_stops_working_after_logout(self):
        self.client.post("/api/auth/login", json=self.credentials)
        stolen = self.client.get_cookie("session").value
        thief = portal.app.test_client()
        thief.set_cookie("session", stolen)
        self.assertEqual(thief.get("/api/auth/me").status_code, 200)
        self.assertEqual(self.client.post("/api/auth/logout").status_code, 200)
        self.assertEqual(thief.get("/api/auth/me").status_code, 401)
        self.assertEqual(thief.get("/api/requests").status_code, 401)

    def test_logout_only_ends_that_browser(self):
        laptop, phone = portal.app.test_client(), portal.app.test_client()
        for device in (laptop, phone):
            self.assertEqual(device.post("/api/auth/login", json=self.credentials).status_code, 200)
        laptop.post("/api/auth/logout")
        self.assertEqual(laptop.get("/api/auth/me").status_code, 401)
        self.assertEqual(phone.get("/api/auth/me").get_json()["student"]["id"], self.student_id)

    def test_cookie_without_server_session_is_rejected(self):
        # Cookies issued before server-side sessions existed carry no session_id.
        with self.client.session_transaction() as session:
            session["student_id"] = self.student_id
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)
        with self.client.session_transaction() as session:
            session["student_id"] = self.student_id
            session["session_id"] = "made-up-session-id"
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)

    def test_session_ids_cannot_be_moved_between_accounts(self):
        self.client.post("/api/auth/login", json=self.credentials)
        with self.client.session_transaction() as session:
            casey_session = session["session_id"]
        other = portal.app.test_client()
        other.post("/api/auth/register", json={
            "email": "drew@example.edu", "password": "another long password", "name": "Drew",
            "program": "Computer Science", "year": "First Year"})
        with portal.get_db() as db:
            drew = db.execute("SELECT student_id FROM accounts WHERE email='drew@example.edu'").fetchone()["student_id"]
        with other.session_transaction() as session:
            session["student_id"] = drew
            session["session_id"] = casey_session
        self.assertEqual(other.get("/api/auth/me").status_code, 401)

    def test_revoked_sessions_are_pruned_at_next_login(self):
        for _ in range(3):
            self.client.post("/api/auth/login", json=self.credentials)
            self.client.post("/api/auth/logout")
        self.client.post("/api/auth/login", json=self.credentials)
        with portal.get_db() as db:
            rows = db.execute("SELECT revoked_at FROM auth_sessions WHERE student_id=%s",
                              (self.student_id,)).fetchall()
        self.assertEqual([row["revoked_at"] for row in rows], [None])

    def test_deleted_profile_invalidates_session(self):
        self.client.post("/api/auth/login", json=self.credentials)
        with portal.get_db() as db:
            db.execute("DELETE FROM accounts WHERE student_id = %s", (self.student_id,))
            db.execute("DELETE FROM students WHERE id = %s", (self.student_id,))
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)


if __name__ == "__main__":
    unittest.main()
