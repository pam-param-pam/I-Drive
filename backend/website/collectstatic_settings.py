"""Minimal settings used only while collecting static files during image builds."""

import os


# Imported application modules expect this value during Django app loading.
os.environ.setdefault("BACKEND_BASE_URL", "http://localhost/api")
os.environ.setdefault("SIGNING_SECRET", "collectstatic-build-only")

SECRET_KEY = "collectstatic-build-only"
DEBUG = False

INSTALLED_APPS = [
    "simple_history",
    "django.contrib.admin",
    "website",
    "mptt",
    "corsheaders",
    "daphne",
    "django_celery_beat",
    "rest_framework",
    "channels",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_user_agents",
]

STATIC_URL = "/api/static/"
STATIC_ROOT = "/var/www/idrive/backend-static"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
