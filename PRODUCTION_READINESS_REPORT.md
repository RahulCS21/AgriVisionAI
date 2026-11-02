# AgriVision AI Production Readiness Audit

**Audit date:** 2026-10-30  
**Scope:** Routes, navigation, forms, templates, imports, SQLite usage,
translations, weather, prediction features, unused/dead code, security, and
performance.  
**Changes made:** This report only. No application code was modified and no
files were deleted.

## Executive summary

**Verdict: Not ready for production deployment.** The app's public pages and
the current test suite are healthy, but production operation requires
deployment configuration and decisions about the exposure and retention of
prediction history and uploaded images. The two features advertised as
predictions are currently unavailable: there is no yield estimator, and there
is no installed TensorFlow runtime or disease model. Crop recommendations and
fertilizer guidance are rule-based/qualitative and are appropriately described
as decision support rather than validated AI predictions.

## Audit results

| Area | Status | Findings |
|---|---|---|
| Routes | **Pass with deployment caveats** | The 17 Flask routes cover the public pages, feature submissions, language selection, and admin operations. Public pages render in the test suite. Admin login is deliberately unavailable (503) until the required environment variables are set. |
| Navigation | **Pass** | Template navigation and dashboard feature links use Flask endpoint URL generation. The route and UI tests confirm the principal public navigation targets render. No broken endpoint references were found in the templates reviewed. |
| Forms | **Pass with notes** | POST forms include CSRF tokens; server-side validation is present for crop, fertilizer, yield, and upload inputs. Weather uses GET appropriately. The contact page is an email link, not an in-app submission form. Yield inputs are validated but cannot produce a prediction. |
| Templates | **Pass with localization gap** | All 15 templates were reviewed. Jinja autoescaping is used for displayed form/history values. Admin login and admin dashboard copy is largely hard-coded English, so those pages do not fully follow the selected language. |
| Imports/dependencies | **Caution** | Core imports work in the tested Python 3.12 environment. TensorFlow is optional and its absence disables disease inference. No dependency manifest or lock file was present at the project root, making environment reproduction and deployment less reliable. |
| Database | **Caution** | SQLite uses parameterized SQL, transaction rollback, and per-operation connections. The database is initialized at runtime and history is paginated. There is no per-user ownership, retention/cleanup policy, schema migration mechanism, or demonstrated multi-instance database strategy. |
| Multilingual support | **Partial** | English, Hindi, Kannada, Tamil, and Telugu are available. Tests cover translated navigation, feature titles, selected form text, validation, and guidance. Admin-page copy remains mostly English, and translation coverage is not comprehensive for every dynamic or historical value. |
| Weather | **Pass with operational limits** | Open-Meteo geocoding is constrained to India; provider values are validated and errors do not become fabricated readings. Timeout and malformed-response tests pass. Each lookup makes two serial external calls, each with an 8-second timeout; tests mock the provider, so live availability was not verified. |
| Prediction modules | **Not production-functional** | Yield estimates are intentionally disabled pending a validated India-specific model. Disease inference is disabled because no model is installed and TensorFlow is unavailable in the audited environment. Crop screening is a fixed broad rule set; fertilizer guidance is based on user-selected Soil Health Card ratings, not a calculated dose. |
| Dead/unused code | **Minor cleanup candidates** | `history_result` is assigned but never used in `app.py`. `app1.py` is absent from the current project tree, although `CLEANUP_REPORT.md` still discusses it as an existing deletion candidate. `dataset/` and `models/` are empty in the inspected tree; they may be intended future locations, not confirmed safe-to-delete. |
| Security | **Action required** | Public history and report pages display all saved entries without user scoping. Uploaded images are stored under the public static directory and can be retrieved by URL. Production secrets and HTTPS cookie security require explicit configuration. Upload request size is capped, but there is no upload rate or storage quota. |
| Performance | **Caution** | Live weather is uncached and can block requests for up to about 16 seconds across its two serial requests. History counts and admin upload enumeration grow with stored data. Disease model loading at import increases worker startup cost when a model is eventually installed. |

## Route, link, and form coverage

The application defines routes for `/`, `/set-language`, `/dashboard`,
`/history`, `/reports`, `/about`, `/contact`, `/weather`, `/yield`, `/disease`,
`/fertilizer`, `/crop-recommendation`, `/admin/login`, `/admin`,
`/admin/logout`, `/admin/records/<record_id>/delete`, and
`/admin/images/<filename>/delete`. It also defines a 413 upload-size handler.

The admin dashboard and its deletion actions are protected by the admin
session. Deletion and other POST forms use CSRF validation. Admin login depends
on `AGRIVISION_SECRET_KEY`, `AGRIVISION_ADMIN_USERNAME`, and
`AGRIVISION_ADMIN_PASSWORD_HASH`; HTTPS deployments should also set
`AGRIVISION_COOKIE_SECURE=1`.

The public history and reports screens are not restricted to an individual
user. Treat their records as globally visible until an ownership/access model
is deliberately provided.

## Security and privacy findings

1. **High — Public access to saved history and image URLs.** `/history` and
   `/reports` render stored records without authentication or user scoping.
   The shared records include submitted inputs and results. Uploaded images
   are served from `static/uploads`, so a referenced image URL is public too.
   This is a privacy risk if submissions or photos are not intended for public
   viewing.
2. **Medium — Uploaded files have no aggregate quota, throttling, or retention
   policy.** Individual requests are limited to 5 MB and filenames/signatures
   are checked, but repeated valid uploads can accumulate indefinitely.
   Uploads are retained even when no disease model is available and no
   diagnosis/history entry is created. The upload directory currently contains
   three PNG files.
3. **High deployment concern — Secret and cookie settings are opt-in.** When
   `AGRIVISION_SECRET_KEY` is absent, each process creates a temporary secret;
   this breaks session continuity across restarts and can differ between
   workers. Admin access is disabled without the configured secret and
   credentials. `SESSION_COOKIE_SECURE` defaults off unless
   `AGRIVISION_COOKIE_SECURE` is enabled. These settings must be made explicit
   before an HTTPS production deployment.
4. **Medium — Upload decoding has no explicit image-dimension/pixel limit.**
   A compressed image within the request cap can still require substantial
   memory when decoded for model inference. This matters if disease inference
   is enabled and the upload endpoint is exposed to untrusted clients.
5. **Medium — No login throttling was found.** Admin password verification is
   performed for each attempt, with no visible rate limit or lockout policy.
6. **Deployment concern — The direct-run path calls Flask's built-in
   `app.run()`.** It is suitable for local development, not as the production
   WSGI serving strategy. No production server/deployment configuration was
   present in the inspected project files.

## Performance and reliability findings

- Weather lookups make sequential geocoding and forecast calls. With the
  configured 8-second timeout on each request, a slow provider can hold a
  request for roughly 16 seconds. There is no cache or application-level
  request throttling.
- Prediction history is unbounded. Counts and grouped statistics scan the
  table, and the admin view sorts every filename in the upload directory.
  These operations can become expensive as data accumulates.
- If a disease model is later installed, it is loaded while importing
  `app.py`; each worker may incur model load time and its own memory footprint.
- A persistent storage, backup, restore, and concurrent-worker strategy for
  SQLite should be defined before deployment.

## File and dead-code observations

- `history_result` in `app.py` is assigned but not read.
- `app1.py` was not present during this audit. The existing
  `CLEANUP_REPORT.md` should not be treated as proof that the file is still
  present.
- `dataset/` and `models/` contained no files at audit time. The app expects a
  disease model at `models/disease_model.h5`, so the empty model directory is
  an expected deployment location rather than evidence of a redundant file.
- `static/uploads/` contains three image files. They are runtime user-upload
  artifacts, not safe-to-delete source files; no files were removed.
- The project `.gitignore` only lists `instance/`. Python cache files and
  runtime uploads are not excluded by the current ignore file. Confirm whether
  such artifacts should be excluded from source-control packaging.
- No dependency or production deployment manifest was found in the project
  root. The current directory is not a Git repository, so tracked/untracked
  status could not be verified.

## Verification performed

- Ran the complete test suite using the installed Python 3.12 interpreter:
  **41 tests passed**.
- Tests cover public page rendering, core form validation/submission, admin
  authentication and CSRF, history behavior, translation cases, and mocked
  weather responses.
- Test logs reported that `AGRIVISION_SECRET_KEY` was unset and TensorFlow was
  unavailable. These conditions match the current runtime configuration; they
  are not test failures.
- Weather tests use mocked provider data. No live Open-Meteo call, production
  load test, deployment test, image resource-exhaustion test, or user-isolation
  test was performed.

## Recommended release gates

1. Decide whether prediction history and image uploads are public or private;
   if private, enforce access/ownership consistently and address already
   stored data.
2. Set and validate a persistent secret, admin credentials, HTTPS cookie
   policy, and a production WSGI server before launch.
3. Establish upload throttling, storage limits, retention/deletion, and image
   pixel/resource limits.
4. Add reproducible dependency and deployment configuration, then verify it
   in the target hosting environment.
5. Clearly scope the product as decision support until validated yield and
   disease models are installed and independently evaluated.
6. Decide how admin pages and all dynamic interface content should behave
   under each supported language.
