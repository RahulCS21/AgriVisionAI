import os
import re
import sqlite3
import tempfile
import unittest
from contextlib import closing
from unittest.mock import patch

from flask import session
from werkzeug.security import check_password_hash, generate_password_hash

from app import _history_connection, app, _record_prediction


class AuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_config = {
            key: app.config.get(key)
            for key in (
                "TESTING",
                "SECRET_KEY",
                "SECRET_KEY_CONFIGURED",
                "ADMIN_USERNAME",
                "ADMIN_PASSWORD_HASH",
                "HISTORY_DATABASE",
            )
        }
        app.config.update(
            TESTING=True,
            SECRET_KEY="authentication-test-secret",
            SECRET_KEY_CONFIGURED=True,
            ADMIN_USERNAME="test-admin",
            ADMIN_PASSWORD_HASH=generate_password_hash("test-admin-password"),
            HISTORY_DATABASE=os.path.join(self.temp_dir.name, "history.sqlite3"),
        )
        self.client = app.test_client()

    def tearDown(self):
        app.config.update(self.original_config)
        self.temp_dir.cleanup()

    def _csrf(self, client, path="/register"):
        page = client.get(path).get_data(as_text=True)
        return re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)

    def _register(self, client=None, username="farm-user", password="secure-pass-123"):
        client = client or self.client
        response = client.post(
            "/register",
            data={
                "csrf_token": self._csrf(client),
                "username": username,
                "password": password,
                "confirm_password": password,
            },
        )
        return response

    def test_registration_hashes_password_and_creates_authenticated_session(self):
        response = self._register()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/dashboard")
        with closing(sqlite3.connect(app.config["HISTORY_DATABASE"])) as connection:
            user = connection.execute(
                "SELECT username, password_hash FROM users"
            ).fetchone()
        self.assertEqual(user[0], "farm-user")
        self.assertNotEqual(user[1], "secure-pass-123")
        self.assertTrue(check_password_hash(user[1], "secure-pass-123"))
        with self.client.session_transaction() as user_session:
            self.assertEqual(user_session["username"], "farm-user")
            self.assertIsInstance(user_session["user_id"], int)
            self.assertTrue(user_session.permanent)

    def test_existing_prediction_database_is_migrated_without_losing_records(self):
        legacy_path = os.path.join(self.temp_dir.name, "legacy.sqlite3")
        with closing(sqlite3.connect(legacy_path)) as connection:
            connection.execute(
                """
                CREATE TABLE prediction_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    feature TEXT NOT NULL,
                    inputs TEXT NOT NULL,
                    result TEXT NOT NULL,
                    image_filename TEXT
                )
                """
            )
            connection.execute(
                "INSERT INTO prediction_history (feature, inputs, result) VALUES (?, ?, ?)",
                ("Crop Recommendation", "{}", "Maize"),
            )
            connection.commit()

        original_database = app.config["HISTORY_DATABASE"]
        app.config["HISTORY_DATABASE"] = legacy_path
        try:
            with _history_connection() as connection:
                columns = {
                    row["name"]
                    for row in connection.execute(
                        "PRAGMA table_info(prediction_history)"
                    )
                }
                self.assertIn("user_id", columns)
                self.assertEqual(
                    connection.execute(
                        "SELECT result FROM prediction_history WHERE id = 1"
                    ).fetchone()["result"],
                    "Maize",
                )
                self.assertIsNotNone(
                    connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'users'"
                    ).fetchone()
                )
        finally:
            app.config["HISTORY_DATABASE"] = original_database

    def test_registration_validates_username_password_and_duplicate_accounts(self):
        csrf = self._csrf(self.client)
        invalid_cases = (
            ("x", "secure-pass-123", "secure-pass-123", "username of 3"),
            ("valid-user", "short", "short", "at least 8 characters"),
            ("valid-user", "secure-pass-123", "different-pass", "Passwords do not match"),
        )
        for username, password, confirmation, expected in invalid_cases:
            with self.subTest(expected=expected):
                response = self.client.post(
                    "/register",
                    data={
                        "csrf_token": csrf,
                        "username": username,
                        "password": password,
                        "confirm_password": confirmation,
                    },
                )
                self.assertEqual(response.status_code, 200)
                self.assertIn(expected.encode(), response.data)

        self.assertEqual(self._register().status_code, 302)
        with self.client.session_transaction() as user_session:
            user_session.clear()
        duplicate = self._register(username="FARM-USER")
        self.assertEqual(duplicate.status_code, 200)
        self.assertIn(b"already registered", duplicate.data)

    def test_registration_and_logout_success_messages_are_visible(self):
        registration = self.client.post(
            "/register",
            data={
                "csrf_token": self._csrf(self.client),
                "username": "flash-user",
                "password": "secure-pass-123",
                "confirm_password": "secure-pass-123",
            },
            follow_redirects=True,
        )
        self.assertEqual(registration.status_code, 200)
        self.assertIn(b"Your account is ready.", registration.data)

        logout = self.client.post(
            "/logout",
            data={"csrf_token": self._csrf(self.client, "/dashboard")},
            follow_redirects=True,
        )
        self.assertEqual(logout.status_code, 200)
        self.assertIn(b"You have been logged out.", logout.data)

    def test_login_rejects_oversized_credentials(self):
        self._register()
        with self.client.session_transaction() as user_session:
            user_session.clear()
        csrf = self._csrf(self.client, "/login")

        response = self.client.post(
            "/login",
            data={
                "csrf_token": csrf,
                "username": "farm-user",
                "password": "x" * 1025,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Invalid username or password.", response.data)

    def test_login_rotates_session_and_logout_requires_csrf(self):
        self._register()
        old_token = self._csrf(self.client, "/dashboard")
        with self.client.session_transaction() as user_session:
            user_session.clear()
            user_session["pre_authentication_value"] = "discard-me"

        response = self.client.post(
            "/login",
            data={
                "csrf_token": self._csrf(self.client, "/login"),
                "username": "farm-user",
                "password": "secure-pass-123",
            },
        )
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as user_session:
            self.assertNotIn("pre_authentication_value", user_session)
            self.assertNotEqual(user_session["csrf_token"], old_token)

        rejected = self.client.post("/logout")
        self.assertEqual(rejected.status_code, 400)
        logout_response = self.client.post(
            "/logout",
            data={"csrf_token": self._csrf(self.client, "/dashboard")},
        )
        self.assertEqual(logout_response.status_code, 302)
        self.assertEqual(logout_response.headers["Location"], "/")
        with self.client.session_transaction() as user_session:
            self.assertNotIn("user_id", user_session)

    def test_protected_pages_require_login_and_return_to_requested_page(self):
        profile_response = self.client.get("/profile")
        self.assertEqual(profile_response.status_code, 302)
        self.assertTrue(profile_response.headers["Location"].startswith("/login?"))
        for path in ("/history", "/reports"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.headers["Location"].startswith("/login?"))
                self.assertIn(path, response.headers["Location"])
        status_response = self.client.get("/system-status")
        self.assertEqual(status_response.status_code, 302)
        self.assertEqual(status_response.headers["Location"], "/admin/login")
        self.assertEqual(self._register().status_code, 302)
        status_response = self.client.get("/system-status")
        self.assertEqual(status_response.status_code, 302)
        self.assertEqual(status_response.headers["Location"], "/admin/login")

    def test_user_profile_shows_only_account_summary_and_navigation(self):
        self._register(username="profile-user")
        page = self.client.get("/profile").get_data(as_text=True)
        self.assertIn("User Profile", page)
        self.assertIn("profile-user", page)
        self.assertIn("Your saved activity", page)
        self.assertIn('href="/history"', page)
        self.assertIn('href="/reports"', page)
        self.assertNotIn("password_hash", page)
        self.assertIn('href="/profile"', page)

    def test_user_activity_is_private_and_admin_routes_are_restricted(self):
        self._register(username="first-user")
        with self.client.session_transaction() as user_session:
            first_user_id = user_session["user_id"]
        with app.test_request_context():
            session["user_id"] = first_user_id
            _record_prediction("Crop Recommendation", {"soil": "Alluvial"}, "Maize")
        self.assertIn(b"Maize", self.client.get("/history").data)
        self.assertIn(
            b'class="stat-value">1</div>',
            self.client.get("/dashboard").data,
        )

        second_client = app.test_client()
        self.assertEqual(self._register(second_client, "second-user").status_code, 302)
        self.assertIn(b"No prediction history yet", second_client.get("/history").data)
        self.assertIn(b"No prediction history yet", second_client.get("/reports").data)
        self.assertNotIn(
            b'class="stat-value">1</div>',
            second_client.get("/dashboard").data,
        )

        for path in (
            "/admin",
            "/admin/reports",
            "/admin/system-status",
            "/admin/users",
        ):
            response = second_client.get(path)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.headers["Location"], "/admin/login")

        login_page = self.client.get("/admin/login").get_data(as_text=True)
        csrf_token = re.search(
            r'name="csrf_token" value="([^"]+)"', login_page
        ).group(1)
        with patch("app._get_live_weather", return_value={"location": "Bengaluru"}):
            response = self.client.post(
                "/admin/login",
                data={
                    "csrf_token": csrf_token,
                    "username": "test-admin",
                    "password": "test-admin-password",
                },
            )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get("/admin/reports").status_code, 200)
        with patch("app._get_live_weather", return_value={"location": "Bengaluru"}):
            self.assertEqual(self.client.get("/admin/system-status").status_code, 200)
        activity = self.client.get("/admin/users").get_data(as_text=True)
        self.assertIn("first-user", activity)
        self.assertIn("second-user", activity)

    def test_user_login_blocks_external_next_redirect(self):
        self._register()
        with self.client.session_transaction() as user_session:
            user_session.clear()
        response = self.client.post(
            "/login?next=https://example.com",
            data={
                "csrf_token": self._csrf(self.client, "/login"),
                "username": "farm-user",
                "password": "secure-pass-123",
                "next": "https://example.com",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/dashboard")


if __name__ == "__main__":
    unittest.main()
