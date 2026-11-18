"""
Django settings for the course registration project.

Every secret and environment-specific value is read from the environment.
Copy .env.example to .env for local development. When DATABASE_URL is unset,
the project uses a local SQLite file.
"""

import os
import sys
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def env_bool(name, default="False"):
    value = os.environ.get(name, default).strip().lower()
    return value in {"1", "true", "yes", "on"}


def env_list(name):
    raw = os.environ.get(name, "")
    return [item.strip() for item in raw.split(",") if item.strip()]


# There is no fallback key. A missing SECRET_KEY stops the process at startup
# instead of silently running production with a known key.
SECRET_KEY = os.environ["SECRET_KEY"]

# Production is the default. Local development sets DEBUG=True in .env.
DEBUG = env_bool("DEBUG")

# Render provides its public hostname in RENDER_EXTERNAL_HOSTNAME.
render_hostname = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "").strip()

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS")
if render_hostname and render_hostname not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(render_hostname)

# The same host, as a full origin, for cross-site POST protection. Anything in
# the environment is kept as well, so local values still work alongside this.
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")
if render_hostname:
    render_origin = f"https://{render_hostname}"
    if render_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(render_origin)

# Printed on the student course registration form.
INSTITUTION_NAME = os.environ.get("INSTITUTION_NAME", "SchoolTry")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "registration",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "registration.context_processors.institution",
                "registration.context_processors.current_student",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# A blank DATABASE_URL means "use SQLite". A postgres URL is used in production.
database_url = os.environ.get("DATABASE_URL", "").strip()
if database_url:
    DATABASES = {
        "default": dj_database_url.parse(
            database_url,
            conn_max_age=600,
            # Neon suspends idle compute, which drops the server side of a
            # pooled connection. Checking the connection before reuse turns
            # that into a transparent reconnect instead of a failed request.
            conn_health_checks=True,
            # Neon requires TLS. ssl_require adds sslmode=require only when the
            # connection string does not already carry an sslmode setting.
            ssl_require="sslmode" not in database_url,
        ),
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"

TIME_ZONE = "Africa/Lagos"

USE_I18N = True

USE_TZ = True

STATIC_URL = "/static/"

# collectstatic gathers everything here; WhiteNoise serves it from the app.
STATIC_ROOT = BASE_DIR / "staticfiles"

# WhiteNoise sits directly after SecurityMiddleware and serves static files in
# production, including compressed and hashed copies.
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

# Hashed, compressed static files in production. The manifest only exists after
# collectstatic has run, so tests use the plain backend and still render.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}

if "test" in sys.argv:
    STORAGES["staticfiles"]["BACKEND"] = (
        "django.contrib.staticfiles.storage.StaticFilesStorage"
    )

# Render terminates HTTPS in front of the app and forwards the original scheme
# in this header, so Django knows the request was secure.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

if not DEBUG:
    # Sent over HTTPS only, so they are withheld from plain HTTP requests.
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # render.com is on the public suffix list, so __Host- cookies are allowed.
    SESSION_COOKIE_NAME = "__Host-sessionid"
    CSRF_COOKIE_NAME = "__Host-csrftoken"
    # Mismatched Host headers are rejected when this matches ALLOWED_HOSTS.
    SECURE_SSL_REDIRECT = True
    # One hour only. Browsers remember this for a year, so a short value keeps
    # a mistake reversible while the deployment is still new.
    SECURE_HSTS_SECONDS = 3600
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False

# Staff area sign-in. These are URL names, so the paths live in one place.
LOGIN_URL = "registration:login"
LOGIN_REDIRECT_URL = "registration:home"
LOGOUT_REDIRECT_URL = "registration:login"

# Request errors are written to stdout as plain text, which is what Render's
# log view shows. Only the django.request logger is named, so the record is
# the request path, the status code and the traceback. Request bodies, cookies
# and environment values are never logged, and the other loggers keep Django's
# defaults.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "plain": {
            "format": "[{levelname}] {asctime} {name}: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "stdout": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "formatter": "plain",
        },
    },
    "loggers": {
        "django.request": {
            "handlers": ["stdout"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}

# A rejected CSRF token gets a friendly page instead of Django's bare default.
CSRF_FAILURE_VIEW = "registration.error_views.csrf_failure"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
