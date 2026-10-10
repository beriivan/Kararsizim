"""
Django settings for the Kararsizim project.

Secrets and environment-specific values are read from environment variables
(a local .env file is loaded in development). See .env.example.
"""

import os
import sys
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def env_list(name, default=""):
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


# --- Core -------------------------------------------------------------------

DEBUG = env_bool("DEBUG", False)

SECRET_KEY = os.environ.get("SECRET_KEY", "")
if not SECRET_KEY:
    raise ImproperlyConfigured("SECRET_KEY environment variable is required (see .env.example).")

# Vercel exposes the deployment's own host names as system env vars
# (without scheme). Trust exactly those, not all of *.vercel.app.
VERCEL_HOSTS = [
    host
    for host in (
        os.environ.get("VERCEL_URL", ""),
        os.environ.get("VERCEL_BRANCH_URL", ""),
        os.environ.get("VERCEL_PROJECT_PRODUCTION_URL", ""),
    )
    if host
]

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1") + VERCEL_HOSTS
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS") + [f"https://{host}" for host in VERCEL_HOSTS]

if not DEBUG:
    # Vercel terminates TLS and forwards the original scheme in this header.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # HSTS is sticky in browsers, so it stays off unless explicitly enabled.
    SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "0"))

# --- Applications -----------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "accounts",
    "polls",
]

AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "home"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
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
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# --- Database ---------------------------------------------------------------
# DATABASE_URL (Supabase transaction pooler, port 6543) is used at runtime.
# Set USE_DIRECT_DB=1 to run migrations through DIRECT_DATABASE_URL instead
# (Supabase direct connection or session pooler, port 5432).
# Without any URL we fall back to SQLite for quick local development.

if "test" in sys.argv[1:2]:
    # `manage.py test` must never touch the real (Supabase) database.
    DATABASE_URL = ""
elif env_bool("USE_DIRECT_DB"):
    DATABASE_URL = os.environ.get("DIRECT_DATABASE_URL", "")
else:
    DATABASE_URL = os.environ.get("DATABASE_URL", "")

if DATABASE_URL:
    DATABASES = {
        "default": {
            **dj_database_url.parse(DATABASE_URL, conn_max_age=0),
            # Transaction pooling does not support server-side cursors
            # or (client-side) prepared statements.
            "DISABLE_SERVER_SIDE_CURSORS": True,
            "OPTIONS": {"prepare_threshold": None},
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# --- Sessions ---------------------------------------------------------------
# Database-backed sessions (Django default); serverless has no shared disk/memory.

SESSION_ENGINE = "django.contrib.sessions.backends.db"

# --- Password validation ----------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- Internationalization ---------------------------------------------------

LANGUAGE_CODE = "tr"
TIME_ZONE = "Europe/Istanbul"
USE_I18N = True
USE_TZ = True

# --- Static files -----------------------------------------------------------

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

# Let WhiteNoise find static files (project `static/` + admin) directly through
# the staticfiles finders, so the app also works when `collectstatic` was not run
# (e.g. a serverless build that doesn't execute it).
WHITENOISE_USE_FINDERS = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
