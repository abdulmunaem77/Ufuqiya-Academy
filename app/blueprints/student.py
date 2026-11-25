from flask import Blueprint, abort, redirect, render_template, url_for
from flask_login import current_user, login_required

from ..forms import EmptyForm
from ..security import is_safe_next
from ..extensions import db
from ..models import (Notification, Certificate, ConsultationBooking, Enrollment, Payment, Workshop,
                      WorkshopRegistration, utcnow)

bp = Blueprint("student", __name__)


@bp.route("/dashboard")
@login_required
def dashboard():
    enrollments = (Enrollment.query.filter(Enrollment.user_id == current_user.id,
                                           Enrollment.status != "cancelled")
                   .order_by(Enrollment.created_at.desc()).all())
    rows = [(e, e.progress()) for e in enrollments]
    regs = (WorkshopRegistration.query.join(Workshop).filter(
        WorkshopRegistration.user_id == current_user.id, WorkshopRegistration.status.in_(("registered", "pending")))
        .order_by(Workshop.starts_at).all())
    bookings = (ConsultationBooking.query.filter_by(user_id=current_user.id)
                .order_by(ConsultationBooking.preferred_at.desc()).all())
    active = [r for r in rows if r[0].status == "active"]
    avg = round(sum(p[0] for _, p in active) / len(active)) if active else 0
    pays = {(p.kind, p.target_id): p for p in Payment.query.filter_by(user_id=current_user.id).all()
            if p.status != "cancelled"}
    certs = {c.course_id for c in Certificate.query.filter_by(user_id=current_user.id).all()}
    return render_template("student/dashboard.html", rows=rows, regs=regs, bookings=bookings,
                           avg=avg, now=utcnow(), form=EmptyForm(), pays=pays, certs=certs)


@bp.route("/notifications")
@login_required
def notifications():
    items = (Notification.query.filter_by(user_id=current_user.id)
             .order_by(Notification.created_at.desc(), Notification.id.desc()).limit(100).all())
    return render_template("student/notifications.html", items=items, form=EmptyForm())


@bp.route("/notifications/read-all", methods=["POST"])
@login_required
def notifications_read_all():
    if not EmptyForm().validate_on_submit():
        abort(400)
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    return redirect(url_for("student.notifications"))


@bp.route("/notifications/<int:nid>/open", methods=["POST"])
@login_required
def notification_open(nid):
    n = db.session.get(Notification, nid)
    if not n or n.user_id != current_user.id:  # ownership check
        abort(404)
    if not EmptyForm().validate_on_submit():
        abort(400)
    n.is_read = True
    db.session.commit()
    return redirect(n.url if n.url and is_safe_next(n.url) else url_for("student.notifications"))
