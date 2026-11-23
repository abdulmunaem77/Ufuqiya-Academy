"""Authorization helpers, audit logging and safe-redirect utilities."""
from functools import wraps
from urllib.parse import urljoin, urlparse

from flask import abort, flash, redirect, request, url_for
from flask_login import current_user

from .extensions import db
from .models import AuditLog


def is_safe_next(target):
    """Allow only same-host relative redirects (prevents open redirect)."""
    if not target or "\\" in target:
        return False
    ref = urlparse(request.host_url)
    test = urlparse(urljoin(request.host_url, target))
    return test.scheme in ("http", "https") and ref.netloc == test.netloc and target.startswith("/") \
        and not target.startswith("//")


def safe_next(default="main.home"):
    target = request.args.get("next") or request.form.get("next")
    return target if is_safe_next(target) else url_for(default)


def permission_required(permission):
    """Server-side RBAC check. 401-style redirect for anonymous, 403 otherwise."""
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            if not current_user.is_authenticated:
                return redirect(url_for("admin.login", next=request.full_path.rstrip("?")))
            if not current_user.is_staff or not current_user.can(permission):
                audit("access_denied", request.path)
                abort(403)
            return fn(*a, **kw)
        return wrapper
    return deco


def audit(action, target="", details="", commit=True):
    """Append an audit row. Never raises into the request."""
    try:
        actor = current_user if current_user and current_user.is_authenticated else None
        db.session.add(AuditLog(
            actor_id=actor.id if actor else None,
            actor_email=(actor.email if actor else None),
            action=action[:60], target=str(target)[:120], details=str(details)[:1000],
            ip=(request.remote_addr or "")[:64]))
        if commit:
            db.session.commit()
    except Exception:  # audit must not break the user flow
        db.session.rollback()


def audit_as(email, action, target="", details=""):
    """Audit an event for an identity that is not (yet) logged in."""
    try:
        db.session.add(AuditLog(actor_email=(email or "")[:254], action=action[:60],
                                target=str(target)[:120], details=str(details)[:1000],
                                ip=(request.remote_addr or "")[:64]))
        db.session.commit()
    except Exception:
        db.session.rollback()


def flash_t(key, category="info"):
    flash(key, category)  # translated at render time by the template
