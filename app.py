import hmac
import json
import math
import os
import re
import secrets
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta
from functools import wraps
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.parse import urlparse

import joblib
import numpy as np
import pandas as pd
from flask import (
    Flask,
    abort,
    flash,
    has_request_context,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from agriculture import (
    SEASONS,
    SOIL_TYPES,
    fertilizer_guidance,
    recommend_indian_crop,
)
from disease_guidance import get_disease_guidance
from translations import LANGUAGES, translate

app = Flask(__name__)
production_environment = (
    os.environ.get("AGRIVISION_ENV", "development").strip().lower()
    == "production"
)
configured_secret_key = os.environ.get("AGRIVISION_SECRET_KEY")
if production_environment and not configured_secret_key:
    raise RuntimeError(
        "AGRIVISION_SECRET_KEY must be configured in production."
    )

local_admin_config = {}
local_admin_config_path = os.path.join(
    app.instance_path,
    "local_admin.json",
)
local_development_enabled = (
    os.environ.get("AGRIVISION_ENV", "development").lower() == "development"
)
if local_development_enabled and os.path.isfile(local_admin_config_path):
    try:
        with open(local_admin_config_path, encoding="utf-8") as config_file:
            local_admin_config = json.load(config_file)
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            "The local administrator configuration cannot be read."
        ) from exc
    if (
        not isinstance(local_admin_config, dict)
        or not all(
            isinstance(local_admin_config.get(key), str)
            and local_admin_config[key]
            for key in ("secret_key", "username", "password_hash")
        )
    ):
        raise RuntimeError("The local administrator configuration is invalid.")

app.config["SECRET_KEY"] = (
    configured_secret_key
    or local_admin_config.get("secret_key")
    or secrets.token_hex(32)
)
app.config["SECRET_KEY_CONFIGURED"] = bool(
    configured_secret_key or local_admin_config.get("secret_key")
)
app.config["ADMIN_USERNAME"] = (
    os.environ.get("AGRIVISION_ADMIN_USERNAME")
    or local_admin_config.get("username")
)
app.config["ADMIN_PASSWORD_HASH"] = (
    os.environ.get("AGRIVISION_ADMIN_PASSWORD_HASH")
    or local_admin_config.get("password_hash")
)
app.config["HISTORY_DATABASE"] = (
    os.environ.get("AGRIVISION_HISTORY_DATABASE")
    or os.path.join(app.instance_path, "prediction_history.sqlite3")
)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get(
    "AGRIVISION_COOKIE_SECURE", "1" if production_environment else ""
).lower() in {"1", "true", "yes"}
app.config["LANGUAGE_COOKIE_SECURE"] = app.config["SESSION_COOKIE_SECURE"]
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=30)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "static", "uploads")
app.config["DISEASE_MODEL_PATH"] = os.path.join(
    app.root_path, "models", "disease_model.h5"
)
app.config["YIELD_MODEL_PATH"] = os.path.join(
    app.root_path, "models", "yield_model.pkl"
)
app.config["WEATHER_API_TIMEOUT"] = 8
if not app.config["SECRET_KEY_CONFIGURED"]:
    app.logger.warning(
        "AGRIVISION_SECRET_KEY is unset; using a process-local key. "
        "Configure a persistent key before deployment."
    )

YIELD_FIELDS = {
    "temperature": "Temperature",
    "rainfall": "Rainfall",
    "humidity": "Humidity",
}

yield_model = None
yield_model_error = ""
if os.path.isfile(app.config["YIELD_MODEL_PATH"]):
    try:
        loaded_yield_model = joblib.load(app.config["YIELD_MODEL_PATH"])
        if list(getattr(loaded_yield_model, "feature_names_in_", ())) != list(
            YIELD_FIELDS
        ):
            raise ValueError(
                "Yield model does not match the application feature schema."
            )
    except (
        OSError,
        EOFError,
        ValueError,
        ImportError,
        AttributeError,
        TypeError,
    ) as exc:
        yield_model_error = "The demonstration yield model could not be loaded."
        app.logger.exception("Failed to load the demonstration yield model: %s", exc)
    else:
        yield_model = loaded_yield_model


def _admin_is_configured():
    secret_key_configured = app.config.get("SECRET_KEY_CONFIGURED") or app.testing
    return all(
        app.config.get(key)
        for key in ("ADMIN_USERNAME", "ADMIN_PASSWORD_HASH")
    ) and secret_key_configured


def _current_language():
    language = request.cookies.get("agrivision_language", "en")
    return language if language in LANGUAGES else "en"


def _translate(message):
    return translate(message, _current_language())


@app.context_processor
def inject_language():
    language = _current_language()
    return {
        "t": lambda message: translate(message, language),
        "current_language": language,
        "languages": LANGUAGES,
        "csrf_token": _csrf_token(),
        "is_authenticated": isinstance(session.get("user_id"), int),
        "current_username": session.get("username", ""),
        "is_admin": session.get("is_admin") is True,
    }


@contextmanager
def _history_connection():
    database_path = app.config["HISTORY_DATABASE"]
    os.makedirs(os.path.dirname(os.path.abspath(database_path)), exist_ok=True)
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS prediction_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                feature TEXT NOT NULL,
                inputs TEXT NOT NULL,
                result TEXT NOT NULL,
                image_filename TEXT,
                user_id INTEGER REFERENCES users(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS weather_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                location TEXT NOT NULL,
                user_id INTEGER REFERENCES users(id)
            )
            """
        )
        columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(prediction_history)"
            ).fetchall()
        }
        if "user_id" not in columns:
            connection.execute(
                "ALTER TABLE prediction_history ADD COLUMN user_id INTEGER REFERENCES users(id)"
            )
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _record_prediction(feature, inputs, result, image_filename=None):
    user_id = session.get("user_id") if has_request_context() else None
    with _history_connection() as connection:
        connection.execute(
            """
            INSERT INTO prediction_history
                (feature, inputs, result, image_filename, user_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                feature,
                json.dumps(inputs),
                result,
                image_filename,
                user_id,
            ),
        )


def _record_weather_request(location):
    user_id = session.get("user_id") if has_request_context() else None
    with _history_connection() as connection:
        connection.execute(
            "INSERT INTO weather_requests (location, user_id) VALUES (?, ?)",
            (location, user_id),
        )


def _csrf_token():
    token = session.get("csrf_token")
    if token is None:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def _validate_csrf():
    token = request.form.get("csrf_token", "")
    expected_token = session.get("csrf_token", "")
    if not token or not expected_token or not hmac.compare_digest(token, expected_token):
        abort(400, description="The form expired. Reload the page and try again.")


def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if session.get("is_admin") is not True:
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)

    return wrapped_view


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not isinstance(session.get("user_id"), int):
            return redirect(
                url_for(
                    "login",
                    next=request.full_path.rstrip("?"),
                )
            )
        return view(*args, **kwargs)

    return wrapped_view


def _safe_local_redirect(target, fallback):
    parsed = urlparse(target or "")
    if (
        parsed.scheme
        or parsed.netloc
        or not parsed.path.startswith("/")
        or parsed.path.startswith("//")
        or "\\" in parsed.path
    ):
        return fallback
    return target


def _safe_upload_path(filename):
    if not filename or os.path.basename(filename) != filename:
        abort(404)
    upload_folder = os.path.realpath(app.config["UPLOAD_FOLDER"])
    image_path = os.path.realpath(os.path.join(upload_folder, filename))
    if os.path.commonpath((upload_folder, image_path)) != upload_folder:
        abort(404)
    return image_path


def _prediction_history(page, per_page=25, user_id=None):
    with _history_connection() as connection:
        where = " WHERE user_id = ?" if user_id is not None else ""
        parameters = (user_id,) if user_id is not None else ()
        total = connection.execute(
            f"SELECT COUNT(*) FROM prediction_history{where}",
            parameters,
        ).fetchone()[0]
        rows = connection.execute(
            f"""
            SELECT id, created_at, feature, inputs, result, image_filename
            FROM prediction_history
            {where}
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            (*parameters, per_page, (page - 1) * per_page),
        ).fetchall()
    records = []
    for row in rows:
        record = dict(row)
        record["inputs"] = json.loads(record["inputs"])
        records.append(record)
    return records, total


def _prediction_statistics(user_id=None):
    counts = {
        "Crop Yield": 0,
        "Disease Detection": 0,
        "Fertilizer Recommendation": 0,
        "Crop Recommendation": 0,
    }
    with _history_connection() as connection:
        where = " WHERE user_id = ?" if user_id is not None else ""
        parameters = (user_id,) if user_id is not None else ()
        rows = connection.execute(
            f"""
            SELECT feature, COUNT(*) AS prediction_count
            FROM prediction_history
            {where}
            GROUP BY feature
            """,
            parameters,
        ).fetchall()
    total_predictions = 0
    for row in rows:
        prediction_count = row["prediction_count"]
        total_predictions += prediction_count
        if row["feature"] in counts:
            counts[row["feature"]] = prediction_count
        elif row["feature"] == "Disease Detection":
            counts["Disease Detection"] = prediction_count
    with _history_connection() as connection:
        weather_requests = connection.execute(
            f"SELECT COUNT(*) FROM weather_requests{where}",
            parameters,
        ).fetchone()[0]
    return {
        "total_predictions": total_predictions,
        "disease_scans": counts["Disease Detection"],
        "yield_predictions": counts["Crop Yield"],
        "fertilizer_recommendations": counts["Fertilizer Recommendation"],
        "crop_recommendations": counts["Crop Recommendation"],
        "weather_requests": weather_requests,
    }


def _system_health(check_api=False):
    yield_model_installed = os.path.isfile(app.config["YIELD_MODEL_PATH"])
    yield_model_ready = yield_model is not None
    yield_status = (
        "Operational"
        if yield_model_ready
        else "Setup Required"
        if yield_model_installed
        else "Model Missing"
    )
    yield_detail = (
        "Experimental demonstration model loaded from 10 generic recovered rows; not production-grade."
        if yield_model_ready
        else yield_model_error
        if yield_model_installed
        else "AI yield model not installed."
    )
    disease_model_installed = os.path.isfile(app.config["DISEASE_MODEL_PATH"])
    disease_model_available = disease_model is not None
    disease_status = (
        "Operational"
        if disease_model_available
        else "Setup Required"
        if disease_model_installed
        else "Model Missing"
    )

    database_available = False
    database_detail = "The prediction database is unavailable."
    database_path = app.config["HISTORY_DATABASE"]
    try:
        if not os.path.isfile(database_path):
            raise sqlite3.OperationalError("Prediction database does not exist.")
        with _history_connection() as connection:
            connection.execute("SELECT COUNT(*) FROM prediction_history").fetchone()
            connection.execute("SELECT COUNT(*) FROM users").fetchone()
        database_available = True
        database_detail = "SQLite prediction history and user accounts are readable."
    except (OSError, sqlite3.Error) as exc:
        app.logger.warning("System status database check failed: %s", exc)

    api_status = "Not checked"
    api_available = False
    api_detail = "Open-Meteo connectivity is checked on this page."
    weather_status = "Configured"
    weather_detail = "Live Indian-city weather lookup is configured."
    if check_api:
        try:
            live_weather = _get_live_weather("Bengaluru")
        except (
            LookupError,
            URLError,
            TimeoutError,
            OSError,
            ValueError,
            KeyError,
            TypeError,
            json.JSONDecodeError,
            UnicodeError,
            IndexError,
            AttributeError,
        ) as exc:
            app.logger.warning("System status weather API check failed: %s", exc)
            api_status = "Unavailable"
            api_detail = "Open-Meteo did not return valid live weather data."
            weather_status = "Unavailable"
            weather_detail = "Live weather lookup failed during this status check."
        else:
            api_available = True
            api_status = "Operational"
            api_detail = "Open-Meteo returned live weather data."
            weather_status = "Operational"
            weather_detail = (
                f"Live weather lookup succeeded for {live_weather['location']}."
            )

    components = [
        {
            "label": "Weather Status",
            "status": weather_status,
            "operational": weather_status in {"Operational", "Configured"},
            "detail": weather_detail,
        },
        {
            "label": "Yield Status",
            "status": yield_status,
            "operational": yield_model_ready,
            "detail": yield_detail,
            "path": app.config["YIELD_MODEL_PATH"],
        },
        {
            "label": "Disease Status",
            "status": disease_status,
            "operational": disease_model_available,
            "detail": (
                "AI disease model is loaded."
                if disease_model_available
                else "AI disease model not installed."
                if not disease_model_installed
                else "The disease model file exists but could not be loaded."
            ),
            "path": app.config["DISEASE_MODEL_PATH"],
        },
        {
            "label": "Database Status",
            "status": "Operational" if database_available else "Unavailable",
            "operational": database_available,
            "detail": database_detail,
            "path": database_path,
        },
        {
            "label": "API Status",
            "status": api_status,
            "operational": api_available,
            "detail": api_detail,
        },
    ]
    return {
        "components": components,
        "yield_model_installed": yield_model_installed,
        "yield_model_ready": yield_model_ready,
        "disease_model_installed": disease_model_installed,
        "disease_model_available": disease_model_available,
    }


PLANTVILLAGE_CLASSES = [
    "Apple___Apple_scab",
    "Apple___Black_rot",
    "Apple___Cedar_apple_rust",
    "Apple___healthy",
    "Blueberry___healthy",
    "Cherry_(including_sour)___Powdery_mildew",
    "Cherry_(including_sour)___healthy",
    "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot",
    "Corn_(maize)___Common_rust_",
    "Corn_(maize)___Northern_Leaf_Blight",
    "Corn_(maize)___healthy",
    "Grape___Black_rot",
    "Grape___Esca_(Black_Measles)",
    "Grape___Leaf_blight_(Isariopsis_Leaf_Spot)",
    "Grape___healthy",
    "Orange___Haunglongbing_(Citrus_greening)",
    "Peach___Bacterial_spot",
    "Peach___healthy",
    "Pepper,_bell___Bacterial_spot",
    "Pepper,_bell___healthy",
    "Potato___Early_blight",
    "Potato___Late_blight",
    "Potato___healthy",
    "Raspberry___healthy",
    "Soybean___healthy",
    "Squash___Powdery_mildew",
    "Strawberry___Leaf_scorch",
    "Strawberry___healthy",
    "Tomato___Bacterial_spot",
    "Tomato___Early_blight",
    "Tomato___Late_blight",
    "Tomato___Leaf_Mold",
    "Tomato___Septoria_leaf_spot",
    "Tomato___Spider_mites Two-spotted_spider_mite",
    "Tomato___Target_Spot",
    "Tomato___Tomato_Yellow_Leaf_Curl_Virus",
    "Tomato___Tomato_mosaic_virus",
    "Tomato___healthy",
]

try:
    import tensorflow as tf
except (ImportError, OSError) as exc:
    tf = None
    app.logger.warning("TensorFlow is unavailable; disease inference is disabled: %s", exc)

disease_model = None
disease_model_error = ""
if tf is not None and os.path.isfile(app.config["DISEASE_MODEL_PATH"]):
    try:
        disease_model = tf.keras.models.load_model(app.config["DISEASE_MODEL_PATH"])
    except (OSError, ValueError, ImportError, TypeError) as exc:
        disease_model_error = "The disease model could not be loaded."
        app.logger.exception("Failed to load the disease model")
elif tf is None:
    disease_model_error = (
        "Disease screening is unavailable: TensorFlow is not installed and no "
        "trained model can be used."
    )
else:
    disease_model_error = (
        "No trained disease model is installed. Image uploads are accepted, but "
        "the system will not generate a diagnosis."
    )


def _read_image_extension(upload):
    extension = os.path.splitext(secure_filename(upload.filename))[1].lower()
    header = upload.stream.read(12)
    upload.stream.seek(0)

    signatures = {
        ".jpg": header.startswith(b"\xff\xd8\xff"),
        ".jpeg": header.startswith(b"\xff\xd8\xff"),
        ".png": header.startswith(b"\x89PNG\r\n\x1a\n"),
        ".gif": header.startswith((b"GIF87a", b"GIF89a")),
        ".webp": header.startswith(b"RIFF") and header[8:12] == b"WEBP",
    }

    if not signatures.get(extension, False):
        return None
    return extension
def _predict_disease(image_path):
    if disease_model is None or tf is None:
        return "", "", disease_model_error

    image = tf.keras.utils.load_img(image_path, target_size=(224, 224))
    image_array = tf.keras.utils.img_to_array(image)
    batch = np.expand_dims(image_array, axis=0)
    scores = np.asarray(disease_model.predict(batch, verbose=0))
    if scores.ndim != 2 or scores.shape[0] != 1:
        raise ValueError("Disease model must return one class-score row per image.")

    scores = scores[0]
    if scores.size != len(PLANTVILLAGE_CLASSES):
        raise ValueError(
            f"Disease model returned {scores.size} scores; expected "
            f"{len(PLANTVILLAGE_CLASSES)} PlantVillage classes."
        )
    if not np.all(np.isfinite(scores)):
        raise ValueError("Disease model returned non-finite class scores.")

    if np.any(scores < 0) or np.any(scores > 1) or not np.isclose(scores.sum(), 1.0):
        shifted_scores = scores - np.max(scores)
        probabilities = np.exp(shifted_scores)
        probabilities /= probabilities.sum()
    else:
        probabilities = scores

    class_index = int(np.argmax(probabilities))
    class_name = PLANTVILLAGE_CLASSES[class_index].replace("___", " - ").replace("_", " ")
    confidence = f"{probabilities[class_index] * 100:.1f}%"
    return class_name, confidence, ""


def _fetch_weather_json(url):
    api_request = Request(
        url,
        headers={"User-Agent": "AgriVisionAI/1.0", "Accept": "application/json"},
    )
    with urlopen(api_request, timeout=app.config["WEATHER_API_TIMEOUT"]) as response:
        return json.loads(response.read().decode("utf-8"))


def _get_live_weather(location_query):
    geocoding_url = (
        "https://geocoding-api.open-meteo.com/v1/search?"
        + urlencode(
            {
                "name": location_query,
                "countryCode": "IN",
                "count": 1,
                "language": "en",
                "format": "json",
            }
        )
    )
    geocoding = _fetch_weather_json(geocoding_url)
    locations = geocoding.get("results")
    if not isinstance(locations, list):
        locations = []
    match = next(
        (
            location
            for location in locations
            if isinstance(location, dict) and location.get("country_code") == "IN"
        ),
        None,
    )
    if match is None:
        raise LookupError("No matching Indian location was found.")
    if "latitude" not in match or "longitude" not in match:
        raise ValueError("Geocoding provider returned an invalid location.")

    forecast_url = (
        "https://api.open-meteo.com/v1/forecast?"
        + urlencode(
            {
                "latitude": match["latitude"],
                "longitude": match["longitude"],
                "current": (
                    "temperature_2m,relative_humidity_2m,wind_speed_10m"
                ),
                "hourly": "precipitation_probability",
                "forecast_days": 1,
                "timezone": "auto",
            }
        )
    )
    forecast = _fetch_weather_json(forecast_url)
    if not isinstance(forecast, dict):
        raise ValueError("Weather provider returned an invalid forecast.")
    current = forecast.get("current")
    hourly = forecast.get("hourly")
    if not isinstance(current, dict) or not isinstance(hourly, dict):
        raise ValueError("Weather provider returned an invalid forecast.")
    current_time_value = current.get("time")
    if not current_time_value:
        raise ValueError("Weather provider returned no observation time.")
    current_time = datetime.fromisoformat(current_time_value)
    time_values = hourly.get("time")
    probabilities = hourly.get("precipitation_probability")
    if (
        not isinstance(time_values, list)
        or not isinstance(probabilities, list)
        or len(time_values) != len(probabilities)
        or not time_values
    ):
        raise ValueError("Weather provider returned no hourly forecast.")
    hourly_times = [datetime.fromisoformat(value) for value in time_values]
    closest_hour = min(
        range(len(hourly_times)),
        key=lambda index: abs((hourly_times[index] - current_time).total_seconds()),
    )
    probability = probabilities[closest_hour]
    if probability is None:
        raise ValueError("Weather provider returned no rainfall probability.")

    weather_values = {
        "temperature": float(current.get("temperature_2m")),
        "humidity": float(current.get("relative_humidity_2m")),
        "rainfall_probability": float(probability),
        "wind_speed": float(current.get("wind_speed_10m")),
    }
    if not all(math.isfinite(value) for value in weather_values.values()):
        raise ValueError("Weather provider returned non-finite conditions.")
    if not 0 <= weather_values["humidity"] <= 100:
        raise ValueError("Weather provider returned invalid humidity.")
    if not 0 <= weather_values["rainfall_probability"] <= 100:
        raise ValueError("Weather provider returned invalid rainfall probability.")
    if weather_values["wind_speed"] < 0:
        raise ValueError("Weather provider returned invalid wind speed.")

    display_location = ", ".join(
        part
        for part in (match.get("name"), match.get("admin1"), match.get("country"))
        if part
    )
    return {
        "temperature": round(weather_values["temperature"], 1),
        "humidity": round(weather_values["humidity"]),
        "rainfall_probability": round(weather_values["rainfall_probability"]),
        "wind_speed": round(weather_values["wind_speed"], 1),
        "location": display_location,
        "source": "Live data from Open-Meteo",
        "observed_at": current_time_value,
    }


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if isinstance(session.get("user_id"), int):
        return redirect(url_for("dashboard_page"))

    error = ""
    username = ""
    if request.method == "POST":
        _validate_csrf()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not re.fullmatch(r"[A-Za-z0-9_.-]{3,32}", username):
            error = _translate(
                "Choose a username of 3–32 letters, numbers, dots, dashes, or underscores."
            )
        elif len(password) < 8:
            error = _translate("Choose a password with at least 8 characters.")
        elif len(password) > 1024:
            error = _translate("Choose a shorter password.")
        elif password != confirm_password:
            error = _translate("Passwords do not match.")
        else:
            try:
                with _history_connection() as connection:
                    connection.execute(
                        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                        (username, generate_password_hash(password)),
                    )
                    user = connection.execute(
                        "SELECT id, username FROM users WHERE username = ?",
                        (username,),
                    ).fetchone()
            except sqlite3.IntegrityError:
                error = _translate("That username is already registered.")
            else:
                session.clear()
                session["user_id"] = user["id"]
                session["username"] = user["username"]
                session["csrf_token"] = secrets.token_urlsafe(32)
                session.permanent = True
                flash(_translate("Your account is ready."), "success")
                next_url = _safe_local_redirect(
                    request.args.get("next", ""), url_for("dashboard_page")
                )
                return redirect(next_url)

    return render_template(
        "register.html",
        error=error,
        username=username,
        next_url=_safe_local_redirect(
            request.args.get("next", ""), url_for("dashboard_page")
        ),
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if isinstance(session.get("user_id"), int):
        return redirect(url_for("dashboard_page"))

    error = ""
    username = ""
    next_url = _safe_local_redirect(
        request.args.get("next", ""), url_for("dashboard_page")
    )
    if request.method == "POST":
        _validate_csrf()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = None
        password_matches = False
        if username and len(username) <= 32 and len(password) <= 1024:
            with _history_connection() as connection:
                user = connection.execute(
                    "SELECT id, username, password_hash FROM users WHERE username = ?",
                    (username,),
                ).fetchone()
        if user is not None and len(password) <= 1024:
            try:
                password_matches = check_password_hash(
                    user["password_hash"], password
                )
            except (TypeError, ValueError):
                app.logger.exception("Stored user password hash is invalid")
                abort(500)
        if password_matches:
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["csrf_token"] = secrets.token_urlsafe(32)
            session.permanent = True
            return redirect(
                _safe_local_redirect(
                    request.form.get("next", ""), url_for("dashboard_page")
                )
            )
        error = _translate("Invalid username or password.")
    return render_template(
        "login.html",
        error=error,
        username=username,
        next_url=next_url,
    )


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    _validate_csrf()
    session.clear()
    flash(_translate("You have been logged out."), "success")
    return redirect(url_for("home"))


@app.route("/profile")
@login_required
def user_profile():
    user_id = session["user_id"]
    with _history_connection() as connection:
        user = connection.execute(
            "SELECT username, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if user is None:
            session.clear()
            return redirect(url_for("login"))
        activity = connection.execute(
            """
            SELECT COUNT(*) AS total,
                   MAX(created_at) AS last_activity
            FROM prediction_history
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
    return render_template(
        "profile.html",
        user=user,
        activity=activity,
    )


@app.route("/set-language", methods=["POST"])
def set_language():
    _validate_csrf()
    language = request.form.get("language", "en")
    if language not in LANGUAGES:
        language = "en"

    next_url = request.form.get("next", "/")
    parsed_url = urlparse(next_url)
    if parsed_url.scheme or parsed_url.netloc or not parsed_url.path.startswith("/") or parsed_url.path.startswith("//"):
        next_url = "/"

    response = redirect(next_url)
    response.set_cookie(
        "agrivision_language",
        language,
        max_age=60 * 60 * 24 * 365,
        httponly=True,
        secure=app.config["LANGUAGE_COOKIE_SECURE"],
        samesite="Lax",
        path="/",
    )
    return response


@app.route("/dashboard")
def dashboard_page():
    features = [
        {
            "title": "Crop Yield Prediction",
            "description": "Estimate crop yield from local growing conditions.",
            "icon": "bi-graph-up-arrow",
            "endpoint": "yield_page",
            "action": "Estimate crop yield",
            "category": "Production insights",
            "status": "Available" if yield_model is not None else "Currently unavailable",
        },
        {
            "title": "Disease Detection",
            "description": "Review plant health with a clear leaf image.",
            "icon": "bi-shield-check",
            "endpoint": "disease_page",
            "action": "Analyze a leaf image",
            "category": "Plant health",
            "status": "Available" if disease_model is not None else "Currently unavailable",
        },
        {
            "title": "Fertilizer Recommendation",
            "description": "Review qualitative guidance using Soil Health Card ratings.",
            "icon": "bi-droplet-half",
            "endpoint": "fertilizer_page",
            "action": "Review soil nutrients",
            "category": "Soil guidance",
            "status": "Available",
        },
        {
            "title": "Crop Recommendation",
            "description": "Screen broad Indian crop suitability ranges.",
            "icon": "bi-signpost-split",
            "endpoint": "crop_recommendation_page",
            "action": "Plan a crop",
            "category": "Crop planning",
            "status": "Available",
        },
        {
            "title": "Weather Dashboard",
            "description": "Retrieve current weather for an Indian city or district.",
            "icon": "bi-cloud-sun",
            "endpoint": "weather_dashboard",
            "action": "View weather",
            "category": "Weather insights",
            "status": "Available",
        },
    ]
    return render_template(
        "dashboard.html",
        features=features,
        total_features=len(features),
        prediction_statistics=_prediction_statistics(
            session.get("user_id")
            if isinstance(session.get("user_id"), int)
            else -1
        ),
    )


@app.route("/history")
@login_required
def prediction_history_page():
    page = _requested_history_page()
    per_page = 20
    user_id = session["user_id"]
    records, total_records = _prediction_history(page, per_page, user_id)
    total_pages = max((total_records + per_page - 1) // per_page, 1)
    if page > total_pages:
        page = total_pages
        records, total_records = _prediction_history(page, per_page, user_id)
    return render_template(
        "history.html",
        records=records,
        page=page,
        total_pages=total_pages,
        total_records=total_records,
    )


@app.route("/reports")
@login_required
def prediction_reports_page():
    page = _requested_history_page()
    per_page = 20
    user_id = session["user_id"]
    records, total_records = _prediction_history(page, per_page, user_id)
    total_pages = max((total_records + per_page - 1) // per_page, 1)
    if page > total_pages:
        page = total_pages
        records, total_records = _prediction_history(page, per_page, user_id)
    return render_template(
        "reports.html",
        records=records,
        page=page,
        total_pages=total_pages,
        total_records=total_records,
        prediction_statistics=_prediction_statistics(user_id),
    )


@app.route("/system-status")
@admin_required
def system_status_page():
    return render_template(
        "system_status.html",
        system_health=_system_health(check_api=True),
    )


def _requested_history_page():
    raw_page = request.args.get("page")
    if raw_page is None:
        return 1
    try:
        page = int(raw_page)
    except ValueError:
        abort(400, description=_translate("Page number must be a positive integer."))
    if page < 1:
        abort(400, description=_translate("Page number must be a positive integer."))
    return page


@app.route("/about")
def about_page():
    return render_template("about.html")


@app.route("/contact")
def contact_page():
    return render_template("contact.html")


@app.route("/privacy")
def privacy_policy_page():
    return render_template("privacy.html")


@app.route("/weather")
def weather_dashboard():
    location_query = request.args.get("location", "").strip()
    weather = None
    error = ""
    weather_requested = False
    if location_query:
        if len(location_query) > 100 or len(location_query) < 2:
            error = _translate("Enter an Indian city or district name (2 to 100 characters).")
        else:
            weather_requested = True
            try:
                weather = _get_live_weather(location_query)
            except LookupError:
                error = _translate("No matching Indian city or district was found.")
            except (
                URLError,
                TimeoutError,
                ValueError,
                KeyError,
                TypeError,
                json.JSONDecodeError,
                UnicodeError,
                IndexError,
                AttributeError,
            ) as exc:
                app.logger.warning("Live weather lookup failed: %s", exc)
                error = _translate("Live weather is temporarily unavailable. Please try again later.")
    if weather_requested:
        _record_weather_request(location_query)
    return render_template(
        "weather.html",
        weather=weather,
        error=error,
        location_query=location_query,
    )


@app.route("/yield", methods=["GET", "POST"])
def yield_page():
    result = ""
    error = ""
    model_ready = yield_model is not None
    values = {field: "" for field in YIELD_FIELDS}

    if request.method == "POST":
        _validate_csrf()
        values = {
            field: request.form.get(field, "").strip()
            for field in YIELD_FIELDS
        }
        numeric_values = {}
        numeric_bounds = {
            "temperature": (-90, 60),
            "rainfall": (0, None),
            "humidity": (0, 100),
        }

        for field, label in YIELD_FIELDS.items():
            value = values[field]
            if not value:
                error = _translate(f"{label} is required.")
                break
            try:
                number = float(value)
            except ValueError:
                error = _translate(f"{label} must be a valid number.")
                break
            if not np.isfinite(number):
                error = _translate(f"{label} must be a finite number.")
                break
            minimum, maximum = numeric_bounds[field]
            if number < minimum or (
                maximum is not None and number > maximum
            ):
                error = _translate(
                    f"{label} must be between {minimum} and {maximum}."
                    if maximum is not None
                    else f"{label} must be at least {minimum}."
                )
                break
            numeric_values[field] = number

        if not error and model_ready:
            try:
                prediction = float(
                    yield_model.predict(
                        pd.DataFrame(
                            [numeric_values], columns=list(YIELD_FIELDS)
                        )
                    )[0]
                )
                if not math.isfinite(prediction):
                    raise ValueError("Yield model returned a non-finite result.")
            except (OSError, ValueError, TypeError, AttributeError) as exc:
                app.logger.exception(
                    "Experimental demonstration yield prediction failed: %s", exc
                )
                error = _translate(
                    "The yield estimate could not be generated. Please check your inputs and try again."
                )
            else:
                result = f"{_translate('Estimated crop yield:')} {prediction:.2f}"
                _record_prediction("Crop Yield", numeric_values, result)

    return render_template(
        "yield.html",
        result=result,
        error=error,
        values=values,
        model_ready=model_ready,
    )


@app.route("/disease", methods=["GET", "POST"])
def disease_page():
    error = ""
    preview_url = ""
    disease_name = ""
    confidence = ""
    guidance = None
    if request.method == "POST":
        _validate_csrf()
        image = request.files.get("image")
        if image is None or not image.filename:
            error = _translate("Choose an image to upload.")
        else:
            extension = _read_image_extension(image)
            if extension is None:
                error = _translate("Upload a valid JPG, PNG, GIF, or WEBP image.")
            else:
                os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
                filename = f"{uuid.uuid4().hex}{extension}"
                image_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                image.save(image_path)
                preview_url = url_for("static", filename=f"uploads/{filename}")
                if disease_model is not None:
                    try:
                        disease_name, confidence, inference_error = _predict_disease(
                            image_path
                        )
                        if inference_error:
                            error = _translate(
                                "The image could not be screened. Please try another clear leaf image."
                            )
                    except (OSError, ValueError) as exc:
                        error = _translate(
                            "The image could not be screened. Please try another clear leaf image."
                        )
                        app.logger.exception("Disease inference failed: %s", exc)

                if disease_name:
                    advisory = get_disease_guidance(disease_name)
                    if advisory is not None:
                        guidance = {
                            section: _translate(message)
                            for section, message in advisory.items()
                        }
                    _record_prediction(
                        "Disease Detection",
                        {"image": filename},
                        f"{disease_name} ({confidence})",
                        image_filename=filename,
                    )

    return render_template(
        "disease.html",
        error=error,
        preview_url=preview_url,
        disease_name=disease_name,
        confidence=confidence,
        guidance=guidance,
        model_missing=disease_model is None,
    )


@app.errorhandler(413)
def request_entity_too_large(_error):
    return render_template(
        "disease.html",
        error=_translate("The image is too large. Choose an image smaller than 5 MB."),
        preview_url="",
        disease_name="",
        confidence="",
        model_missing=disease_model is None,
    ), 413


@app.route("/fertilizer", methods=["GET", "POST"])
def fertilizer_page():
    result = ""
    error = ""
    recommendations = []
    values = {"nitrogen": "", "phosphorus": "", "potassium": ""}
    statuses = {
        "nitrogen": "",
        "phosphorus": "",
        "potassium": "",
    }

    if request.method == "POST":
        _validate_csrf()
        values = {
            nutrient: request.form.get(nutrient, "").strip()
            for nutrient in values
        }
        statuses = {
            nutrient: request.form.get(f"{nutrient}_status", "").strip()
            for nutrient in statuses
        }
        try:
            levels = {nutrient: float(value) for nutrient, value in values.items()}
            if any(
                not math.isfinite(level) or level < 0
                for level in levels.values()
            ):
                raise ValueError
        except ValueError:
            error = _translate(
                "Enter a valid non-negative number for each N, P, and K value."
            )
        if not error and any(status not in {"Low", "Medium", "High"} for status in statuses.values()):
            error = _translate("Choose the Low, Medium, or High rating shown on your Soil Health Card for each nutrient.")
        if not error:
            nutrient_labels = {
                "nitrogen": "Nitrogen (N)",
                "phosphorus": "Phosphorus (P)",
                "potassium": "Potassium (K)",
            }
            recommendations = [
                {
                    "key": nutrient,
                    "nutrient": nutrient_labels[nutrient],
                    "advice": _translate(advice),
                }
                for nutrient, advice in zip(
                    ("nitrogen", "phosphorus", "potassium"),
                    fertilizer_guidance(statuses),
                )
            ]
            result = " ".join(item["advice"] for item in recommendations)
            _record_prediction(
                "Fertilizer Recommendation",
                {"values": levels, "soil_health_card_ratings": statuses},
                result,
            )

    return render_template(
        "fertilizer.html",
        result=result,
        error=error,
        recommendations=recommendations,
        values=values,
        statuses=statuses,
    )


@app.route("/crop-recommendation", methods=["GET", "POST"])
def crop_recommendation_page():
    error = ""
    result = ""
    reasoning = None
    values = {
        "soil_type": "",
        "season": "",
        "temperature": "",
        "rainfall": "",
    }

    if request.method == "POST":
        _validate_csrf()
        values = {
            field: request.form.get(field, "").strip()
            for field in values
        }

        if not values["soil_type"]:
            error = _translate("Select a soil type.")
        elif values["soil_type"] not in SOIL_TYPES:
            error = _translate("Select a valid soil type from the list.")
        elif values["season"] not in SEASONS:
            error = _translate("Select a valid Indian growing season.")
        else:
            numeric_fields = (
                ("temperature", "Temperature", -5, 55),
                ("rainfall", "Rainfall during crop season", 0, 4000),
            )
            conditions = {}
            for field, label, minimum, maximum in numeric_fields:
                value = values[field]
                if not value:
                    error = _translate(f"{label} is required.")
                    break
                try:
                    number = float(value)
                except ValueError:
                    error = _translate(f"{label} must be a valid number.")
                    break
                if not math.isfinite(number):
                    error = _translate(f"{label} must be a finite number.")
                    break
                if not minimum <= number <= maximum:
                    error = _translate(
                        f"{label} must be between {minimum} and {maximum}."
                    )
                    break
                conditions[field] = number

            if not error:
                result, _suitability_score, reasoning = recommend_indian_crop(
                    values["soil_type"],
                    values["season"],
                    conditions["temperature"],
                    conditions["rainfall"],
                )
                _record_prediction(
                    "Crop Recommendation",
                    {
                        "soil_type": values["soil_type"],
                        "season": values["season"],
                        **conditions,
                    },
                    f"Rule-based crop screening: {result}",
                )

    return render_template(
        "crop_recommendation.html",
        error=error,
        result=result,
        reasoning=reasoning,
        values=values,
        soil_types=SOIL_TYPES,
        seasons=SEASONS,
    )


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if not _admin_is_configured():
        return (
            render_template(
                "admin_login.html",
                error="Admin login is unavailable until the server credentials and secret key are configured.",
                csrf_token="",
                configured=False,
            ),
            503,
        )

    error = ""
    csrf_token = _csrf_token()
    if request.method == "POST":
        _validate_csrf()
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        password_matches = False
        if len(username) <= 128 and len(password) <= 1024:
            try:
                password_matches = check_password_hash(
                    app.config["ADMIN_PASSWORD_HASH"], password
                )
            except (TypeError, ValueError):
                app.logger.exception("Admin password hash configuration is invalid")
                return (
                    render_template(
                        "admin_login.html",
                        error="Admin login is misconfigured. Contact the application administrator.",
                        csrf_token="",
                        configured=False,
                    ),
                    503,
                )
        if hmac.compare_digest(username, app.config["ADMIN_USERNAME"]) and password_matches:
            session.clear()
            session["is_admin"] = True
            session["csrf_token"] = secrets.token_urlsafe(32)
            session.permanent = True
            return redirect(url_for("admin_dashboard"))
        error = "Invalid username or password."

    return render_template(
        "admin_login.html",
        error=error,
        csrf_token=csrf_token,
        configured=True,
    )


@app.route("/admin")
@admin_required
def admin_dashboard():
    page = max(request.args.get("page", 1, type=int), 1)
    per_page = 25
    records, total_records = _prediction_history(page, per_page)
    total_pages = max((total_records + per_page - 1) // per_page, 1)
    if page > total_pages:
        return redirect(url_for("admin_dashboard", page=total_pages))

    upload_folder = app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_folder, exist_ok=True)
    images = []
    for filename in sorted(os.listdir(upload_folder)):
        if os.path.splitext(filename)[1].lower() not in {
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".webp",
        }:
            continue
        image_path = _safe_upload_path(filename)
        if os.path.isfile(image_path):
            images.append(
                {
                    "filename": filename,
                    "url": url_for("static", filename=f"uploads/{filename}"),
                }
            )

    with _history_connection() as connection:
        total_users = connection.execute(
            "SELECT COUNT(*) FROM users"
        ).fetchone()[0]
    prediction_statistics = _prediction_statistics()
    return render_template(
        "admin_dashboard.html",
        records=records,
        images=images,
        page=page,
        total_pages=total_pages,
        total_users=total_users,
        prediction_statistics=prediction_statistics,
        total_records=total_records,
        csrf_token=_csrf_token(),
    )


@app.route("/admin/predictions")
@admin_required
def admin_prediction_logs():
    page = max(request.args.get("page", 1, type=int), 1)
    per_page = 25
    records, total_records = _prediction_history(page, per_page)
    total_pages = max((total_records + per_page - 1) // per_page, 1)
    if page > total_pages:
        return redirect(url_for("admin_prediction_logs", page=total_pages))
    return render_template(
        "admin_prediction_logs.html",
        records=records,
        page=page,
        total_pages=total_pages,
        total_records=total_records,
        csrf_token=_csrf_token(),
    )


@app.route("/admin/reports")
@admin_required
def admin_reports():
    page = _requested_history_page()
    per_page = 20
    records, total_records = _prediction_history(page, per_page)
    total_pages = max((total_records + per_page - 1) // per_page, 1)
    if page > total_pages:
        return redirect(url_for("admin_reports", page=total_pages))
    return render_template(
        "reports.html",
        records=records,
        page=page,
        total_pages=total_pages,
        total_records=total_records,
        prediction_statistics=_prediction_statistics(),
    )


@app.route("/admin/system-status")
@admin_required
def admin_system_status():
    return render_template(
        "system_status.html",
        system_health=_system_health(check_api=True),
    )


@app.route("/admin/users")
@admin_required
def admin_user_activity():
    with _history_connection() as connection:
        users = connection.execute(
            """
            SELECT users.id, users.username, users.created_at,
                   COUNT(prediction_history.id) AS activity_count,
                   MAX(prediction_history.created_at) AS last_activity
            FROM users
            LEFT JOIN prediction_history ON prediction_history.user_id = users.id
            GROUP BY users.id
            ORDER BY users.created_at DESC, users.id DESC
            """
        ).fetchall()
    return render_template("admin_users.html", users=users)


@app.route("/admin/logout", methods=["POST"])
@admin_required
def admin_logout():
    _validate_csrf()
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("admin_login"))


@app.route("/admin/records/<int:record_id>/delete", methods=["POST"])
@admin_required
def admin_delete_record(record_id):
    _validate_csrf()
    with _history_connection() as connection:
        record = connection.execute(
            "SELECT image_filename FROM prediction_history WHERE id = ?",
            (record_id,),
        ).fetchone()
        if record is None:
            abort(404)
        filename = record["image_filename"]
        if filename:
            image_path = _safe_upload_path(filename)
            if os.path.isfile(image_path):
                os.remove(image_path)
        connection.execute("DELETE FROM prediction_history WHERE id = ?", (record_id,))
    flash("Prediction record deleted.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/images/<filename>/delete", methods=["POST"])
@admin_required
def admin_delete_image(filename):
    _validate_csrf()
    image_path = _safe_upload_path(filename)
    if os.path.isfile(image_path):
        os.remove(image_path)
    with _history_connection() as connection:
        connection.execute(
            "UPDATE prediction_history SET image_filename = NULL WHERE image_filename = ?",
            (filename,),
        )
    flash("Uploaded image deleted.", "success")
    return redirect(url_for("admin_dashboard"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
