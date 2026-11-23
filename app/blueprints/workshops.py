from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from ..extensions import db, limiter
from ..forms import EmptyForm
from ..models import Workshop, WorkshopRegistration, utcnow
from ..payments import cancel_open_payment, get_or_create_payment, payment_for
from ..security import audit, verified_or_redirect

bp = Blueprint("workshops", __name__, url_prefix="/workshops")


def _ws_or_404(slug):
    ws = Workshop.query.filter_by(slug=slug).first_or_404()
    if not ws.is_published and not (current_user.is_authenticated and current_user.can("workshops")):
        abort(404)
    return ws


def _reg(ws):
    if not current_user.is_authenticated:
        return None
    return WorkshopRegistration.query.filter_by(user_id=current_user.id, workshop_id=ws.id).first()


@bp.route("/")
def index():
    upcoming = (Workshop.query.filter(Workshop.is_published.is_(True), Workshop.starts_at > utcnow())
                .order_by(Workshop.starts_at).all())
    past = (Workshop.query.filter(Workshop.is_published.is_(True), Workshop.starts_at <= utcnow())
            .order_by(Workshop.starts_at.desc()).limit(6).all())
    return render_template("workshops/index.html", upcoming=upcoming, past=past)


@bp.route("/<slug>")
def detail(slug):
    ws = _ws_or_404(slug)
    reg = _reg(ws)
    live = reg if reg and reg.status in ("registered", "pending") else None
    pay = payment_for(current_user, "workshop", live.id) if live and live.status == "pending" else None
    return render_template("workshops/detail.html", ws=ws, reg=live, pay=pay, form=EmptyForm())


@bp.route("/<slug>/register", methods=["POST"])
@login_required
@limiter.limit("20 per hour")
def register(slug):
    ws = _ws_or_404(slug)
    if not ws.is_published or not EmptyForm().validate_on_submit():
        abort(400)
    if not ws.is_upcoming:
        flash("ws.closed", "error")
        return redirect(url_for("workshops.detail", slug=slug))
    reg = _reg(ws)
    if reg and reg.status in ("registered", "pending"):
        flash("ws.already", "info")
        return redirect(url_for("workshops.detail", slug=slug))
    blocked = verified_or_redirect(url_for("workshops.detail", slug=slug))
    if blocked:
        return blocked
    if ws.seats_left <= 0:
        flash("ws.full", "error")
        return redirect(url_for("workshops.detail", slug=slug))
    status = "registered" if not ws.price else "pending"  # paid seats are held until payment is confirmed
    try:
        if reg:
            reg.status = status
        else:
            db.session.add(WorkshopRegistration(user_id=current_user.id, workshop_id=ws.id, status=status))
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
    audit("workshop_register", f"workshop:{ws.id}", status)
    if status == "pending":
        reg = _reg(ws)
        pay = get_or_create_payment(current_user, "workshop", reg.id, ws.title_en, ws.price)
        flash("ws.pending", "success")
        return redirect(url_for("pay.view", pid=pay.id))
    flash("ws.registered", "success")
    return redirect(url_for("workshops.detail", slug=slug))


@bp.route("/<slug>/cancel", methods=["POST"])
@login_required
def cancel(slug):
    ws = _ws_or_404(slug)
    reg = _reg(ws)
    if not reg or not EmptyForm().validate_on_submit():
        abort(400)
    reg.status = "cancelled"
    cancel_open_payment(current_user, "workshop", reg.id)
    db.session.commit()
    audit("workshop_cancel", f"workshop:{ws.id}")
    flash("ws.cancelled", "info")
    return redirect(url_for("student.dashboard"))
