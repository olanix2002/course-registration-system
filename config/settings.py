"""
Django settings for the course registration project.

Every secret and environment-specific value is read from the environment.
Copy .env.example to .env for local development. When DATABASE_URL is unset,
the project uses a local SQLite file.
"""

import os
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


SECRET_KEY = os.environ["SECRET_KEY"]

DEBUG = env_bool("DEBUG")

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS")

CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

# Printed on the student course registration form.
INSTITUTION_NAME = os.environ.get("INSTITUTION_NAME", "Sample University")

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
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# A blank DATABASE_URL means "use SQLite". A postgres URL is used in production.
database_url = os.environ.get("DATABASE_URL", "").strip()
if database_url:
    DATABASES = {
        "default": dj_database_url.parse(database_url, conn_max_age=600),
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

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

STATIC_URL = "/static/"

# Staff area sign-in. These are URL names, so the paths live in one place.
LOGIN_URL = "registration:login"
LOGIN_REDIRECT_URL = "registration:home"
LOGOUT_REDIRECT_URL = "registration:login"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
