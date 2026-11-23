from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from ..extensions import db, limiter
from ..forms import EmptyForm
from ..models import (ENROLL_ACTIVE, ENROLL_PENDING, LEVELS, Category, Course, Enrollment,
                      Lesson, LessonProgress)
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
    return render_template("courses/detail.html", course=course, enrollment=_enrollment(course),
                           related=related, form=EmptyForm())


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
    flash("course.enrolled" if status == ENROLL_ACTIVE else "course.pending", "success")
    return redirect(url_for("courses.learn" if status == ENROLL_ACTIVE else "courses.detail", slug=slug))


@bp.route("/<slug>/cancel", methods=["POST"])
@login_required
def cancel(slug):
    course = _course_or_404(slug)
    enr = _enrollment(course)
    if not EmptyForm().validate_on_submit() or not enr:
        abort(400)
    enr.status = "cancelled"
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
    return render_template("courses/learn.html", course=course, done=done, current=current,
                           progress=enr.progress(), form=EmptyForm())


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
