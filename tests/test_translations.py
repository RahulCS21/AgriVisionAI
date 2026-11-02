import re
import os
import tempfile
import unittest
from unittest.mock import patch

from app import app
from translations import LANGUAGES, translate


class TranslationTests(unittest.TestCase):
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

    def _select_language(self, language, next_path="/"):
        page = self.client.get("/").get_data(as_text=True)
        csrf_token = re.search(
            r'name="csrf_token" value="([^"]+)"', page
        ).group(1)
        return self.client.post(
            "/set-language",
            data={
                "csrf_token": csrf_token,
                "language": language,
                "next": next_path,
            },
        )

    def _create_user(self):
        page = self.client.get("/register").get_data(as_text=True)
        csrf_token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
        response = self.client.post(
            "/register",
            data={
                "csrf_token": csrf_token,
                "username": "translation-test-user",
                "password": "test-password-123",
                "confirm_password": "test-password-123",
            },
        )
        self.assertEqual(response.status_code, 302)

    def test_english_is_the_default_and_selector_lists_supported_languages(self):
        response = self.client.get("/yield")
        page = response.get_data(as_text=True)

        self.assertIn('<html lang="en">', page)
        self.assertIn("Generate Yield Estimate", page)
        for language_name in LANGUAGES.values():
            with self.subTest(language=language_name):
                self.assertIn(language_name, page)

    def test_language_selection_persists_and_translates_navigation_and_forms(self):
        for code in ("hi", "kn", "ta", "te"):
            with self.subTest(language=code):
                response = self._select_language(code, "/yield")
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.headers["Location"], "/yield")
                self.assertIn("agrivision_language", response.headers["Set-Cookie"])

                page = self.client.get("/yield").get_data(as_text=True)
                self.assertIn(f'<html lang="{code}">', page)
                self.assertIn(translate("Home", code), page)
                self.assertIn(translate("Temperature", code), page)
                self.assertIn(
                    translate("Generate Yield Estimate", code),
                    page,
                )

    def test_homepage_translations_keep_a_single_language_selector_in_the_navbar(self):
        for code in LANGUAGES:
            with self.subTest(language=code):
                self.client.delete_cookie("agrivision_language")
                self._select_language(code)
                page = self.client.get("/").get_data(as_text=True)
                selector_position = page.index('id="languageSelector"')

                self.assertIn(f'<html lang="{code}">', page)
                self.assertEqual(page.count('id="languageSelector"'), 1)
                self.assertLess(
                    page.rfind("<nav", 0, selector_position),
                    selector_position,
                )
                self.assertGreater(
                    page.find("</nav>", selector_position),
                    selector_position,
                )
                self.assertIn(translate("Grow with insight.", code), page)
                self.assertIn(translate("Harvest with confidence.", code), page)

    def test_feature_pages_render_translated_titles_for_each_language(self):
        pages = (
            ("/dashboard", "Dashboard"),
            ("/history", "Prediction History"),
            ("/reports", "Prediction Reports"),
            ("/system-status", "System Status"),
            ("/yield", "Crop Yield Prediction"),
            ("/disease", "Disease Detection"),
            ("/fertilizer", "Fertilizer Recommendation"),
            ("/crop-recommendation", "Crop Recommendation"),
            ("/weather", "Weather Dashboard"),
            ("/about", "About Us"),
            ("/contact", "Contact Us"),
        )
        for code in LANGUAGES:
            self.client.delete_cookie("agrivision_language")
            self._select_language(code)
            for path, title in pages:
                with self.subTest(language=code, page=path):
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
                            page = self.client.get(path).get_data(as_text=True)
                    else:
                        page = self.client.get(path).get_data(as_text=True)
                    self.assertIn(translate(title, code), page)

    def test_public_pages_show_clean_translated_copy(self):
        phrases = (
            ("/yield", "Estimate crop yield from temperature, rainfall, and humidity."),
            ("/yield", "Enter your local conditions to get a crop yield estimate."),
            ("/disease", "Upload a clear leaf image to review plant health and receive practical guidance."),
            ("/fertilizer", "Use your Soil Health Card nutrient ratings to review cautious, crop-aware nutrient guidance."),
            ("/crop-recommendation", "Compare major Indian crops with broad soil, season, temperature, and monsoon-rainfall suitability bands."),
            ("/weather", "Choose a location to view current conditions"),
        )
        for code in LANGUAGES:
            self.client.delete_cookie("agrivision_language")
            self._select_language(code)
            report_page = self.client.get("/reports").get_data(as_text=True)
            self.assertIn(translate("Crop Recommendations", code), report_page)
            for path, phrase in phrases:
                with self.subTest(language=code, page=path):
                    page = self.client.get(path).get_data(as_text=True)
                    self.assertIn(translate(phrase, code), page)

    def test_translated_validation_and_prediction_output_keep_model_value(self):
        self._select_language("hi")
        invalid_response = self.client.post(
            "/yield",
            data={
                "csrf_token": re.search(
                    r'name="csrf_token" value="([^"]+)"',
                    self.client.get("/yield").get_data(as_text=True),
                ).group(1),
                "temperature": "",
                "rainfall": "100",
                "humidity": "60",
            },
        )
        self.assertIn("तापमान आवश्यक है।".encode(), invalid_response.data)

        valid_response = self.client.post(
            "/crop-recommendation",
            data={
                "csrf_token": re.search(
                    r'name="csrf_token" value="([^"]+)"',
                    self.client.get("/crop-recommendation").get_data(as_text=True),
                ).group(1),
                "soil_type": "Alluvial",
                "season": "Kharif",
                "temperature": "25",
                "rainfall": "800",
            },
        )
        page = valid_response.get_data(as_text=True)
        self.assertIn(translate("Top crop for further consideration", "hi"), page)
        self.assertIn("Maize", page)

    def test_language_redirect_cannot_leave_the_site(self):
        response = self._select_language("hi", "//example.com")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/")

    def test_unknown_language_falls_back_to_english(self):
        response = self._select_language("xx", "/")

        self.assertIn("agrivision_language=en", response.headers["Set-Cookie"])
        self.assertIn("Dashboard", self.client.get("/dashboard").get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
