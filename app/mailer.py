"""E-mail: always recorded in ``EmailOutbox``; additionally sent over SMTP when
MAIL_SERVER + MAIL_FROM are configured.  Never raises into a request."""
import logging
import smtplib
from email.message import EmailMessage

from flask import current_app, url_for
from itsdangerous import BadData, URLSafeTimedSerializer

from .extensions import db
from .models import EmailOutbox

log = logging.getLogger("wahj.mail")


def _clean(value):
    return " ".join(str(value).replace("\r", " ").replace("\n", " ").split())  # no header injection


def send_mail(to, subject, body, kind):
    cfg = current_app.config
    row = EmailOutbox(to_email=_clean(to)[:254], kind=kind[:40], subject=_clean(subject)[:300], body=body)
    if cfg.get("MAIL_ENABLED"):
        try:
            msg = EmailMessage()
            msg["From"], msg["To"], msg["Subject"] = _clean(cfg["MAIL_FROM"]), row.to_email, row.subject
            msg.set_content(body)
            if cfg["MAIL_USE_SSL"]:
                server = smtplib.SMTP_SSL(cfg["MAIL_SERVER"], cfg["MAIL_PORT"], timeout=10)
            else:
                server = smtplib.SMTP(cfg["MAIL_SERVER"], cfg["MAIL_PORT"], timeout=10)
            with server:
                if cfg["MAIL_USE_TLS"] and not cfg["MAIL_USE_SSL"]:
                    server.starttls()
                if cfg["MAIL_USERNAME"]:
                    server.login(cfg["MAIL_USERNAME"], cfg["MAIL_PASSWORD"])
                server.send_message(msg)
            row.status = "sent"
        except Exception as exc:  # network/auth errors must not break the page
            row.status, row.error = "failed", f"{type(exc).__name__}"[:300]
            log.warning("SMTP send failed: %s", type(exc).__name__)
    else:
        row.status = "not_configured"
    try:
        db.session.add(row)
        db.session.commit()
    except Exception:
        db.session.rollback()
    return row


def notify_staff(subject, body, kind):
    to = current_app.config.get("MAIL_ADMIN_TO")
    if to:
        send_mail(to, subject, body, kind)


# ---- signed one-time-ish tokens ------------------------------------------------
def _ser(purpose):
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=f"ufuqia-{purpose}")  # legacy salt kept on purpose: renaming would invalidate links already e-mailed


def make_token(purpose, user):
    # The password-hash tail ties reset tokens to the current password: using
    # one (or changing the password) invalidates every outstanding token.
    return _ser(purpose).dumps({"u": user.id, "e": user.email, "f": user.password_hash[-10:]})


def read_token(purpose, token, max_age):
    try:
        return _ser(purpose).loads(token, max_age=max_age)
    except BadData:
        return None


def external_url(endpoint, **values):
    base = current_app.config.get("PUBLIC_BASE_URL")
    if base:
        return base + url_for(endpoint, **values)
    return url_for(endpoint, _external=True, **values)
