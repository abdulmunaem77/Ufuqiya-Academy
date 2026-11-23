from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from ..extensions import db, limiter
from ..forms import LoginForm, PasswordChangeForm, ProfileForm, RegisterForm
from ..models import ROLE_STUDENT, User
from ..security import audit, audit_as, safe_next

bp = Blueprint("auth", __name__)

# Verified against when the e-mail is unknown, so response time does not reveal
# which e-mails exist.
_DUMMY = User(email="x", name="x", password_hash="")
_DUMMY.set_password("dummy-password-for-timing")


def authenticate(email, password, staff_only=False):
    """Return the user on success, else None. Handles lock-out and auditing."""
    email = (email or "").strip().lower()
    user = User.query.filter_by(email=email).first()
    cfg = current_app.config
    if user is None:
        _DUMMY.check_password(password or "")
        audit_as(email, "login_failed", "unknown_user")
        return None
    if user.is_locked:
        _DUMMY.check_password(password or "")
        audit_as(email, "login_blocked", "locked")
        return None
    ok = user.check_password(password or "") and user.is_active_account \
        and (user.is_staff or not staff_only)
    if not ok:
        user.register_failure(cfg["MAX_FAILED_LOGINS"], cfg["LOCKOUT_MINUTES"])
        db.session.commit()
        audit_as(email, "login_failed", "bad_credentials")
        return None
    user.register_success()
    db.session.commit()
    return user


def start_session(user, remember=False):
    lang = session.get("lang")
    session.clear()  # defeat session fixation
    if lang:
        session["lang"] = lang
    session.permanent = True
    login_user(user, remember=remember)
    audit("login_success", user.email)


@bp.route("/register", methods=["GET", "POST"])
@limiter.limit("10 per hour", methods=["POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("student.dashboard"))
    form = RegisterForm()
    if form.validate_on_submit():
        email = form.email.data.lower()
        if User.query.filter_by(email=email).first():
            form.email.errors.append("val.email_taken")
        else:
            user = User(email=email, name=form.name.data, role=ROLE_STUDENT,
                        locale=session.get("lang", "ar"))
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            start_session(user)
            audit("register", user.email)
            flash("auth.welcome", "success")
            return redirect(safe_next("student.dashboard"))
    return render_template("auth/register.html", form=form)


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute; 40 per hour", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("student.dashboard"))
    form = LoginForm()
    if form.validate_on_submit():
        user = authenticate(form.email.data, form.password.data)
        if user:
            start_session(user, remember=form.remember.data)
            if user.is_staff and not request.args.get("next"):
                return redirect(url_for("admin.dashboard"))
            return redirect(safe_next("student.dashboard"))
        flash("auth.invalid", "error")
    return render_template("auth/login.html", form=form)


@bp.route("/logout", methods=["POST"])
def logout():
    if current_user.is_authenticated:
        audit("logout", current_user.email)
    lang = session.get("lang")
    logout_user()
    session.clear()
    if lang:
        session["lang"] = lang
    flash("auth.logged_out", "info")
    return redirect(url_for("main.home"))


@bp.route("/account", methods=["GET", "POST"])
@login_required
def account():
    form = ProfileForm(obj=current_user)
    if form.validate_on_submit():
        current_user.name = form.name.data
        current_user.locale = form.locale.data
        session["lang"] = form.locale.data
        db.session.commit()
        audit("profile_update", current_user.email)
        flash("account.saved", "success")
        return redirect(url_for("auth.account"))
    return render_template("auth/account.html", form=form)


@bp.route("/account/password", methods=["GET", "POST"])
@login_required
@limiter.limit("10 per hour", methods=["POST"])
def change_password():
    form = PasswordChangeForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current.data):
            form.current.errors.append("val.password_wrong")
        elif form.current.data == form.password.data:
            form.password.errors.append("val.password_same")
        else:
            current_user.set_password(form.password.data)
            current_user.must_change_password = False
            db.session.commit()
            audit("password_change", current_user.email)
            flash("account.password_changed", "success")
            return redirect(url_for("admin.dashboard" if current_user.is_staff else "student.dashboard"))
    return render_template("auth/password.html", form=form)
