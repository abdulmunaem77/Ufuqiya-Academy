import re
import time

import pytest

from app import totp
from app.extensions import db
from app.media import embed_url
from app.models import (AuditLog, Certificate, ConsultationBooking, Course, EmailOutbox, Enrollment,
                        Lesson, LessonProgress, Payment, User, Workshop, WorkshopRegistration, utcnow)
from conftest import PASSWORD, csrf_from, login, make_user, post
from config import TestConfig
from app import create_app


def _reset_g():
    from flask import g
    g.pop("csrf_token", None)
    g.pop("_login_user", None)


# ------------------------------------------------------------------ payments
def test_paid_course_manual_payment_flow(app, client, student):
    login(client, "student@example.com")
    r = post(client, "/courses/web-development-fundamentals/enroll", page="/courses/web-development-fundamentals")
    pay = Payment.query.one()
    assert r.status_code == 302 and f"/payments/{pay.id}" in r.headers["Location"]
    assert pay.status == "awaiting" and float(pay.amount) == 90 and pay.kind == "course"
    enr = Enrollment.query.one()
    assert enr.status == "pending"
    assert client.get("/courses/web-development-fundamentals/learn").status_code == 302  # still locked
    # student submits reference
    assert post(client, f"/payments/{pay.id}", {"method": "bank_transfer", "reference": "TRX-123456", "note": ""}).status_code == 302
    assert db.session.get(Payment, pay.id).status == "submitted"
    # staff confirms
    make_user("sup@example.com", role="support")
    staff = app.test_client(); login(staff, "sup@example.com", admin=True)
    assert "TRX-123456" in staff.get("/admin/payments").get_data(as_text=True)
    assert post(staff, f"/admin/payments/{pay.id}/confirm", page="/admin/payments").status_code == 302
    assert db.session.get(Payment, pay.id).status == "confirmed" and db.session.get(Enrollment, enr.id).status == "active"
    assert client.get("/courses/web-development-fundamentals/learn").status_code == 200
    assert any(a.action == "payment_confirm" for a in AuditLog.query.all())
    assert EmailOutbox.query.filter_by(kind="payment_confirm").count() == 1
    # a decided payment cannot be flipped
    post(staff, f"/admin/payments/{pay.id}/reject", page="/admin/payments")
    assert db.session.get(Payment, pay.id).status == "confirmed"


def test_payment_reject_then_resubmit(app, client, student):
    login(client, "student@example.com")
    post(client, "/courses/web-development-fundamentals/enroll", page="/courses/web-development-fundamentals")
    pay = Payment.query.one()
    post(client, f"/payments/{pay.id}", {"method": "cash", "reference": "ABC-111", "note": ""})
    make_user("adm@example.com", role="admin")
    staff = app.test_client(); login(staff, "adm@example.com", admin=True)
    post(staff, f"/admin/payments/{pay.id}/reject", page="/admin/payments")
    assert db.session.get(Payment, pay.id).status == "rejected"
    assert db.session.get(Enrollment, 1).status == "pending"
    post(client, f"/payments/{pay.id}", {"method": "cash", "reference": "ABC-222", "note": ""})
    assert db.session.get(Payment, pay.id).status == "submitted"


def test_cannot_view_or_pay_someone_elses_payment(app, client, student):
    other = make_user("o@example.com")
    p = Payment(user_id=other.id, kind="course", target_id=1, title="x", amount=10)
    db.session.add(p); db.session.commit()
    login(client, "student@example.com")
    assert client.get(f"/payments/{p.id}").status_code == 404
    assert post(client, f"/payments/{p.id}", {"method": "cash", "reference": "hack-123"}, page="/account").status_code == 404
    assert db.session.get(Payment, p.id).status == "awaiting"


def test_student_cannot_confirm_payment(app, client, student):
    p = Payment(user_id=student.id, kind="course", target_id=1, title="x", amount=10)
    db.session.add(p); db.session.commit()
    login(client, "student@example.com")
    assert post(client, f"/admin/payments/{p.id}/confirm", page="/account").status_code == 403
    assert db.session.get(Payment, p.id).status == "awaiting"


def test_editor_cannot_see_payments_but_support_can(app):
    make_user("ed@example.com", role="editor"); make_user("su@example.com", role="support")
    e = app.test_client(); login(e, "ed@example.com", admin=True)
    s = app.test_client(); login(s, "su@example.com", admin=True)
    assert e.get("/admin/payments").status_code == 403 and s.get("/admin/payments").status_code == 200
    assert s.get("/admin/outbox").status_code == 403  # outbox is owner-only


def test_paid_workshop_holds_seat_until_confirmed(app, client, student):
    ws = Workshop.query.filter(Workshop.starts_at > utcnow(), Workshop.price > 0).first()
    login(client, "student@example.com")
    r = post(client, f"/workshops/{ws.slug}/register", page=f"/workshops/{ws.slug}")
    reg = WorkshopRegistration.query.one()
    assert reg.status == "pending" and "/payments/" in r.headers["Location"] and ws.seats_taken == 1
    pay = Payment.query.one()
    make_user("o@example.com", role="owner")
    staff = app.test_client(); login(staff, "o@example.com", admin=True)
    post(staff, f"/admin/payments/{pay.id}/confirm", page="/admin/payments")
    assert db.session.get(WorkshopRegistration, reg.id).status == "registered"


def test_paid_consultation_creates_payment_and_cancel_closes_it(app, client, student):
    from datetime import timedelta
    login(client, "student@example.com")
    when = (utcnow() + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M")
    r = post(client, "/consultations/ai-adoption-strategy-session/book", {"when": when, "notes": ""}, page="/consultations/ai-adoption-strategy-session/book")
    assert "/payments/" in r.headers["Location"]
    b = ConsultationBooking.query.one()
    post(client, f"/consultations/booking/{b.id}/cancel", page="/dashboard")
    assert Payment.query.one().status == "cancelled"


def test_free_items_create_no_payment(client, student):
    login(client, "student@example.com")
    post(client, "/courses/generative-ai-everyday-work/enroll", page="/courses/generative-ai-everyday-work")
    assert Payment.query.count() == 0


# ---------------------------------------------------- e-mail verify / reset
def outbox_link(kind, pattern):
    row = EmailOutbox.query.filter_by(kind=kind).order_by(EmailOutbox.id.desc()).first()
    assert row, kind
    return re.search(pattern, row.body).group(0)


def test_registration_records_verification_mail_and_link_verifies(client, app):
    post(client, "/register", {"name": "Nora", "email": "n@example.com", "password": PASSWORD, "confirm": PASSWORD, "accept": "y"})
    u = User.query.filter_by(email="n@example.com").one()
    assert not u.email_verified
    row = EmailOutbox.query.filter_by(kind="verify").one()
    assert row.status == "not_configured" and row.to_email == "n@example.com"
    link = re.search(r"http://localhost/verify-email/\S+", row.body).group(0)
    assert client.get(link.replace("http://localhost", "")).status_code == 302
    assert db.session.get(User, u.id).email_verified
    assert client.get("/verify-email/garbage").status_code == 302  # no crash, no verification


class MailRequired(TestConfig):
    REQUIRE_EMAIL_VERIFICATION = True


def test_unverified_user_blocked_when_verification_required():
    app = create_app(MailRequired)
    with app.app_context():
        db.create_all()
        from app.seed import seed_sample_content
        seed_sample_content()
        make_user("u@example.com")
        c = app.test_client()
        c.application.before_request_funcs.setdefault(None, []).insert(0, _reset_g)
        login(c, "u@example.com")
        post(c, "/courses/generative-ai-everyday-work/enroll", page="/courses/generative-ai-everyday-work")
        assert Enrollment.query.count() == 0
        db.session.get(User, 1).email_verified = True
        db.session.commit()
        post(c, "/courses/generative-ai-everyday-work/enroll", page="/courses/generative-ai-everyday-work")
        assert Enrollment.query.count() == 1
        db.session.remove(); db.drop_all()


def test_password_reset_flow_single_use_and_no_enumeration(app, client, student):
    r1 = post(client, "/forgot-password", {"email": "student@example.com"})
    r2 = post(client, "/forgot-password", {"email": "ghost@example.com"})
    assert r1.status_code == r2.status_code == 302 and r1.headers["Location"] == r2.headers["Location"]
    assert EmailOutbox.query.filter_by(kind="reset").count() == 1  # nothing for the unknown address
    link = outbox_link("reset", r"/reset-password/\S+")
    new = "Brand-New-Passw0rd!"
    assert client.get(link).status_code == 200
    assert post(client, link, {"password": new, "confirm": new}, page=link).status_code == 302
    assert login(client, "student@example.com", new).status_code == 302
    post(client, "/logout", page="/account")
    # same link cannot be reused, and tampered links fail
    assert client.get(link).status_code == 302
    assert client.get(link[:-3] + "xyz").status_code == 302
    assert not User.query.filter_by(email="student@example.com").one().check_password(PASSWORD)


def test_crlf_header_injection_in_mail_fields(app):
    from app.mailer import send_mail
    row = send_mail("a@b.co\r\nBcc: evil@x.co", "Hi\r\nBcc: evil@x.co", "body", "test")
    assert "\n" not in row.to_email and "\r" not in row.subject


# --------------------------------------------------------------------- 2FA
def enroll_2fa(client):
    post(client, "/account/2fa", {"action": "start"}, page="/account/2fa")
    with client.session_transaction() as s:
        secret = s["totp_setup"]
    code = totp._code(secret, int(time.time() // 30))
    r = post(client, "/account/2fa", {"action": "enable", "en-code": code}, page="/account/2fa")
    return secret, r


def test_totp_rfc_vector_and_replay():
    import base64
    sec = base64.b32encode(b"12345678901234567890").decode().rstrip("=")
    assert totp.verify(sec, "287082", 0, now=59) == 1
    assert totp.verify(sec, "287082", 1, now=59) is None  # same step cannot be reused
    assert totp.verify(sec, "000000", 0, now=59) is None and totp.verify(sec, "abc", 0, now=59) is None


def test_2fa_setup_login_backup_and_replay(app, student):
    c = app.test_client(); login(c, "student@example.com")
    secret, r = enroll_2fa(c)
    html = r.get_data(as_text=True)
    codes = re.findall(r"<code dir=\"ltr\">([a-z0-9]{10})</code>", html)
    assert len(codes) == 8 and User.query.filter_by(email="student@example.com").one().totp_enabled
    assert all(cd not in (User.query.first().backup_codes or "") for cd in codes)  # only digests stored
    post(c, "/logout", page="/account")
    # password alone no longer logs in
    r = login(c, "student@example.com")
    assert r.status_code == 302 and "/login/2fa" in r.headers["Location"]
    assert c.get("/dashboard").status_code == 302
    # wrong code
    assert post(c, "/login/2fa", {"code": "123456"}, page="/login/2fa").status_code == 200
    # replaying the code used at enrolment is refused
    now_code = totp._code(secret, int(time.time() // 30))
    assert post(c, "/login/2fa", {"code": now_code}, page="/login/2fa").status_code == 200
    # a fresh step works
    nxt = totp._code(secret, int(time.time() // 30) + 1)
    assert post(c, "/login/2fa", {"code": nxt}, page="/login/2fa").status_code == 302
    assert c.get("/dashboard").status_code == 200
    post(c, "/logout", page="/account")
    # backup code works once
    login(c, "student@example.com")
    assert post(c, "/login/2fa", {"code": codes[0]}, page="/login/2fa").status_code == 302
    post(c, "/logout", page="/account")
    login(c, "student@example.com")
    assert post(c, "/login/2fa", {"code": codes[0]}, page="/login/2fa").status_code == 200


def test_2fa_attempts_limited(app, student):
    c = app.test_client(); login(c, "student@example.com")
    enroll_2fa(c); post(c, "/logout", page="/account")
    login(c, "student@example.com")
    for _ in range(5):
        post(c, "/login/2fa", {"code": "000000"}, page="/login/2fa")
    with c.session_transaction() as s:
        assert "pending_2fa" not in s
    assert c.get("/dashboard").status_code == 302


def test_2fa_pending_step_expires(app, student):
    c = app.test_client(); login(c, "student@example.com")
    enroll_2fa(c); post(c, "/logout", page="/account"); login(c, "student@example.com")
    with c.session_transaction() as s:
        pend = dict(s["pending_2fa"]); pend["ts"] -= 1000; s["pending_2fa"] = pend
    assert c.get("/login/2fa").status_code == 302
    assert c.get("/login/2fa").headers["Location"].endswith("/login")


def test_2fa_direct_access_without_password_step(client):
    assert client.get("/login/2fa").status_code == 302


def test_disable_2fa_needs_password_and_code(app, student):
    c = app.test_client(); login(c, "student@example.com")
    secret, _ = enroll_2fa(c)
    code = totp._code(secret, int(time.time() // 30) + 1)
    assert post(c, "/account/2fa", {"action": "disable", "dis-password": "bad-bad-bad1", "dis-code": code}, page="/account/2fa").status_code == 200
    assert User.query.first().totp_enabled
    assert post(c, "/account/2fa", {"action": "disable", "dis-password": PASSWORD, "dis-code": code}, page="/account/2fa").status_code == 302
    assert not User.query.first().totp_enabled


class Staff2FA(TestConfig):
    REQUIRE_STAFF_2FA = True


def test_staff_forced_to_enrol_2fa_and_cannot_disable():
    app = create_app(Staff2FA)
    with app.app_context():
        db.create_all()
        make_user("boss@example.com", role="owner")
        c = app.test_client()
        c.application.before_request_funcs.setdefault(None, []).insert(0, _reset_g)
        login(c, "boss@example.com", admin=True)
        for url in ("/admin/", "/admin/users", "/admin/audit"):
            r = c.get(url)
            assert r.status_code == 302 and "/account/2fa" in r.headers["Location"], url
        assert c.get("/account/2fa").status_code == 200
        enroll_2fa(c)
        assert c.get("/admin/").status_code == 200
        code = totp._code(User.query.first().totp_secret, int(time.time() // 30) + 1)
        assert post(c, "/account/2fa", {"action": "disable", "dis-password": PASSWORD, "dis-code": code}, page="/account/2fa").status_code == 403
        db.session.remove(); db.drop_all()


def test_admin_login_with_2fa_goes_to_admin(app, owner):
    c = app.test_client(); login(c, "owner@example.com", admin=True)
    secret, _ = enroll_2fa(c); post(c, "/logout", page="/account")
    r = login(c, "owner@example.com", admin=True)
    assert "/login/2fa" in r.headers["Location"]
    code = totp._code(secret, int(time.time() // 30) + 1)
    r = post(c, "/login/2fa", {"code": code}, page="/login/2fa")
    assert r.status_code == 302 and "/admin" in r.headers["Location"]


# ------------------------------------------------------------ certificates
def complete_course(client, user, slug="generative-ai-everyday-work"):
    post(client, f"/courses/{slug}/enroll", page=f"/courses/{slug}")
    course = Course.query.filter_by(slug=slug).one()
    for l in course.lessons:
        db.session.add(LessonProgress(user_id=user.id, lesson_id=l.id))
    db.session.commit()
    return course


def test_certificate_requires_completion_and_is_verifiable(app, client, student):
    login(client, "student@example.com")
    post(client, "/courses/generative-ai-everyday-work/enroll", page="/courses/generative-ai-everyday-work")
    r = client.get("/courses/generative-ai-everyday-work/certificate")
    assert r.status_code == 302 and Certificate.query.count() == 0
    complete_course(client, student)
    r = client.get("/courses/generative-ai-everyday-work/certificate")
    assert r.status_code == 200 and Certificate.query.count() == 1
    cert = Certificate.query.one()
    assert cert.code.startswith("UF-") and cert.holder_name in r.get_data(as_text=True)
    assert "تجريبي" in r.get_data(as_text=True) or "not an accredited" in r.get_data(as_text=True)  # sample course is labelled
    client.get("/courses/generative-ai-everyday-work/certificate")
    assert Certificate.query.count() == 1  # idempotent
    anon = app.test_client()
    assert anon.get(f"/verify/{cert.code}").status_code == 200
    assert anon.get(f"/verify/{cert.code.lower()}").status_code == 200
    assert anon.get("/verify/UF-DOESNOTEXIST").status_code == 404


def test_certificate_not_for_unenrolled_or_pending(client, student):
    login(client, "student@example.com")
    assert client.get("/courses/generative-ai-everyday-work/certificate").status_code == 403


# ------------------------------------------------------------------- video
@pytest.mark.parametrize("url,ok", [
    ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", True), ("https://youtu.be/dQw4w9WgXcQ", True),
    ("https://vimeo.com/123456789", True), ("https://www.youtube.com/embed/dQw4w9WgXcQ", True),
    ("http://youtube.com/watch?v=dQw4w9WgXcQ", False), ("https://evil.example/watch?v=dQw4w9WgXcQ", False),
    ("javascript:alert(1)", False), ("https://youtube.com.evil.co/watch?v=dQw4w9WgXcQ", False),
    ("https://www.youtube.com/watch?v=\"><script>", False), ("", False)])
def test_embed_url_allowlist(url, ok):
    assert bool(embed_url(url)) == ok
    if ok:
        assert embed_url(url).startswith(("https://www.youtube-nocookie.com/embed/", "https://player.vimeo.com/video/"))


def test_lesson_video_renders_and_bad_url_rejected(app, owner, student):
    c = app.test_client(); login(c, "owner@example.com", admin=True)
    les = Lesson.query.first()
    base = {"position": 1, "title_ar": "ت", "title_en": "T", "body_ar": "", "body_en": "", "minutes": 5}
    assert post(c, f"/admin/lessons/{les.id}/edit", {**base, "video_url": "https://evil.example/x"}, page=f"/admin/lessons/{les.id}/edit").status_code == 200
    assert post(c, f"/admin/lessons/{les.id}/edit", {**base, "video_url": "https://youtu.be/dQw4w9WgXcQ"}, page=f"/admin/lessons/{les.id}/edit").status_code == 302
    s = app.test_client(); login(s, "student@example.com")
    slug = les.course.slug
    post(s, f"/courses/{slug}/enroll", page=f"/courses/{slug}")
    r = s.get(f"/courses/{slug}/learn?lesson={les.id}")
    html = r.get_data(as_text=True)
    assert 'src="https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ"' in html
    assert "youtube-nocookie.com" in r.headers["Content-Security-Policy"] and "frame-src" in r.headers["Content-Security-Policy"]


# --------------------------------------------------------------- misc
def test_outbox_owner_only_view(app, owner):
    post(app.test_client(), "/forgot-password", {"email": "owner@example.com"})
    c = app.test_client(); login(c, "owner@example.com", admin=True)
    assert "reset" in c.get("/admin/outbox").get_data(as_text=True)


def test_db_url_normalisation(monkeypatch):
    import importlib, config
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@host:5432/db")
    assert config._db_url() == "postgresql+psycopg://u:p@host:5432/db"
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host/db")
    assert config._db_url().startswith("postgresql+psycopg://")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///x.db")
    assert config._db_url() == "sqlite:///x.db"


# ---------------------------------------------------------------- backup / restore
def test_sqlite_backup_restore_roundtrip(tmp_path):
    from app.backup import backup, restore, kind
    from app.extensions import db as _db
    import sqlite3
    dbfile = tmp_path / "live.db"
    uri = f"sqlite:///{dbfile}"
    con = sqlite3.connect(dbfile); con.execute("create table t(x text)"); con.execute("insert into t values('before')"); con.commit(); con.close()
    assert kind(uri) == "sqlite"
    b = backup(uri, tmp_path / "bk")
    assert b.suffix == ".sqlite3" and (b.stat().st_mode & 0o777) == 0o600
    con = sqlite3.connect(dbfile); con.execute("update t set x='after'"); con.execute("insert into t values('extra')"); con.commit(); con.close()
    safety = restore(uri, b, tmp_path / "safe")
    rows = sqlite3.connect(dbfile).execute("select x from t").fetchall()
    assert rows == [("before",)]
    assert safety and sqlite3.connect(safety).execute("select count(*) from t").fetchone() == (2,)  # nothing lost
    # pruning keeps the newest N
    for _ in range(3):
        backup(uri, tmp_path / "keep", keep=2)
        time.sleep(1.1)
    assert len(list((tmp_path / "keep").glob("*.sqlite3"))) == 2


def test_restore_rejects_wrong_or_corrupt_files(tmp_path):
    from app.backup import restore, BackupError
    uri = f"sqlite:///{tmp_path/'x.db'}"
    bad = tmp_path / "junk.sqlite3"; bad.write_bytes(b"not a database")
    with pytest.raises(Exception):
        restore(uri, bad, tmp_path / "s")
    wrong = tmp_path / "x.pgdump"; wrong.write_bytes(b"PGDMP")
    with pytest.raises(BackupError):
        restore(uri, wrong, tmp_path / "s")
    with pytest.raises(BackupError):
        restore(uri, tmp_path / "missing.sqlite3", tmp_path / "s")


def test_restore_cli_requires_confirmation(app, tmp_path):
    runner = app.test_cli_runner()
    f = tmp_path / "a.sqlite3"; f.write_bytes(b"x")
    r = runner.invoke(args=["restore-db", str(f)])
    assert r.exit_code != 0 and "--yes" in r.output


# --------------------------------------------------------------- reviews / notifications
def test_reviews_only_for_active_enrolees_and_average(app, client, student):
    from app.models import Review
    slug = "generative-ai-everyday-work"
    login(client, "student@example.com")
    assert post(client, f"/courses/{slug}/review", {"rating": "5", "comment": "x"}, page=f"/courses/{slug}").status_code == 403
    post(client, f"/courses/{slug}/enroll", page=f"/courses/{slug}")
    assert post(client, f"/courses/{slug}/review", {"rating": "9", "comment": ""}, page="/account").status_code == 302
    assert Review.query.count() == 0  # out-of-range rejected by the form
    post(client, f"/courses/{slug}/review", {"rating": "4", "comment": "Good <b>course</b>"}, page="/account")
    post(client, f"/courses/{slug}/review", {"rating": "5", "comment": "Updated"}, page="/account")
    assert Review.query.count() == 1 and Review.query.one().rating == 5  # one per user: updated in place
    course = Course.query.filter_by(slug=slug).one()
    assert course.rating_summary() == (5.0, 1)
    other = make_user("r2@example.com"); c2 = app.test_client(); login(c2, "r2@example.com")
    post(c2, f"/courses/{slug}/enroll", page=f"/courses/{slug}")
    post(c2, f"/courses/{slug}/review", {"rating": "4", "comment": "<script>alert(1)</script>"}, page="/account")
    assert course.rating_summary() == (4.5, 2)
    html = app.test_client().get(f"/courses/{slug}").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in html and "Updated" in html


def test_review_moderation_hides_from_public_and_average(app, client, student, owner):
    from app.models import Review
    slug = "generative-ai-everyday-work"
    login(client, "student@example.com")
    post(client, f"/courses/{slug}/enroll", page=f"/courses/{slug}")
    post(client, f"/courses/{slug}/review", {"rating": "1", "comment": "spammy"}, page="/account")
    rid = Review.query.one().id
    adm = app.test_client(); login(adm, "owner@example.com", admin=True)
    assert adm.get("/admin/reviews").status_code == 200
    post(adm, f"/admin/reviews/{rid}/toggle", page="/admin/reviews")
    assert "spammy" not in app.test_client().get(f"/courses/{slug}").get_data(as_text=True)
    assert Course.query.filter_by(slug=slug).one().rating_summary() == (0.0, 0)
    assert post(client, f"/admin/reviews/{rid}/delete", page="/account").status_code == 403  # students cannot moderate
    post(adm, f"/admin/reviews/{rid}/delete", page="/admin/reviews")
    assert Review.query.count() == 0


def test_db_rejects_invalid_rows_even_if_app_is_bypassed(app, student):
    from sqlalchemy.exc import IntegrityError
    from app.models import Review
    db.session.add(Review(user_id=student.id, course_id=1, rating=9)); 
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()
    db.session.add(Payment(user_id=student.id, kind="course", target_id=1, amount=-5))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()
    c = Course.query.first(); c.price = -1
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()
    u = User(email="bad@example.com", name="Bad", role="superuser", password_hash="x")
    db.session.add(u)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_notifications_flow_and_ownership(app, client, student):
    from app.models import Notification
    p = Payment(user_id=student.id, kind="course", target_id=1, title="X Course", amount=10, status="submitted")
    db.session.add(p); db.session.commit()
    own = make_user("own@example.com", role="owner"); adm = app.test_client(); login(adm, "own@example.com", admin=True)
    post(adm, f"/admin/payments/{p.id}/confirm", page="/admin/payments")
    n = Notification.query.filter_by(user_id=student.id, kind="payment").one()
    assert not n.is_read
    login(client, "student@example.com")
    html = client.get("/notifications").get_data(as_text=True)
    assert "X Course" in html and 'class="bell__n"' in client.get("/dashboard").get_data(as_text=True)
    other = make_user("snoop@example.com"); c2 = app.test_client(); login(c2, "snoop@example.com")
    assert post(c2, f"/notifications/{n.id}/open", page="/account").status_code == 404  # not yours
    r = post(client, f"/notifications/{n.id}/open", page="/account")
    assert r.status_code == 302 and db.session.get(Notification, n.id).is_read
    assert 'class="bell__n"' not in client.get("/dashboard").get_data(as_text=True)


def test_new_brand_everywhere(client):
    for lang, name in (("ar", "أكاديمية وهج للتدريب والاستشارات الرقمية"), ("en", "WAHJ Academy")):
        client.get(f"/lang/{lang}")
        for url in ("/", "/about", "/courses/", "/login", "/contact"):
            html = client.get(url).get_data(as_text=True)
            assert name in html, (lang, url)
            assert "أفقيا" not in html and "Ufuqia" not in html and "ufuqia" not in html.lower().replace("ufuqiya-academy", ""), (lang, url)
    assert "من شغف التعلم إلى التميز" in client.get("/lang/ar", follow_redirects=True).get_data(as_text=True)
