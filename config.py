import os
import secrets
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


class Config:
    APP_ENV = os.environ.get("APP_ENV", "development").lower()
    IS_PRODUCTION = APP_ENV == "production"

    SECRET_KEY = os.environ.get("SECRET_KEY") or None
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'instance' / 'ufuqia.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEFAULT_CURRENCY = os.environ.get("DEFAULT_CURRENCY", "USD")

    # Sessions / cookies
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = IS_PRODUCTION
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = IS_PRODUCTION
    REMEMBER_COOKIE_DURATION = timedelta(days=14)
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)

    # CSRF
    WTF_CSRF_TIME_LIMIT = 4 * 3600
    WTF_CSRF_SSL_STRICT = IS_PRODUCTION

    # Rate limiting
    RATELIMIT_ENABLED = True
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_HEADERS_ENABLED = True
    TRUSTED_PROXY_COUNT = int(os.environ.get("TRUSTED_PROXY_COUNT", "0"))

    # Account lock-out after repeated failures
    MAX_FAILED_LOGINS = 5
    LOCKOUT_MINUTES = 15

    MAX_CONTENT_LENGTH = 64 * 1024  # forms only; no uploads in this app
    PER_PAGE = 9

    @classmethod
    def validate(cls):
        """Called once at startup."""
        if cls.IS_PRODUCTION and not cls.SECRET_KEY:
            raise RuntimeError("SECRET_KEY must be set when APP_ENV=production.")


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-only-secret-key-not-for-use"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    RATELIMIT_ENABLED = False
    WTF_CSRF_ENABLED = True
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False
    SERVER_NAME = None


def ephemeral_secret():
    return secrets.token_hex(32)
