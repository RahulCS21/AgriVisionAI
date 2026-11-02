# AgriVision AI — Final Quality Audit / Bug Report

**Audit date:** 2026-10-31  
**Scope:** Read-only quality audit. No application code or existing data was
modified. This report is the only file created for the audit.

## Executive Summary

- **Automated tests:** 58 passed; 0 failed.
- **Routes:** 27 Flask endpoints registered. Public and protected route smoke
  checks returned expected responses; protected pages redirected as expected.
- **Templates/navigation:** 22 HTML templates compiled. No missing template,
  literal `url_for` endpoint, or literal internal link/form-action reference
  was found.
- **Browser sample:** No console errors or failed network requests on sampled
  pages. Mobile dashboard overflows horizontally at a narrow viewport.
- **Database:** SQLite opened successfully and contains user, prediction, and
  weather-request tables. Reports are derived from prediction history rather
  than stored in a separate reports table.
- **Main concerns:** Development admin configuration loads by default unless
  production mode is explicitly selected; production cookies are not Secure by
  default; uploaded images are served from public static storage; no dependency
  manifest is present; and a prior production audit document is stale.

## Findings

| # | Issue Name | File Name | Severity | Exact Fix Recommendation |
|---|------------|-----------|----------|--------------------------|
| 1 | Local admin credentials load when environment mode is unset | `app.py:50-53, 71-85` | High | Fail closed outside explicit local development: load `instance/local_admin.json` only when `AGRIVISION_ENV=development` is explicitly set. Require production mode and configured production secret/admin credentials at startup; do not make development the implicit default for hosted deployments. |
| 2 | Production session cookies may be sent over HTTP | `app.py:92-95` | High | Require `AGRIVISION_COOKIE_SECURE=1` for production/HTTPS deployments and fail startup or emit a deployment-blocking error when production mode has secure cookies disabled. |
| 3 | Uploaded disease images are public and accumulate without database references | `app.py:98, 1188-1191`; `static/uploads/` | Medium | Store uploads outside Flask's public static directory and serve them through an authorization-checked route. Associate each saved image with its owner/record, delete temporary images when inference is unavailable or fails, and define an upload retention/quota policy. During this audit, three PNG files in the upload folder had no matching `prediction_history.image_filename` reference. |
| 4 | Admin login has no attempt throttling | `app.py:1394-1434` | Medium | Add per-account and per-source rate limiting or progressive delays, with security logging and a documented recovery/unlock policy. |
| 5 | Dependency installation is not reproducible from the project root | `requirements.txt` (missing); project root | Medium | Add a maintained dependency manifest with supported Python version and pinned/runtime-bounded direct dependencies. Document TensorFlow/model dependencies separately as optional and validated. |
| 6 | Existing production-readiness report contradicts current code | `PRODUCTION_READINESS_REPORT.md:25-52, 104-109` | Medium | Refresh or mark the report superseded. It describes 17 routes, disabled admin login, public/global history, no user ownership, and an empty model directory; current code has 27 endpoints, user/admin auth, owner-scoped records, and `models/yield_model.pkl`. |
| 7 | Dashboard cards cause horizontal scrolling on narrow mobile screens | `templates/dashboard.html:31-55`; `static/css/style.css:682-724` | Low | Allow the flex content inside `.dashboard-stat` to shrink and wrap long labels (especially “Fertilizer Recommendations”), or change the narrow-screen stats layout to a single column. At a 345px browser content width, the document measured 362px wide (17px overflow). |
| 8 | Unknown routes use an unbranded default 404 response | `app.py` (no 404 handler); `templates/404.html` (missing) | Low | Add a branded 404 template and Flask 404 handler with links back to Home and Dashboard; preserve the 404 status code. The current unknown-route response is HTTP 404 but contains no AgriVision branding. |
| 9 | Successful login has no explicit success feedback | `app.py:842-847, 1425-1433`; `templates/login.html`; `templates/admin_login.html` | Low | Flash a concise successful sign-in message before redirecting, or provide an equivalent dashboard status banner. Registration and logout already show success feedback. |
| 10 | Duplicate and unreferenced uploaded images remain in static storage | `static/uploads/1470b972fefb424a832fc49c6fcf3d17.png`; `static/uploads/8d706216b48f4170a4bb405b96c32236.png`; `instance/prediction_history.sqlite3` | Low | Confirm retention/ownership before cleanup, then remove duplicate orphan files through a controlled maintenance task. Add an orphan-file cleanup procedure. The two listed PNG files have identical content; none of the three PNG files currently has a history reference. |
| 11 | Schema setup runs on each database connection | `app.py:175-230`; `app.py:324-379` | Low | Move table creation and schema inspection into an explicit, versioned migration/initialization step. Add appropriate indexes (at minimum prediction ownership and weather-request ownership) if production data volume warrants them. The current local smoke timings were fast; this is a scale/per-request overhead risk, not an observed slow-page failure. |
| 12 | Weather requests can block on two sequential external calls | `app.py:105, 639-643` and `_get_live_weather` | Medium | Cache geocoding/forecast results for a short documented interval, and consider a total request deadline/retry policy. Each provider call can take up to 8 seconds; a two-call lookup can therefore approach 16 seconds under provider/network timeout conditions. Live external-provider latency was not load-tested in this audit. |

## Area-by-Area Audit

### 1. Flask Routes, 404s, and Navigation

- **Pass:** 27 Flask endpoints registered, including authentication, public
  modules, admin reports/users/system status, prediction logs, and delete
  actions.
- **Pass:** Public GET routes rendered. Profile/history/reports redirected
  anonymous users to login; system status and admin routes redirected
  non-admin users to admin login.
- **Pass:** No missing templates and no broken literal route or static-file
  references were found in templates. Form actions and navigation use valid
  Flask endpoints.
- **Finding:** Unknown paths return an unbranded default 404 page (Issue 8).

### 2. Authentication

- Registration, login, logout, profile, admin login, and admin dashboard flows
  are covered by automated tests.
- Password hashes use Werkzeug; successful authentication clears prior session
  state, rotates the CSRF token, and marks the session permanent.
- Logout uses POST and CSRF validation. Configured session lifetime is
  30 minutes; cookies are HTTP-only and SameSite=Lax.
- **Findings:** Local admin configuration is enabled by default when the
  environment selector is unset (Issue 1); Secure cookies default off
  (Issue 2); no login throttling (Issue 4); no explicit login-success message
  (Issue 9).

### 3. Database

- SQLite connection and schema were readable during the audit.
- Tables present: `users`, `prediction_history`, and `weather_requests`.
- The audited database contained 1 user, 15 prediction-history records, and 2
  weather-request records.
- `users.username` has a case-insensitive unique constraint; stored passwords
  are hashes. Prediction records include a nullable `user_id` for preserved
  legacy records.
- Reports are computed from prediction history; there is no separate report
  storage table. This is consistent with the current implementation.
- **Findings:** Runtime schema setup occurs on database connections (Issue 11).
  No backup/restore procedure was verified.

### 4. Feature Testing

- Crop yield, disease upload, weather page, fertilizer, crop recommendation,
  history, and reports are covered by the passing regression suite.
- Crop recommendations are rule-based suitability screening, not an AI
  prediction. Fertilizer advice is qualitative and does not calculate
  application rates.
- The disease model is not installed/available in this environment; the UI
  reports screening as unavailable rather than fabricating a diagnosis.
- A yield estimator file is present, but its agricultural validity/provenance
  is not established by this audit. It should not be treated as production
  validated.
- Weather tests use mocked provider data; this audit did not establish current
  Open-Meteo uptime or real-world latency (Issue 12).

### 5. UI/UX

- **Pass:** All 22 HTML templates compiled; no missing template references.
- **Pass:** No JavaScript console errors or failed network requests were
  observed while visiting the sampled landing, dashboard, weather, yield,
  disease, fertilizer, crop recommendation, login, and registration pages.
- **Pass with issue:** The mobile navigation toggle appeared at the sampled
  narrow viewport. The dashboard stats overflow the viewport at a narrow
  width (Issue 7).
- **Finding:** The 404 response is not branded (Issue 8).
- Login success currently redirects without an explicit confirmation; other
  result cards and registration/logout success feedback are present (Issue 9).

### 6. Security

- Password hashing, CSRF checks, user/admin route guards, and safe local
  redirects are present and covered by tests.
- The configured local secret is persistent and was not printed or included in
  this report.
- **Findings:** Production should explicitly opt out of local-development
  configuration (Issue 1) and enable Secure cookies (Issue 2). Uploaded images
  are served under the public static directory (Issue 3). Login attempts are
  not rate-limited (Issue 4).
- This was a source/configuration and test audit, not an external penetration
  test.

### 7. Files

- Required application modules, templates, tests, local startup script, and
  yield model file are present.
- No dependency manifest (`requirements.txt`, `pyproject.toml`, or equivalent)
  is present (Issue 5).
- `recovery/train_model.py` and its recovered CSV are not referenced by the
  active app; the recovery documentation describes them as historical
  artifacts. Do not run this script as part of application startup.
- The project contains several overlapping audit/readiness documents; at
  least one has stale statements (Issue 6).
- Two uploaded PNG files are byte-identical; three PNGs lack database record
  references (Issue 10).
- No other exact duplicate files were found in the project-scope file scan,
  excluding `.venv`, bytecode caches, and the ignored `instance` directory.

### 8. Performance

- Local Flask test-client medians for sampled page GETs were below 3 ms after
  warm-up; observed maxima were below 31 ms in this small local sample. These
  are not production/load-test results.
- No slow local-rendering page was identified in the sample.
- **Risks:** Sequential external weather calls can approach a 16-second
  timeout (Issue 12); repeated schema setup and unindexed owner filters may
  add overhead as data grows (Issue 11); admin upload enumeration grows with
  files retained in the static folder (Issue 3).

### 9. Testing

- Command: `.venv\Scripts\python.exe -m unittest discover -s tests -v`
- Result: **58 tests passed; 0 failed.**
- Failed tests: **None.**
- Additional checks: route-map inventory, template compilation, link/action
  scan, protected-route smoke tests, SQLite schema/count inspection, browser
  console/network sampling, and narrow-screen layout measurement.

## Recommended Priority

1. **Before production:** address Issues 1–4 (environment isolation, Secure
   cookies, private upload storage/retention, and authentication throttling).
2. Add dependency/deployment reproducibility and update stale documentation
   (Issues 5–6).
3. Correct narrow-screen dashboard overflow and add branded 404/login feedback
   (Issues 7–9).
4. Establish orphan-file cleanup, migrations/indexes, and weather caching
   (Issues 10–12).

## Files Reviewed

Application source, all templates, CSS, tests, project documentation and audit
reports, recovery scripts/data, model directory, upload directory, and the
active SQLite schema were reviewed. No application code was changed.
