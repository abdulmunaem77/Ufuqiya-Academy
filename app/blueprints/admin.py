"""Owner / staff control panel.

Security model (does not rely on URL secrecy):
  * every route except /admin/login passes ``before_request`` (authenticated,
    active staff account) and then an explicit permission check;
  * all mutations are POST + CSRF-validated;
  * every mutation writes an append-only audit row.
"""
import re
import secrets
from datetime import timezone

from flask import (Blueprint, abort, current_app, flash, redirect, render_template, request,
                   url_for)
from flask_login import current_user, login_required
from sqlalchemy import func, or_

from .. import current_lang
from ..extensions import db, limiter
from ..forms import (AdminLoginForm, CategoryForm, ContentForm, CourseForm, EmptyForm,
                     InstructorForm, LessonForm, RoleForm, ServiceForm, StaffCreateForm,
                     StatusForm, TestimonialForm, WorkshopForm)
from ..i18n import CONTENT_KEYS, site_default
from ..mailer import send_mail
from ..models import (PAYMENT_STATUSES, EmailOutbox, Payment, BOOKING_STATUSES, ENROLL_STATUSES, ROLE_OWNER, ROLE_STUDENT, STAFF_ROLES,
                      AuditLog, Category, ConsultationBooking, ConsultationService, ContactMessage,
                      Course, Enrollment, Instructor, Lesson, SiteContent, Testimonial, User,
                      Workshop, WorkshopRegistration, utcnow)
from .. import payments as pay_service
from ..security import audit, audit_as, permission_required, safe_next
from .auth import authenticate, complete_login

bp = Blueprint("admin", __name__, url_prefix="/admin")
PER = 20


# ----------------------------------------------------------------- guards ---
@bp.before_request
def require_staff():
    if request.endpoint in ("admin.login",):
        return None
    if not current_user.is_authenticated:
        return redirect(url_for("admin.login", next=request.path))
    if not current_user.is_staff or not current_user.is_active_account:
        audit("access_denied", request.path)
        abort(403)


def need(permission):
    if not current_user.can(permission):
        audit("access_denied", request.path, permission)
        abort(403)


def _page():
    return max(request.args.get("page", 1, type=int) or 1, 1)


def _like(term):
    return "%" + term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def slugify(text):
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:60]
    return s or "item"


def unique_slug(model, base, exclude_id=None):
    slug, n = base, 2
    while True:
        q = model.query.filter_by(slug=slug)
        if exclude_id:
            q = q.filter(model.id != exclude_id)
        if not q.first():
            return slug
        slug, n = f"{base}-{n}", n + 1


# ------------------------------------------------------------------ login ---
@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("6 per minute; 20 per hour", methods=["POST"])
def login():
    if current_user.is_authenticated and current_user.is_staff:
        return redirect(url_for("admin.dashboard"))
    form = AdminLoginForm()
    if form.validate_on_submit():
        user = authenticate(form.email.data, form.password.data, staff_only=True)
        if user:  # staff sessions are never "remembered"; 2FA step handled inside
            return complete_login(user, False, request.args.get("next") or request.form.get("next"), True)
        flash("auth.invalid", "error")
    return render_template("admin/login.html", form=form)


# -------------------------------------------------------------- dashboard ---
@bp.route("/")
@permission_required("dashboard")
def dashboard():
    now = utcnow()
    from datetime import timedelta
    stats = {
        "students": User.query.filter_by(role=ROLE_STUDENT).count(),
        "courses": Course.query.count(),
        "enrollments": Enrollment.query.filter(Enrollment.status != "cancelled").count(),
        "pending_enrollments": Enrollment.query.filter_by(status="pending").count(),
        "workshops": Workshop.query.filter(Workshop.starts_at > now).count(),
        "registrations": WorkshopRegistration.query.filter_by(status="registered").count(),
        "pending_bookings": ConsultationBooking.query.filter_by(status="pending").count(),
        "new_messages": ContactMessage.query.filter_by(status="new").count(),
        "pending_payments": Payment.query.filter_by(status="submitted").count(),
        "new_students_30d": User.query.filter(User.role == ROLE_STUDENT,
                                              User.created_at > now - timedelta(days=30)).count(),
    }
    by_cat = (db.session.query(Category, func.count(Enrollment.id))
              .outerjoin(Course, Course.category_id == Category.id)
              .outerjoin(Enrollment, (Enrollment.course_id == Course.id) & (Enrollment.status != "cancelled"))
              .group_by(Category.id).order_by(Category.position).all())
    recent = Enrollment.query.order_by(Enrollment.created_at.desc()).limit(6).all() \
        if current_user.can("enrollments") else []
    logs = AuditLog.query.order_by(AuditLog.id.desc()).limit(8).all() if current_user.can("audit") else []
    return render_template("admin/dashboard.html", stats=stats, by_cat=by_cat, recent=recent, logs=logs)


# ------------------------------------------------------- generic CRUD ------
class Entity:
    def __init__(self, key, model, form, perm, columns, label, search=(), slug_source=None,
                 guards=(), choices=None, order=None, sample_flag=True):
        self.key, self.model, self.form, self.perm = key, model, form, perm
        self.columns, self.label, self.search = columns, label, search
        self.slug_source, self.guards, self.choices = slug_source, guards, choices
        self.order = order


def _yn(v): return "✓" if v else "—"


def _course_choices(form):
    form.category_id.choices = [(c.id, f"{c.name_en} / {c.name_ar}") for c in Category.query.order_by(Category.position)]
    form.instructor_id.choices = [(i.id, f"{i.name_en} / {i.name_ar}") for i in Instructor.query.order_by(Instructor.id)]


def _inst_choices(form):
    form.instructor_id.choices = [(i.id, f"{i.name_en} / {i.name_ar}") for i in Instructor.query.order_by(Instructor.id)]


ENTITIES = {e.key: e for e in [
    Entity("courses", Course, CourseForm, "courses", label="entity.courses",
           columns=[("col.title", lambda o, l: o.loc("title", l)),
                    ("col.category", lambda o, l: o.category.loc("name", l)),
                    ("col.price", lambda o, l: str(o.price)),
                    ("col.enrolled", lambda o, l: str(len(o.enrollments))),
                    ("col.published", lambda o, l: _yn(o.is_published)),
                    ("col.sample", lambda o, l: _yn(o.is_sample))],
           search=("title_ar", "title_en"), slug_source="title_en", choices=_course_choices,
           guards=(lambda o: (len(o.enrollments) == 0, "admin.err.has_enrollments"),),
           order=Course.id.desc()),
    Entity("workshops", Workshop, WorkshopForm, "workshops", label="entity.workshops",
           columns=[("col.title", lambda o, l: o.loc("title", l)),
                    ("col.starts", lambda o, l: current_app.jinja_env.filters["dt"](o.starts_at)),
                    ("col.seats", lambda o, l: f"{o.seats_taken}/{o.capacity}"),
                    ("col.published", lambda o, l: _yn(o.is_published)),
                    ("col.sample", lambda o, l: _yn(o.is_sample))],
           search=("title_ar", "title_en"), slug_source="title_en", choices=_inst_choices,
           guards=(lambda o: (len(o.registrations) == 0, "admin.err.has_registrations"),),
           order=Workshop.starts_at.desc()),
    Entity("services", ConsultationService, ServiceForm, "consultations", label="entity.services",
           columns=[("col.title", lambda o, l: o.loc("title", l)),
                    ("col.duration", lambda o, l: f"{o.duration_minutes}"),
                    ("col.price", lambda o, l: str(o.price)),
                    ("col.published", lambda o, l: _yn(o.is_published)),
                    ("col.sample", lambda o, l: _yn(o.is_sample))],
           search=("title_ar", "title_en"), slug_source="title_en", choices=_inst_choices,
           guards=(lambda o: (ConsultationBooking.query.filter_by(service_id=o.id).count() == 0,
                              "admin.err.has_bookings"),),
           order=ConsultationService.id.desc()),
    Entity("instructors", Instructor, InstructorForm, "courses", label="entity.instructors",
           columns=[("col.name", lambda o, l: o.loc("name", l)),
                    ("col.jobtitle", lambda o, l: o.loc("title", l)),
                    ("col.sample", lambda o, l: _yn(o.is_sample))],
           search=("name_ar", "name_en"),
           guards=(lambda o: (not o.courses and not Workshop.query.filter_by(instructor_id=o.id).count()
                              and not ConsultationService.query.filter_by(instructor_id=o.id).count(),
                              "admin.err.in_use"),),
           order=Instructor.id.desc()),
    Entity("categories", Category, CategoryForm, "courses", label="entity.categories",
           columns=[("col.name", lambda o, l: o.loc("name", l)), ("col.slug", lambda o, l: o.slug),
                    ("col.courses", lambda o, l: str(len(o.courses)))],
           search=("name_ar", "name_en", "slug"),
           guards=(lambda o: (not o.courses, "admin.err.in_use"),), order=Category.position),
    Entity("testimonials", Testimonial, TestimonialForm, "content", label="entity.testimonials",
           columns=[("col.name", lambda o, l: o.loc("author", l)),
                    ("col.published", lambda o, l: _yn(o.is_published)),
                    ("col.sample", lambda o, l: _yn(o.is_sample))],
           search=("author_ar", "author_en"), order=Testimonial.id.desc()),
]}


def _entity(key):
    ent = ENTITIES.get(key)
    if not ent:
        abort(404)
    need(ent.perm)
    return ent


@bp.route("/e/<entity>/")
def entity_list(entity):
    ent = _entity(entity)
    q = (request.args.get("q") or "").strip()[:80]
    query = ent.model.query
    if q and ent.search:
        query = query.filter(or_(*(getattr(ent.model, c).ilike(_like(q), escape="\\") for c in ent.search)))
    pagination = query.order_by(ent.order if ent.order is not None else ent.model.id).paginate(
        page=_page(), per_page=PER, error_out=False)
    lang = current_lang()
    rows = [(o, [fn(o, lang) for _, fn in ent.columns]) for o in pagination.items]
    return render_template("admin/list.html", ent=ent, rows=rows, pagination=pagination, q=q,
                           form=EmptyForm())


def _to_utc(naive_local):
    return naive_local.replace(tzinfo=current_app.config["ACADEMY_TZ"]).astimezone(timezone.utc).replace(tzinfo=None)


@bp.route("/e/<entity>/new", methods=["GET", "POST"])
@bp.route("/e/<entity>/<int:oid>/edit", methods=["GET", "POST"])
def entity_edit(entity, oid=None):
    ent = _entity(entity)
    obj = db.get_or_404(ent.model, oid) if oid else None
    form = ent.form(obj=obj)
    if ent.choices:
        ent.choices(form)
    if obj is not None and request.method == "GET" and hasattr(obj, "starts_at"):
        form.starts_at.data = obj.starts_at.replace(tzinfo=timezone.utc).astimezone(
            current_app.config["ACADEMY_TZ"]).replace(tzinfo=None)
    if form.validate_on_submit():
        creating = obj is None
        obj = obj or ent.model()
        data = {f.name: f.data for f in form if f.name not in ("csrf_token", "slug")}
        if "starts_at" in data:
            data["starts_at"] = _to_utc(data["starts_at"])
        if "position" in data and data["position"] is None:
            data["position"] = 0
        for k, v in data.items():
            setattr(obj, k, v)
        if hasattr(ent.model, "slug"):
            typed = (form.slug.data or "").strip()
            if typed:
                if ent.model.query.filter(ent.model.slug == typed, ent.model.id != (obj.id or 0)).first():
                    form.slug.errors.append("val.slug_taken")
                    return render_template("admin/form.html", ent=ent, form=form, obj=obj, creating=creating)
                obj.slug = typed
            elif creating or not obj.slug:
                obj.slug = unique_slug(ent.model, slugify(getattr(form, ent.slug_source).data), obj.id)
        db.session.add(obj)
        db.session.commit()
        audit(f"{ent.key}_{'create' if creating else 'update'}", f"{ent.key}:{obj.id}")
        flash("admin.saved", "success")
        if ent.key == "courses" and creating:
            return redirect(url_for("admin.lessons", course_id=obj.id))
        return redirect(url_for("admin.entity_list", entity=ent.key))
    return render_template("admin/form.html", ent=ent, form=form, obj=obj, creating=obj is None)


@bp.route("/e/<entity>/<int:oid>/delete", methods=["POST"])
def entity_delete(entity, oid):
    ent = _entity(entity)
    obj = db.get_or_404(ent.model, oid)
    if not EmptyForm().validate_on_submit():
        abort(400)
    for guard in ent.guards:
        ok, msg = guard(obj)
        if not ok:
            flash(msg, "error")
            return redirect(url_for("admin.entity_list", entity=ent.key))
    db.session.delete(obj)
    db.session.commit()
    audit(f"{ent.key}_delete", f"{ent.key}:{oid}")
    flash("admin.deleted", "success")
    return redirect(url_for("admin.entity_list", entity=ent.key))


# ---------------------------------------------------------------- lessons ---
@bp.route("/courses/<int:course_id>/lessons", methods=["GET", "POST"])
@permission_required("courses")
def lessons(course_id):
    course = db.get_or_404(Course, course_id)
    form = LessonForm(position=len(course.lessons) + 1)
    if form.validate_on_submit():
        les = Lesson(course_id=course.id)
        form.populate_obj(les)
        db.session.add(les)
        db.session.commit()
        audit("lesson_create", f"lesson:{les.id}", f"course:{course.id}")
        flash("admin.saved", "success")
        return redirect(url_for("admin.lessons", course_id=course.id))
    return render_template("admin/lessons.html", course=course, form=form, del_form=EmptyForm())


@bp.route("/lessons/<int:lesson_id>/edit", methods=["GET", "POST"])
@permission_required("courses")
def lesson_edit(lesson_id):
    les = db.get_or_404(Lesson, lesson_id)
    form = LessonForm(obj=les)
    if form.validate_on_submit():
        form.populate_obj(les)
        db.session.commit()
        audit("lesson_update", f"lesson:{les.id}")
        flash("admin.saved", "success")
        return redirect(url_for("admin.lessons", course_id=les.course_id))
    return render_template("admin/lesson_form.html", course=les.course, form=form)


@bp.route("/lessons/<int:lesson_id>/delete", methods=["POST"])
@permission_required("courses")
def lesson_delete(lesson_id):
    les = db.get_or_404(Lesson, lesson_id)
    if not EmptyForm().validate_on_submit():
        abort(400)
    from ..models import LessonProgress
    LessonProgress.query.filter_by(lesson_id=les.id).delete()
    cid = les.course_id
    db.session.delete(les)
    db.session.commit()
    audit("lesson_delete", f"lesson:{lesson_id}")
    flash("admin.deleted", "success")
    return redirect(url_for("admin.lessons", course_id=cid))


# --------------------------------------------------- workshop registrations -
@bp.route("/workshops/<int:wid>/registrations")
@permission_required("workshops")
def workshop_regs(wid):
    ws = db.get_or_404(Workshop, wid)
    return render_template("admin/workshop_regs.html", ws=ws)


# ---------------------------------------------------------- consultations ---
@bp.route("/bookings")
@permission_required("consultations")
def bookings():
    status = request.args.get("status")
    q = ConsultationBooking.query
    if status in BOOKING_STATUSES:
        q = q.filter_by(status=status)
    pagination = q.order_by(ConsultationBooking.created_at.desc()).paginate(page=_page(), per_page=PER, error_out=False)
    return render_template("admin/bookings.html", pagination=pagination, status=status,
                           statuses=BOOKING_STATUSES, form=EmptyForm())


def _set_status(model, oid, allowed, perm, audit_name, back):
    need(perm)
    obj = db.get_or_404(model, oid)
    form = StatusForm()
    form.status.choices = [(s, s) for s in allowed]
    if not form.validate_on_submit():
        abort(400)
    old, obj.status = obj.status, form.status.data
    db.session.commit()
    audit(audit_name, f"{model.__tablename__}:{oid}", f"{old}->{obj.status}")
    flash("admin.saved", "success")
    return redirect(request.referrer if request.referrer and request.referrer.startswith(request.host_url)
                    else url_for(back))


@bp.route("/bookings/<int:oid>/status", methods=["POST"])
def booking_status(oid):
    resp = _set_status(ConsultationBooking, oid, BOOKING_STATUSES, "consultations", "booking_status", "admin.bookings")
    b = db.session.get(ConsultationBooking, oid)
    if b and b.status in ("confirmed", "cancelled"):
        send_mail(b.user.email, f"Consultation {b.status}",
                  f"{b.service.title_en} — {b.preferred_at:%Y-%m-%d %H:%M} UTC: {b.status}.\n"
                  f"{b.service.title_ar} — الحالة: {b.status}", "booking_status")
    return resp


@bp.route("/enrollments")
@permission_required("enrollments")
def enrollments():
    status = request.args.get("status")
    q = Enrollment.query
    if status in ENROLL_STATUSES:
        q = q.filter_by(status=status)
    pagination = q.order_by(Enrollment.created_at.desc()).paginate(page=_page(), per_page=PER, error_out=False)
    return render_template("admin/enrollments.html", pagination=pagination, status=status,
                           statuses=ENROLL_STATUSES, form=EmptyForm())


@bp.route("/enrollments/<int:oid>/status", methods=["POST"])
def enrollment_status(oid):
    return _set_status(Enrollment, oid, ENROLL_STATUSES, "enrollments", "enrollment_status", "admin.enrollments")


# --------------------------------------------------------------- students ---
@bp.route("/students")
@permission_required("students")
def students():
    q = (request.args.get("q") or "").strip()[:80]
    query = User.query.filter_by(role=ROLE_STUDENT)
    if q:
        query = query.filter(or_(User.email.ilike(_like(q), escape="\\"), User.name.ilike(_like(q), escape="\\")))
    pagination = query.order_by(User.created_at.desc()).paginate(page=_page(), per_page=PER, error_out=False)
    return render_template("admin/students.html", pagination=pagination, q=q)


@bp.route("/students/<int:uid>")
@permission_required("students")
def student_detail(uid):
    u = db.get_or_404(User, uid)
    if u.role != ROLE_STUDENT:
        abort(404)
    regs = WorkshopRegistration.query.filter_by(user_id=u.id).all()
    books = ConsultationBooking.query.filter_by(user_id=u.id).all()
    return render_template("admin/student_detail.html", u=u, rows=[(e, e.progress()) for e in u.enrollments],
                           regs=regs, books=books, form=EmptyForm())


@bp.route("/students/<int:uid>/toggle", methods=["POST"])
@permission_required("students")
def student_toggle(uid):
    u = db.get_or_404(User, uid)
    if u.role != ROLE_STUDENT:
        abort(404)
    if not EmptyForm().validate_on_submit():
        abort(400)
    u.is_active_account = not u.is_active_account
    db.session.commit()
    audit("student_activate" if u.is_active_account else "student_deactivate", f"user:{u.id}")
    flash("admin.saved", "success")
    return redirect(url_for("admin.student_detail", uid=u.id))


# ---------------------------------------------------------------- content ---
@bp.route("/content")
@permission_required("content")
def content():
    rows = []
    for key in CONTENT_KEYS:
        row = db.session.get(SiteContent, key)
        rows.append((key, row.value_ar if row else site_default(key, "ar"),
                     row.value_en if row else site_default(key, "en")))
    return render_template("admin/content.html", rows=rows)


@bp.route("/content/<key>", methods=["GET", "POST"])
@permission_required("content")
def content_edit(key):
    if key not in CONTENT_KEYS:
        abort(404)
    row = db.session.get(SiteContent, key)
    form = ContentForm(value_ar=row.value_ar if row else site_default(key, "ar"),
                       value_en=row.value_en if row else site_default(key, "en")) \
        if request.method == "GET" else ContentForm()
    if form.validate_on_submit():
        row = row or SiteContent(key=key)
        row.value_ar, row.value_en = form.value_ar.data, form.value_en.data
        db.session.add(row)
        db.session.commit()
        audit("content_update", key)
        flash("admin.saved", "success")
        return redirect(url_for("admin.content"))
    return render_template("admin/content_edit.html", form=form, key=key)


# --------------------------------------------------------------- messages ---
@bp.route("/messages")
@permission_required("messages")
def messages():
    status = request.args.get("status")
    q = ContactMessage.query
    if status in ("new", "read", "resolved"):
        q = q.filter_by(status=status)
    pagination = q.order_by(ContactMessage.created_at.desc()).paginate(page=_page(), per_page=PER, error_out=False)
    return render_template("admin/messages.html", pagination=pagination, status=status, form=EmptyForm())


@bp.route("/messages/<int:oid>/status", methods=["POST"])
def message_status(oid):
    return _set_status(ContactMessage, oid, ("new", "read", "resolved"), "messages", "message_status", "admin.messages")


# ------------------------------------------------------------------ users ---
@bp.route("/users")
@permission_required("users")
def users():
    pagination = User.query.filter(User.role != ROLE_STUDENT).order_by(User.created_at).paginate(
        page=_page(), per_page=PER, error_out=False)
    return render_template("admin/users.html", pagination=pagination, form=EmptyForm())


@bp.route("/users/new", methods=["GET", "POST"])
@permission_required("users")
def user_new():
    form = StaffCreateForm()
    form.role.choices = [(r, r) for r in STAFF_ROLES if r != ROLE_OWNER]
    if form.validate_on_submit():
        email = form.email.data.lower()
        if User.query.filter_by(email=email).first():
            form.email.errors.append("val.email_taken")
        else:
            u = User(email=email, name=form.name.data, role=form.role.data, must_change_password=True,
                     email_verified=True)
            u.set_password(form.password.data)
            db.session.add(u)
            db.session.commit()
            audit("staff_create", f"user:{u.id}", u.role)
            flash("admin.saved", "success")
            return redirect(url_for("admin.users"))
    return render_template("admin/user_form.html", form=form)


def _managed_user(uid):
    u = db.get_or_404(User, uid)
    if u.id == current_user.id or u.role == ROLE_OWNER:  # no self-lockout, owner immutable here
        abort(403)
    return u


@bp.route("/users/<int:uid>/role", methods=["POST"])
@permission_required("users")
def user_role(uid):
    u = _managed_user(uid)
    form = RoleForm()
    form.role.choices = [(r, r) for r in STAFF_ROLES if r != ROLE_OWNER] + [(ROLE_STUDENT, ROLE_STUDENT)]
    if not form.validate_on_submit():
        abort(400)
    old, u.role = u.role, form.role.data
    db.session.commit()
    audit("role_change", f"user:{u.id}", f"{old}->{u.role}")
    flash("admin.saved", "success")
    return redirect(url_for("admin.users"))


@bp.route("/users/<int:uid>/toggle", methods=["POST"])
@permission_required("users")
def user_toggle(uid):
    u = _managed_user(uid)
    if not EmptyForm().validate_on_submit():
        abort(400)
    u.is_active_account = not u.is_active_account
    db.session.commit()
    audit("user_activate" if u.is_active_account else "user_deactivate", f"user:{u.id}")
    flash("admin.saved", "success")
    return redirect(url_for("admin.users"))


@bp.route("/users/<int:uid>/reset-password", methods=["POST"])
@permission_required("users")
def user_reset(uid):
    u = _managed_user(uid)
    if not EmptyForm().validate_on_submit():
        abort(400)
    temp = secrets.token_urlsafe(12) + "9a"
    u.set_password(temp)
    u.must_change_password = True
    u.failed_logins, u.locked_until = 0, None
    db.session.commit()
    audit("password_reset", f"user:{u.id}")
    # Shown once, in this response only; never stored or put in a cookie.
    return render_template("admin/temp_password.html", u=u, temp=temp)


# ------------------------------------------------------------------ audit ---
@bp.route("/audit")
@permission_required("audit")
def audit_log():
    action = (request.args.get("action") or "").strip()[:60]
    q = AuditLog.query
    if action:
        q = q.filter(AuditLog.action.ilike(_like(action), escape="\\"))
    pagination = q.order_by(AuditLog.id.desc()).paginate(page=_page(), per_page=40, error_out=False)
    return render_template("admin/audit.html", pagination=pagination, action=action)


# --------------------------------------------------------------- payments ---
@bp.route("/payments")
@permission_required("payments")
def payments():
    status = request.args.get("status")
    q = Payment.query
    if status in PAYMENT_STATUSES:
        q = q.filter_by(status=status)
    pagination = q.order_by(Payment.created_at.desc()).paginate(page=_page(), per_page=PER, error_out=False)
    return render_template("admin/payments.html", pagination=pagination, status=status,
                           statuses=PAYMENT_STATUSES, form=EmptyForm())


@bp.route("/payments/<int:pid>/<decision>", methods=["POST"])
@permission_required("payments")
def payment_decide(pid, decision):
    if decision not in ("confirm", "reject"):
        abort(404)
    p = db.get_or_404(Payment, pid)
    if not EmptyForm().validate_on_submit():
        abort(400)
    if p.status not in ("awaiting", "submitted", "rejected"):
        flash("admin.err.payment_final", "error")
        return redirect(url_for("admin.payments"))
    if decision == "confirm":
        pay_service.confirm(p, current_user)
    else:
        pay_service.reject(p, current_user)
    db.session.commit()
    audit(f"payment_{decision}", f"payment:{p.id}", f"{p.amount} {p.currency} user:{p.user_id}")
    send_mail(p.user.email, f"Payment {'confirmed' if decision == 'confirm' else 'rejected'}: {p.title}",
              f"{p.title}: {'تم تأكيد الدفع وتفعيل طلبك' if decision == 'confirm' else 'تعذّر تأكيد الدفع، يرجى مراجعة المرجع وإعادة الإرسال'}\n"
              f"{p.title}: payment {'confirmed — your request is now active' if decision == 'confirm' else 'could not be confirmed — please check the reference and resubmit'}.",
              "payment_" + decision)
    flash("admin.saved", "success")
    return redirect(request.referrer if request.referrer and request.referrer.startswith(request.host_url)
                    else url_for("admin.payments"))


# ----------------------------------------------------------------- outbox ---
@bp.route("/outbox")
@permission_required("outbox")
def outbox():
    pagination = EmailOutbox.query.order_by(EmailOutbox.id.desc()).paginate(page=_page(), per_page=30, error_out=False)
    return render_template("admin/outbox.html", pagination=pagination, mail_on=current_app.config["MAIL_ENABLED"])
