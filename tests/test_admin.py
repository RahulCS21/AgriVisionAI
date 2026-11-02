import io
import os
import re
import sqlite3
import tempfile
import unittest
from contextlib import closing
from unittest.mock import patch

from werkzeug.security import generate_password_hash

from app import _prediction_history, _record_prediction, app


class AdminPanelTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_config = {
            key: app.config.get(key)
            for key in (
                "TESTING",
                "SECRET_KEY",
                "ADMIN_USERNAME",
                "ADMIN_PASSWORD_HASH",
                "HISTORY_DATABASE",
                "UPLOAD_FOLDER",
            )
        }
        app.config.update(
            TESTING=True,
            SECRET_KEY="test-session-secret",
            ADMIN_USERNAME="test-admin",
            ADMIN_PASSWORD_HASH=generate_password_hash("test-password"),
            HISTORY_DATABASE=os.path.join(self.temp_dir.name, "history.sqlite3"),
            UPLOAD_FOLDER=os.path.join(self.temp_dir.name, "uploads"),
        )
        os.makedirs(app.config["UPLOAD_FOLDER"])
        self.client = app.test_client()

    def tearDown(self):
        app.config.update(self.original_config)
        self.temp_dir.cleanup()

    def _login(self, username="test-admin", password="test-password"):
        response = self.client.get("/admin/login")
        page = response.get_data(as_text=True)
        csrf_token = re.search(
            r'name="csrf_token" value="([^"]+)"', page
        ).group(1)
        return self.client.post(
            "/admin/login",
            data={
                "csrf_token": csrf_token,
                "username": username,
                "password": password,
            },
            follow_redirects=False,
        )

    def _admin_csrf_token(self):
        page = self.client.get("/admin").get_data(as_text=True)
        return re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)

    def _csrf_token(self, path):
        page = self.client.get(path).get_data(as_text=True)
        return re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)

    def test_admin_pages_require_authentication_and_login_is_csrf_protected(self):
        for path in (
            "/admin",
            "/admin/predictions",
            "/admin/reports",
            "/admin/users",
            "/admin/system-status",
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.headers["Location"], "/admin/login")

        response = self.client.post("/admin/logout")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/admin/login")

        for path in (
            "/admin/records/1/delete",
            "/admin/images/example.png/delete",
        ):
            with self.subTest(path=path):
                response = self.client.post(path)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.headers["Location"], "/admin/login")

        response = self.client.post(
            "/admin/login",
            data={"username": "test-admin", "password": "test-password"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.get("/admin").status_code, 302)

    def test_dashboard_metrics_and_prediction_logs(self):
        from app import _history_connection, _record_weather_request

        with _history_connection() as connection:
            connection.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                ("dashboard-user", generate_password_hash("test-user-password")),
            )
        _record_prediction("Crop Yield", {}, "Yield result")
        _record_prediction("Disease Detection", {}, "Disease result")
        _record_prediction("Fertilizer Recommendation", {}, "Fertilizer result")
        _record_prediction("Crop Recommendation", {}, "Crop result")
        _record_weather_request("Mysuru")
        self.assertEqual(self._login().status_code, 302)

        dashboard = self.client.get("/admin").get_data(as_text=True)
        for metric, value in (
            ("Total Users", "1"),
            ("Total Predictions", "4"),
            ("Crop Yield Predictions", "1"),
            ("Disease Scans", "1"),
            ("Fertilizer Recommendations", "1"),
            ("Crop Recommendations", "1"),
            ("Weather Requests", "1"),
        ):
            with self.subTest(metric=metric):
                self.assertIn(metric, dashboard)
                self.assertIn(f">{value}</div>", dashboard)

        logs = self.client.get("/admin/predictions")
        self.assertEqual(logs.status_code, 200)
        self.assertIn(b"Prediction logs", logs.data)
        self.assertIn(b"Fertilizer Recommendation", logs.data)
        self.assertEqual(self.client.get("/admin/users").status_code, 200)
        self.assertEqual(self.client.get("/admin/reports").status_code, 200)
        with patch(
            "app._get_live_weather",
            return_value={"location": "Bengaluru, Karnataka"},
        ):
            status = self.client.get("/admin/system-status")
        self.assertEqual(status.status_code, 200)

    def test_weather_lookup_is_counted_without_becoming_a_prediction(self):
        from app import _prediction_statistics

        with patch(
            "app._get_live_weather",
            return_value={
                "location": "Mysuru, Karnataka",
                "temperature": 25,
                "humidity": 60,
                "rainfall_probability": 10,
                "wind_speed": 5,
                "observed_at": "2026-10-31T12:00",
            },
        ):
            response = self.client.get("/weather?location=Mysuru")

        self.assertEqual(response.status_code, 200)
        statistics = _prediction_statistics()
        self.assertEqual(statistics["total_predictions"], 0)
        self.assertEqual(statistics["weather_requests"], 1)

    def test_admin_login_rejects_bad_credentials_and_accepts_valid_credentials(self):
        with self.client.session_transaction() as user_session:
            user_session["pre_authentication_value"] = "discard-me"
        invalid_response = self._login(password="wrong-password")
        self.assertEqual(invalid_response.status_code, 200)
        self.assertIn(b"Invalid username or password.", invalid_response.data)

        response = self._login()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/admin")
        cookie = response.headers["Set-Cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)
        self.assertEqual(self.client.get("/admin").status_code, 200)
        with self.client.session_transaction() as admin_session:
            self.assertTrue(admin_session["is_admin"])
            self.assertTrue(admin_session.permanent)
            self.assertNotIn("pre_authentication_value", admin_session)
        csrf_token = self._admin_csrf_token()
        logout_response = self.client.post(
            "/admin/logout", data={"csrf_token": csrf_token}, follow_redirects=True
        )
        self.assertIn(b"You have been logged out.", logout_response.data)
        self.assertEqual(self.client.get("/admin").status_code, 302)

    def test_missing_server_configuration_disables_admin_login(self):
        app.config["ADMIN_PASSWORD_HASH"] = None

        response = self.client.get("/admin/login")

        self.assertEqual(response.status_code, 503)
        self.assertIn(b"Admin login is unavailable", response.data)

    def test_admin_login_rejects_oversized_credentials(self):
        response = self._login(password="x" * 1025)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Invalid username or password.", response.data)

    def test_successful_feature_submissions_appear_in_admin_history(self):
        yield_response = self.client.post(
            "/yield",
            data={
                "csrf_token": self._csrf_token("/yield"),
                "temperature": "25",
                "rainfall": "100",
                "humidity": "60",
            },
        )
        fertilizer_response = self.client.post(
            "/fertilizer",
            data={
                "csrf_token": self._csrf_token("/fertilizer"),
                "nitrogen": "60",
                "nitrogen_status": "Low",
                "phosphorus": "30",
                "phosphorus_status": "Medium",
                "potassium": "30",
                "potassium_status": "High",
            },
        )
        disease_response = self.client.post(
            "/disease",
            data={
                "csrf_token": self._csrf_token("/disease"),
                "image": (
                    io.BytesIO(b"\x89PNG\r\n\x1a\nimage-data"),
                    "leaf.png",
                )
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(yield_response.status_code, 200)
        self.assertEqual(fertilizer_response.status_code, 200)
        self.assertEqual(disease_response.status_code, 200)
        self.assertEqual(self._login().status_code, 302)
        dashboard = self.client.get("/admin").get_data(as_text=True)

        self.assertIn("Fertilizer Recommendation", dashboard)
        self.assertIn("Estimated crop yield:", dashboard)
        self.assertNotIn("Leaf spot", dashboard)
        self.assertIn("Disease detection images", dashboard)
        self.assertIn("Delete image", dashboard)
        self.assertIn("1 images", dashboard)
        records, total = _prediction_history(1)
        self.assertEqual(total, 2)
        self.assertEqual(
            {record["feature"] for record in records},
            {"Crop Yield", "Fertilizer Recommendation"},
        )

    def test_csrf_protects_deletion_and_record_deletion_removes_associated_image(self):
        filename = "leaf.png"
        image_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        with open(image_path, "wb") as image_file:
            image_file.write(b"\x89PNG\r\n\x1a\nimage-data")
        _record_prediction(
            "Disease Detection",
            {"image": filename},
            "Verified test diagnosis",
            image_filename=filename,
        )
        self._login()
        database_path = app.config["HISTORY_DATABASE"]
        with closing(sqlite3.connect(database_path)) as connection:
            record_id, filename = connection.execute(
                "SELECT id, image_filename FROM prediction_history"
            ).fetchone()
        self.assertTrue(os.path.isfile(image_path))

        rejected = self.client.post(f"/admin/records/{record_id}/delete")
        self.assertEqual(rejected.status_code, 400)

        response = self.client.post(
            f"/admin/records/{record_id}/delete",
            data={"csrf_token": self._admin_csrf_token()},
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(os.path.exists(image_path))
        with closing(sqlite3.connect(database_path)) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM prediction_history WHERE id = ?",
                    (record_id,),
                ).fetchone()[0],
                0,
            )

    def test_image_deletion_preserves_history_without_dangling_image_reference(self):
        filename = "managed-image.png"
        image_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        with open(image_path, "wb") as image_file:
            image_file.write(b"\x89PNG\r\n\x1a\nimage-data")
        _record_prediction(
            "Disease Detection",
            {"image": filename},
            "Model unavailable",
            image_filename=filename,
        )
        self._login()

        response = self.client.post(
            f"/admin/images/{filename}/delete",
            data={"csrf_token": self._admin_csrf_token()},
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(os.path.exists(image_path))
        with closing(sqlite3.connect(app.config["HISTORY_DATABASE"])) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT image_filename FROM prediction_history"
                ).fetchone()[0],
                None,
            )

    def test_image_delete_rejects_path_traversal(self):
        self._login()
        response = self.client.post(
            "/admin/images/%2E%2E%2Fsecret.txt/delete",
            data={"csrf_token": self._admin_csrf_token()},
        )

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
