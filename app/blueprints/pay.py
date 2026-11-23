from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from ..extensions import db, limiter
from ..forms import PaymentSubmitForm
from ..i18n import site_text
from ..mailer import notify_staff
from ..models import Payment
from ..security import audit
from .. import current_lang

bp = Blueprint("pay", __name__, url_prefix="/payments")


@bp.route("/<int:pid>", methods=["GET", "POST"])
@login_required
@limiter.limit("20 per hour", methods=["POST"])
def view(pid):
    p = db.session.get(Payment, pid)
    if not p or p.user_id != current_user.id:  # ownership check
        abort(404)
    form = PaymentSubmitForm()
    editable = p.status in ("awaiting", "rejected")
    if editable and form.validate_on_submit():
        p.method, p.reference, p.note, p.status = form.method.data, form.reference.data, form.note.data or "", "submitted"
        db.session.commit()
        audit("payment_submit", f"payment:{p.id}")
        notify_staff(f"Payment submitted #{p.id}", f"{current_user.email} submitted reference for: {p.title} ({p.amount} {p.currency}).", "payment_submitted")
        flash("pay.submitted", "success")
        return redirect(url_for("pay.view", pid=p.id))
    return render_template("pay/view.html", p=p, form=form, editable=editable,
                           instructions=site_text("payment_instructions", current_lang()))
