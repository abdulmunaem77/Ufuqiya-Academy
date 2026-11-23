import logging
import os
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user
from flask_wtf.csrf import CSRFError
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config, TestConfig, ephemeral_secret

from .extensions import csrf, db, limiter, login_manager, migrate
from .i18n import LANGS, month_name, translate

log = logging.getLogger("ufuqia")


def create_app(config_object=None):
    cfg = config_object or Config
    cfg.validate()
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(cfg)
    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError:  # read-only filesystem (serverless)
        pass

    if not app.config.get("SECRET_KEY"):  # development only (validate() blocks production)
        app.config["SECRET_KEY"] = ephemeral_secret()
        log.warning("SECRET_KEY not set: using an ephemeral key; sessions reset on restart.")

    n = app.config.get("TRUSTED_PROXY_COUNT", 0)
    if n:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=n, x_proto=n, x_host=n)

    tzname = os.environ.get("ACADEMY_TIMEZONE", "Asia/Riyadh")
    try:
        app.config["ACADEMY_TZ"] = ZoneInfo(tzname)
    except ZoneInfoNotFoundError:
        app.config["ACADEMY_TZ"] = ZoneInfo("UTC")
        tzname = "UTC"
    app.config["ACADEMY_TZ_NAME"] = tzname
    hosts = [h.strip() for h in os.environ.get("TRUSTED_HOSTS", "").split(",") if h.strip()]
    if hosts and not app.config.get("TESTING"):
        app.config["TRUSTED_HOSTS"] = hosts  # reject forged Host headers (reset-link poisoning)

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    limiter.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.session_protection = "strong"
    login_manager.login_message = None

    from .blueprints import register_blueprints
    register_blueprints(app)
    _register_hooks(app)
    _register_errors(app)
    _register_template_helpers(app)

    from .cli import register_cli
    register_cli(app)
    return app


def current_lang():
    lang = session.get("lang")
    if lang not in LANGS and current_user.is_authenticated:
        lang = current_user.locale
    return lang if lang in LANGS else "ar"


def _register_hooks(app):
    @app.before_request
    def force_password_change():
        if (current_user.is_authenticated and current_user.must_change_password
                and request.endpoint not in {"auth.change_password", "auth.logout", "static", "main.set_language"}):
            return redirect(url_for("auth.change_password"))

    @app.before_request
    def force_staff_2fa():
        if (app.config.get("REQUIRE_STAFF_2FA") and current_user.is_authenticated and current_user.is_staff
                and not current_user.totp_enabled
                and request.endpoint not in {"auth.twofa_manage", "auth.logout", "auth.change_password",
                                             "static", "main.set_language"}):
            return redirect(url_for("auth.twofa_manage"))

    @app.after_request
    def security_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        resp.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        resp.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        resp.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
            "font-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; "
            "frame-src https://www.youtube-nocookie.com https://player.vimeo.com; frame-ancestors 'none'")
        if app.config["IS_PRODUCTION"]:
            resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        # Authenticated / form pages must not be cached by shared caches.
        if request.endpoint != "static":
            resp.headers.setdefault("Cache-Control", "no-store" if current_user.is_authenticated
                                    else "no-cache")
        return resp


def _register_errors(app):
    def page(code, title_key, msg_key):
        resp = render_template("errors/error.html", code=code, title_key=title_key, msg_key=msg_key)
        return resp, code

    @app.errorhandler(400)
    def e400(e): return page(400, "err.400.title", "err.400.msg")

    @app.errorhandler(CSRFError)
    def ecsrf(e):
        app.logger.warning("CSRF rejected on %s: %s", request.path, e.description)
        return page(400, "err.csrf.title", "err.csrf.msg")

    @app.errorhandler(403)
    def e403(e): return page(403, "err.403.title", "err.403.msg")

    @app.errorhandler(404)
    def e404(e): return page(404, "err.404.title", "err.404.msg")

    @app.errorhandler(413)
    def e413(e): return page(413, "err.400.title", "err.400.msg")

    @app.errorhandler(429)
    def e429(e): return page(429, "err.429.title", "err.429.msg")

    @app.errorhandler(500)
    def e500(e):
        db.session.rollback()
        return page(500, "err.500.title", "err.500.msg")

    @app.errorhandler(Exception)
    def eany(e):
        from werkzeug.exceptions import HTTPException
        if isinstance(e, HTTPException):
            return e
        app.logger.exception("Unhandled error")  # details go to logs, never to the user
        db.session.rollback()
        return page(500, "err.500.title", "err.500.msg")


def _register_template_helpers(app):
    @app.context_processor
    def inject():
        lang = current_lang()

        def t(key, **kw):
            return translate(key, lang, **kw)

        def money(value):
            value = Decimal(value or 0)
            if value == 0:
                return t("common.free")
            txt = f"{value:,.2f}".rstrip("0").rstrip(".") if value % 1 else f"{value:,.0f}"
            return f"{txt} {app.config['DEFAULT_CURRENCY']}"

        return dict(t=t, lang=lang, dir="rtl" if lang == "ar" else "ltr", LANGS=LANGS,
                    money=money, now_year=__import__('datetime').date.today().year, tzname=app.config["ACADEMY_TZ_NAME"],
                    is_staff=current_user.is_authenticated and current_user.is_staff)

    def to_local(dt):
        from datetime import timezone
        return dt.replace(tzinfo=timezone.utc).astimezone(app.config["ACADEMY_TZ"])

    @app.template_filter("dt")
    def fmt_dt(value, with_time=True):
        if not value:
            return "—"
        d = to_local(value)
        s = f"{d.day} {month_name(d.month, current_lang())} {d.year}"
        return f"{s} · {d:%H:%M}" if with_time else s

    @app.template_filter("d")
    def fmt_d(value):
        return fmt_dt(value, with_time=False)

    @app.template_filter("local_input")
    def local_input(value):
        return to_local(value).strftime("%Y-%m-%dT%H:%M") if value else ""

    @app.template_filter("paras")
    def paras(text):
        from markupsafe import Markup, escape
        parts = [p.strip() for p in (text or "").split("\n\n") if p.strip()]
        return Markup("".join(f"<p>{escape(p)}</p>" for p in parts))

    app.jinja_env.globals["loc"] = lambda obj, field: obj.loc(field, current_lang())

    @app.route("/healthz")
    @limiter.exempt
    def healthz():
        return jsonify(status="ok")
