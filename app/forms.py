import re
from datetime import timedelta
from decimal import Decimal

from flask_wtf import FlaskForm
from wtforms import (BooleanField, DecimalField, HiddenField, IntegerField, PasswordField,
                     SelectField, StringField, TextAreaField)
from wtforms.fields import DateTimeLocalField
from wtforms.validators import (DataRequired, Email, InputRequired, EqualTo, Length, NumberRange, Optional,
                                Regexp, ValidationError)

from .models import ALL_ROLES, BOOKING_STATUSES, ENROLL_STATUSES, LEVELS, utcnow

SLUG_RE = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
strip = lambda v: v.strip() if isinstance(v, str) else v


def strong_password(min_len=10):
    def _check(form, field):
        pw = field.data or ""
        if len(pw) < min_len:
            raise ValidationError("val.password_len")
        if not (re.search(r"[A-Za-z؀-ۿ]", pw) and re.search(r"\d", pw)):
            raise ValidationError("val.password_mix")
        email = (getattr(form, "email", None) and form.email.data or "").lower()
        if email and pw.lower() == email:
            raise ValidationError("val.password_email")
    return _check


class _F(FlaskForm):
    class Meta:
        # Messages are i18n keys; templates translate them.
        locales = ["en"]


REQ = DataRequired(message="val.required")
REQN = InputRequired(message="val.required")  # numbers: 0 is a valid value
EMAIL = Email(message="val.email", check_deliverability=False)


def length(mx, mn=0):
    return Length(min=mn, max=mx, message="val.length")


class RegisterForm(_F):
    name = StringField("name", [REQ, length(120, 2)], filters=[strip])
    email = StringField("email", [REQ, EMAIL, length(254)], filters=[strip])
    password = PasswordField("password", [REQ, length(128), strong_password(10)])
    confirm = PasswordField("confirm", [REQ, EqualTo("password", message="val.password_match")])
    accept = BooleanField("accept", [DataRequired(message="val.accept")])


class LoginForm(_F):
    email = StringField("email", [REQ, length(254)], filters=[strip])
    password = PasswordField("password", [REQ, length(128)])
    remember = BooleanField("remember")


class ProfileForm(_F):
    name = StringField("name", [REQ, length(120, 2)], filters=[strip])
    locale = SelectField("locale", choices=[("ar", "العربية"), ("en", "English")])


class PasswordChangeForm(_F):
    current = PasswordField("current", [REQ, length(128)])
    password = PasswordField("password", [REQ, length(128), strong_password(10)])
    confirm = PasswordField("confirm", [REQ, EqualTo("password", message="val.password_match")])


TOPICS = ("general", "course", "workshop", "consultation", "corporate", "support")


class ContactForm(_F):
    name = StringField("name", [REQ, length(120, 2)], filters=[strip])
    email = StringField("email", [REQ, EMAIL, length(254)], filters=[strip])
    topic = SelectField("topic", choices=[(x, x) for x in TOPICS])
    message = TextAreaField("message", [REQ, length(3000, 10)], filters=[strip])
    website = StringField("website")  # honeypot: real users leave it empty


class BookingForm(_F):
    when = DateTimeLocalField("when", [REQ], format="%Y-%m-%dT%H:%M",
                              render_kw={"step": 900})
    notes = TextAreaField("notes", [Optional(), length(1000)], filters=[strip])

    def validate_when(self, field):
        # Compared in naive-local terms; view converts to UTC afterwards.
        pass


class CourseSearchForm(_F):
    class Meta(_F.Meta):
        csrf = False


# ------------------------------------------------------------------ admin ---
class AdminLoginForm(LoginForm):
    pass


class _Entity(_F):
    pass


def _bool(label): return BooleanField(label)


class CategoryForm(_Entity):
    slug = StringField("slug", [REQ, Regexp(SLUG_RE, message="val.slug"), length(80)], filters=[strip])
    name_ar = StringField("name_ar", [REQ, length(120)], filters=[strip])
    name_en = StringField("name_en", [REQ, length(120)], filters=[strip])
    description_ar = StringField("description_ar", [Optional(), length(400)], filters=[strip])
    description_en = StringField("description_en", [Optional(), length(400)], filters=[strip])
    position = IntegerField("position", [Optional(), NumberRange(0, 999)], default=0)


class InstructorForm(_Entity):
    name_ar = StringField("name_ar", [REQ, length(120)], filters=[strip])
    name_en = StringField("name_en", [REQ, length(120)], filters=[strip])
    title_ar = StringField("title_ar", [Optional(), length(160)], filters=[strip])
    title_en = StringField("title_en", [Optional(), length(160)], filters=[strip])
    bio_ar = TextAreaField("bio_ar", [Optional(), length(3000)], filters=[strip])
    bio_en = TextAreaField("bio_en", [Optional(), length(3000)], filters=[strip])
    is_sample = _bool("is_sample")


class CourseForm(_Entity):
    slug = StringField("slug", [Optional(), Regexp(SLUG_RE, message="val.slug"), length(120)], filters=[strip])
    category_id = SelectField("category_id", coerce=int)
    instructor_id = SelectField("instructor_id", coerce=int)
    title_ar = StringField("title_ar", [REQ, length(200)], filters=[strip])
    title_en = StringField("title_en", [REQ, length(200)], filters=[strip])
    summary_ar = StringField("summary_ar", [REQ, length(400)], filters=[strip])
    summary_en = StringField("summary_en", [REQ, length(400)], filters=[strip])
    description_ar = TextAreaField("description_ar", [REQ, length(8000)], filters=[strip])
    description_en = TextAreaField("description_en", [REQ, length(8000)], filters=[strip])
    level = SelectField("level", choices=[(l, l) for l in LEVELS])
    price = DecimalField("price", [REQN, NumberRange(0, 100000, message="val.number")], places=2, default=Decimal("0"))
    duration_hours = IntegerField("duration_hours", [REQN, NumberRange(1, 1000, message="val.number")])
    is_published = _bool("is_published")
    is_featured = _bool("is_featured")
    is_sample = _bool("is_sample")


class LessonForm(_F):
    position = IntegerField("position", [REQN, NumberRange(1, 500, message="val.number")])
    title_ar = StringField("title_ar", [REQ, length(200)], filters=[strip])
    title_en = StringField("title_en", [REQ, length(200)], filters=[strip])
    body_ar = TextAreaField("body_ar", [Optional(), length(8000)], filters=[strip])
    body_en = TextAreaField("body_en", [Optional(), length(8000)], filters=[strip])
    minutes = IntegerField("minutes", [REQN, NumberRange(1, 600, message="val.number")], default=10)


class WorkshopForm(_Entity):
    slug = StringField("slug", [Optional(), Regexp(SLUG_RE, message="val.slug"), length(120)], filters=[strip])
    instructor_id = SelectField("instructor_id", coerce=int)
    title_ar = StringField("title_ar", [REQ, length(200)], filters=[strip])
    title_en = StringField("title_en", [REQ, length(200)], filters=[strip])
    summary_ar = StringField("summary_ar", [REQ, length(400)], filters=[strip])
    summary_en = StringField("summary_en", [REQ, length(400)], filters=[strip])
    description_ar = TextAreaField("description_ar", [REQ, length(8000)], filters=[strip])
    description_en = TextAreaField("description_en", [REQ, length(8000)], filters=[strip])
    starts_at = DateTimeLocalField("starts_at", [REQ], format="%Y-%m-%dT%H:%M")
    duration_minutes = IntegerField("duration_minutes", [REQN, NumberRange(15, 1440, message="val.number")])
    capacity = IntegerField("capacity", [REQN, NumberRange(1, 5000, message="val.number")])
    price = DecimalField("price", [REQN, NumberRange(0, 100000, message="val.number")], places=2, default=Decimal("0"))
    is_published = _bool("is_published")
    is_sample = _bool("is_sample")


class ServiceForm(_Entity):
    slug = StringField("slug", [Optional(), Regexp(SLUG_RE, message="val.slug"), length(120)], filters=[strip])
    instructor_id = SelectField("instructor_id", coerce=int)
    title_ar = StringField("title_ar", [REQ, length(200)], filters=[strip])
    title_en = StringField("title_en", [REQ, length(200)], filters=[strip])
    summary_ar = StringField("summary_ar", [REQ, length(400)], filters=[strip])
    summary_en = StringField("summary_en", [REQ, length(400)], filters=[strip])
    duration_minutes = IntegerField("duration_minutes", [REQN, NumberRange(15, 480, message="val.number")])
    price = DecimalField("price", [REQN, NumberRange(0, 100000, message="val.number")], places=2, default=Decimal("0"))
    is_published = _bool("is_published")
    is_sample = _bool("is_sample")


class TestimonialForm(_Entity):
    author_ar = StringField("author_ar", [REQ, length(120)], filters=[strip])
    author_en = StringField("author_en", [REQ, length(120)], filters=[strip])
    role_ar = StringField("role_ar", [Optional(), length(160)], filters=[strip])
    role_en = StringField("role_en", [Optional(), length(160)], filters=[strip])
    text_ar = TextAreaField("text_ar", [REQ, length(1000)], filters=[strip])
    text_en = TextAreaField("text_en", [REQ, length(1000)], filters=[strip])
    is_published = _bool("is_published")
    is_sample = _bool("is_sample")


class ContentForm(_F):
    value_ar = TextAreaField("value_ar", [REQ, length(2000)], filters=[strip])
    value_en = TextAreaField("value_en", [REQ, length(2000)], filters=[strip])


class StatusForm(_F):
    status = SelectField("status", choices=[])


class StaffCreateForm(_F):
    name = StringField("name", [REQ, length(120, 2)], filters=[strip])
    email = StringField("email", [REQ, EMAIL, length(254)], filters=[strip])
    role = SelectField("role", choices=[(r, r) for r in ALL_ROLES])
    password = PasswordField("password", [REQ, length(128), strong_password(12)])


class RoleForm(_F):
    role = SelectField("role", choices=[(r, r) for r in ALL_ROLES])


class EmptyForm(_F):
    """CSRF-only form for POST buttons."""
