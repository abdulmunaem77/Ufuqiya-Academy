import os
import secrets
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _db_url():
    """Normalise provider URLs (postgres:// , postgresql://) to the psycopg3 driver."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        base = Path("/tmp") if os.environ.get("VERCEL") else BASE_DIR / "instance"
        return f"sqlite:///{base / 'ufuqia.db'}"
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def _bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


class Config:
    APP_ENV = os.environ.get("APP_ENV", "development").lower()
    IS_PRODUCTION = APP_ENV == "production"

    SECRET_KEY = os.environ.get("SECRET_KEY") or None
    SQLALCHEMY_DATABASE_URI = _db_url()
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    ON_VERCEL = bool(os.environ.get("VERCEL"))
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

    # E-mail (SMTP). Leave MAIL_SERVER empty to run without sending: messages are
    # then only recorded in the owner-visible outbox.
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
    MAIL_USE_TLS = _bool("MAIL_USE_TLS", True)      # STARTTLS (port 587)
    MAIL_USE_SSL = _bool("MAIL_USE_SSL", False)     # implicit TLS (port 465)
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_FROM = os.environ.get("MAIL_FROM", "")
    MAIL_ADMIN_TO = os.environ.get("MAIL_ADMIN_TO", "")  # staff inbox for contact/booking alerts
    MAIL_ENABLED = bool(MAIL_SERVER and MAIL_FROM)
    REQUIRE_EMAIL_VERIFICATION = _bool("REQUIRE_EMAIL_VERIFICATION", bool(MAIL_SERVER and MAIL_FROM))
    PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")  # used in e-mail links

    # Two-factor authentication
    REQUIRE_STAFF_2FA = _bool("REQUIRE_STAFF_2FA", IS_PRODUCTION)

    # Account lock-out after repeated failures
    MAX_FAILED_LOGINS = 5
    LOCKOUT_MINUTES = 15

    MAX_CONTENT_LENGTH = 64 * 1024  # forms only; no uploads in this app
    PER_PAGE = 9
    SHOW_SAMPLE_NOTICE = os.environ.get("SHOW_SAMPLE_NOTICE", "1").strip().lower() in {"1", "true", "yes", "on"}

    @classmethod
    def validate(cls):
        """Called once at startup."""
        if cls.IS_PRODUCTION and not cls.SECRET_KEY:
            raise RuntimeError("SECRET_KEY must be set when APP_ENV=production.")
        if cls.ON_VERCEL and cls.SQLALCHEMY_DATABASE_URI.startswith("sqlite") and cls.IS_PRODUCTION:
            raise RuntimeError("Vercel's filesystem is ephemeral: set DATABASE_URL to a PostgreSQL database.")
        if cls.ON_VERCEL and cls.RATELIMIT_STORAGE_URI.startswith("memory"):
            import logging
            logging.getLogger("ufuqia").warning(
                "Rate limits are per serverless instance (memory://). Set RATELIMIT_STORAGE_URI to Redis.")


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-only-secret-key-not-for-use"
    SQLALCHEMY_DATABASE_URI = os.environ.get("TEST_DATABASE_URL", "sqlite://")  # set to run the suite on PostgreSQL
    RATELIMIT_ENABLED = False
    MAIL_SERVER = ""
    MAIL_ENABLED = False
    REQUIRE_EMAIL_VERIFICATION = False
    REQUIRE_STAFF_2FA = False
    WTF_CSRF_ENABLED = True
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False
    SERVER_NAME = None


def ephemeral_secret():
    return secrets.token_hex(32)
