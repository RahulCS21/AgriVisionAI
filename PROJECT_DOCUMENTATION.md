# AgriVision AI — Project Documentation

## Project Overview

AgriVision AI is a Flask web application for agriculture-related information
and decision support. It provides crop suitability screening, Soil Health
Card-based fertilizer guidance, weather lookup for Indian locations, and
educational plant-disease guidance. Users can register and sign in to access
their own prediction history and reports; administrators have separate access
to reports, system status, and user activity.

The installed crop-yield model is a demonstration model trained on a small
recovered dataset with undocumented provenance and yield units. It is not
validated for production agricultural decisions. Technical model limitations
are shown in the administrator system-status area, not in public prediction
results. Disease image classification remains unavailable unless a compatible
trained model and TensorFlow are installed. Crop suitability uses broad,
manually maintained rules, and fertilizer advice is qualitative.

## Features

- **Home and dashboard:** Overview pages linking to the application modules.
- **Crop suitability screening:** Ranks broad crop profiles using soil type,
  Indian growing season, temperature, and seasonal rainfall, and shows
  factor-level reasoning.
- **Fertilizer guidance:** Accepts lab values and Low/Medium/High Soil Health
  Card ratings for nitrogen, phosphorus, and potassium. Advice is based on
  selected ratings; numeric values are recorded but do not determine fertilizer
  dosage.
- **Weather dashboard:** Searches for an Indian city or district using
  Open-Meteo and displays current temperature, relative humidity, precipitation
  probability, wind speed, and provider observation time when the lookup
  succeeds.
- **Disease image page:** Accepts JPG, PNG, GIF, or WEBP uploads, limited to
  5 MB per request. A diagnosis is generated only when a compatible model is
  installed and loaded. The guidance catalogue is educational, not a confirmed
  diagnosis or verified local treatment database.
- **Yield page:** Uses temperature, rainfall, and humidity to produce a
  user-friendly estimate only when the installed model is available. Successful
  outputs are saved to SQLite; unavailable models produce a clear status
  message and no prediction record.
- **Accounts and sessions:** Registration, login, and CSRF-protected logout;
  passwords are stored as Werkzeug hashes in SQLite. Sessions expire after
  30 minutes.
- **Prediction history and reports:** Login-protected, per-account views of
  paginated SQLite records and summary counts. Older unassigned records remain
  available for administrator review and are not exposed to user accounts.
- **System status:** The admin-only `/admin/system-status` page shows model,
  database, and weather-provider details. The Open-Meteo API check performs a
  live Bengaluru lookup; missing models do not produce placeholder results.
- **Administrator interface:** Configured administrators can review all
  records, reports, system status, registered-user activity, and uploaded images.
- **Multilingual interface:** Supports English, Hindi, Kannada, Tamil, and
  Telugu, with language selection saved in a browser cookie.
- **Informational pages:** About and contact pages.

## Technologies Used

| Technology | Use |
|---|---|
| Python | Application language and decision-support modules |
| Flask | Web framework, routes, sessions, templates, and static assets |
| Jinja | Server-rendered HTML templates |
| SQLite | Local user accounts and prediction-history storage |
| NumPy | Numeric validation and image score handling |
| pandas, scikit-learn, joblib | Recovered dataset processing, demonstration yield model training, and model loading |
| TensorFlow / Keras (optional) | Disease image inference when installed with a compatible model |
| Werkzeug | Password hash verification and secure filename handling |
| Open-Meteo APIs | Indian location geocoding and weather forecast data |
| Bootstrap 5 and Bootstrap Icons | Front-end layout and icons, loaded from a CDN |
| HTML and CSS | Page templates and application styling |

`requirements.txt` pins the application libraries and constrains Gunicorn to
major version 23. TensorFlow is optional for the app to start, but required for
disease inference. See `DEPLOYMENT.md` for Render.com and Railway.app setup,
environment variables, and persistent SQLite storage requirements.

## Folder Structure

```text
AgriVionAI/
├── app.py                       # Flask app, routes, persistence, weather, inference
├── agriculture.py               # Crop suitability profiles and fertilizer guidance
├── disease_guidance.py          # Educational disease guidance mapped to model labels
├── translations.py              # Supported languages and translation catalog
├── Procfile                     # Gunicorn production web command
├── requirements.txt             # Python runtime dependencies
├── DEPLOYMENT.md                # Render and Railway setup
├── ADMIN_SETUP.md               # Admin configuration and account/access setup
├── REALISM_AUDIT.md             # Data/model limitations and realism notes
├── CLEANUP_REPORT.md            # Prior file cleanup assessment
├── PRODUCTION_READINESS_REPORT.md # Production readiness audit
├── PROJECT_DOCUMENTATION.md     # This documentation
├── dataset/                     # Reserved dataset location
├── instance/
│   └── prediction_history.sqlite3 # Runtime SQLite database, when initialized
├── models/
│   └── yield_model.pkl          # Existing demonstration estimator
├── recovery/                    # Historical recovery material; not loaded at runtime
├── static/
│   ├── css/
│   │   └── style.css            # Application styles
│   └── uploads/                 # Runtime image uploads
├── templates/                   # Flask/Jinja page templates
└── tests/                       # unittest test suite
```

The `instance/` database and `static/uploads/` content are runtime data, not
application source. SQLite includes a `users` table and associates new
prediction records with the signed-in user. Existing records without an owner
remain unassigned. Back up and manage runtime data according to deployment
retention and privacy requirements.

## How to Run the Project

### Requirements

- Python with Flask, NumPy, pandas, scikit-learn, joblib, and the application's
  other imports installed.
- A compatible TensorFlow installation and model only if disease inference is
  required.
- Internet access for live weather lookups.

Install the project's dependencies with `pip install -r requirements.txt`.

### Local development on Windows

From PowerShell:

```powershell
Set-Location C:\Intership\AgriVionAI
& C:\Intership\.venv\Scripts\Activate.ps1
python app.py
```

Alternatively, run the interpreter directly:

```powershell
Set-Location C:\Intership\AgriVionAI
& C:\Intership\.venv\Scripts\python.exe app.py
```

Open the local address printed by Flask in the terminal. The direct
`app.run()` startup is for local development; deploy behind a production WSGI
server and HTTPS for production.

### Optional administrator configuration

Admin login is disabled until the server has a persistent Flask secret,
username, and Werkzeug password hash. See [ADMIN_SETUP.md](./ADMIN_SETUP.md)
for PowerShell commands and detailed setup. The relevant variables are:

- `AGRIVISION_SECRET_KEY`
- `AGRIVISION_ADMIN_USERNAME`
- `AGRIVISION_ADMIN_PASSWORD_HASH`
- `AGRIVISION_COOKIE_SECURE=1` when serving over HTTPS

Do not commit secret keys, credentials, or password hashes to source control.

### Disease model configuration

The application checks for a Keras model at
`models/disease_model.h5`. The expected output has one score for each of the
38 PlantVillage classes defined by the application. Installing a model without
verifying its class ordering, preprocessing, calibration, and suitability is
not sufficient for safe production use.

## Modules Description

### `app.py`

The sole Flask startup module. It defines the Flask application and route
handlers, session and CSRF helpers, upload checks, SQLite history operations,
Open-Meteo requests, and optional Keras disease inference. Running this file
directly starts the development server.

### `agriculture.py`

Contains broad crop profile data, soil and season choices, crop suitability
ranking, and qualitative nutrient guidance. Crop recommendations are
transparent rule-based screening, not an AI model or district-specific plan.

### `disease_guidance.py`

Maps supported PlantVillage class labels to educational information about
possible causes, symptoms, prevention, practices, and cautious treatment
language. The text does not confirm that a disease is present.

### `translations.py`

Defines the supported language names and translation lookup used by page
templates and selected validation/guidance messages. Untranslated text falls
back to the original message.

### Templates

Templates under `templates/` render the public pages, feature forms, admin
screens, and shared layout. `base.html` supplies the main navigation, language
selector, footer, and shared assets. `_prediction_records.html` is a reusable
history table included by history and reports pages.

### Tests

The `tests/` directory contains Python `unittest` cases for admin behavior,
translations, UI and feature forms, history, weather-provider responses, and
yield-input validation. Weather tests mock provider responses and therefore
do not establish live API availability.

## Screenshots Placeholders

Replace the placeholders below with current screenshots. Avoid including
personal data, credentials, private records, or identifiable user-uploaded
images.

### Home page

![Placeholder: AgriVision AI home page](docs/screenshots/home-page.png)

### Dashboard

![Placeholder: AgriVision AI dashboard](docs/screenshots/dashboard.png)

### Crop recommendation

![Placeholder: Crop suitability screening result](docs/screenshots/crop-recommendation.png)

### Fertilizer guidance

![Placeholder: Soil Health Card fertilizer guidance](docs/screenshots/fertilizer-guidance.png)

### Weather dashboard

![Placeholder: Live weather dashboard](docs/screenshots/weather-dashboard.png)

### Disease page

![Placeholder: Disease image screening and model availability status](docs/screenshots/disease-page.png)

### History and reports

![Placeholder: Prediction history and reports](docs/screenshots/history-reports.png)

These are documentation placeholders only; screenshot files were not created.

## Future Scope

- Add a traceable, licensed India-specific yield dataset and validated model,
  with geographic and time-aware evaluation and clearly published limitations.
- Integrate a suitable plant-disease model with verified preprocessing,
  class mapping, calibration, out-of-distribution handling, and expert review.
- Replace broad crop screening bands with reviewed state/district crop
  calendars and locally relevant soil, irrigation, rainfall, and variety data.
- Validate fertilizer guidance against official crop- and district-specific
  recommendations; document rating definitions, units, and source references.
- Add authentication rate limiting and account recovery.
- Add upload authorization, quotas, throttling, retention, and cleanup; current
  uploaded image files are served from the static asset directory.
- Limit decoded image dimensions when inference is enabled.
- Add weather caching, request throttling, service monitoring, and explicit
  provider attribution appropriate to deployment.
- Establish reproducible dependency management, migrations, backups, and a
  production WSGI deployment configuration.
- Expand translations to cover admin pages and all user-facing dynamic text.
- Add accessibility, browser compatibility, and production load testing.

## Troubleshooting Guide

| Symptom | Likely cause | What to check |
|---|---|---|
| `ModuleNotFoundError` while starting | The selected Python environment is missing a dependency or is not the intended environment. | Activate the project environment and install the project's pinned dependencies once a dependency manifest is provided. |
| Startup warning says the secret key is unset | `AGRIVISION_SECRET_KEY` is not configured. | Set a persistent, randomly generated secret in the server environment. A process-local fallback is not appropriate for production sessions. |
| `/admin/login` returns 503 | Required admin environment variables are missing or invalid. | Configure the secret, username, and Werkzeug password hash as described in `ADMIN_SETUP.md`; restart the application afterward. |
| Disease page says inference is unavailable | TensorFlow, the model file, or both are unavailable; the model may also fail to load. | Check the TensorFlow installation and `models/disease_model.h5`. Confirm the model is compatible and returns 38 class scores in the expected order. |
| Uploaded image is rejected | Unsupported extension/signature, missing file, or request exceeds the 5 MB limit. | Use a valid JPG, PNG, GIF, or WEBP image under the configured upload limit. |
| Weather lookup says unavailable | No network connection, provider timeout, malformed provider response, or no matching Indian location. | Check outbound HTTPS access to Open-Meteo and retry with a city or district name. The app intentionally does not display fabricated fallback values. |
| Weather values take a long time to appear | Geocoding and forecast calls are sequential and each may wait up to the configured timeout. | Check provider/network latency; production deployments should consider caching and monitoring. |
| Form submission returns HTTP 400 saying the form expired | The CSRF token is missing or stale, or the form was open across a session change. | Reload the page and submit the refreshed form. |
| Prediction history is empty | No successful result is associated with the signed-in account, or a different SQLite file is in use. | Sign in with the account that created the prediction. Older unassigned records are visible only to administrators. |
| Sessions do not survive restart or differ between workers | A process-local secret is in use or different workers have different keys. | Configure the same persistent `AGRIVISION_SECRET_KEY` for every production worker. |

For production incidents, review application logs and deployment health
checks. Do not expose secrets, uploaded private images, or personal history
records in support logs.
