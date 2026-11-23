"""Database models.

Written with portable SQLAlchemy types only so the same schema runs on SQLite
(development) and PostgreSQL (production).  Bilingual content uses paired
``*_ar`` / ``*_en`` columns.
"""
from datetime import datetime, timedelta, timezone

from flask_login import UserMixin
from sqlalchemy import UniqueConstraint
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db, login_manager


def utcnow():
    """Naive UTC timestamp (portable across SQLite/PostgreSQL)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# --------------------------------------------------------------------- roles
ROLE_OWNER, ROLE_ADMIN, ROLE_EDITOR, ROLE_SUPPORT, ROLE_STUDENT = (
    "owner", "admin", "editor", "support", "student")
STAFF_ROLES = (ROLE_OWNER, ROLE_ADMIN, ROLE_EDITOR, ROLE_SUPPORT)
ALL_ROLES = STAFF_ROLES + (ROLE_STUDENT,)

# role -> permissions. Enforced server-side by @permission_required.
ROLE_PERMISSIONS = {
    ROLE_OWNER: {"dashboard", "courses", "workshops", "consultations", "students",
                 "enrollments", "content", "messages", "users", "audit", "payments", "outbox"},
    ROLE_ADMIN: {"dashboard", "courses", "workshops", "consultations", "students",
                 "enrollments", "content", "messages", "payments"},
    ROLE_EDITOR: {"dashboard", "courses", "workshops", "content"},
    ROLE_SUPPORT: {"dashboard", "consultations", "students", "enrollments", "messages", "payments"},
    ROLE_STUDENT: set(),
}


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(254), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=ROLE_STUDENT, index=True)
    is_active_account = db.Column(db.Boolean, nullable=False, default=True)
    must_change_password = db.Column(db.Boolean, nullable=False, default=False)
    locale = db.Column(db.String(2), nullable=False, default="ar")
    failed_logins = db.Column(db.Integer, nullable=False, default=0)
    locked_until = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    last_login_at = db.Column(db.DateTime)
    email_verified = db.Column(db.Boolean, nullable=False, default=False)
    # TOTP two-factor authentication (RFC 6238)
    totp_secret = db.Column(db.String(64))
    totp_enabled = db.Column(db.Boolean, nullable=False, default=False)
    totp_last_step = db.Column(db.Integer, nullable=False, default=0)  # replay protection
    backup_codes = db.Column(db.Text, default="")  # newline-separated HMAC digests

    enrollments = db.relationship("Enrollment", back_populates="user", cascade="all, delete-orphan")

    # Flask-Login: deactivated accounts cannot keep a session.
    @property
    def is_active(self):
        return self.is_active_account

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method="scrypt")

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_staff(self):
        return self.role in STAFF_ROLES

    @property
    def is_owner(self):
        return self.role == ROLE_OWNER

    def can(self, permission):
        return self.is_active_account and permission in ROLE_PERMISSIONS.get(self.role, set())

    @property
    def is_locked(self):
        return bool(self.locked_until and self.locked_until > utcnow())

    def register_failure(self, max_failed, lock_minutes):
        self.failed_logins = (self.failed_logins or 0) + 1
        if self.failed_logins >= max_failed:
            self.locked_until = utcnow() + timedelta(minutes=lock_minutes)
            self.failed_logins = 0

    def register_success(self):
        self.failed_logins = 0
        self.locked_until = None
        self.last_login_at = utcnow()

    def __repr__(self):
        return f"<User {self.id} {self.role}>"


@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None


class Bilingual:
    """Mixin: ``obj.loc('title', 'ar')`` falls back to the other language."""

    def loc(self, field, lang):
        primary = getattr(self, f"{field}_{lang}", None)
        if primary:
            return primary
        other = "en" if lang == "ar" else "ar"
        return getattr(self, f"{field}_{other}", "") or ""


class Category(Bilingual, db.Model):
    __tablename__ = "categories"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False)
    name_ar = db.Column(db.String(120), nullable=False)
    name_en = db.Column(db.String(120), nullable=False)
    description_ar = db.Column(db.String(400), default="")
    description_en = db.Column(db.String(400), default="")
    position = db.Column(db.Integer, nullable=False, default=0)
    courses = db.relationship("Course", back_populates="category")


class Instructor(Bilingual, db.Model):
    __tablename__ = "instructors"
    id = db.Column(db.Integer, primary_key=True)
    name_ar = db.Column(db.String(120), nullable=False)
    name_en = db.Column(db.String(120), nullable=False)
    title_ar = db.Column(db.String(160), default="")
    title_en = db.Column(db.String(160), default="")
    bio_ar = db.Column(db.Text, default="")
    bio_en = db.Column(db.Text, default="")
    is_sample = db.Column(db.Boolean, nullable=False, default=False)
    courses = db.relationship("Course", back_populates="instructor")


LEVELS = ("beginner", "intermediate", "advanced")


class Course(Bilingual, db.Model):
    __tablename__ = "courses"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False, index=True)
    instructor_id = db.Column(db.Integer, db.ForeignKey("instructors.id"), nullable=False)
    title_ar = db.Column(db.String(200), nullable=False)
    title_en = db.Column(db.String(200), nullable=False)
    summary_ar = db.Column(db.String(400), nullable=False, default="")
    summary_en = db.Column(db.String(400), nullable=False, default="")
    description_ar = db.Column(db.Text, nullable=False, default="")
    description_en = db.Column(db.Text, nullable=False, default="")
    level = db.Column(db.String(20), nullable=False, default="beginner")
    price = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    duration_hours = db.Column(db.Integer, nullable=False, default=1)
    is_published = db.Column(db.Boolean, nullable=False, default=True, index=True)
    is_featured = db.Column(db.Boolean, nullable=False, default=False)
    is_sample = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    category = db.relationship("Category", back_populates="courses")
    instructor = db.relationship("Instructor", back_populates="courses")
    lessons = db.relationship("Lesson", back_populates="course", order_by="Lesson.position",
                              cascade="all, delete-orphan")
    enrollments = db.relationship("Enrollment", back_populates="course", cascade="all, delete-orphan")

    @property
    def is_free(self):
        return not self.price


class Lesson(Bilingual, db.Model):
    __tablename__ = "lessons"
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False, index=True)
    position = db.Column(db.Integer, nullable=False, default=1)
    title_ar = db.Column(db.String(200), nullable=False)
    title_en = db.Column(db.String(200), nullable=False)
    body_ar = db.Column(db.Text, default="")
    body_en = db.Column(db.Text, default="")
    video_url = db.Column(db.String(300), default="")  # YouTube/Vimeo only (validated)
    minutes = db.Column(db.Integer, nullable=False, default=10)
    course = db.relationship("Course", back_populates="lessons")


ENROLL_PENDING, ENROLL_ACTIVE, ENROLL_CANCELLED = "pending", "active", "cancelled"
ENROLL_STATUSES = (ENROLL_PENDING, ENROLL_ACTIVE, ENROLL_CANCELLED)


class Enrollment(db.Model):
    __tablename__ = "enrollments"
    __table_args__ = (UniqueConstraint("user_id", "course_id", name="uq_enrollment"),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default=ENROLL_PENDING)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    user = db.relationship("User", back_populates="enrollments")
    course = db.relationship("Course", back_populates="enrollments")

    def progress(self):
        total = len(self.course.lessons)
        if not total:
            return 0, 0, 0
        ids = [l.id for l in self.course.lessons]
        done = LessonProgress.query.filter(
            LessonProgress.user_id == self.user_id, LessonProgress.lesson_id.in_(ids)).count()
        return round(done * 100 / total), done, total


class LessonProgress(db.Model):
    __tablename__ = "lesson_progress"
    __table_args__ = (UniqueConstraint("user_id", "lesson_id", name="uq_progress"),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    lesson_id = db.Column(db.Integer, db.ForeignKey("lessons.id"), nullable=False)
    completed_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class Workshop(Bilingual, db.Model):
    __tablename__ = "workshops"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    instructor_id = db.Column(db.Integer, db.ForeignKey("instructors.id"), nullable=False)
    title_ar = db.Column(db.String(200), nullable=False)
    title_en = db.Column(db.String(200), nullable=False)
    summary_ar = db.Column(db.String(400), nullable=False, default="")
    summary_en = db.Column(db.String(400), nullable=False, default="")
    description_ar = db.Column(db.Text, nullable=False, default="")
    description_en = db.Column(db.Text, nullable=False, default="")
    starts_at = db.Column(db.DateTime, nullable=False, index=True)  # UTC
    duration_minutes = db.Column(db.Integer, nullable=False, default=90)
    capacity = db.Column(db.Integer, nullable=False, default=30)
    price = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    is_published = db.Column(db.Boolean, nullable=False, default=True, index=True)
    is_sample = db.Column(db.Boolean, nullable=False, default=False)
    instructor = db.relationship("Instructor")
    registrations = db.relationship("WorkshopRegistration", back_populates="workshop",
                                    cascade="all, delete-orphan")

    @property
    def seats_taken(self):
        return sum(1 for r in self.registrations if r.status != "cancelled")

    @property
    def seats_left(self):
        return max(self.capacity - self.seats_taken, 0)

    @property
    def is_upcoming(self):
        return self.starts_at > utcnow()


class WorkshopRegistration(db.Model):
    __tablename__ = "workshop_registrations"
    __table_args__ = (UniqueConstraint("user_id", "workshop_id", name="uq_ws_reg"),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    workshop_id = db.Column(db.Integer, db.ForeignKey("workshops.id"), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="registered")  # registered|pending|cancelled
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    user = db.relationship("User")
    workshop = db.relationship("Workshop", back_populates="registrations")


class ConsultationService(Bilingual, db.Model):
    __tablename__ = "consultation_services"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    instructor_id = db.Column(db.Integer, db.ForeignKey("instructors.id"), nullable=False)
    title_ar = db.Column(db.String(200), nullable=False)
    title_en = db.Column(db.String(200), nullable=False)
    summary_ar = db.Column(db.String(400), nullable=False, default="")
    summary_en = db.Column(db.String(400), nullable=False, default="")
    duration_minutes = db.Column(db.Integer, nullable=False, default=60)
    price = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    is_published = db.Column(db.Boolean, nullable=False, default=True)
    is_sample = db.Column(db.Boolean, nullable=False, default=False)
    instructor = db.relationship("Instructor")


BOOKING_STATUSES = ("pending", "confirmed", "completed", "cancelled")


class ConsultationBooking(db.Model):
    __tablename__ = "consultation_bookings"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    service_id = db.Column(db.Integer, db.ForeignKey("consultation_services.id"), nullable=False)
    preferred_at = db.Column(db.DateTime, nullable=False)  # UTC
    notes = db.Column(db.Text, default="")
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    user = db.relationship("User")
    service = db.relationship("ConsultationService")


class ContactMessage(db.Model):
    __tablename__ = "contact_messages"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(254), nullable=False)
    topic = db.Column(db.String(40), nullable=False, default="general")
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="new", index=True)  # new|read|resolved
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class Testimonial(Bilingual, db.Model):
    """Always a labelled fictional sample unless the owner replaces it with a
    genuine, consented testimonial (then is_sample=False)."""
    __tablename__ = "testimonials"
    id = db.Column(db.Integer, primary_key=True)
    author_ar = db.Column(db.String(120), nullable=False)
    author_en = db.Column(db.String(120), nullable=False)
    role_ar = db.Column(db.String(160), default="")
    role_en = db.Column(db.String(160), default="")
    text_ar = db.Column(db.Text, nullable=False)
    text_en = db.Column(db.Text, nullable=False)
    is_published = db.Column(db.Boolean, nullable=False, default=True)
    is_sample = db.Column(db.Boolean, nullable=False, default=True)


class SiteContent(db.Model):
    """Editable site copy (CMS): hero, about, footer blurb, contact details."""
    __tablename__ = "site_content"
    key = db.Column(db.String(60), primary_key=True)
    value_ar = db.Column(db.Text, nullable=False, default="")
    value_en = db.Column(db.Text, nullable=False, default="")
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)


class AuditLog(db.Model):
    """Append-only: the application exposes no edit/delete path for rows."""
    __tablename__ = "audit_logs"
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    actor_email = db.Column(db.String(254))
    action = db.Column(db.String(60), nullable=False, index=True)
    target = db.Column(db.String(120), default="")
    details = db.Column(db.Text, default="")
    ip = db.Column(db.String(64), default="")


PAYMENT_KINDS = ("course", "workshop", "consultation")
PAYMENT_STATUSES = ("awaiting", "submitted", "confirmed", "rejected", "cancelled")


class Payment(db.Model):
    """Manual-payment ledger. The platform processes NO card/online transactions:
    a student pays offline (e.g. bank transfer), submits the reference they were
    given, and staff confirm or reject it. Nothing here is a real charge."""
    __tablename__ = "payments"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    kind = db.Column(db.String(20), nullable=False)
    target_id = db.Column(db.Integer, nullable=False)  # enrollment / workshop_registration / booking id
    title = db.Column(db.String(300), nullable=False, default="")  # snapshot of what is being paid for
    amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    currency = db.Column(db.String(8), nullable=False, default="USD")
    method = db.Column(db.String(60), default="")
    reference = db.Column(db.String(120), default="")  # supplied by the student
    note = db.Column(db.String(500), default="")
    status = db.Column(db.String(20), nullable=False, default="awaiting", index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    decided_at = db.Column(db.DateTime)
    decided_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    user = db.relationship("User", foreign_keys=[user_id])


class Certificate(db.Model):
    __tablename__ = "certificates"
    __table_args__ = (UniqueConstraint("user_id", "course_id", name="uq_certificate"),)
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(24), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    holder_name = db.Column(db.String(120), nullable=False)  # snapshot at issue time
    issued_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    user = db.relationship("User")
    course = db.relationship("Course")


class EmailOutbox(db.Model):
    """Every e-mail the app produces. status: sent | failed | not_configured.
    Visible to the owner only (bodies can contain one-time links)."""
    __tablename__ = "email_outbox"
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
    to_email = db.Column(db.String(254), nullable=False)
    kind = db.Column(db.String(40), nullable=False)
    subject = db.Column(db.String(300), nullable=False)
    body = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="not_configured")
    error = db.Column(db.String(300), default="")
