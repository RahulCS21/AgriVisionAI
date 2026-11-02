import re
import os
import tempfile
import unittest
from unittest.mock import patch

from app import YIELD_FIELDS, app, yield_model


class YieldPredictionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_history_database = app.config["HISTORY_DATABASE"]
        app.config["HISTORY_DATABASE"] = os.path.join(
            self.temp_dir.name, "history.sqlite3"
        )
        app.config["TESTING"] = True
        self.client = app.test_client()
        self._create_user()

    def tearDown(self):
        app.config["HISTORY_DATABASE"] = self.original_history_database
        self.temp_dir.cleanup()

    def _csrf_token(self):
        page = self.client.get("/yield").get_data(as_text=True)
        return re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)

    def _create_user(self):
        page = self.client.get("/register").get_data(as_text=True)
        csrf_token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
        response = self.client.post(
            "/register",
            data={
                "csrf_token": csrf_token,
                "username": "yield-test-user",
                "password": "test-password-123",
                "confirm_password": "test-password-123",
            },
        )
        self.assertEqual(response.status_code, 302)

    def test_form_names_match_yield_input_fields(self):
        response = self.client.get("/yield")
        input_tags = re.findall(r"<input[^>]*>", response.get_data(as_text=True))
        input_names = [
            re.search(r'\bname="([^"]+)"', tag).group(1)
            for tag in input_tags
            if re.search(r'\btype="number"', tag)
        ]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(input_names, list(YIELD_FIELDS))

    def test_empty_fields_show_field_specific_errors(self):
        valid_values = {
            "temperature": "25",
            "rainfall": "100",
            "humidity": "60",
        }
        for field, label in YIELD_FIELDS.items():
            with self.subTest(field=field):
                values = {**valid_values, field: ""}
                values["csrf_token"] = self._csrf_token()
                response = self.client.post("/yield", data=values)

                self.assertEqual(response.status_code, 200)
                self.assertIn(f"{label} is required.".encode(), response.data)

    def test_missing_field_shows_validation_error(self):
        response = self.client.post(
            "/yield",
            data={
                "csrf_token": self._csrf_token(),
                "temperature": "25",
                "rainfall": "100",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Humidity is required.", response.data)

    def test_invalid_and_non_finite_numbers_show_validation_errors(self):
        for value, expected_error in (
            ("not-a-number", b"Temperature must be a valid number."),
            ("nan", b"Temperature must be a finite number."),
            ("inf", b"Temperature must be a finite number."),
            ("-91", b"Temperature must be between -90 and 60."),
        ):
            with self.subTest(value=value):
                response = self.client.post(
                    "/yield",
                    data={
                        "csrf_token": self._csrf_token(),
                        "temperature": value,
                        "rainfall": "100",
                        "humidity": "60",
                    },
                )

                self.assertEqual(response.status_code, 200)
                self.assertIn(expected_error, response.data)

        response = self.client.post(
            "/yield",
            data={
                "csrf_token": self._csrf_token(),
                "temperature": "25",
                "rainfall": "100",
                "humidity": "101",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Humidity must be between 0 and 100.", response.data)

    def test_missing_yield_model_is_informational_and_does_not_store_prediction(self):
        missing_path = os.path.join(self.temp_dir.name, "missing-yield-model.pkl")
        with patch("app.yield_model", None), patch.dict(
            app.config, YIELD_MODEL_PATH=missing_path
        ):
            response = self.client.post(
                "/yield",
                data={
                    "csrf_token": self._csrf_token(),
                    "temperature": "25",
                    "rainfall": "100",
                    "humidity": "60",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            b"Yield predictions are currently unavailable.", response.data
        )
        self.assertNotIn(b"Model Status", response.data)
        self.assertNotIn(b"Required model path", response.data)
        self.assertNotIn(missing_path.encode(), response.data)
        self.assertNotIn(b'class="alert-danger"', response.data)
        self.assertNotIn(b"Predicted Yield:", response.data)
        from app import _prediction_history

        records, total = _prediction_history(1)
        self.assertEqual(records, [])
        self.assertEqual(total, 0)

    def test_demo_model_prediction_is_saved_and_shown_in_history_and_reports(self):
        self.assertIsNotNone(yield_model)
        response = self.client.post(
            "/yield",
            data={
                "csrf_token": self._csrf_token(),
                "temperature": "30",
                "rainfall": "60",
                "humidity": "80",
            },
        )
        page = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Estimated crop yield:", page)
        self.assertIn('class="prediction-result mb-4"', page)
        self.assertIn('role="status"', page)
        for technical_content in (
            "Experimental Demonstration Prediction:",
            "generic recovered",
            "not production-grade",
            "yield units undocumented",
            "Required model path",
        ):
            with self.subTest(technical_content=technical_content):
                self.assertNotIn(technical_content, page)

        from app import _prediction_history, _prediction_statistics

        records, total = _prediction_history(1)
        self.assertEqual(total, 1)
        self.assertEqual(records[0]["feature"], "Crop Yield")
        self.assertEqual(records[0]["inputs"], {
            "temperature": 30.0,
            "rainfall": 60.0,
            "humidity": 80.0,
        })
        self.assertTrue(records[0]["result"].startswith("Estimated crop yield:"))

        history_page = self.client.get("/history").get_data(as_text=True)
        reports_page = self.client.get("/reports").get_data(as_text=True)
        self.assertIn(records[0]["result"], history_page)
        self.assertIn(records[0]["result"], reports_page)
        self.assertIn('class="stat-value">1</div>', reports_page)
        self.assertEqual(_prediction_statistics()["yield_predictions"], 1)


if __name__ == "__main__":
    unittest.main()
