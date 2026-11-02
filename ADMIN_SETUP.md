# Admin Panel Setup

## Local development

From PowerShell in the project directory, start the app with:

```powershell
.\run_local.ps1
```

On first run, the script creates a local administrator with username `admin`
and prints a randomly generated password once. Save that password securely.
The password is stored only as a Werkzeug hash. The persistent Flask session
secret and admin hash are kept in `instance/local_admin.json`, which is ignored
by Git. Local settings load by default for local runs; set
`AGRIVISION_ENV=production` in hosted deployments to prevent loading this
development account. Explicit `AGRIVISION_SECRET_KEY` and admin environment
variables take precedence.
If the password is lost, remove that file and start the script again to create
a new local account; existing database accounts and prediction records are not
affected.

## Production or hosted deployments

The admin account is configured through server-side environment variables. Do
not commit passwords, password hashes, or the Flask session secret to source
control.

Required variables:

- `AGRIVISION_SECRET_KEY`: a long, random value used to sign Flask sessions.
- `AGRIVISION_ENV=production`: disables loading local development credentials.
- `AGRIVISION_HISTORY_DATABASE`: optional absolute path to the SQLite database;
  defaults to `instance/prediction_history.sqlite3`.
- `AGRIVISION_ADMIN_USERNAME`: the administrator username.
- `AGRIVISION_ADMIN_PASSWORD_HASH`: a Werkzeug password hash, not the plaintext password.

Generate values in PowerShell from the project directory (with its Python
environment active):

```powershell
$env:AGRIVISION_SECRET_KEY = python -c "import secrets; print(secrets.token_hex(32))"
$env:AGRIVISION_ADMIN_USERNAME = "admin"
$env:AGRIVISION_ADMIN_PASSWORD_HASH = python -c "from getpass import getpass; from werkzeug.security import generate_password_hash; print(generate_password_hash(getpass()))"
```

The password prompt is not echoed. Start the Flask application in the same
PowerShell session so it inherits these variables. Visit `/admin/login` to
sign in. The admin session expires after 30 minutes. The admin dashboard
provides user and feature totals; administrators can review `/admin/predictions`,
manage accounts at `/admin/users`, view reports at `/admin/reports`, and inspect
technical model/database status at `/admin/system-status`.

Users can create accounts at `/register`, sign in at `/login`, and sign out
with the navigation's CSRF-protected Log out button. Passwords are stored as
Werkzeug hashes in the SQLite `users` table. History and reports require a
user session and show only records associated with that account. The
`/system-status` route is restricted to administrators.

In production, secure cookies default to enabled. Use HTTPS and do not disable
`AGRIVISION_COOKIE_SECURE`. User accounts and prediction history are stored at
`AGRIVISION_HISTORY_DATABASE`; configure it to point to a persistent volume and
back up that file with the application data.
