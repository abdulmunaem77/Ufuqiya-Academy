from datetime import datetime, timedelta, timezone

from flask import Blueprint, abort, current_app, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from ..extensions import db, limiter
from ..forms import BookingForm, EmptyForm
from ..models import ConsultationBooking, ConsultationService, utcnow
from ..security import audit

bp = Blueprint("consult", __name__, url_prefix="/consultations")


def _service_or_404(slug):
    s = ConsultationService.query.filter_by(slug=slug).first_or_404()
    if not s.is_published:
        abort(404)
    return s


@bp.route("/")
def index():
    services = ConsultationService.query.filter_by(is_published=True).order_by(ConsultationService.id).all()
    return render_template("consult/index.html", services=services)


@bp.route("/<slug>/book", methods=["GET", "POST"])
@login_required
@limiter.limit("10 per hour", methods=["POST"])
def book(slug):
    service = _service_or_404(slug)
    form = BookingForm()
    if form.validate_on_submit():
        local = form.when.data.replace(tzinfo=current_app.config["ACADEMY_TZ"])
        when = local.astimezone(timezone.utc).replace(tzinfo=None)
        now = utcnow()
        if when < now + timedelta(hours=24):
            form.when.errors.append("val.booking_soon")
        elif when > now + timedelta(days=90):
            form.when.errors.append("val.booking_far")
        elif ConsultationBooking.query.filter(
                ConsultationBooking.user_id == current_user.id,
                ConsultationBooking.service_id == service.id,
                ConsultationBooking.status.in_(("pending", "confirmed"))).count() >= 2:
            flash("consult.limit", "error")
        else:
            b = ConsultationBooking(user_id=current_user.id, service_id=service.id,
                                    preferred_at=when, notes=form.notes.data or "")
            db.session.add(b)
            db.session.commit()
            audit("consult_book", f"booking:{b.id}")
            flash("consult.booked", "success")
            return redirect(url_for("student.dashboard"))
    return render_template("consult/book.html", service=service, form=form)


@bp.route("/booking/<int:booking_id>/cancel", methods=["POST"])
@login_required
def cancel(booking_id):
    b = db.session.get(ConsultationBooking, booking_id)
    if not b or b.user_id != current_user.id:  # ownership check (no IDOR)
        abort(404)
    if not EmptyForm().validate_on_submit() or b.status not in ("pending", "confirmed"):
        abort(400)
    b.status = "cancelled"
    db.session.commit()
    audit("consult_cancel", f"booking:{b.id}")
    flash("consult.cancelled", "info")
    return redirect(url_for("student.dashboard"))
