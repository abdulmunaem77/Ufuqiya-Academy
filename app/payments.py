"""Manual-payment workflow (no gateway, no online charging)."""
from flask import current_app

from .extensions import db
from .models import (ENROLL_ACTIVE, ConsultationBooking, Enrollment, Payment, WorkshopRegistration,
                     utcnow)


def get_or_create_payment(user, kind, target_id, title, amount):
    p = Payment.query.filter_by(user_id=user.id, kind=kind, target_id=target_id).first()
    if p and p.status != "cancelled":
        return p
    if p:  # re-request after cancellation: reuse the row
        p.status, p.reference, p.note, p.decided_at, p.decided_by = "awaiting", "", "", None, None
    else:
        p = Payment(user_id=user.id, kind=kind, target_id=target_id)
        db.session.add(p)
    p.title, p.amount, p.currency = title[:300], amount, current_app.config["DEFAULT_CURRENCY"]
    db.session.commit()
    return p


def payment_for(user, kind, target_id):
    return Payment.query.filter_by(user_id=user.id, kind=kind, target_id=target_id).first()


def target_of(payment):
    model = {"course": Enrollment, "workshop": WorkshopRegistration,
             "consultation": ConsultationBooking}[payment.kind]
    return db.session.get(model, payment.target_id)


def cancel_open_payment(user, kind, target_id):
    p = payment_for(user, kind, target_id)
    if p and p.status in ("awaiting", "submitted", "rejected"):
        p.status = "cancelled"


def confirm(payment, staff):
    """Mark paid and release what was paid for."""
    t = target_of(payment)
    if t is not None:
        if payment.kind == "course" and t.status != "cancelled":
            t.status = ENROLL_ACTIVE
        elif payment.kind == "workshop" and t.status != "cancelled":
            t.status = "registered"
        # consultations: the slot itself is confirmed separately from Bookings
    payment.status, payment.decided_at, payment.decided_by = "confirmed", utcnow(), staff.id


def reject(payment, staff):
    payment.status, payment.decided_at, payment.decided_by = "rejected", utcnow(), staff.id
