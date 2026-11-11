import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes"}


DEBUG = _bool("DJANGO_DEBUG", False)
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "dev-only-insecure-key"
    else:
        raise RuntimeError("DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is false")

ALLOWED_HOSTS = [h.strip() for h in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]

INSTALLED_APPS = ["django.contrib.staticfiles", "rest_framework", "routing"]
MIDDLEWARE = [
    "django.middleware.gzip.GZipMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "routing.api.middleware.AbuseGuardMiddleware",  # burst / abuse guard (before CommonMiddleware)
    "django.middleware.common.CommonMiddleware",
]
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
DATABASES: dict = {}  # stateless: no database required
USE_TZ = True
TIME_ZONE = "UTC"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
os.makedirs(STATIC_ROOT, exist_ok=True)

# Private server-side credential. NEVER exposed to the frontend.
MAPBOX_SERVER_TOKEN = os.getenv("MAPBOX_SERVER_TOKEN", "")
PROVIDER_TIMEOUT_S = float(os.getenv("PROVIDER_TIMEOUT_S", "10"))
DATA_UPLOAD_MAX_MEMORY_SIZE = 64 * 1024  # request size cap

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
NUM_PROXIES = int(os.getenv("NUM_PROXIES", "1"))

# Abuse / burst guard settings (read by AbuseGuardMiddleware)
ABUSE_BURST_LIMIT = int(os.getenv("ABUSE_BURST_LIMIT", "30"))
ABUSE_WINDOW_S = int(os.getenv("ABUSE_WINDOW_S", "60"))
ABUSE_BLOCK_S = int(os.getenv("ABUSE_BLOCK_S", "300"))

REST_FRAMEWORK = {
    "EXCEPTION_HANDLER": "routing.api.errors.exception_handler",
    "DEFAULT_THROTTLE_RATES": {"analyze": "10/min", "heatmap": "20/min", "geocode": "60/min"},
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
    "UNAUTHENTICATED_USER": None,
}

if not DEBUG:
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = _bool("DJANGO_SSL_REDIRECT", True)
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
    SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
    X_FRAME_OPTIONS = "DENY"  # Django's default, but explicit is better than implicit

LOGGING = {"version": 1, "disable_existing_loggers": False,
           "handlers": {"console": {"class": "logging.StreamHandler"}},
           "root": {"handlers": ["console"], "level": os.getenv("LOG_LEVEL", "INFO")}}

# Production: Django (WhiteNoise) serves the built React app from the same origin, so no CORS is needed.
FRONTEND_DIST = BASE_DIR / "frontend_dist"
if FRONTEND_DIST.exists():
    WHITENOISE_ROOT = FRONTEND_DIST
    WHITENOISE_INDEX_FILE = True
