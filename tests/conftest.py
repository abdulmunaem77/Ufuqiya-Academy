import re

import pytest

from app import create_app
from app.extensions import db, limiter
from app.models import ROLE_OWNER, User
from app.seed import seed_sample_content
from config import TestConfig

PASSWORD = "Str0ng-Passw0rd!"


@pytest.fixture()
def app():
    app = create_app(TestConfig)

    @app.before_request
    def _fresh_csrf_per_request():
        # Tests keep one app context open for direct DB access; Flask-WTF caches
        # the token on ``g`` which would otherwise leak between requests.
        from flask import g
        g.pop("csrf_token", None)
    with app.app_context():
        db.create_all()
        seed_sample_content()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def make_user(email, role="student", password=PASSWORD, name="Test User", **kw):
    u = User(email=email, name=name, role=role, **kw)
    u.set_password(password)
    db.session.add(u)
    db.session.commit()
    return u


def csrf_from(html):
    m = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert m, "no csrf token in page"
    return m.group(1)


def post(client, url, data=None, page=None, follow=False):
    """POST with a valid CSRF token fetched from ``page`` (a GET url)."""
    html = client.get(page or url).get_data(as_text=True)
    if 'name="csrf_token"' not in html:  # tokens are per-session, any form page will do
        html = client.get("/contact").get_data(as_text=True)
    token = csrf_from(html)
    return client.post(url, data={**(data or {}), "csrf_token": token}, follow_redirects=follow)


def login(client, email, password=PASSWORD, admin=False):
    url = "/admin/login" if admin else "/login"
    return post(client, url, {"email": email, "password": password})


@pytest.fixture()
def student(app):
    return make_user("student@example.com")


@pytest.fixture()
def owner(app):
    return make_user("owner@example.com", role=ROLE_OWNER, name="Owner")
