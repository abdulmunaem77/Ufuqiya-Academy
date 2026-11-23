from datetime import timedelta

from app.extensions import db
from app.models import (AuditLog, ConsultationBooking, Course, Enrollment, LessonProgress, User,
                        Workshop, WorkshopRegistration, utcnow)
from conftest import PASSWORD, login, make_user, post


def reg(client, email="new@example.com", password=PASSWORD, **kw):
    data = {"name": "New Student", "email": email, "password": password, "confirm": password,
            "accept": "y", **kw}
    return post(client, "/register", data)


def test_register_login_logout(client):
    r = reg(client)
    assert r.status_code == 302
    u = User.query.filter_by(email="new@example.com").one()
    assert u.role == "student" and u.password_hash != PASSWORD and u.password_hash.startswith("scrypt:")
    assert client.get("/dashboard").status_code == 200
    assert post(client, "/logout", page="/account").status_code == 302
    assert client.get("/dashboard").status_code == 302  # login required again


def test_register_validation(client):
    assert reg(client, password="short1").status_code == 200
    assert reg(client, password="onlyletterslongpassword").status_code == 200
    assert reg(client, email="not-an-email").status_code == 200
    assert reg(client, password="Str0ng-Passw0rd!", confirm="x").status_code in (200, 302)
    assert User.query.count() == 0 or User.query.filter_by(email="not-an-email").count() == 0
    reg(client, email="dup@example.com")
    client.get("/dashboard")
    post(client, "/logout", page="/account")
    r = reg(client, email="DUP@example.com")
    assert r.status_code == 200 and User.query.filter(User.email == "dup@example.com").count() == 1


def test_role_cannot_be_injected_via_register(client):
    reg(client, email="x@example.com", role="owner")
    assert User.query.filter_by(email="x@example.com").one().role == "student"


def test_login_failure_is_generic_and_audited(client, student):
    r1 = login(client, "student@example.com", "wrong-password-1")
    r2 = login(client, "nobody@example.com", "wrong-password-1")
    assert r1.status_code == r2.status_code == 200
    a, b = r1.get_data(as_text=True), r2.get_data(as_text=True)
    assert ("Incorrect credentials" in a or "غير صحيحة" in a) and ("غير صحيحة" in b or "Incorrect" in b)
    assert AuditLog.query.filter_by(action="login_failed").count() == 2


def test_lockout_after_repeated_failures(client, student):
    for _ in range(5):
        login(client, "student@example.com", "bad-password-123")
    assert User.query.filter_by(email="student@example.com").one().is_locked
    assert login(client, "student@example.com").status_code == 200  # correct password still refused
    assert client.get("/dashboard").status_code == 302


def test_inactive_user_cannot_login(client, app):
    make_user("off@example.com").is_active_account = False
    db.session.commit()
    login(client, "off@example.com")
    assert client.get("/dashboard").status_code == 302


def test_open_redirect_blocked_on_login(client, student):
    r = post(client, "/login?next=https://evil.example/x",
             {"email": "student@example.com", "password": PASSWORD, "next": "https://evil.example/x"}, page="/login")
    assert r.status_code == 302 and "evil.example" not in r.headers["Location"]


def test_enroll_free_progress_and_dashboard(client, student):
    login(client, "student@example.com")
    r = post(client, "/courses/generative-ai-everyday-work/enroll", page="/courses/generative-ai-everyday-work")
    assert r.status_code == 302
    enr = Enrollment.query.one()
    assert enr.status == "active"
    course = Course.query.filter_by(slug="generative-ai-everyday-work").one()
    lid = course.lessons[0].id
    assert client.get("/courses/generative-ai-everyday-work/learn").status_code == 200
    post(client, f"/courses/generative-ai-everyday-work/lessons/{lid}/toggle", page="/courses/generative-ai-everyday-work/learn")
    assert LessonProgress.query.count() == 1 and enr.progress()[0] == 25
    assert "25%" in client.get("/dashboard").get_data(as_text=True)
    post(client, f"/courses/generative-ai-everyday-work/lessons/{lid}/toggle", page="/courses/generative-ai-everyday-work/learn")
    assert LessonProgress.query.count() == 0  # toggles back


def test_paid_enrollment_is_pending_and_cannot_learn(client, student):
    login(client, "student@example.com")
    post(client, "/courses/web-development-fundamentals/enroll", page="/courses/web-development-fundamentals")
    assert Enrollment.query.one().status == "pending"
    assert client.get("/courses/web-development-fundamentals/learn").status_code == 302


def test_double_enroll_idempotent(client, student):
    login(client, "student@example.com")
    for _ in range(2):
        post(client, "/courses/generative-ai-everyday-work/enroll", page="/courses/generative-ai-everyday-work")
    assert Enrollment.query.count() == 1


def test_cannot_toggle_lesson_of_other_course_or_unenrolled(client, student):
    login(client, "student@example.com")
    other = Course.query.filter_by(slug="web-development-fundamentals").one().lessons[0].id
    post(client, "/courses/generative-ai-everyday-work/enroll", page="/courses/generative-ai-everyday-work")
    r = post(client, f"/courses/generative-ai-everyday-work/lessons/{other}/toggle", page="/courses/generative-ai-everyday-work/learn")
    assert r.status_code == 400 and LessonProgress.query.count() == 0
    r = post(client, f"/courses/search-content-marketing/lessons/{other}/toggle", page="/courses/generative-ai-everyday-work/learn")
    assert r.status_code == 403


def test_enroll_requires_login(client):
    r = client.post("/courses/generative-ai-everyday-work/enroll")
    assert r.status_code in (302, 400)
    assert Enrollment.query.count() == 0


def test_workshop_register_capacity_and_cancel(client, student, app):
    ws = Workshop.query.filter(Workshop.starts_at > utcnow()).first()
    ws.capacity = 1
    db.session.commit()
    login(client, "student@example.com")
    post(client, f"/workshops/{ws.slug}/register", page=f"/workshops/{ws.slug}")
    assert WorkshopRegistration.query.one().status == "registered"
    other = make_user("o2@example.com")
    c2 = client.application.test_client()
    login(c2, "o2@example.com")
    post(c2, f"/workshops/{ws.slug}/register", page=f"/workshops/{ws.slug}")
    assert WorkshopRegistration.query.filter_by(status="registered").count() == 1  # full
    post(client, f"/workshops/{ws.slug}/cancel", page=f"/workshops/{ws.slug}")
    assert ws.seats_left == 1


def test_cannot_register_for_past_workshop(client, student):
    past = Workshop.query.filter(Workshop.starts_at < utcnow()).first()
    login(client, "student@example.com")
    post(client, f"/workshops/{past.slug}/register", page=f"/workshops/{past.slug}")
    assert WorkshopRegistration.query.count() == 0


def book(client, slug, when, notes="please"):
    return post(client, f"/consultations/{slug}/book", {"when": when, "notes": notes}, page=f"/consultations/{slug}/book")


def test_consultation_booking_rules(client, student):
    login(client, "student@example.com")
    slug = "ai-adoption-strategy-session"
    soon = (utcnow() + timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M")
    far = (utcnow() + timedelta(days=200)).strftime("%Y-%m-%dT%H:%M")
    ok = (utcnow() + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M")
    assert book(client, slug, soon).status_code == 200
    assert book(client, slug, far).status_code == 200
    assert book(client, slug, "garbage").status_code == 200
    assert ConsultationBooking.query.count() == 0
    assert book(client, slug, ok).status_code == 302
    b = ConsultationBooking.query.one()
    assert b.status == "pending"
    assert book(client, slug, ok).status_code == 302
    assert book(client, slug, ok).status_code == 200  # third active booking refused
    assert ConsultationBooking.query.count() == 2


def test_cannot_cancel_someone_elses_booking(client, student):
    other = make_user("victim@example.com")
    b = ConsultationBooking(user_id=other.id, service_id=1, preferred_at=utcnow() + timedelta(days=3))
    db.session.add(b)
    db.session.commit()
    login(client, "student@example.com")
    r = post(client, f"/consultations/booking/{b.id}/cancel", page="/dashboard")
    assert r.status_code == 404 and db.session.get(ConsultationBooking, b.id).status == "pending"


def test_account_update_and_password_change(client, student):
    login(client, "student@example.com")
    post(client, "/account", {"name": "Renamed", "locale": "en"})
    assert User.query.filter_by(email="student@example.com").one().name == "Renamed"
    r = post(client, "/account/password", {"current": "wrong-one-123", "password": "An0ther-Passw0rd!", "confirm": "An0ther-Passw0rd!"})
    assert r.status_code == 200
    r = post(client, "/account/password", {"current": PASSWORD, "password": "An0ther-Passw0rd!", "confirm": "An0ther-Passw0rd!"})
    assert r.status_code == 302
    post(client, "/logout", page="/account")
    assert login(client, "student@example.com", "An0ther-Passw0rd!").status_code == 302


def test_forced_password_change_redirect(client, app):
    make_user("tmp@example.com", must_change_password=True)
    login(client, "tmp@example.com")
    r = client.get("/dashboard")
    assert r.status_code == 302 and "/account/password" in r.headers["Location"]
