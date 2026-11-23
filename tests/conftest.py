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
    token = csrf_from(client.get(page or url).get_data(as_text=True))
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
