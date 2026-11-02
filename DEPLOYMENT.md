# Deployment

The production web process uses Gunicorn via the root `Procfile`:

```text
web: AGRIVISION_ENV=production gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 4 app:app
```

Install dependencies from `requirements.txt`. Keep the service on Python 3.12
or newer. Set these environment variables in the hosting provider (never commit
production secrets):

| Variable | Required | Value |
| --- | --- | --- |
| `AGRIVISION_ENV` | Yes | `production` |
| `AGRIVISION_SECRET_KEY` | Yes | A unique, persistent random secret; the app refuses to start without it in production. |
| `AGRIVISION_HISTORY_DATABASE` | Yes | Absolute path to the SQLite file on persistent storage. |
| `AGRIVISION_ADMIN_USERNAME` | Optional | Administrator login name. |
| `AGRIVISION_ADMIN_PASSWORD_HASH` | Optional | Werkzeug hash for the administrator password. |
| `AGRIVISION_COOKIE_SECURE` | Optional | Defaults to `1` in production; only set to `0` when HTTPS is not available. |
| `PORT` | Provider-managed | The platform's assigned web port; Gunicorn binds to it. |

Generate a secret and, if enabling admin login, a password hash locally with
the project's Python environment:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
python -c "from getpass import getpass; from werkzeug.security import generate_password_hash; print(generate_password_hash(getpass()))"
```

Configure a persistent disk/volume before setting the SQLite path. SQLite data
on the application's temporary filesystem is lost when the service is
replaced. This app uses one Gunicorn worker to avoid multi-process SQLite write
contention. The optional disease-inference feature additionally requires
TensorFlow and a compatible `models/disease_model.h5`; neither is included in
the core requirements because the model is not part of this deployment.
Files uploaded to `static/uploads` are not durable on an ephemeral service
filesystem; use persistent storage or external object storage if uploaded
images must survive deploys.

## Render.com

1. Create a **Web Service** from the repository and select the directory
   containing `app.py`, `requirements.txt`, and `Procfile` as the root
   directory.
2. Select Python and set the build command to `pip install -r requirements.txt`.
   The Procfile supplies the start command; if entering it manually, use
   `AGRIVISION_ENV=production gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 4 app:app`.
3. Add a persistent disk mounted at `/var/data`.
4. Add the required variables above, setting
   `AGRIVISION_HISTORY_DATABASE=/var/data/prediction_history.sqlite3`.
   Generate `AGRIVISION_SECRET_KEY` locally and add it as a secret environment
   variable. Set `AGRIVISION_ENV=production`.
5. Optionally add the admin username and password hash, then deploy. Confirm
   the service health by opening its Render URL and registering/signing in.

## Railway.app

1. Create a Railway project from the repository and deploy the service from
   the directory containing `app.py`, `requirements.txt`, and `Procfile`.
2. Railway installs `requirements.txt`; use the Procfile start command or set
   the service's start command to
   `AGRIVISION_ENV=production gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 4 app:app`.
3. Add a Railway Volume mounted at `/data`.
4. Add the required variables in the service's Variables panel, setting
   `AGRIVISION_HISTORY_DATABASE=/data/prediction_history.sqlite3`,
   `AGRIVISION_ENV=production`, and a generated persistent
   `AGRIVISION_SECRET_KEY`. Add the optional admin variables if needed.
5. Deploy, generate a public domain, and verify the site and account flows.

Keep the volume mount path and SQLite environment variable unchanged across
deployments. Back up the SQLite file regularly; a persistent volume is not a
backup.
