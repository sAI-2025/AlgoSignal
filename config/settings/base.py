import sys
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parents[2]
APPS_DIR = BASE_DIR / "apps"
if str(APPS_DIR) not in sys.path:
    sys.path.insert(0, str(APPS_DIR))

env = environ.Env(
    DEBUG=(bool, False),
    USE_TZ=(bool, True),
    LOG_LEVEL=(str, "INFO"),
)

environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY", default="unsafe-dev-secret")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = [
    host.strip()
    for host in env("ALLOWED_HOSTS", default="localhost,127.0.0.1").split(",")
    if host.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "apps.core.apps.CoreConfig",
    "apps.companies.apps.CompaniesConfig",
    "apps.market_data.apps.MarketDataConfig",
    "apps.fetcher.apps.FetcherConfig",
    "apps.indicators.apps.IndicatorsConfig",
    "apps.signals.apps.SignalsConfig",
    "apps.scanner.apps.ScannerConfig",
    "apps.analytics.apps.AnalyticsConfig",
    "apps.visualization.apps.VisualizationConfig",
    "apps.explorer.apps.ExplorerConfig",
    "apps.dashboard.apps.DashboardConfig",
]

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
                "apps.core.context_processors.market_status",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = env("TIME_ZONE", default="Asia/Kolkata")
USE_I18N = True
USE_TZ = env("USE_TZ")

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "user": "120/min",
        "anon": "30/min",
    },
    "EXCEPTION_HANDLER": "apps.core.api.exception_handler.api_exception_handler",
    "UNAUTHENTICATED_USER": None,
}

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "login"

CACHE_URL = env("CACHE_URL", default="locmemcache://")
CACHES = {"default": env.cache(default=CACHE_URL)}

MARKET_DATA_PROVIDER = env("MARKET_DATA_PROVIDER", default="yfinance")
INDEX_UNIVERSE = env("INDEX_UNIVERSE", default="NIFTY100")
PROVIDER_THROTTLE_SECONDS = env.float("PROVIDER_THROTTLE_SECONDS", default=2.0)

# Provider reliability policy (ARCHITECTURE §8.4)
PROVIDER_MAX_RETRIES = env.int("PROVIDER_MAX_RETRIES", default=3)
PROVIDER_TRANSIENT_DELAYS = (5, 15, 45)
PROVIDER_RATE_LIMIT_DELAYS = (30, 60, 120)
PROVIDER_CIRCUIT_THRESHOLD = env.int("PROVIDER_CIRCUIT_THRESHOLD", default=5)
PROVIDER_COOLDOWN_SECONDS = env.int("PROVIDER_COOLDOWN_SECONDS", default=1800)
FETCH_HEARTBEAT_TIMEOUT_MIN = env.int("FETCH_HEARTBEAT_TIMEOUT_MIN", default=15)
NIFTY_INDEX_CSV_URLS = env.json("NIFTY_INDEX_CSV_URLS", default={})
NIFTY_IMPORT_USER_AGENT = env(
    "NIFTY_IMPORT_USER_AGENT",
    default="AlgoSignal/1.0 (constituent-import; contact: local-dev)",
)

NSE_HOLIDAYS_FILE = env("NSE_HOLIDAYS_FILE", default="")

LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "algosignal.log"),
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 3,
            "formatter": "standard",
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": env("LOG_LEVEL"),
    },
}
