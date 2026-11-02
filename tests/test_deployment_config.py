import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class DeploymentConfigTests(unittest.TestCase):
    def test_production_uses_environment_secret_database_and_secure_cookies(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = str(Path(temp_dir) / "persistent" / "history.sqlite3")
            environment = os.environ.copy()
            environment.update(
                {
                    "AGRIVISION_ENV": "production",
                    "AGRIVISION_SECRET_KEY": "test-production-secret",
                    "AGRIVISION_HISTORY_DATABASE": database_path,
                }
            )
            environment.pop("AGRIVISION_COOKIE_SECURE", None)
            script = "\n".join(
                (
                    "from app import _history_connection, app",
                    "assert app.config['SECRET_KEY'] == 'test-production-secret'",
                    "assert app.config['SECRET_KEY_CONFIGURED'] is True",
                    f"assert app.config['HISTORY_DATABASE'] == {database_path!r}",
                    "assert app.config['SESSION_COOKIE_SECURE'] is True",
                    "with _history_connection() as connection:",
                    "    connection.execute('SELECT 1')",
                    "assert app.test_client().get('/').status_code == 200",
                )
            )

            result = subprocess.run(
                [sys.executable, "-c", script],
                cwd=PROJECT_ROOT,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(Path(database_path).is_file())

    def test_production_requires_a_persistent_secret_key(self):
        environment = os.environ.copy()
        environment["AGRIVISION_ENV"] = "production"
        environment.pop("AGRIVISION_SECRET_KEY", None)
        result = subprocess.run(
            [sys.executable, "-c", "import app"],
            cwd=PROJECT_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "AGRIVISION_SECRET_KEY must be configured in production",
            result.stderr,
        )

    def test_procfile_points_gunicorn_at_the_platform_port_and_wsgi_app(self):
        procfile = (PROJECT_ROOT / "Procfile").read_text(encoding="utf-8").strip()

        self.assertEqual(
            procfile,
            "web: AGRIVISION_ENV=production gunicorn --bind 0.0.0.0:$PORT "
            "--workers 1 --threads 4 app:app",
        )


if __name__ == "__main__":
    unittest.main()
