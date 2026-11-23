import pytest

from app.extensions import db
from app.models import (AuditLog, Category, ConsultationBooking, ContactMessage, Course,
                        Enrollment, Instructor, SiteContent, User, Workshop, utcnow)
from conftest import PASSWORD, login, make_user, post

ADMIN_URLS = ["/admin/", "/admin/e/courses/", "/admin/e/workshops/", "/admin/e/services/", "/admin/e/instructors/",
              "/admin/e/categories/", "/admin/e/testimonials/", "/admin/bookings", "/admin/enrollments",
              "/admin/students", "/admin/content", "/admin/messages", "/admin/users", "/admin/audit",
              "/admin/e/courses/new", "/admin/users/new", "/admin/courses/1/lessons", "/admin/workshops/1/registrations"]


def staff_client(app, role, email=None):
    email = email or f"{role}@example.com"
    make_user(email, role=role)
    c = app.test_client()
    assert login(c, email, admin=True).status_code == 302
    return c


@pytest.mark.parametrize("lang", ["ar", "en"])
def test_owner_sees_every_admin_page(app, owner, lang):
    c = app.test_client()
    login(c, "owner@example.com", admin=True)
    c.get(f"/lang/{lang}")
    for url in ADMIN_URLS:
        assert c.get(url).status_code == 200, url


def test_anonymous_redirected_everywhere(client):
    for url in ADMIN_URLS:
        r = client.get(url)
        assert r.status_code == 302 and "/admin/login" in r.headers["Location"], url


def test_student_forbidden_everywhere(client, student):
    login(client, "student@example.com")
    for url in ADMIN_URLS:
        assert client.get(url).status_code == 403, url
    assert AuditLog.query.filter_by(action="access_denied").count() >= len(ADMIN_URLS)


def test_student_cannot_use_admin_login(client, student):
    login(client, "student@example.com", admin=True)
    assert client.get("/admin/").status_code in (302, 403)
    assert client.get("/dashboard").status_code == 302  # not even logged in


def test_admin_post_requires_csrf(app, owner):
    c = app.test_client()
    login(c, "owner@example.com", admin=True)
    n = Course.query.count()
    assert c.post("/admin/e/courses/1/delete").status_code == 400
    assert c.post("/admin/e/courses/1/delete", data={"csrf_token": "forged"}).status_code == 400
    assert Course.query.count() == n


RBAC = {  # role -> {url: expected status}
    "editor": {"/admin/e/courses/": 200, "/admin/e/workshops/": 200, "/admin/content": 200, "/admin/users": 403,
               "/admin/audit": 403, "/admin/students": 403, "/admin/messages": 403, "/admin/bookings": 403,
               "/admin/e/services/": 403},
    "support": {"/admin/students": 200, "/admin/messages": 200, "/admin/bookings": 200, "/admin/enrollments": 200,
                "/admin/e/courses/": 403, "/admin/content": 403, "/admin/users": 403, "/admin/audit": 403,
                "/admin/e/workshops/new": 403},
    "admin": {"/admin/e/courses/": 200, "/admin/students": 200, "/admin/users": 403, "/admin/audit": 403},
}


@pytest.mark.parametrize("role", RBAC)
def test_role_based_permissions(app, role):
    c = staff_client(app, role)
    for url, code in RBAC[role].items():
        assert c.get(url).status_code == code, (role, url)


def test_rbac_applies_to_mutations_too(app):
    c = staff_client(app, "support")
    n = Course.query.count()
    assert post(c, "/admin/e/courses/1/delete", page="/admin/messages").status_code == 403
    assert post(c, "/admin/users/1/toggle", page="/admin/messages").status_code == 403
    assert Course.query.count() == n


def test_course_crud_with_audit(app, owner):
    c = app.test_client()
    login(c, "owner@example.com", admin=True)
    data = {"slug": "", "category_id": Category.query.first().id, "instructor_id": Instructor.query.first().id,
            "title_ar": "دورة اختبار", "title_en": "Test Course!", "summary_ar": "ملخص", "summary_en": "Sum",
            "description_ar": "وصف", "description_en": "Desc", "level": "beginner", "price": "12.50",
            "duration_hours": "3", "is_published": "y"}
    r = post(c, "/admin/e/courses/new", data, page="/admin/e/courses/new")
    assert r.status_code == 302
    course = Course.query.filter_by(title_en="Test Course!").one()
    assert course.slug == "test-course" and float(course.price) == 12.5 and course.is_published
    data["title_en"] = "Renamed"
    assert post(c, f"/admin/e/courses/{course.id}/edit", data, page=f"/admin/e/courses/{course.id}/edit").status_code == 302
    assert db.session.get(Course, course.id).title_en == "Renamed" and db.session.get(Course, course.id).slug == "test-course"
    # same title again -> unique slug
    data["title_en"] = "Test Course!"
    post(c, "/admin/e/courses/new", data, page="/admin/e/courses/new")
    assert Course.query.filter_by(slug="test-course-2").count() == 1
    assert post(c, f"/admin/e/courses/{course.id}/delete", page="/admin/e/courses/").status_code == 302
    assert db.session.get(Course, course.id) is None
    actions = {a.action for a in AuditLog.query.all()}
    assert {"courses_create", "courses_update", "courses_delete", "login_success"} <= actions


def test_course_validation_rejects_bad_input(app, owner):
    c = app.test_client()
    login(c, "owner@example.com", admin=True)
    bad = {"slug": "Bad Slug!", "category_id": 1, "instructor_id": 1, "title_ar": "", "title_en": "x" * 500,
           "summary_ar": "s", "summary_en": "s", "description_ar": "d", "description_en": "d", "level": "hacker",
           "price": "-5", "duration_hours": "0"}
    n = Course.query.count()
    assert post(c, "/admin/e/courses/new", bad, page="/admin/e/courses/new").status_code == 200
    assert Course.query.count() == n


def test_cannot_delete_course_with_enrollments(app, owner, student):
    db.session.add(Enrollment(user_id=student.id, course_id=1, status="active"))
    db.session.commit()
    c = app.test_client()
    login(c, "owner@example.com", admin=True)
    post(c, "/admin/e/courses/1/delete", page="/admin/e/courses/")
    assert db.session.get(Course, 1) is not None


def test_cannot_delete_category_in_use(app, owner):
    c = app.test_client()
    login(c, "owner@example.com", admin=True)
    post(c, "/admin/e/categories/1/delete", page="/admin/e/categories/")
    assert db.session.get(Category, 1) is not None


def test_unknown_entity_404(app, owner):
    c = app.test_client()
    login(c, "owner@example.com", admin=True)
    assert c.get("/admin/e/users/").status_code == 404  # whitelist, no arbitrary model access
    assert c.get("/admin/e/audit_logs/").status_code == 404


def test_workshop_time_zone_roundtrip(app, owner):
    c = app.test_client()
    login(c, "owner@example.com", admin=True)
    data = {"slug": "tz-test", "instructor_id": 1, "title_ar": "ت", "title_en": "TZ", "summary_ar": "s", "summary_en": "s",
            "description_ar": "d", "description_en": "d", "starts_at": "2030-01-10T18:00", "duration_minutes": "60",
            "capacity": "10", "price": "0", "is_published": "y"}
    post(c, "/admin/e/workshops/new", data, page="/admin/e/workshops/new")
    w = Workshop.query.filter_by(slug="tz-test").one()
    assert w.starts_at.hour == 15  # 18:00 academy time (UTC+3) stored as 15:00 UTC
    assert 'value="2030-01-10T18:00"' in c.get(f"/admin/e/workshops/{w.id}/edit").get_data(as_text=True)


def test_status_changes_and_validation(app, owner, student):
    from datetime import timedelta
    b = ConsultationBooking(user_id=student.id, service_id=1, preferred_at=utcnow() + timedelta(days=3))
    e = Enrollment(user_id=student.id, course_id=2, status="pending")
    m = ContactMessage(name="n", email="e@example.com", message="hello hello")
    db.session.add_all([b, e, m]); db.session.commit()
    c = app.test_client()
    login(c, "owner@example.com", admin=True)
    post(c, f"/admin/bookings/{b.id}/status", {"status": "confirmed"}, page="/admin/bookings")
    post(c, f"/admin/enrollments/{e.id}/status", {"status": "active"}, page="/admin/enrollments")
    post(c, f"/admin/messages/{m.id}/status", {"status": "resolved"}, page="/admin/messages")
    assert (b.status, e.status, m.status) == ("confirmed", "active", "resolved")
    assert post(c, f"/admin/bookings/{b.id}/status", {"status": "<script>"}, page="/admin/bookings").status_code == 400
    assert b.status == "confirmed"


def test_content_editing_shows_on_site(app, owner):
    c = app.test_client()
    login(c, "owner@example.com", admin=True)
    post(c, "/admin/content/hero_title", {"value_ar": "عنوان جديد", "value_en": "Brand new headline"}, page="/admin/content/hero_title")
    assert db.session.get(SiteContent, "hero_title").value_en == "Brand new headline"
    pub = app.test_client()
    pub.get("/lang/en")
    assert "Brand new headline" in pub.get("/").get_data(as_text=True)
    assert c.get("/admin/content/not_a_key").status_code == 404


def test_content_is_escaped(app, owner):
    c = app.test_client()
    login(c, "owner@example.com", admin=True)
    post(c, "/admin/content/hero_title", {"value_ar": "x", "value_en": "<script>alert(1)</script>"}, page="/admin/content/hero_title")
    pub = app.test_client(); pub.get("/lang/en")
    assert "<script>alert(1)</script>" not in pub.get("/").get_data(as_text=True)


def test_owner_user_management_rules(app, owner):
    c = app.test_client()
    login(c, "owner@example.com", admin=True)
    r = post(c, "/admin/users/new", {"name": "Ed", "email": "ed@example.com", "role": "editor", "password": "Temp-Passw0rd-123"}, page="/admin/users/new")
    assert r.status_code == 302
    ed = User.query.filter_by(email="ed@example.com").one()
    assert ed.role == "editor" and ed.must_change_password
    # owner role cannot be granted through the UI
    assert post(c, "/admin/users/new", {"name": "X", "email": "x@example.com", "role": "owner", "password": "Temp-Passw0rd-123"}, page="/admin/users/new").status_code == 200
    assert User.query.filter_by(email="x@example.com").count() == 0
    assert post(c, f"/admin/users/{ed.id}/role", {"role": "support"}, page="/admin/users").status_code == 302
    assert ed.role == "support"
    assert post(c, f"/admin/users/{ed.id}/role", {"role": "owner"}, page="/admin/users").status_code == 400
    # owner cannot edit themselves or other owners
    assert post(c, f"/admin/users/{owner.id}/toggle", page="/admin/users").status_code == 403
    assert post(c, f"/admin/users/{owner.id}/role", {"role": "student"}, page="/admin/users").status_code == 403
    assert owner.role == "owner" and owner.is_active_account
    # deactivate -> cannot log in; reset password shows a temp password once
    post(c, f"/admin/users/{ed.id}/toggle", page="/admin/users")
    assert not ed.is_active_account
    r = post(c, f"/admin/users/{ed.id}/reset-password", page="/admin/users")
    assert r.status_code == 200 and b"<code" in r.data
    assert any(a.action == "password_reset" for a in AuditLog.query.all())
    assert "Temp-Passw0rd" not in "".join(a.details or "" for a in AuditLog.query.all())


def test_deactivated_staff_session_is_cut(app):
    c = staff_client(app, "editor")
    u = User.query.filter_by(email="editor@example.com").one()
    u.is_active_account = False
    db.session.commit()
    assert c.get("/admin/e/courses/").status_code in (302, 403)


def test_admin_cannot_see_audit_but_owner_can_and_is_readonly(app, owner):
    c = app.test_client()
    login(c, "owner@example.com", admin=True)
    assert c.get("/admin/audit").status_code == 200
    for method in (c.post, c.put, c.delete):
        assert method("/admin/audit").status_code in (400, 405)


def test_audit_log_records_login_failure_without_password(app, owner):
    c = app.test_client()
    login(c, "owner@example.com", "Wrong-Passw0rd-1", admin=True)
    rows = AuditLog.query.filter_by(action="login_failed").all()
    assert rows and all("Wrong-Passw0rd" not in (r.details or "") for r in rows)
