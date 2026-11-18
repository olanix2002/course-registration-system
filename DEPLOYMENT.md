# Deployment guide

This walks through deploying the project to Render with a Neon PostgreSQL
database. Follow the steps in order. Nothing here has been run against a live
Render or Neon account, so treat the first deploy as something to watch.

## What is already in the repository

| File | Purpose |
| --- | --- |
| `build.sh` | Installs packages, collects static files, migrates, creates the staff account, seeds sample data |
| `render.yaml` | Optional Blueprint that sets the build and start commands |
| `.python-version` | Pins Python 3.12 |
| `requirements.txt` | Pinned packages, including gunicorn, WhiteNoise and psycopg2 |
| `deploy_check.py` | Runs `check --deploy` with fake values, for local use only |

## Step 1: Create the Neon database

1. Sign in at https://console.neon.tech and create a project. Pick the region
   closest to your Render region, for example Frankfurt if Render runs in
   Frankfurt.
2. In the project dashboard, open **Connection string** and switch it to
   **direct** rather than pooled. Copy the direct string, the one whose host
   does not contain `-pooler`. It looks like:

   ```
   postgresql://USER:PASSWORD@ep-something.REGION.aws.neon.tech/DBNAME?sslmode=require
   ```

   Keep `?sslmode=require` on the end. The project adds `sslmode=require`
   itself when the string has no `sslmode`, but keeping it explicit is clearer.
3. That direct string is the value you paste into Render as `DATABASE_URL` in
   step 4.

### Use the direct connection string, not the pooled one

Neon offers two connection strings, and this project uses the **direct** one
for `DATABASE_URL` everywhere: the Render environment variable, the migration
step in `build.sh`, and any local command you run against the live database.

The direct string keeps every session on its own connection, so Django's
migration runner behaves exactly as it does locally and session level features
such as prepared statements work without restriction. The pooled string routes
through Neon's pooler in transaction mode, which does not support the full set
of session level features, and it is the usual cause of `migrate` failing
during a build with an error about prepared statements or an unsupported
command.

Because the build and the running app both use the direct string, there is no
separate migration step to remember. `build.sh` runs `migrate` against the same
`DATABASE_URL` the web process uses.

If a future change ever needs pooling for connection limits, keep the direct
string for migrations and use the pooler for runtime only. Do not point both
at the pooler.

## Step 2: Push the repository to GitHub

The repository must be on GitHub before Render can build it.

```bash
git add .
git commit -m "Add deployment configuration"
git push origin main
```

Confirm that `.env` and `db.sqlite3` are not in the repository. Both are listed
in `.gitignore`, and `.env` holds your local secrets.

## Step 3: Create the Render web service

1. Sign in at https://dashboard.render.com.
2. Choose **New**, then **Web Service**.
3. Connect your GitHub account if asked, then select the repository.
4. Fill in the settings:

   | Setting | Value |
   | --- | --- |
   | Name | `course-registration` (this becomes part of the URL) |
   | Region | the same region you chose for Neon, if possible |
   | Branch | `main` |
   | Runtime | `Python 3` |
   | Build Command | `./build.sh` |
   | Start Command | `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120` |
   | Instance Type | `Free` |

5. If `./build.sh` fails with a permission error, change the build command to
   `bash build.sh`. Render checks out files without the executable bit in some
   cases, and `bash build.sh` avoids that.

Alternatively, choose **New**, then **Blueprint**, and select the repository.
Render reads `render.yaml` and fills in the build and start commands for you.
You still have to enter the secret values by hand.

## Step 4: Set the environment variables

In the service, open **Environment** and add each of these. Use **Add
Environment Variable** once per row.

| Key | Value |
| --- | --- |
| `SECRET_KEY` | A long random string. Generate one with the command below. |
| `DEBUG` | `False` |
| `DATABASE_URL` | The Neon **direct** connection string from step 1 |
| `ADMIN_USERNAME` | The staff username you want, for example `admin` |
| `ADMIN_PASSWORD` | A strong password for that staff account |
| `INSTITUTION_NAME` | `SchoolTry` |
| `ALLOWED_HOSTS` | Your Render hostname, for example `course-registration.onrender.com` |
| `CSRF_TRUSTED_ORIGINS` | `https://course-registration.onrender.com` |
| `PYTHON_VERSION` | `3.12.7` |

Generate a secret key locally with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Notes on the variables:

- `SECRET_KEY` has no fallback in `settings.py`. If it is missing the app stops
  at startup rather than running with a known key. That is deliberate.
- `DEBUG` defaults to `False`, so leaving it out is safe, but setting it
  explicitly documents the intent.
- `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` are both optional. Render sets
  `RENDER_EXTERNAL_HOSTNAME` automatically, and `settings.py` adds that host to
  `ALLOWED_HOSTS` and `https://<host>` to `CSRF_TRUSTED_ORIGINS`. Set them
  yourself if you attach a custom domain.
- `PYTHON_VERSION` is a belt and braces measure alongside `.python-version`.
  If Render reports a different Python version in the build log, the variable
  is the one that wins.

## Step 5: Deploy

1. Choose **Create Web Service**, or **Manual Deploy** then **Deploy latest
   commit** if the service already exists.
2. Watch the build log. The build runs, in order: `pip install`, `collectstatic`,
   `migrate`, `create_admin`, `seed_data`.
3. A successful build ends with the gunicorn start line and a log entry saying
   the service is live.

The build is safe to run again. `pip` skips installed packages, `collectstatic`
and `migrate` are idempotent, `create_admin` updates the existing account
instead of duplicating it, and `seed_data` skips rows that already exist.

## Step 6: Check the live site

1. Open the service URL. The student identification page should load with
   styling, which confirms WhiteNoise is serving static files.
2. Open `/manage/` and sign in with `ADMIN_USERNAME` and `ADMIN_PASSWORD`.
3. Register a course as a student, then open the printable form and check the
   institution name reads `SchoolTry`.
4. If the page loads without styling, the static files were not collected.
   Check the build log for the `collectstatic` step.

## Troubleshooting

| Symptom | Likely cause |
| --- | --- |
| `KeyError: 'SECRET_KEY'` in the log | `SECRET_KEY` is not set on the service |
| `DisallowedHost` | `ALLOWED_HOSTS` does not include the hostname being used |
| `CSRF verification failed` on a form | `CSRF_TRUSTED_ORIGINS` is missing the `https://` origin |
| Page loads with no CSS | `collectstatic` did not run, or `STATIC_ROOT` is not being served |
| `migrate` fails on the build | Try the direct Neon connection string, see step 1 |
| Build fails on `./build.sh` | Use `bash build.sh` as the build command |

## Local checks before deploying

Run the test suite:

```bash
python manage.py test
```

Run the deployment checks with fake values. This never reads `.env` and never
touches a real database:

```bash
python deploy_check.py
```

Two warnings are expected and are deliberate:

- `security.W005` asks for `SECURE_HSTS_INCLUDE_SUBDOMAINS`. The site is served
  from `onrender.com`, a shared parent domain, so enabling this would affect
  hosts that are not yours.
- `security.W021` asks for `SECURE_HSTS_PRELOAD`. Preloading is a permanent
  commitment and is not appropriate for a project at this stage.

`SECURE_HSTS_SECONDS` is set to one hour rather than a year, so a mistake is
reversible while the deployment is new. Raise it once the site is settled.
