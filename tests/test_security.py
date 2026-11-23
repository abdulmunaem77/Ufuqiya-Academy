import re

import pytest

from app import create_app
from app.extensions import db, limiter
from app.models import ROLE_OWNER, User
from config import Config, TestConfig
from conftest import PASSWORD, csrf_from, login, make_user, post


def test_security_headers(client):
    h = client.get("/").headers
    assert h["X-Content-Type-Options"] == "nosniff" and h["X-Frame-Options"] == "DENY"
    csp = h["Content-Security-Policy"]
    assert "script-src 'self'" in csp and "'unsafe-inline'" not in csp and "frame-ancestors 'none'" in csp
    assert "Referrer-Policy" in h


def test_no_inline_script_or_style_in_pages(app, owner):
    """CSP forbids inline code, so templates must not contain any."""
    c = app.test_client()
    login(c, "owner@example.com", admin=True)
    for url in ["/", "/courses/", "/courses/web-development-fundamentals", "/workshops/", "/contact", "/admin/",
                "/admin/e/courses/", "/consultations/"]:
        html = c.get(url).get_data(as_text=True)
        assert not re.search(r"<script(?![^>]*\bsrc=)", html), url
        assert not re.search(r"\sstyle=", html), url
        assert not re.search(r"\son(click|load|error|change|submit)=", html), url


def test_csrf_enforced_on_every_public_post(client, student):
    login(client, "student@example.com")
    for url in ["/logout", "/account", "/account/password", "/contact", "/courses/generative-ai-everyday-work/enroll",
                "/workshops/prompt-engineering-live-lab/register", "/consultations/ai-adoption-strategy-session/book"]:
        assert client.post(url, data={}).status_code == 400, url
    anon = client.application.test_client()
    for url in ["/login", "/register", "/admin/login"]:
        assert anon.post(url, data={"email": "a@b.co", "password": "x"}).status_code == 400, url


def test_csrf_token_bound_to_session(app):
    a, b = app.test_client(), app.test_client()
    tok = csrf_from(a.get("/login").get_data(as_text=True))
    b.get("/login")
    assert b.post("/login", data={"csrf_token": tok, "email": "x@y.co", "password": "p"}).status_code == 400


def test_session_cookie_flags(client, student):
    r = login(client, "student@example.com")
    cookie = r.headers["Set-Cookie"]
    assert "HttpOnly" in cookie and "SameSite=Lax" in cookie


def test_production_requires_secret_and_secure_cookies(monkeypatch):
    class Prod(Config):
        IS_PRODUCTION = True
        SECRET_KEY = None
    with pytest.raises(RuntimeError):
        create_app(Prod)
    assert Config.SESSION_COOKIE_HTTPONLY and Config.SESSION_COOKIE_SAMESITE == "Lax"


def test_session_fixation_defeated(client, student):
    client.get("/login")
    with client.session_transaction() as s:
        s["attacker_planted"] = "yes"
    login(client, "student@example.com")
    with client.session_transaction() as s:
        assert "attacker_planted" not in s


def test_logout_clears_session(client, student):
    login(client, "student@example.com")
    post(client, "/logout", page="/account")
    with client.session_transaction() as s:
        assert "_user_id" not in s


def test_xss_escaped_in_user_content(client, app):
    from app.models import ContactMessage
    payload = "<img src=x onerror=alert(1)>"
    post(client, "/contact", {"name": payload, "email": "a@example.com", "topic": "general", "message": payload + " long enough"}, page="/contact")
    make_user("o@example.com", role=ROLE_OWNER)
    c = app.test_client()
    login(c, "o@example.com", admin=True)
    html = c.get("/admin/messages").get_data(as_text=True)
    assert payload not in html and "&lt;img" in html


def test_sql_injection_in_login(client, student):
    for p in ["' OR '1'='1", "admin'--", "x@example.com' OR 1=1 --"]:
        login(client, p, p)
        assert client.get("/dashboard").status_code == 302


def test_idor_student_pages(client, student):
    """/dashboard only ever shows the current user's data."""
    from app.models import Enrollment
    other = make_user("other@example.com", name="Zed Other")
    db.session.add(Enrollment(user_id=other.id, course_id=1, status="active"))
    db.session.commit()
    login(client, "student@example.com")
    client.get("/lang/en")
    html = client.get("/dashboard").get_data(as_text=True)
    assert "Zed Other" not in html and "Generative AI" not in html


def test_error_pages_do_not_leak(app, client):
    @app.route("/boom")
    def boom():
        raise RuntimeError("secret-internal-detail /etc/passwd")
    app.config["PROPAGATE_EXCEPTIONS"] = False
    r = client.get("/boom")
    assert r.status_code == 500
    body = r.get_data(as_text=True)
    assert "secret-internal-detail" not in body and "Traceback" not in body
    assert client.get("/nope-404").status_code == 404
    assert client.post("/", data={}).status_code in (400, 405)


def test_max_content_length(client):
    r = client.post("/contact", data={"message": "x" * 200_000})
    assert r.status_code in (400, 413)


def test_passwords_hashed_with_scrypt_and_salted(app):
    a, b = make_user("a1@example.com"), make_user("b1@example.com")
    assert a.password_hash != b.password_hash and PASSWORD not in a.password_hash


class RateConfig(TestConfig):
    RATELIMIT_ENABLED = True


def test_rate_limit_login_and_admin_login():
    app = create_app(RateConfig)
    with app.app_context():
        db.create_all()
        limiter.reset()
        c = app.test_client()
        codes = []
        for _ in range(14):
            tok = csrf_from(c.get("/login").get_data(as_text=True))
            codes.append(c.post("/login", data={"csrf_token": tok, "email": "n@example.com", "password": "bad-password-1"}).status_code)
        assert 429 in codes and codes[0] == 200
        limiter.reset()
        codes = []
        for _ in range(9):
            tok = csrf_from(c.get("/admin/login").get_data(as_text=True))
            codes.append(c.post("/admin/login", data={"csrf_token": tok, "email": "n@example.com", "password": "bad-password-1"}).status_code)
        assert 429 in codes
        tok = csrf_from(c.get("/admin/login").get_data(as_text=True))
        r = c.post("/admin/login", data={"csrf_token": tok, "email": "n@example.com", "password": "x"})
        assert r.status_code == 429 and "Traceback" not in r.get_data(as_text=True)
        limiter.reset()
        db.session.remove()
        db.drop_all()


def test_rate_limit_register_and_contact():
    app = create_app(RateConfig)
    with app.app_context():
        db.create_all()
        limiter.reset()
        c = app.test_client()
        codes = []
        for i in range(8):
            tok = csrf_from(c.get("/contact").get_data(as_text=True))
            codes.append(c.post("/contact", data={"csrf_token": tok, "name": "Sam", "email": "s@example.com", "topic": "general",
                                                  "message": "hello there friend"}).status_code)
        assert codes.count(429) >= 3
        limiter.reset()
        db.session.remove()
        db.drop_all()


def test_rate_limit_shared_across_instances_via_redis(monkeypatch):
    """Two app instances (≈ two serverless workers) must share one counter when Redis is used."""
    import os
    uri = os.environ.get("TEST_REDIS_URL")
    if not uri:
        pytest.skip("set TEST_REDIS_URL to run")

    class RedisRate(RateConfig):
        RATELIMIT_STORAGE_URI = uri

    a = create_app(RedisRate)
    with a.app_context():
        db.create_all()
        limiter.reset()
        ca = a.test_client()
        codes = []
        for _ in range(6):
            tok = csrf_from(ca.get("/contact").get_data(as_text=True))
            codes.append(ca.post("/contact", data={"csrf_token": tok, "name": "Sam", "email": "s@example.com", "topic": "general",
                                                   "message": "hello there friend"}).status_code)
        # a *second* app object pointing at the same Redis sees the exhausted limit
        b = create_app(RedisRate)
        cb = b.test_client()
        tok = csrf_from(cb.get("/contact").get_data(as_text=True))
        r = cb.post("/contact", data={"csrf_token": tok, "name": "Sam", "email": "s@example.com", "topic": "general",
                                      "message": "hello there friend"})
        assert 429 in codes and r.status_code == 429
        limiter.reset()
        db.session.remove(); db.drop_all()
