from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from flask_login import current_user

from ..extensions import db, limiter
from ..forms import ContactForm
from ..models import (Category, ConsultationService, ContactMessage, Course, Testimonial,
                      Workshop, utcnow)
from ..security import audit, is_safe_next
from .. import current_lang
from ..i18n import LANGS, site_text

bp = Blueprint("main", __name__)


@bp.app_context_processor
def _site_helpers():
    lang = current_lang()
    return {"site": lambda key: site_text(key, lang)}


@bp.route("/")
def home():
    categories = Category.query.order_by(Category.position).all()
    featured = (Course.query.filter_by(is_published=True, is_featured=True)
                .order_by(Course.created_at.desc()).limit(6).all())
    workshops = (Workshop.query.filter(Workshop.is_published.is_(True), Workshop.starts_at > utcnow())
                 .order_by(Workshop.starts_at).limit(3).all())
    testimonials = Testimonial.query.filter_by(is_published=True).limit(3).all()
    stats = {
        "courses": Course.query.filter_by(is_published=True).count(),
        "workshops": Workshop.query.filter(Workshop.is_published.is_(True),
                                           Workshop.starts_at > utcnow()).count(),
        "services": ConsultationService.query.filter_by(is_published=True).count(),
        "categories": len(categories),
    }
    return render_template("pages/home.html", categories=categories, featured=featured,
                           workshops=workshops, testimonials=testimonials, stats=stats)


@bp.route("/about")
def about():
    return render_template("pages/about.html")


@bp.route("/contact", methods=["GET", "POST"])
@limiter.limit("5 per hour", methods=["POST"])
def contact():
    form = ContactForm(topic=request.args.get("topic", "general"))
    if current_user.is_authenticated and request.method == "GET":
        form.name.data, form.email.data = current_user.name, current_user.email
    if form.validate_on_submit():
        if form.website.data:  # honeypot tripped: pretend success, store nothing
            flash("contact.sent", "success")
            return redirect(url_for("main.contact"))
        db.session.add(ContactMessage(name=form.name.data, email=form.email.data.lower(),
                                      topic=form.topic.data, message=form.message.data))
        db.session.commit()
        flash("contact.sent", "success")
        return redirect(url_for("main.contact"))
    return render_template("pages/contact.html", form=form)


@bp.route("/lang/<code>")
def set_language(code):
    if code not in LANGS:
        abort(404)
    session["lang"] = code
    if current_user.is_authenticated and current_user.locale != code:
        current_user.locale = code
        db.session.commit()
    target = request.args.get("next")
    return redirect(target if is_safe_next(target) else url_for("main.home"))


@bp.route("/robots.txt")
def robots():
    return ("User-agent: *\nDisallow: /admin/\nDisallow: /dashboard\nDisallow: /account\n",
            200, {"Content-Type": "text/plain; charset=utf-8"})
