from flask import Blueprint, render_template
from flask_login import current_user, login_required

from ..forms import EmptyForm
from ..models import ConsultationBooking, Enrollment, WorkshopRegistration, Workshop, utcnow

bp = Blueprint("student", __name__)


@bp.route("/dashboard")
@login_required
def dashboard():
    enrollments = (Enrollment.query.filter(Enrollment.user_id == current_user.id,
                                           Enrollment.status != "cancelled")
                   .order_by(Enrollment.created_at.desc()).all())
    rows = [(e, e.progress()) for e in enrollments]
    regs = (WorkshopRegistration.query.join(Workshop).filter(
        WorkshopRegistration.user_id == current_user.id, WorkshopRegistration.status == "registered")
        .order_by(Workshop.starts_at).all())
    bookings = (ConsultationBooking.query.filter_by(user_id=current_user.id)
                .order_by(ConsultationBooking.preferred_at.desc()).all())
    active = [r for r in rows if r[0].status == "active"]
    avg = round(sum(p[0] for _, p in active) / len(active)) if active else 0
    return render_template("student/dashboard.html", rows=rows, regs=regs, bookings=bookings,
                           avg=avg, now=utcnow(), form=EmptyForm())
