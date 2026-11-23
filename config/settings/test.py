from .base import *  # noqa: F401,F403
from .base import REST_FRAMEWORK  # noqa: F401,F403

DEBUG = False
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
MAILERS = {
    "default": {
        "BACKEND": "django.core.mail.backends.locmem.EmailBackend",
    }
}

# Disable throttling in tests to avoid inter-test rate limiting
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
    "anon": "1000/min",
    "user": "1000/min",
    "company_import": "1000/min",
    "search": "1000/min",
    "chart": "1000/min",
}
