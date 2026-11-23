import time

from flask import (Blueprint, abort, current_app, flash, redirect, render_template, request,
                   session, url_for)
from flask_login import current_user, login_required, login_user, logout_user

from .. import totp
from ..extensions import db, limiter
from ..forms import (ForgotForm, LoginForm, PasswordChangeForm, ProfileForm, RegisterForm,
                     ResetForm, TwoFADisableForm, TwoFAForm)
from ..mailer import external_url, make_token, read_token, send_mail
from ..models import ROLE_STUDENT, User
from ..security import audit, audit_as, is_safe_next, safe_next

bp = Blueprint("auth", __name__)

# Verified against when the e-mail is unknown so response time does not reveal
# which e-mails exist.
_DUMMY = User(email="x", name="x", password_hash="")
_DUMMY.set_password("dummy-password-for-timing")

PENDING_TTL = 300  # seconds allowed between password step and 2FA step


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
    return user


def start_session(user, remember=False):
    lang = session.get("lang")
    session.clear()  # defeat session fixation
    if lang:
        session["lang"] = lang
    session.permanent = True
    user.register_success()
    db.session.commit()
    login_user(user, remember=remember and not user.is_staff)
    audit("login_success", user.email)


def complete_login(user, remember, next_url, staff_area):
    """Password was correct: either finish, or demand the second factor."""
    if user.totp_enabled:
        lang = session.get("lang")
        session.clear()
        if lang:
            session["lang"] = lang
        session["pending_2fa"] = {"uid": user.id, "remember": bool(remember), "next": next_url or "",
                                  "staff": staff_area, "ts": int(time.time()), "tries": 0}
        return redirect(url_for("auth.twofa_login"))
    start_session(user, remember)
    if staff_area:
        return redirect(next_url if is_safe_next(next_url) else url_for("admin.dashboard"))
    if user.is_staff and not next_url:
        return redirect(url_for("admin.dashboard"))
    return redirect(next_url if is_safe_next(next_url) else url_for("student.dashboard"))


def send_verification(user):
    link = external_url("auth.verify_email", token=make_token("verify", user))
    send_mail(user.email, "Verify your e-mail · تأكيد البريد الإلكتروني",
              f"مرحبًا {user.name},\nلتأكيد بريدك الإلكتروني افتح الرابط (صالح 3 أيام):\n{link}\n\n"
              f"Hello {user.name},\nConfirm your e-mail address with this link (valid 3 days):\n{link}\n\n"
              "إن لم تنشئ حسابًا فتجاهل الرسالة · If you did not sign up, ignore this message.", "verify")


# ---------------------------------------------------------------- register/login
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
            send_verification(user)
            flash("auth.welcome", "success")
            if current_app.config["REQUIRE_EMAIL_VERIFICATION"]:
                flash("auth.verify_sent", "info")
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
            return complete_login(user, form.remember.data, request.args.get("next") or request.form.get("next"), False)
        flash("auth.invalid", "error")
    return render_template("auth/login.html", form=form)


@bp.route("/login/2fa", methods=["GET", "POST"])
@limiter.limit("10 per minute; 30 per hour", methods=["POST"])
def twofa_login():
    pend = session.get("pending_2fa")
    if not pend or time.time() - pend.get("ts", 0) > PENDING_TTL:
        session.pop("pending_2fa", None)
        flash("auth.2fa_expired", "error")
        return redirect(url_for("admin.login" if pend and pend.get("staff") else "auth.login"))
    user = db.session.get(User, pend["uid"])
    form = TwoFAForm()
    if form.validate_on_submit() and user and user.is_active_account and user.totp_enabled:
        code = form.code.data
        step = totp.verify(user.totp_secret, code, user.totp_last_step)
        ok = False
        if step:
            user.totp_last_step, ok = step, True
        else:
            rest = totp.consume_backup_code(user.backup_codes, code)
            if rest is not None:
                user.backup_codes, ok = rest, True
                audit_as(user.email, "2fa_backup_code_used")
        if ok:
            db.session.commit()
            session.pop("pending_2fa", None)
            return complete_login_after_2fa(user, pend)
        pend["tries"] = pend.get("tries", 0) + 1
        session["pending_2fa"] = pend
        audit_as(user.email, "2fa_failed")
        if pend["tries"] >= 5:
            session.pop("pending_2fa", None)
            user.register_failure(1, current_app.config["LOCKOUT_MINUTES"])
            db.session.commit()
            flash("auth.invalid", "error")
            return redirect(url_for("admin.login" if pend["staff"] else "auth.login"))
        form.code.errors.append("val.2fa_code")
    return render_template("auth/twofa_login.html", form=form)


def complete_login_after_2fa(user, pend):
    start_session(user, pend["remember"])
    nxt = pend.get("next")
    if pend.get("staff"):
        return redirect(nxt if is_safe_next(nxt) else url_for("admin.dashboard"))
    if user.is_staff and not nxt:
        return redirect(url_for("admin.dashboard"))
    return redirect(nxt if is_safe_next(nxt) else url_for("student.dashboard"))


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


# ---------------------------------------------------------------- e-mail verification
@bp.route("/verify-email/<token>")
def verify_email(token):
    data = read_token("verify", token, 3 * 24 * 3600)
    user = db.session.get(User, data["u"]) if data else None
    if not user or user.email != data["e"]:
        flash("auth.verify_bad", "error")
        return redirect(url_for("main.home"))
    if not user.email_verified:
        user.email_verified = True
        db.session.commit()
        audit_as(user.email, "email_verified")
    flash("auth.verified", "success")
    return redirect(url_for("student.dashboard" if current_user.is_authenticated else "auth.login"))


@bp.route("/verify-email/resend", methods=["POST"])
@login_required
@limiter.limit("5 per hour")
def resend_verification():
    from ..forms import EmptyForm
    if not EmptyForm().validate_on_submit():
        abort(400)
    if not current_user.email_verified:
        send_verification(current_user)
    flash("auth.verify_sent", "info")
    return redirect(request.referrer if request.referrer and request.referrer.startswith(request.host_url)
                    else url_for("student.dashboard"))


# ---------------------------------------------------------------- password reset
@bp.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("5 per hour", methods=["POST"])
def forgot_password():
    form = ForgotForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()
        if user and user.is_active_account:
            link = external_url("auth.reset_password", token=make_token("reset", user))
            send_mail(user.email, "Password reset · إعادة تعيين كلمة المرور",
                      f"لإعادة تعيين كلمة المرور افتح الرابط (صالح ساعة واحدة، ويُستخدم مرة واحدة):\n{link}\n\n"
                      f"Reset your password with this link (valid 1 hour, single use):\n{link}\n\n"
                      "إن لم تطلب ذلك فتجاهل الرسالة · If you did not request this, ignore it.", "reset")
            audit_as(user.email, "password_reset_requested")
        flash("auth.reset_sent", "info")  # same answer whether or not the account exists
        return redirect(url_for("auth.login"))
    return render_template("auth/forgot.html", form=form, mail_on=current_app.config["MAIL_ENABLED"])


@bp.route("/reset-password/<token>", methods=["GET", "POST"])
@limiter.limit("10 per hour", methods=["POST"])
def reset_password(token):
    data = read_token("reset", token, 3600)
    user = db.session.get(User, data["u"]) if data else None
    if (not user or user.email != data["e"] or user.password_hash[-10:] != data["f"]
            or not user.is_active_account):
        flash("auth.reset_bad", "error")
        return redirect(url_for("auth.forgot_password"))
    form = ResetForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        user.must_change_password = False
        user.failed_logins, user.locked_until = 0, None
        user.email_verified = True  # proved control of the mailbox
        db.session.commit()
        audit_as(user.email, "password_reset_done")
        flash("account.password_changed", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/reset.html", form=form)


# ---------------------------------------------------------------- account
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


# ---------------------------------------------------------------- 2FA management
@bp.route("/account/2fa", methods=["GET", "POST"])
@login_required
def twofa_manage():
    """GET: status page / setup QR. POST (action=start|enable|disable)."""
    from ..forms import EmptyForm
    action = request.form.get("action")
    enable_form, disable_form = TwoFAForm(prefix="en"), TwoFADisableForm(prefix="dis")
    if request.method == "POST":
        if action == "start" and EmptyForm().validate_on_submit() and not current_user.totp_enabled:
            session["totp_setup"] = totp.new_secret()
            return redirect(url_for("auth.twofa_manage"))
        if action == "enable" and enable_form.validate_on_submit():
            secret = session.get("totp_setup")
            step = totp.verify(secret, enable_form.code.data, 0) if secret else None
            if step:
                codes, stored = totp.new_backup_codes()
                u = current_user
                u.totp_secret, u.totp_enabled, u.totp_last_step, u.backup_codes = secret, True, step, stored
                db.session.commit()
                session.pop("totp_setup", None)
                audit("2fa_enabled", u.email)
                return render_template("auth/twofa_codes.html", codes=codes)  # shown once
            enable_form.code.errors.append("val.2fa_code")
        if action == "disable" and disable_form.validate_on_submit():
            u = current_user
            if current_app.config["REQUIRE_STAFF_2FA"] and u.is_staff:
                abort(403)
            if not u.check_password(disable_form.password.data):
                disable_form.password.errors.append("val.password_wrong")
            elif not totp.verify(u.totp_secret, disable_form.code.data, u.totp_last_step) \
                    and totp.consume_backup_code(u.backup_codes, disable_form.code.data) is None:
                disable_form.code.errors.append("val.2fa_code")
            else:
                u.totp_secret, u.totp_enabled, u.backup_codes, u.totp_last_step = None, False, "", 0
                db.session.commit()
                audit("2fa_disabled", u.email)
                flash("2fa.disabled", "info")
                return redirect(url_for("auth.twofa_manage"))
    secret = session.get("totp_setup")
    qr = uri = None
    if secret and not current_user.totp_enabled:
        uri = totp.provisioning_uri(current_user.email, secret)
        qr = totp.qr_svg(uri)
    return render_template("auth/twofa.html", enable_form=enable_form, disable_form=disable_form,
                           secret=secret, qr=qr, required=current_app.config["REQUIRE_STAFF_2FA"] and current_user.is_staff,
                           codes_left=len([x for x in (current_user.backup_codes or "").split("\n") if x]))
