import io
import os
import re
import tempfile
import unittest
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

from flask import session

from app import _get_live_weather, app


class UiPageTests(unittest.TestCase):
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

    def _csrf_token(self, path):
        page = self.client.get(path).get_data(as_text=True)
        return re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)

    def _create_user(self):
        page = self.client.get("/register").get_data(as_text=True)
        csrf_token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
        response = self.client.post(
            "/register",
            data={
                "csrf_token": csrf_token,
                "username": "ui-test-user",
                "password": "test-password-123",
                "confirm_password": "test-password-123",
            },
        )
        self.assertEqual(response.status_code, 302)

    def _record_for_current_user(self, feature, inputs, result, image_filename=None):
        from app import _record_prediction

        with self.client.session_transaction() as user_session:
            user_id = user_session["user_id"]
        with app.test_request_context():
            session["user_id"] = user_id
            _record_prediction(feature, inputs, result, image_filename)

    def test_all_pages_render_with_shared_navigation_and_footer(self):
        pages = (
            "/",
            "/dashboard",
            "/history",
            "/reports",
            "/system-status",
            "/about",
            "/contact",
            "/privacy",
            "/weather",
            "/yield",
            "/disease",
            "/fertilizer",
            "/crop-recommendation",
        )
        for path in pages:
            with self.subTest(path=path):
                if path == "/system-status":
                    with self.client.session_transaction() as user_session:
                        user_session["is_admin"] = True
                    with patch(
                        "app._get_live_weather",
                        return_value={
                            "location": "Bengaluru, Karnataka, India",
                            "temperature": 25,
                        },
                    ):
                        response = self.client.get(path)
                else:
                    response = self.client.get(path)
                page = response.get_data(as_text=True)

                self.assertEqual(response.status_code, 200)
                self.assertIn("AgriVision", page)
                self.assertIn("Disease Detection", page)
                self.assertIn("Fertilizer Recommendation", page)
                self.assertIn("Crop Recommendation", page)
                self.assertIn("Weather", page)
                self.assertIn("Dashboard", page)
                self.assertIn("Prediction History", page)
                self.assertIn("Reports", page)
                self.assertIn("Contact", page)
                self.assertIn('href="/about"', page)
                self.assertIn('href="/contact"', page)
                self.assertIn('href="/privacy"', page)
                self.assertIn('href="/admin/login"', page)
                self.assertIn("&copy; 2026 AgriVision AI", page)
                self.assertNotIn("Internship Project", page)
                self.assertIn("static/css/style.css", page)

    def test_admin_access_is_footer_only_and_footer_links_render(self):
        response = self.client.get("/")
        page = response.get_data(as_text=True)
        navbar = page.split("</nav>", 1)[0]
        footer = page.split("<footer", 1)[1]

        self.assertNotIn('href="/admin/login"', navbar)
        self.assertNotIn('href="/admin"', navbar)
        for label, href in (
            ("About Us", "/about"),
            ("Contact Us", "/contact"),
            ("Privacy Policy", "/privacy"),
            ("Admin Access", "/admin/login"),
        ):
            with self.subTest(label=label):
                self.assertIn(label, footer)
                self.assertIn(f'href="{href}"', footer)
        self.assertIn('class="footer-admin-link"', footer)

    def test_homepage_has_feature_cards_and_about_section(self):
        response = self.client.get("/")
        page = response.get_data(as_text=True)

        self.assertIn("Crop Yield Prediction", page)
        self.assertIn("Plant health", page)
        self.assertIn("Soil guidance", page)
        self.assertIn('href="/about"', page)
        self.assertIn('href="/yield"', page)
        self.assertIn('href="/disease"', page)
        self.assertIn('href="/fertilizer"', page)
        self.assertIn('href="/crop-recommendation"', page)
        self.assertIn('href="/weather"', page)

    def test_dashboard_shows_modules_statistics_and_quick_links(self):
        response = self.client.get("/dashboard")
        page = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        for expected_content in (
            "Your agriculture intelligence hub",
            "Total Predictions",
            "Disease Scans",
            "Yield Predictions",
            "Fertilizer Recommendations",
            "5 platform modules",
            "Estimate crop yield from local growing conditions.",
            "Review plant health with a clear leaf image.",
        ):
            with self.subTest(expected_content=expected_content):
                self.assertIn(expected_content, page)
        for technical_content in (
            "Experimental Demonstration Yield Model",
            "only 10 generic recovered dataset rows",
            "not production-grade",
            "Trained disease model",
            "Model Missing",
            "Rule-based",
        ):
            with self.subTest(technical_content=technical_content):
                self.assertNotIn(technical_content, page)

        for route in (
            "/yield",
            "/disease",
            "/fertilizer",
            "/crop-recommendation",
            "/weather",
            "/history",
            "/reports",
        ):
            with self.subTest(route=route):
                self.assertIn(f'href="{route}"', page)

    def test_public_pages_hide_model_audit_details_and_clean_legacy_yield_rows(self):
        self._record_for_current_user(
            "Crop Yield",
            {"temperature": 25, "rainfall": 100},
            "Experimental Demonstration Prediction: 3.14 "
            "(recovered dataset yield units undocumented; not production-grade)",
        )
        public_pages = (
            "/",
            "/about",
            "/dashboard",
            "/history",
            "/reports",
            "/weather",
            "/yield",
            "/fertilizer",
            "/crop-recommendation",
        )
        for path in public_pages:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                page = response.get_data(as_text=True)
                for audit_detail in (
                    "Experimental Demonstration Prediction",
                    "recovered dataset",
                    "yield units undocumented",
                    "not production-grade",
                    "Required model path",
                    "Model Status",
                ):
                    with self.subTest(audit_detail=audit_detail):
                        self.assertNotIn(audit_detail, page)

        for path in ("/history", "/reports"):
            page = self.client.get(path).get_data(as_text=True)
            self.assertIn("Estimated crop yield: 3.14", page)

        with patch("app.disease_model", None):
            disease_page = self.client.get("/disease").get_data(as_text=True)
        self.assertNotIn("Required model path", disease_page)
        self.assertNotIn(app.config["DISEASE_MODEL_PATH"], disease_page)

    def test_about_page_has_company_content_and_developer_contact(self):
        response = self.client.get("/about")
        page = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        for section in (
            "Our mission",
            "Our vision",
            "Core features",
            "AI-powered agriculture solutions",
            "Crop Yield Prediction",
            "Plant Disease Detection",
            "Fertilizer Recommendation",
            "Crop Recommendation",
            "Sustainable farming",
            "Smart decision support",
            "Rahul Sharma C.",
            "420dutyon@gmail.com",
            "https://github.com/RahulCS21",
        ):
            with self.subTest(section=section):
                self.assertIn(section, page)
        for disallowed_phrase in (
            "internship",
            "student project",
            "college project",
            "beginner project",
            "learning project",
        ):
            with self.subTest(disallowed_phrase=disallowed_phrase):
                self.assertNotIn(disallowed_phrase, page.lower())

    def test_feature_forms_keep_their_existing_fields(self):
        expected_fields = {
            "/yield": ("temperature", "rainfall", "humidity"),
            "/disease": ("image",),
            "/fertilizer": (
                "nitrogen",
                "nitrogen_status",
                "phosphorus",
                "phosphorus_status",
                "potassium",
                "potassium_status",
            ),
            "/crop-recommendation": (
                "soil_type",
                "season",
                "temperature",
                "rainfall",
            ),
        }
        for path, fields in expected_fields.items():
            with self.subTest(path=path):
                page = self.client.get(path).get_data(as_text=True)
                for field in fields:
                    self.assertIn(f'name="{field}"', page)

    def test_crop_recommendation_returns_a_result_and_records_history(self):
        response = self.client.post(
            "/crop-recommendation",
            data={
                "csrf_token": self._csrf_token("/crop-recommendation"),
                "soil_type": "Alluvial",
                "season": "Kharif",
                "temperature": "25",
                "rainfall": "800",
            },
        )
        page = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Top crop for further consideration", page)
        self.assertIn("Maize", page)
        self.assertIn("broad rule-based screening", page)

        from app import _prediction_history

        records, total = _prediction_history(1)
        self.assertEqual(total, 1)
        self.assertEqual(records[0]["feature"], "Crop Recommendation")
        self.assertEqual(records[0]["inputs"]["soil_type"], "Alluvial")
        from app import _prediction_statistics

        self.assertEqual(_prediction_statistics()["crop_recommendations"], 1)

    def test_history_and_reports_show_saved_prediction_records_and_statistics(self):
        predictions = (
            ("Crop Yield", {"temperature": 25, "rainfall": 100}, "Predicted Yield: 2.50 ton/hectare"),
            ("Disease Detection", {"image": "leaf-scan.jpg"}, "Leaf spot (94%)"),
            ("Fertilizer Recommendation", {"nitrogen": 40, "phosphorus": 30, "potassium": 20}, "Potential nutrient gaps: Nitrogen"),
            ("Crop Recommendation", {"soil_type": "Alluvial", "season": "Kharif", "temperature": 25}, "Maize"),
        )
        for feature, inputs, result in predictions:
            self._record_for_current_user(
                feature,
                inputs,
                result,
                image_filename="leaf-scan.jpg" if feature == "Disease Detection" else None,
            )

        history_response = self.client.get("/history")
        history_page = history_response.get_data(as_text=True)
        self.assertEqual(history_response.status_code, 200)
        for text in (
            "Date and Time",
            "Module Name",
            "Input Data",
            "Prediction Result",
            "Crop Yield",
            "Disease Detection",
            "Fertilizer Recommendation",
            "Crop Recommendation",
            "Predicted Yield: 2.50 ton/hectare",
            "leaf-scan.jpg",
        ):
            with self.subTest(page="history", text=text):
                self.assertIn(text, history_page)

        report_response = self.client.get("/reports")
        report_page = report_response.get_data(as_text=True)
        self.assertEqual(report_response.status_code, 200)
        for text in (
            "Prediction Reports",
            "Total Predictions",
            "Disease Scans",
            "Yield Predictions",
            "Fertilizer Recommendations",
            "Crop Recommendations",
            "Recent prediction activity",
        ):
            with self.subTest(page="reports", text=text):
                self.assertIn(text, report_page)
        self.assertNotIn("System Health", report_page)
        self.assertNotIn("API Status", report_page)
        self.assertEqual(report_page.count('class="stat-value">4</div>'), 1)
        self.assertEqual(report_page.count('class="stat-value">1</div>'), 4)

        dashboard_page = self.client.get("/dashboard").get_data(as_text=True)
        self.assertIn("Total Predictions", dashboard_page)
        self.assertIn("Crop Recommendations", dashboard_page)
        self.assertEqual(dashboard_page.count('class="stat-value">1</div>'), 4)
        self.assertIn('href="/history"', dashboard_page)
        self.assertIn('href="/reports"', dashboard_page)
        self.assertNotIn('href="/system-status"', dashboard_page)

    def test_history_and_reports_handle_empty_and_invalid_page_requests(self):
        for path in ("/history", "/reports"):
            with self.subTest(path=path):
                empty_response = self.client.get(path)
                self.assertEqual(empty_response.status_code, 200)
                self.assertIn(b"No prediction history yet", empty_response.data)

                for page in ("0", "-1", "invalid"):
                    with self.subTest(page=page):
                        response = self.client.get(f"{path}?page={page}")
                        self.assertEqual(response.status_code, 400)

    def test_history_and_reports_paginate_saved_records(self):
        for index in range(21):
            self._record_for_current_user(
                "Crop Yield", {"temperature": index}, f"Entry {index}"
            )

        first_page = self.client.get("/history?page=1").get_data(as_text=True)
        second_page = self.client.get("/history?page=2").get_data(as_text=True)
        report_second_page = self.client.get("/reports?page=2").get_data(as_text=True)

        self.assertIn("Entry 20", first_page)
        self.assertNotIn("Entry 0", first_page)
        self.assertIn("Entry 0", second_page)
        self.assertNotIn("Entry 1", second_page)
        self.assertIn("Entry 0", report_second_page)
        self.assertIn('href="/history?page=2"', first_page)

    def test_disease_prediction_result_is_saved_to_public_history(self):
        from app import _prediction_history

        original_upload_folder = app.config["UPLOAD_FOLDER"]
        with tempfile.TemporaryDirectory() as upload_folder:
            app.config["UPLOAD_FOLDER"] = upload_folder
            try:
                with patch("app.disease_model", object()), patch(
                    "app.disease_model_error", ""
                ), patch("app._predict_disease", return_value=("Leaf spot", "98.0%", "")):
                    response = self.client.post(
                        "/disease",
                        data={
                            "csrf_token": self._csrf_token("/disease"),
                            "image": (io.BytesIO(b"\xff\xd8\xfftest"), "leaf.jpg"),
                        },
                        content_type="multipart/form-data",
                    )
            finally:
                app.config["UPLOAD_FOLDER"] = original_upload_folder

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Leaf spot", response.data)
        records, total = _prediction_history(1)
        self.assertEqual(total, 1)
        self.assertEqual(records[0]["feature"], "Disease Detection")
        self.assertEqual(records[0]["result"], "Leaf spot (98.0%)")
        self.assertTrue(records[0]["image_filename"])
        from app import _prediction_statistics

        self.assertEqual(_prediction_statistics()["disease_scans"], 1)

    def test_disease_upload_without_model_does_not_create_a_diagnosis_or_history_record(self):
        from app import _prediction_history

        original_upload_folder = app.config["UPLOAD_FOLDER"]
        with tempfile.TemporaryDirectory() as upload_folder:
            app.config["UPLOAD_FOLDER"] = upload_folder
            try:
                with patch("app.disease_model", None), patch(
                    "app.disease_model_error",
                    "No trained disease model is installed. Image uploads are accepted, but the system will not generate a diagnosis.",
                ):
                    response = self.client.post(
                        "/disease",
                        data={
                            "csrf_token": self._csrf_token("/disease"),
                            "image": (io.BytesIO(b"\xff\xd8\xfftest"), "leaf.jpg"),
                        },
                        content_type="multipart/form-data",
                    )
            finally:
                app.config["UPLOAD_FOLDER"] = original_upload_folder

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Image screening is currently unavailable.", response.data)
        self.assertNotIn(b"Required model path", response.data)
        self.assertNotIn(app.config["DISEASE_MODEL_PATH"].encode(), response.data)
        self.assertNotIn(b"Disease Name:", response.data)
        self.assertNotIn(b"Leaf spot", response.data)
        records, total = _prediction_history(1)
        self.assertEqual(records, [])
        self.assertEqual(total, 0)

    def test_disease_results_show_multilingual_farmer_guidance(self):
        original_upload_folder = app.config["UPLOAD_FOLDER"]
        with tempfile.TemporaryDirectory() as upload_folder:
            app.config["UPLOAD_FOLDER"] = upload_folder
            try:
                with patch("app.disease_model", object()), patch(
                    "app.disease_model_error", ""
                ), patch(
                    "app._predict_disease",
                    return_value=("Tomato - Early blight", "96.4%", ""),
                ):
                    csrf_token = self._csrf_token("/disease")
                    response = self.client.post(
                        "/disease",
                        data={
                            "csrf_token": csrf_token,
                            "image": (io.BytesIO(b"\xff\xd8\xfftest"), "leaf.jpg"),
                        },
                        content_type="multipart/form-data",
                    )
                    english_page = response.get_data(as_text=True)
                    self.client.set_cookie("agrivision_language", "hi")
                    hindi_page = self.client.post(
                        "/disease",
                        data={
                            "csrf_token": csrf_token,
                            "image": (io.BytesIO(b"\xff\xd8\xfftest"), "leaf.jpg"),
                        },
                        content_type="multipart/form-data",
                    ).get_data(as_text=True)
            finally:
                app.config["UPLOAD_FOLDER"] = original_upload_folder

        self.assertEqual(response.status_code, 200)
        for expected_text in (
            "Tomato - Early blight",
            "96.4%",
            "Possible Cause",
            "Symptoms to Check",
            "Prevention Methods",
            "Recommended Treatment",
            "Best Farming Practices",
            "AI image screening is advisory",
        ):
            with self.subTest(language="en", text=expected_text):
                self.assertIn(expected_text, english_page)
        self.assertIn("पौध स्वास्थ्य और किसान मार्गदर्शन", hindi_page)
        self.assertIn("किसान मार्गदर्शन", hindi_page)
        self.assertIn("संभावित कारण", hindi_page)
        self.assertIn("फफूंद रोगजनक संक्रमित अवशेष", hindi_page)
        self.assertIn("96.4%", hindi_page)

    def test_every_supported_model_class_has_farmer_guidance(self):
        from app import PLANTVILLAGE_CLASSES
        from disease_guidance import get_disease_guidance
        from translations import LANGUAGES, translate

        guidance_phrases = set()
        for class_name in PLANTVILLAGE_CLASSES:
            display_name = class_name.replace("___", " - ").replace("_", " ")
            with self.subTest(class_name=display_name):
                guidance = get_disease_guidance(display_name)
                self.assertIsNotNone(guidance)
                self.assertEqual(
                    set(guidance),
                    {"cause", "symptoms", "prevention", "treatment", "practices"},
                )
                guidance_phrases.update(guidance.values())

        for phrase in guidance_phrases:
            for language in LANGUAGES:
                if language == "en":
                    continue
                with self.subTest(phrase=phrase, language=language):
                    self.assertNotEqual(translate(phrase, language), phrase)

    def test_crop_recommendation_validates_missing_invalid_and_out_of_range_fields(self):
        base_values = {
            "soil_type": "Alluvial",
            "season": "Kharif",
            "temperature": "25",
            "rainfall": "800",
        }
        cases = (
            ({**base_values, "soil_type": ""}, b"Select a soil type."),
            ({**base_values, "soil_type": "Unknown"}, b"Select a valid soil type from the list."),
            ({**base_values, "season": ""}, b"Select a valid Indian growing season."),
            ({**base_values, "temperature": ""}, b"Temperature is required."),
            ({**base_values, "rainfall": "rainy"}, b"Rainfall during crop season must be a valid number."),
            ({**base_values, "temperature": "nan"}, b"Temperature must be a finite number."),
        )
        for values, expected_message in cases:
            with self.subTest(values=values):
                response = self.client.post(
                    "/crop-recommendation",
                    data={**values, "csrf_token": self._csrf_token("/crop-recommendation")},
                )
                self.assertEqual(response.status_code, 200)
                self.assertIn(expected_message, response.data)
                self.assertNotIn(b"Top crop for further consideration", response.data)

    def test_contact_page_remains_available(self):
        response = self.client.get("/contact")
        page = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Get in touch", page)
        self.assertIn("mailto:420dutyon@gmail.com", page)

    def test_weather_dashboard_does_not_show_fabricated_conditions(self):
        response = self.client.get("/weather")
        page = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("No weather values are shown until a live location lookup succeeds.", page)
        self.assertIn("Temperature affects crop development", page)
        self.assertNotIn("Demo data", page)
        self.assertNotIn("27°C", page)

    def test_weather_dashboard_uses_live_india_only_provider_responses(self):
        geocoding_response = {
            "results": [
                {
                    "name": "Mysuru",
                    "admin1": "Karnataka",
                    "country": "India",
                    "country_code": "IN",
                    "latitude": 12.3,
                    "longitude": 76.6,
                }
            ]
        }
        forecast_response = {
            "current": {
                "time": "2025-01-01T10:00",
                "temperature_2m": 25.2,
                "relative_humidity_2m": 60,
                "wind_speed_10m": 8.5,
            },
            "hourly": {
                "time": ["2025-01-01T10:00"],
                "precipitation_probability": [30],
            },
        }
        with patch(
            "app._fetch_weather_json",
            side_effect=[geocoding_response, forecast_response],
        ) as fetch:
            weather = _get_live_weather("Mysuru")

        self.assertEqual(weather["location"], "Mysuru, Karnataka, India")
        self.assertEqual(weather["temperature"], 25.2)
        self.assertEqual(weather["humidity"], 60)
        self.assertEqual(weather["rainfall_probability"], 30)
        self.assertEqual(weather["wind_speed"], 8.5)
        geocoding_query = parse_qs(urlparse(fetch.call_args_list[0].args[0]).query)
        self.assertEqual(geocoding_query["countryCode"], ["IN"])
        self.assertEqual(fetch.call_count, 2)

    def test_weather_dashboard_rejects_non_indian_locations_and_malformed_forecasts(self):
        non_indian_result = {
            "results": [
                {
                    "name": "Example",
                    "country": "United States",
                    "country_code": "US",
                    "latitude": 10,
                    "longitude": 20,
                }
            ]
        }
        with patch("app._fetch_weather_json", return_value=non_indian_result):
            with self.assertRaises(LookupError):
                _get_live_weather("Example")

        indian_result = {
            "results": [
                {
                    "name": "Mysuru",
                    "country": "India",
                    "country_code": "IN",
                    "latitude": 12.3,
                    "longitude": 76.6,
                }
            ]
        }
        malformed_forecast = {"current": {}, "hourly": {"time": [], "precipitation_probability": []}}
        with patch(
            "app._fetch_weather_json",
            side_effect=[indian_result, malformed_forecast],
        ):
            response = self.client.get("/weather?location=Mysuru")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Live weather is temporarily unavailable", response.data)
        self.assertNotIn(b"27", response.data)

    def test_weather_dashboard_handles_missing_or_unavailable_live_data(self):
        with patch(
            "app._get_live_weather",
            side_effect=LookupError("No matching Indian location was found."),
        ):
            missing_response = self.client.get("/weather?location=Unknown%20Place")
        self.assertEqual(missing_response.status_code, 200)
        self.assertIn(b"No matching Indian city or district was found.", missing_response.data)
        self.assertNotIn(b"27", missing_response.data)

        with patch("app._get_live_weather", side_effect=TimeoutError):
            unavailable_response = self.client.get("/weather?location=Mysuru")
        self.assertEqual(unavailable_response.status_code, 200)
        self.assertIn(b"Live weather is temporarily unavailable", unavailable_response.data)

        with patch("app._get_live_weather") as get_weather:
            invalid_response = self.client.get("/weather?location=x")
        self.assertEqual(invalid_response.status_code, 200)
        self.assertIn(b"Enter an Indian city or district name", invalid_response.data)
        get_weather.assert_not_called()

    def test_static_stylesheet_is_served(self):
        response = self.client.get("/static/css/style.css")
        try:
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"prefers-reduced-motion", response.data)
            self.assertIn(b"@media", response.data)
        finally:
            response.close()

    def test_yield_and_fertilizer_forms_still_submit_successfully(self):
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
                "nitrogen_status": "Medium",
                "phosphorus": "30",
                "phosphorus_status": "Medium",
                "potassium": "30",
                "potassium_status": "Medium",
            },
        )

        self.assertEqual(yield_response.status_code, 200)
        self.assertIn(b"Estimated crop yield:", yield_response.data)
        self.assertIn(b'class="prediction-result mb-4"', yield_response.data)
        self.assertNotIn(b"Predicted Yield:", yield_response.data)
        self.assertEqual(fertilizer_response.status_code, 200)
        self.assertIn(b"No fertilizer rates are calculated", fertilizer_response.data)

        from app import _prediction_history

        records, total = _prediction_history(1)
        self.assertEqual(total, 2)
        self.assertEqual(
            {record["feature"] for record in records},
            {"Crop Yield", "Fertilizer Recommendation"},
        )
        from app import _prediction_statistics

        statistics = _prediction_statistics()
        self.assertEqual(statistics["total_predictions"], 2)
        self.assertEqual(statistics["fertilizer_recommendations"], 1)
        self.assertEqual(statistics["yield_predictions"], 1)

    def test_disease_form_still_shows_upload_validation(self):
        with patch("app.disease_model", None):
            response = self.client.get("/disease")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Image screening is currently unavailable.", response.data)
        self.assertNotIn(b"Required model path", response.data)
        self.assertNotIn(app.config["DISEASE_MODEL_PATH"].encode(), response.data)

        with patch("app.disease_model", None):
            response = self.client.post(
                "/disease",
                data={"csrf_token": self._csrf_token("/disease")},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Choose an image to upload.", response.data)

    def test_system_status_reports_models_database_weather_and_api(self):
        from app import _record_prediction

        _record_prediction("Crop Recommendation", {"soil": "Alluvial"}, "Maize")
        with self.client.session_transaction() as user_session:
            user_session["is_admin"] = True
        with patch(
            "app._get_live_weather",
            return_value={
                "location": "Bengaluru, Karnataka, India",
                "temperature": 25,
            },
        ) as weather_lookup:
            response = self.client.get("/system-status")

        page = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        for label in (
            "Weather Status",
            "Yield Status",
            "Disease Status",
            "Database Status",
            "API Status",
            "Operational",
            "Model Missing",
            "Open-Meteo returned live weather data.",
            "SQLite prediction history and user accounts are readable.",
        ):
            with self.subTest(label=label):
                self.assertIn(label, page)
        self.assertIn(app.config["YIELD_MODEL_PATH"], page)
        self.assertIn(app.config["DISEASE_MODEL_PATH"], page)
        self.assertIn(app.config["HISTORY_DATABASE"], page)
        weather_lookup.assert_called_once_with("Bengaluru")

    def test_system_status_handles_weather_api_failure_without_crashing(self):
        from urllib.error import URLError

        with self.client.session_transaction() as user_session:
            user_session["is_admin"] = True
        with patch("app._get_live_weather", side_effect=URLError("offline")):
            response = self.client.get("/system-status")

        page = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("API Status", page)
        self.assertIn("Unavailable", page)
        self.assertIn("Open-Meteo did not return valid live weather data.", page)


if __name__ == "__main__":
    unittest.main()
