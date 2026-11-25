from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from ..extensions import db, limiter
from ..forms import EmptyForm, ReviewForm
import secrets

from ..media import embed_url
from ..models import (ENROLL_ACTIVE, ENROLL_PENDING, LEVELS, Category, Certificate, Course, Enrollment,
                      Lesson, LessonProgress, Review)
from ..payments import cancel_open_payment, get_or_create_payment, payment_for
from ..security import verified_or_redirect
from ..security import audit

bp = Blueprint("courses", __name__, url_prefix="/courses")


def _like(term):
    term = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{term}%"


@bp.route("/")
def index():
    q = (request.args.get("q") or "").strip()[:80]
    cat = (request.args.get("category") or "").strip()[:80]
    level = request.args.get("level") if request.args.get("level") in LEVELS else ""
    price = request.args.get("price") if request.args.get("price") in ("free", "paid") else ""
    sort = request.args.get("sort") if request.args.get("sort") in ("new", "price_asc", "price_desc") else "new"
    page = request.args.get("page", 1, type=int) or 1

    query = Course.query.filter_by(is_published=True)
    if q:
        pat = _like(q)
        query = query.filter(or_(*(getattr(Course, c).ilike(pat, escape="\\") for c in
                                   ("title_ar", "title_en", "summary_ar", "summary_en",
                                    "description_ar", "description_en"))))
    category = Category.query.filter_by(slug=cat).first() if cat else None
    if category:
        query = query.filter(Course.category_id == category.id)
    if level:
        query = query.filter(Course.level == level)
    if price == "free":
        query = query.filter(Course.price == 0)
    elif price == "paid":
        query = query.filter(Course.price > 0)
    order = {"new": Course.created_at.desc(), "price_asc": Course.price.asc(),
             "price_desc": Course.price.desc()}[sort]
    pagination = query.order_by(order, Course.id.desc()).paginate(
        page=max(page, 1), per_page=current_app.config["PER_PAGE"], error_out=False)
    categories = Category.query.order_by(Category.position).all()
    return render_template("courses/index.html", pagination=pagination, categories=categories,
                           q=q, cat=cat if category else "", level=level, price=price, sort=sort,
                           levels=LEVELS)


def _course_or_404(slug):
    course = Course.query.filter_by(slug=slug).first_or_404()
    if not course.is_published and not (current_user.is_authenticated and current_user.can("courses")):
        abort(404)
    return course


def _enrollment(course):
    if not current_user.is_authenticated:
        return None
    return Enrollment.query.filter_by(user_id=current_user.id, course_id=course.id).first()


@bp.route("/<slug>")
def detail(slug):
    course = _course_or_404(slug)
    related = (Course.query.filter(Course.category_id == course.category_id, Course.id != course.id,
                                   Course.is_published.is_(True)).limit(3).all())
    enr = _enrollment(course)
    pay = payment_for(current_user, "course", enr.id) if enr and enr.status == "pending" else None
    reviews = (Review.query.filter_by(course_id=course.id, is_visible=True)
               .order_by(Review.created_at.desc()).limit(20).all())
    mine = Review.query.filter_by(course_id=course.id, user_id=current_user.id).first() \
        if current_user.is_authenticated else None
    review_form = ReviewForm(rating=str(mine.rating) if mine else "5", comment=mine.comment if mine else "")
    can_review = bool(enr and enr.status == ENROLL_ACTIVE)
    return render_template("courses/detail.html", course=course, enrollment=enr, pay=pay,
                           related=related, form=EmptyForm(), reviews=reviews, summary=course.rating_summary(),
                           mine=mine, can_review=can_review, review_form=review_form)


@bp.route("/<slug>/enroll", methods=["POST"])
@login_required
@limiter.limit("20 per hour")
def enroll(slug):
    course = _course_or_404(slug)
    if not course.is_published or not EmptyForm().validate_on_submit():
        abort(400)
    existing = _enrollment(course)
    if existing and existing.status != "cancelled":
        flash("course.already", "info")
        return redirect(url_for("courses.detail", slug=slug))
    blocked = verified_or_redirect(url_for("courses.detail", slug=slug))
    if blocked:
        return blocked
    status = ENROLL_ACTIVE if course.is_free else ENROLL_PENDING
    try:
        if existing:  # re-enrol after cancellation
            existing.status = status
        else:
            db.session.add(Enrollment(user_id=current_user.id, course_id=course.id, status=status))
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
    audit("enroll", f"course:{course.id}", status)
    if status == ENROLL_ACTIVE:
        flash("course.enrolled", "success")
        return redirect(url_for("courses.learn", slug=slug))
    enr = _enrollment(course)
    pay = get_or_create_payment(current_user, "course", enr.id, course.title_en, course.price)
    flash("course.pending", "success")
    return redirect(url_for("pay.view", pid=pay.id))


@bp.route("/<slug>/cancel", methods=["POST"])
@login_required
def cancel(slug):
    course = _course_or_404(slug)
    enr = _enrollment(course)
    if not EmptyForm().validate_on_submit() or not enr:
        abort(400)
    enr.status = "cancelled"
    cancel_open_payment(current_user, "course", enr.id)
    db.session.commit()
    audit("enroll_cancel", f"course:{course.id}")
    flash("course.cancelled", "info")
    return redirect(url_for("student.dashboard"))


@bp.route("/<slug>/learn")
@login_required
def learn(slug):
    course = _course_or_404(slug)
    enr = _enrollment(course)
    if not enr or enr.status != ENROLL_ACTIVE:
        flash("course.need_enroll", "info")
        return redirect(url_for("courses.detail", slug=slug))
    done = {p.lesson_id for p in LessonProgress.query.filter_by(user_id=current_user.id).filter(
        LessonProgress.lesson_id.in_([l.id for l in course.lessons] or [0])).all()}
    current_id = request.args.get("lesson", type=int)
    current = next((l for l in course.lessons if l.id == current_id), None) or next(
        (l for l in course.lessons if l.id not in done), None) or (course.lessons[0] if course.lessons else None)
    progress = enr.progress()
    return render_template("courses/learn.html", course=course, done=done, current=current,
                           progress=progress, form=EmptyForm(), video=embed_url(current.video_url) if current else None,
                           complete=progress[2] > 0 and progress[1] == progress[2])


@bp.route("/<slug>/lessons/<int:lesson_id>/toggle", methods=["POST"])
@login_required
def toggle_lesson(slug, lesson_id):
    course = _course_or_404(slug)
    enr = _enrollment(course)
    lesson = db.session.get(Lesson, lesson_id)
    if (not enr or enr.status != ENROLL_ACTIVE or not lesson or lesson.course_id != course.id
            or not EmptyForm().validate_on_submit()):
        abort(403 if not enr else 400)
    row = LessonProgress.query.filter_by(user_id=current_user.id, lesson_id=lesson.id).first()
    if row:
        db.session.delete(row)
    else:
        db.session.add(LessonProgress(user_id=current_user.id, lesson_id=lesson.id))
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
    return redirect(url_for("courses.learn", slug=slug, lesson=lesson.id))


def _new_code():
    return "UF-" + secrets.token_hex(5).upper()


@bp.route("/<slug>/certificate")
@login_required
def certificate(slug):
    """Issued only at 100% lesson completion; a public verify page exists per code."""
    course = _course_or_404(slug)
    enr = _enrollment(course)
    if not enr or enr.status != ENROLL_ACTIVE:
        abort(403)
    pct, done, total = enr.progress()
    if total == 0 or done < total:
        flash("cert.not_ready", "info")
        return redirect(url_for("courses.learn", slug=slug))
    cert = Certificate.query.filter_by(user_id=current_user.id, course_id=course.id).first()
    if not cert:
        cert = Certificate(user_id=current_user.id, course_id=course.id, code=_new_code(),
                           holder_name=current_user.name)
        db.session.add(cert)
        db.session.commit()
        audit("certificate_issued", f"certificate:{cert.id}")
        from ..notify import notify
        notify(current_user.id, "certificate", "صدرت شهادتك", "Your certificate was issued",
               course.title_ar, course.title_en, url_for("courses.certificate", slug=slug), commit=True)
    return render_template("courses/certificate.html", cert=cert, verify_url=url_for("main.verify_certificate", code=cert.code, _external=True))


@bp.route("/<slug>/review", methods=["POST"])
@login_required
@limiter.limit("20 per hour")
def review(slug):
    course = _course_or_404(slug)
    enr = _enrollment(course)
    if not enr or enr.status != ENROLL_ACTIVE:
        abort(403)  # only active enrolees may rate
    form = ReviewForm()
    if not form.validate_on_submit():
        flash("review.invalid", "error")
        return redirect(url_for("courses.detail", slug=slug) + "#reviews")
    row = Review.query.filter_by(user_id=current_user.id, course_id=course.id).first()
    if row:
        row.rating, row.comment = int(form.rating.data), form.comment.data or ""
    else:
        db.session.add(Review(user_id=current_user.id, course_id=course.id, rating=int(form.rating.data),
                              comment=form.comment.data or ""))
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
    audit("review_save", f"course:{course.id}", form.rating.data)
    flash("review.saved", "success")
    return redirect(url_for("courses.detail", slug=slug) + "#reviews")
