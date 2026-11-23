"""Lightweight bilingual (Arabic RTL / English LTR) translation layer.

Every UI string lives in ``T`` as ``key: (arabic, english)``.  Templates call
``t('key', n=3)``.  tests/test_i18n.py fails if a key used by a template or
form is missing in either language.
"""
LANGS = ("ar", "en")

MONTHS = {
    "ar": ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر",
           "أكتوبر", "نوفمبر", "ديسمبر"],
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
}


def month_name(m, lang):
    return MONTHS[lang if lang in MONTHS else "ar"][m - 1]


# Editable site copy (managed from the control panel). key -> (ar, en)
SITE_DEFAULTS = {
    "hero_title": ("معرفة نافعة، ومهارات تصنع المستقبل", "Useful knowledge, and skills that shape the future"),
    "hero_lead": ("دورات احترافية وورش تفاعلية مباشرة واستشارات متخصصة في الذكاء الاصطناعي والتقنية والتسويق الرقمي والتطوير المهني.",
                  "Professional courses, live interactive workshops and expert consultations in AI, technology, digital marketing and professional development."),
    "about_text": ("أكاديمية أفقيا للتدريب والاستشارات منصة تعليمية تؤمن بأن المعرفة النافعة والمهارات التطبيقية هي طريق الأفراد والمؤسسات نحو المستقبل. نقدّم محتوى عمليًا واضحًا، ونرافق المتعلّم من الفهم إلى التطبيق.",
                   "Ufuqia Academy for Training & Consulting is a learning platform built on the belief that useful knowledge and applied skills are the way forward for people and organisations. We offer clear, practical content and accompany learners from understanding to application."),
    "footer_blurb": ("معرفة نافعة، ومهارات تصنع المستقبل.", "Useful knowledge, and skills that shape the future."),
    "contact_email": ("info@example.com (بريد تجريبي — يُستبدل ببريد الأكاديمية)", "info@example.com (placeholder — replace with the academy's address)"),
    "payment_instructions": ("للدفع حوّل المبلغ إلى حساب الأكاديمية ثم أدخل رقم الحوالة/المرجع في النموذج أدناه. (بيانات الحساب: تُضاف من لوحة التحكم ← محتوى الموقع.)",
                             "To pay, transfer the amount to the academy's account, then enter the transfer number/reference in the form below. (Account details: add them in Control panel → Site content.)"),
    "contact_hours": ("الأحد – الخميس، 9 صباحًا – 5 مساءً", "Sunday – Thursday, 9:00 – 17:00"),
}
CONTENT_KEYS = tuple(SITE_DEFAULTS)


def site_default(key, lang):
    ar, en = SITE_DEFAULTS[key]
    return ar if lang == "ar" else en


def site_text(key, lang):
    """DB value (owner-edited) with fallback to the built-in default."""
    try:
        from .extensions import db
        from .models import SiteContent
        row = db.session.get(SiteContent, key)
        if row:
            v = row.value_ar if lang == "ar" else row.value_en
            if v:
                return v
    except Exception:
        pass
    return site_default(key, lang) if key in SITE_DEFAULTS else ""


T = {
    # ---- brand / nav -----------------------------------------------------
    "brand.name": ("أكاديمية أفقيا للتدريب والاستشارات", "Ufuqia Academy – Training & Consulting"),
    "brand.short": ("أفقيا", "Ufuqia"),
    "brand.tagline": ("معرفة نافعة، ومهارات تصنع المستقبل.", "Useful knowledge, and skills that shape the future."),
    "notice.sample": ("نسخة تجريبية: الدورات والمدرّبون والآراء المعروضة محتوى خيالي لأغراض العرض فقط.",
                      "Demo edition: the courses, instructors and testimonials shown are fictional content for demonstration only."),
    "nav.skip": ("تخطَّ إلى المحتوى", "Skip to content"),
    "nav.menu": ("القائمة", "Menu"),
    "nav.main": ("التنقل الرئيسي", "Main navigation"),
    "nav.home": ("الرئيسية", "Home"),
    "nav.courses": ("الدورات", "Courses"),
    "nav.workshops": ("الورش", "Workshops"),
    "nav.consult": ("الاستشارات", "Consulting"),
    "nav.about": ("عن الأكاديمية", "About"),
    "nav.contact": ("تواصل معنا", "Contact"),
    "nav.login": ("تسجيل الدخول", "Log in"),
    "nav.register": ("إنشاء حساب", "Sign up"),
    "nav.logout": ("تسجيل الخروج", "Log out"),
    "nav.dashboard": ("لوحتي", "My dashboard"),
    "nav.account": ("حسابي", "My account"),
    "nav.admin": ("لوحة التحكم", "Control panel"),
    "footer.explore": ("استكشف", "Explore"),
    "footer.account": ("الحساب", "Account"),
    "footer.contact": ("تواصل", "Contact"),
    "footer.rights": ("جميع الحقوق محفوظة", "All rights reserved"),

    # ---- common ------------------------------------------------------------
    "common.free": ("مجاني", "Free"),
    "common.sample": ("محتوى تجريبي", "Sample"),
    "common.draft": ("مسودة", "Draft"),
    "common.save": ("حفظ", "Save"),
    "common.cancel": ("إلغاء", "Cancel"),
    "common.edit": ("تعديل", "Edit"),
    "common.delete": ("حذف", "Delete"),
    "common.view": ("عرض", "View"),
    "common.back": ("رجوع", "Back"),
    "common.all": ("الكل", "All"),
    "common.close": ("إغلاق", "Close"),
    "common.next": ("التالي", "Next"),
    "common.prev": ("السابق", "Previous"),
    "common.view_all": ("عرض الكل", "View all"),
    "common.none_yet": ("لا يوجد محتوى بعد.", "Nothing here yet."),

    # ---- home --------------------------------------------------------------
    "hero.eyebrow": ("التعلّم عن بُعد · ورش مباشرة · استشارات", "Online learning · Live workshops · Consulting"),
    "hero.cta_courses": ("استعرض الدورات", "Browse courses"),
    "hero.cta_consult": ("احجز استشارة", "Book a consultation"),
    "search.label": ("ابحث عن دورة", "Find a course"),
    "search.placeholder": ("مثال: الذكاء الاصطناعي، التسويق…", "e.g. AI, marketing…"),
    "search.go": ("بحث", "Search"),
    "stats.courses": ("دورة منشورة", "published courses"),
    "stats.workshops": ("ورشة قادمة", "upcoming workshops"),
    "stats.services": ("خدمة استشارية", "consulting services"),
    "stats.categories": ("مجالات تعلّم", "learning areas"),
    "home.cats_eyebrow": ("مجالات التعلّم", "Learning areas"),
    "home.cats_title": ("اختر مجالك", "Choose your path"),
    "home.featured_eyebrow": ("دورات مميّزة", "Featured courses"),
    "home.featured_title": ("ابدأ من هنا", "Start here"),
    "home.ws_eyebrow": ("مباشر عبر الإنترنت", "Live online"),
    "home.ws_title": ("ورش تفاعلية قادمة", "Upcoming interactive workshops"),
    "home.consult_eyebrow": ("استشارات احترافية", "Professional consulting"),
    "home.consult_title": ("جلسة واحدة قد تختصر عليك شهورًا", "One session can save you months"),
    "home.consult_text": ("احجز جلسة مع مدرّب مختص لتحديد خطواتك التالية بوضوح، سواء كنت فردًا أو فريقًا أو مؤسسة.",
                          "Book a session with a specialist to define your next steps clearly — whether you are an individual, a team or an organisation."),
    "home.consult_cta": ("استعرض الاستشارات", "See consulting services"),
    "home.step1": ("اختر الخدمة الاستشارية المناسبة", "Choose the right consulting service"),
    "home.step2": ("حدّد الموعد المفضّل واكتب احتياجك", "Pick a preferred time and describe your need"),
    "home.step3": ("يؤكّد فريقنا الموعد معك", "Our team confirms the slot with you"),
    "home.testi_eyebrow": ("آراء المتعلّمين", "Learner voices"),
    "home.testi_title": ("ماذا سيقول متعلّمونا", "What learners will say"),
    "home.testi_note": ("النصوص أعلاه أمثلة خيالية للتصميم فقط وليست آراء حقيقية.",
                        "The texts above are fictional design examples, not real opinions."),
    "home.cta_title": ("جاهز لخطوتك التالية؟", "Ready for your next step?"),
    "home.cta_text": ("أنشئ حسابك المجاني وتابع تقدّمك في دوراتك من لوحة واحدة.", "Create your free account and track your progress from one dashboard."),

    # ---- about / contact ----------------------------------------------------
    "about.mission_title": ("رسالتنا", "Our mission"),
    "about.v1_t": ("نفع حقيقي", "Real usefulness"), "about.v1_d": ("نختار ما يُطبَّق في العمل والحياة، لا ما يُحفظ فقط.", "We choose what applies at work and in life, not just what is memorised."),
    "about.v2_t": ("مهارات تصنع الفرق", "Skills that matter"), "about.v2_d": ("تمارين ومشاريع صغيرة تُترجم المعرفة إلى قدرة.", "Exercises and small projects turn knowledge into ability."),
    "about.v3_t": ("مرافقة مستمرة", "Ongoing support"), "about.v3_d": ("ورش مباشرة واستشارات تكمل التعلّم الذاتي.", "Live workshops and consulting complement self-paced learning."),
    "contact.sub": ("استفسار عن دورة أو ورشة أو استشارة أو تدريب لمؤسستك؟ اكتب لنا.", "Questions about a course, workshop, consultation or training for your organisation? Write to us."),
    "contact.send": ("إرسال الرسالة", "Send message"),
    "contact.sent": ("تم استلام رسالتك، وسنرد عليك قريبًا.", "Your message was received; we will reply soon."),
    "contact.info": ("معلومات التواصل", "Contact details"),
    "contact.email": ("البريد الإلكتروني", "Email"),
    "contact.hours": ("ساعات العمل", "Working hours"),
    "contact.mode": ("نمط الخدمة", "Service mode"),
    "contact.mode_v": ("عن بُعد عبر الإنترنت", "Online, remote"),

    # ---- auth / account ----------------------------------------------------------
    "auth.login_title": ("أهلًا بعودتك", "Welcome back"),
    "auth.login_sub": ("سجّل الدخول لمتابعة دوراتك.", "Log in to continue your courses."),
    "auth.register_title": ("أنشئ حسابك", "Create your account"),
    "auth.register_sub": ("حساب الطالب مجاني ويتيح التسجيل والمتابعة.", "A student account is free and lets you enrol and track progress."),
    "auth.no_account": ("ليس لديك حساب؟", "No account yet?"),
    "auth.have_account": ("لديك حساب بالفعل؟", "Already have an account?"),
    "auth.invalid": ("بيانات الدخول غير صحيحة أو أن الحساب مقفل مؤقتًا.", "Incorrect credentials, or the account is temporarily locked."),
    "auth.logged_out": ("تم تسجيل خروجك.", "You have been logged out."),
    "auth.welcome": ("مرحبًا بك في أفقيا!", "Welcome to Ufuqia!"),
    "auth.password_hint": ("10 أحرف على الأقل، وتحتوي على حروف وأرقام.", "At least 10 characters, with letters and digits."),
    "account.profile": ("الملف الشخصي", "Profile"),
    "account.saved": ("تم حفظ التغييرات.", "Changes saved."),
    "account.security": ("الأمان", "Security"),
    "account.security_text": ("حدّث كلمة المرور بانتظام ولا تشاركها مع أحد.", "Update your password regularly and never share it."),
    "account.change_password": ("تغيير كلمة المرور", "Change password"),
    "account.password_changed": ("تم تغيير كلمة المرور.", "Password changed."),
    "account.must_change": ("لأسباب أمنية يجب تغيير كلمة المرور المؤقتة قبل المتابعة.", "For security you must change the temporary password before continuing."),
    "account.member_since": ("عضو منذ", "Member since"),

    # ---- courses ---------------------------------------------------------------
    "courses.sub": ("ابحث وصفِّ حسب المجال والمستوى والسعر.", "Search and filter by category, level and price."),
    "courses.count": ("{n} دورة", "{n} course(s)"),
    "courses.none": ("لا توجد دورات مطابقة. جرّب تعديل البحث.", "No matching courses. Try adjusting your search."),
    "filter.all_categories": ("كل المجالات", "All categories"),
    "filter.all_levels": ("كل المستويات", "All levels"),
    "filter.any_price": ("أي سعر", "Any price"),
    "filter.paid": ("مدفوع", "Paid"),
    "filter.sort": ("الترتيب", "Sort"),
    "filter.clear": ("مسح التصفية", "Clear filters"),
    "sort.new": ("الأحدث", "Newest"),
    "sort.price_asc": ("السعر: الأقل", "Price: low to high"),
    "sort.price_desc": ("السعر: الأعلى", "Price: high to low"),
    "level.beginner": ("مبتدئ", "Beginner"), "level.intermediate": ("متوسط", "Intermediate"), "level.advanced": ("متقدم", "Advanced"),
    "course.hours": ("{n} ساعة", "{n} h"),
    "course.minutes": ("{n} دقيقة", "{n} min"),
    "course.about": ("عن الدورة", "About this course"),
    "course.curriculum": ("محتوى الدورة", "Curriculum"),
    "course.instructor": ("المدرّب", "Instructor"),
    "course.lessons": ("الدروس", "Lessons"),
    "course.lesson_n": ("الدرس {n}", "Lesson {n}"),
    "course.related": ("دورات ذات صلة", "Related courses"),
    "course.enroll": ("سجّل في الدورة", "Enrol in this course"),
    "course.enroll_free": ("ابدأ مجانًا", "Start for free"),
    "course.login_to_enroll": ("سجّل الدخول للتسجيل", "Log in to enrol"),
    "course.continue": ("تابع التعلّم", "Continue learning"),
    "course.ask": ("لديك سؤال عن الدورة؟", "Questions about this course?"),
    "course.contact_us": ("تواصل معنا", "Contact us"),
    "course.pay_note": ("لا توجد بوابة دفع إلكتروني حاليًا: يُسجَّل طلبك وتؤكّد الأكاديمية الدفع معك يدويًا.",
                        "There is no online payment gateway yet: your request is recorded and the academy confirms payment with you manually."),
    "course.pending": ("طلبك قيد المراجعة. سيُفعَّل الوصول بعد تأكيد الدفع من الأكاديمية.", "Your request is pending. Access is activated once the academy confirms payment."),
    "course.enrolled": ("تم تسجيلك في الدورة. بالتوفيق!", "You are enrolled. Good luck!"),
    "course.already": ("أنت مسجَّل في هذه الدورة بالفعل.", "You are already enrolled in this course."),
    "course.cancelled": ("تم إلغاء تسجيلك في الدورة.", "Your enrolment was cancelled."),
    "course.need_enroll": ("سجّل في الدورة أولًا للوصول إلى دروسها.", "Enrol first to access the lessons."),
    "course.mark_done": ("تم إنجاز الدرس", "Mark as complete"),
    "course.mark_undone": ("إلغاء الإنجاز", "Mark as incomplete"),

    # ---- workshops ------------------------------------------------------------------
    "ws.sub": ("جلسات مباشرة وتفاعلية عبر الإنترنت مع مدرّبين مختصين.", "Live, interactive online sessions with specialist instructors."),
    "ws.upcoming": ("الورش القادمة", "Upcoming workshops"),
    "ws.upcoming_one": ("قادمة", "Upcoming"),
    "ws.past": ("ورش سابقة", "Past workshops"),
    "ws.none": ("لا توجد ورش مجدولة حاليًا.", "No workshops scheduled right now."),
    "ws.seats_left": ("{n} مقعد متاح", "{n} seat(s) left"),
    "ws.seats": ("المقاعد المتاحة", "Seats left"),
    "ws.ended": ("انتهت", "Ended"),
    "ws.host": ("مقدّم الورشة", "Host"),
    "ws.timezone": ("المنطقة الزمنية", "Time zone"),
    "ws.format": ("النمط", "Format"),
    "ws.online": ("مباشر عبر الإنترنت", "Live online"),
    "ws.register": ("سجّل مقعدك", "Reserve your seat"),
    "ws.login_to_register": ("سجّل الدخول للتسجيل", "Log in to register"),
    "ws.you_registered": ("أنت مسجَّل في هذه الورشة. سنرسل إليك تفاصيل الدخول.", "You are registered. We will send you the joining details."),
    "ws.registered": ("تم تسجيلك في الورشة.", "You are registered for the workshop."),
    "ws.already": ("أنت مسجَّل في هذه الورشة بالفعل.", "You are already registered."),
    "ws.full": ("اكتملت المقاعد.", "This workshop is full."),
    "ws.closed": ("انتهى موعد هذه الورشة.", "This workshop has already taken place."),
    "ws.cancel": ("إلغاء التسجيل", "Cancel registration"),
    "ws.cancel_confirm": ("هل تريد إلغاء تسجيلك في الورشة؟", "Cancel your registration for this workshop?"),
    "ws.cancelled": ("تم إلغاء تسجيلك.", "Your registration was cancelled."),

    # ---- consultations -------------------------------------------------------------------
    "consult.sub": ("جلسات فردية أو للفرق مع مختصين لتحديد الخطوة التالية بوضوح.", "One-to-one or team sessions with specialists to define your next step."),
    "consult.minutes": ("{n} دقيقة", "{n} min"),
    "consult.book": ("احجز الآن", "Book now"),
    "consult.how": ("يُرسَل الطلب أولًا بحالة «قيد الانتظار» ثم يؤكّد فريق الأكاديمية الموعد. لا يوجد دفع إلكتروني حاليًا.",
                    "Requests start as “pending”; the academy team then confirms the slot. There is no online payment yet."),
    "consult.pick": ("اختر الموعد المفضّل", "Choose your preferred time"),
    "consult.when_hint": ("بتوقيت الأكاديمية، بعد 24 ساعة على الأقل وخلال 90 يومًا.", "In academy time, at least 24 hours ahead and within 90 days."),
    "consult.request": ("أرسل طلب الحجز", "Send booking request"),
    "consult.summary": ("ملخص الخدمة", "Service summary"),
    "consult.pending_note": ("الموعد غير مؤكَّد حتى يراجعه فريق الأكاديمية.", "The slot is not confirmed until the academy team reviews it."),
    "consult.booked": ("تم إرسال طلب الحجز وهو قيد المراجعة.", "Booking request sent and pending review."),
    "consult.limit": ("لديك حجزان نشطان لهذه الخدمة بالفعل.", "You already have two active bookings for this service."),
    "consult.cancelled": ("تم إلغاء الحجز.", "Booking cancelled."),

    # ---- student dashboard -------------------------------------------------------------------
    "dash.hello": ("مرحبًا، {name}", "Hello, {name}"),
    "dash.sub": ("دوراتك وورشك وحجوزاتك في مكان واحد.", "Your courses, workshops and bookings in one place."),
    "dash.k_courses": ("دوراتي", "My courses"), "dash.k_progress": ("متوسط التقدّم", "Average progress"),
    "dash.k_workshops": ("ورش مسجَّلة", "Registered workshops"), "dash.k_bookings": ("حجوزات نشطة", "Active bookings"),
    "dash.my_courses": ("دوراتي", "My courses"), "dash.my_workshops": ("ورشي", "My workshops"), "dash.my_bookings": ("حجوزات الاستشارات", "My consultations"),
    "dash.no_courses": ("لم تسجّل في دورة بعد.", "You have not enrolled in a course yet."),
    "dash.no_workshops": ("لا ورش مسجَّلة.", "No registered workshops."),
    "dash.no_bookings": ("لا توجد حجوزات.", "No bookings."),
    "dash.lessons_done": ("{done} من {total} دروس", "{done} of {total} lessons"),
    "dash.cancel_confirm": ("هل أنت متأكد من الإلغاء؟", "Are you sure you want to cancel?"),

    # ---- statuses / topics / roles ---------------------------------------------------------------
    "status.pending": ("قيد الانتظار", "Pending"), "status.active": ("نشط", "Active"), "status.cancelled": ("ملغى", "Cancelled"),
    "status.confirmed": ("مؤكَّد", "Confirmed"), "status.completed": ("مكتمل", "Completed"), "status.disabled": ("معطّل", "Disabled"),
    "status.new": ("جديدة", "New"), "status.read": ("مقروءة", "Read"), "status.resolved": ("تمت المعالجة", "Resolved"),
    "topic.general": ("استفسار عام", "General enquiry"), "topic.course": ("عن دورة", "About a course"),
    "topic.workshop": ("عن ورشة", "About a workshop"), "topic.consultation": ("عن استشارة", "About consulting"),
    "topic.corporate": ("تدريب مؤسسي", "Corporate training"), "topic.support": ("دعم فني", "Technical support"),
    "role.owner": ("المالك", "Owner"), "role.admin": ("مدير", "Admin"), "role.editor": ("محرّر محتوى", "Content editor"),
    "role.support": ("دعم", "Support"), "role.student": ("طالب", "Student"),

    # ---- admin ---------------------------------------------------------------------------------
    "admin.login_title": ("دخول الإدارة", "Staff sign-in"), "admin.login_sub": ("للعاملين المصرّح لهم فقط. تُسجَّل محاولات الدخول.", "Authorised staff only. Sign-in attempts are logged."),
    "admin.nav.dashboard": ("نظرة عامة", "Overview"), "admin.nav.bookings": ("حجوزات الاستشارات", "Consultation bookings"),
    "admin.nav.students": ("الطلاب", "Students"), "admin.nav.enrollments": ("التسجيلات", "Enrolments"),
    "admin.nav.content": ("محتوى الموقع", "Site content"), "admin.nav.messages": ("الرسائل", "Messages"),
    "admin.nav.users": ("الفريق والصلاحيات", "Team & roles"), "admin.nav.audit": ("سجل التدقيق", "Audit log"),
    "admin.view_site": ("عرض الموقع", "View site"),
    "entity.courses": ("الدورات", "Courses"), "entity.categories": ("التصنيفات", "Categories"), "entity.instructors": ("المدرّبون", "Instructors"),
    "entity.workshops": ("الورش", "Workshops"), "entity.services": ("الخدمات الاستشارية", "Consulting services"), "entity.testimonials": ("الآراء", "Testimonials"),
    "admin.new": ("جديد", "New"), "admin.new_staff": ("عضو فريق جديد", "New team member"),
    "admin.lessons": ("الدروس", "Lessons"), "admin.add_lesson": ("إضافة درس", "Add a lesson"), "admin.registrations": ("المسجّلون", "Registrations"),
    "admin.saved": ("تم الحفظ.", "Saved."), "admin.deleted": ("تم الحذف.", "Deleted."),
    "admin.confirm_delete": ("حذف هذا العنصر نهائيًا؟", "Delete this item permanently?"),
    "admin.confirm_toggle": ("تغيير حالة هذا الحساب؟", "Change this account's status?"),
    "admin.confirm_reset": ("إنشاء كلمة مرور مؤقتة جديدة لهذا المستخدم؟", "Generate a new temporary password for this user?"),
    "admin.err.has_enrollments": ("لا يمكن حذف دورة لها تسجيلات — ألغِ نشرها بدلًا من ذلك.", "A course with enrolments cannot be deleted — unpublish it instead."),
    "admin.err.has_registrations": ("لا يمكن حذف ورشة لها مسجّلون — ألغِ نشرها بدلًا من ذلك.", "A workshop with registrations cannot be deleted — unpublish it instead."),
    "admin.err.has_bookings": ("لا يمكن حذف خدمة لها حجوزات — ألغِ نشرها بدلًا من ذلك.", "A service with bookings cannot be deleted — unpublish it instead."),
    "admin.err.in_use": ("العنصر مستخدم في محتوى آخر ولا يمكن حذفه.", "This item is used by other content and cannot be deleted."),
    "admin.slug_hint": ("أحرف إنجليزية صغيرة وأرقام وشرطات. اتركه فارغًا للتوليد التلقائي.", "Lowercase letters, digits and hyphens. Leave empty to auto-generate."),
    "admin.tz_hint": ("بتوقيت الأكاديمية.", "In academy time zone."),
    "admin.k.students": ("طلاب", "Students"), "admin.k.courses": ("دورات", "Courses"), "admin.k.enrollments": ("تسجيلات نشطة", "Active enrolments"),
    "admin.k.workshops": ("ورش قادمة", "Upcoming workshops"), "admin.k.regs": ("تسجيل", "registrations"),
    "admin.k.bookings": ("حجوزات بانتظار التأكيد", "Bookings awaiting"), "admin.k.messages": ("رسائل جديدة", "New messages"),
    "admin.enroll_by_cat": ("التسجيلات حسب المجال", "Enrolments by category"),
    "admin.recent_enroll": ("أحدث التسجيلات", "Recent enrolments"), "admin.recent_activity": ("آخر النشاطات", "Recent activity"),
    "admin.enroll_note": ("الدورات المدفوعة تبدأ «قيد الانتظار»؛ غيّر الحالة إلى «نشط» بعد تأكيد الدفع خارج المنصة.",
                          "Paid courses start “pending”; set them to “active” after confirming payment outside the platform."),
    "admin.content_note": ("نصوص الواجهة الرئيسية قابلة للتعديل بالعربية والإنجليزية. تُحفظ كنص عادي.", "Key site texts are editable in Arabic and English. Stored as plain text."),
    "admin.search_students": ("ابحث بالاسم أو البريد", "Search by name or email"),
    "admin.deactivate": ("تعطيل", "Deactivate"), "admin.activate": ("تفعيل", "Activate"),
    "admin.reset_password": ("إعادة تعيين كلمة المرور", "Reset password"),
    "admin.temp_pw_note": ("كلمة المرور المؤقتة أدناه تظهر مرة واحدة فقط ولا تُحفظ. سلّمها للمستخدم بوسيلة آمنة؛ سيُطلب منه تغييرها عند الدخول.",
                           "The temporary password below is shown once and is not stored. Hand it over securely; the user must change it at sign-in."),
    "admin.roles_note": ("حساب المالك لا يُعدَّل من هنا، ولا يمكنك تعديل حسابك. تُسجَّل كل التغييرات في سجل التدقيق.", "The owner account cannot be changed here and you cannot edit your own. All changes are written to the audit log."),
    "admin.staff_pw_hint": ("12 حرفًا على الأقل مع حروف وأرقام. سيُجبَر المستخدم على تغييرها.", "At least 12 characters with letters and digits. The user will be forced to change it."),
    "admin.audit_note": ("سجل للقراءة فقط: لا توجد واجهة لتعديل أو حذف السجلات.", "Read-only log: there is no interface to edit or delete entries."),
    "col.title": ("العنوان", "Title"), "col.name": ("الاسم", "Name"), "col.category": ("المجال", "Category"), "col.price": ("السعر", "Price"),
    "col.enrolled": ("مسجّلون", "Enrolled"), "col.published": ("منشور", "Published"), "col.sample": ("تجريبي", "Sample"),
    "col.starts": ("الموعد", "Starts"), "col.seats": ("المقاعد", "Seats"), "col.duration": ("المدة (د)", "Min."),
    "col.jobtitle": ("المسمى", "Job title"), "col.slug": ("المعرّف", "Slug"), "col.courses": ("الدورات", "Courses"),
    "col.date": ("التاريخ", "Date"), "col.joined": ("انضم", "Joined"), "col.last_login": ("آخر دخول", "Last login"),
    "col.item": ("العنصر", "Item"), "col.actor": ("المنفِّذ", "Actor"), "col.action": ("الإجراء", "Action"),
    "col.target": ("الهدف", "Target"), "col.details": ("تفاصيل", "Details"),
    "content.hero_title": ("عنوان الصفحة الرئيسية", "Home headline"), "content.hero_lead": ("نص تعريفي للرئيسية", "Home intro text"),
    "content.about_text": ("نص «عن الأكاديمية»", "About text"), "content.footer_blurb": ("نص التذييل", "Footer blurb"),
    "content.contact_email": ("البريد الظاهر", "Public email"), "content.contact_hours": ("ساعات العمل", "Working hours"),

    # ---- form field labels (f.<field name>) ----------------------------------------------------------
    "f.name": ("الاسم", "Name"), "f.email": ("البريد الإلكتروني", "Email"), "f.password": ("كلمة المرور", "Password"),
    "f.confirm": ("تأكيد كلمة المرور", "Confirm password"), "f.current": ("كلمة المرور الحالية", "Current password"),
    "f.accept": ("أوافق على شروط الاستخدام وسياسة الخصوصية", "I agree to the terms of use and privacy policy"),
    "f.remember": ("تذكّرني على هذا الجهاز", "Remember me on this device"), "f.locale": ("لغة الواجهة", "Interface language"),
    "f.topic": ("الموضوع", "Topic"), "f.message": ("الرسالة", "Message"), "f.website": ("الموقع", "Website"),
    "f.when": ("الموعد المفضّل", "Preferred time"), "f.notes": ("ملاحظات", "Notes"),
    "f.slug": ("المعرّف (slug)", "Slug"), "f.category": ("المجال", "Category"), "f.category_id": ("المجال", "Category"),
    "f.instructor_id": ("المدرّب", "Instructor"), "f.level": ("المستوى", "Level"), "f.price": ("السعر", "Price"),
    "f.duration_hours": ("المدة (ساعات)", "Duration (hours)"), "f.duration_minutes": ("المدة (دقائق)", "Duration (minutes)"),
    "f.minutes": ("المدة (دقائق)", "Minutes"), "f.position": ("الترتيب", "Position"),
    "f.title_ar": ("العنوان (عربي)", "Title (Arabic)"), "f.title_en": ("العنوان (إنجليزي)", "Title (English)"),
    "f.name_ar": ("الاسم (عربي)", "Name (Arabic)"), "f.name_en": ("الاسم (إنجليزي)", "Name (English)"),
    "f.summary_ar": ("ملخص (عربي)", "Summary (Arabic)"), "f.summary_en": ("ملخص (إنجليزي)", "Summary (English)"),
    "f.description_ar": ("الوصف (عربي)", "Description (Arabic)"), "f.description_en": ("الوصف (إنجليزي)", "Description (English)"),
    "f.bio_ar": ("نبذة (عربي)", "Bio (Arabic)"), "f.bio_en": ("نبذة (إنجليزي)", "Bio (English)"),
    "f.body_ar": ("نص الدرس (عربي)", "Lesson text (Arabic)"), "f.body_en": ("نص الدرس (إنجليزي)", "Lesson text (English)"),
    "f.author_ar": ("الاسم (عربي)", "Author (Arabic)"), "f.author_en": ("الاسم (إنجليزي)", "Author (English)"),
    "f.role_ar": ("الصفة (عربي)", "Role (Arabic)"), "f.role_en": ("الصفة (إنجليزي)", "Role (English)"),
    "f.text_ar": ("النص (عربي)", "Text (Arabic)"), "f.text_en": ("النص (إنجليزي)", "Text (English)"),
    "f.value_ar": ("النص بالعربية", "Arabic text"), "f.value_en": ("النص بالإنجليزية", "English text"),
    "f.is_published": ("منشور", "Published"), "f.is_featured": ("مميّز في الرئيسية", "Featured on home"),
    "f.is_sample": ("محتوى تجريبي خيالي (يظهر عليه وسم)", "Fictional sample (shows a label)"),
    "f.starts_at": ("موعد البدء", "Starts at"), "f.capacity": ("السعة", "Capacity"),
    "f.role": ("الدور", "Role"), "f.status": ("الحالة", "Status"),
    "f.title": ("العنوان", "Title"), "f.csrf_token": ("", ""),

    # ---- validation / flashes ------------------------------------------------------------------------------
    "val.required": ("هذا الحقل مطلوب.", "This field is required."),
    "val.invalid": ("القيمة غير صالحة.", "Invalid value."),
    "val.email": ("أدخل بريدًا إلكترونيًا صالحًا.", "Enter a valid email address."),
    "val.email_taken": ("هذا البريد مسجَّل مسبقًا.", "This email is already registered."),
    "val.length": ("الطول غير مناسب.", "The length is not allowed."),
    "val.number": ("أدخل رقمًا ضمن المدى المسموح.", "Enter a number within the allowed range."),
    "val.accept": ("يجب الموافقة للمتابعة.", "You must agree to continue."),
    "val.slug": ("حروف إنجليزية صغيرة وأرقام وشرطات فقط.", "Lowercase letters, digits and hyphens only."),
    "val.slug_taken": ("المعرّف مستخدم مسبقًا.", "This slug is already in use."),
    "val.password_len": ("كلمة المرور قصيرة.", "The password is too short."),
    "val.password_mix": ("يجب أن تحتوي على حروف وأرقام.", "It must contain letters and digits."),
    "val.password_email": ("لا يجوز أن تطابق كلمة المرور بريدك.", "The password must not equal your email."),
    "val.password_match": ("كلمتا المرور غير متطابقتين.", "The passwords do not match."),
    "val.password_wrong": ("كلمة المرور الحالية غير صحيحة.", "The current password is incorrect."),
    "val.password_same": ("اختر كلمة مرور مختلفة عن الحالية.", "Choose a password different from the current one."),
    "val.booking_soon": ("اختر موعدًا بعد 24 ساعة على الأقل.", "Choose a time at least 24 hours from now."),
    "val.booking_far": ("اختر موعدًا خلال 90 يومًا.", "Choose a time within 90 days."),

    # ---- errors ----------------------------------------------------------------------------------------------------
    "err.400.title": ("طلب غير صالح", "Bad request"), "err.400.msg": ("تعذّر فهم الطلب. أعد المحاولة.", "We could not process that request. Please try again."),
    "err.csrf.title": ("انتهت صلاحية الجلسة", "Session expired"), "err.csrf.msg": ("انتهت صلاحية النموذج لأسباب أمنية. ارجع وأعد المحاولة.", "The form expired for security reasons. Go back and try again."),
    "err.403.title": ("غير مصرّح", "Access denied"), "err.403.msg": ("ليست لديك صلاحية الوصول إلى هذه الصفحة.", "You do not have permission to view this page."),
    "err.404.title": ("الصفحة غير موجودة", "Page not found"), "err.404.msg": ("ربما نُقلت الصفحة أو أن الرابط غير صحيح.", "The page may have moved or the link is wrong."),
    "err.429.title": ("محاولات كثيرة", "Too many requests"), "err.429.msg": ("تجاوزت الحد المسموح. انتظر قليلًا ثم أعد المحاولة.", "You have exceeded the allowed rate. Please wait a moment and try again."),
    "err.500.title": ("حدث خطأ", "Something went wrong"), "err.500.msg": ("حدث خطأ غير متوقع من جانبنا. تم تسجيله وسنعالجه.", "An unexpected error occurred on our side. It has been logged."),
    "err.home": ("العودة إلى الرئيسية", "Back to home"),
}


T.update({
    # ---- e-mail verification / password reset ---------------------------------
    "auth.forgot_title": ("نسيت كلمة المرور؟", "Forgot your password?"),
    "auth.forgot_sub": ("أدخل بريدك وسنرسل رابط إعادة التعيين.", "Enter your e-mail and we will send a reset link."),
    "auth.mail_off": ("خدمة البريد غير مفعّلة على هذا الخادم حاليًا؛ إن لم يصلك رابط فتواصل مع الإدارة لإصدار كلمة مرور مؤقتة.",
                      "E-mail sending is not enabled on this server yet; if no link arrives, ask the staff to issue a temporary password."),
    "auth.send_link": ("إرسال الرابط", "Send link"),
    "auth.reset_sent": ("إن كان البريد مسجّلًا فقد أُرسل إليه رابط إعادة التعيين.", "If that e-mail is registered, a reset link has been sent."),
    "auth.reset_bad": ("رابط إعادة التعيين غير صالح أو منتهٍ. اطلب رابطًا جديدًا.", "The reset link is invalid or expired. Request a new one."),
    "auth.reset_title": ("كلمة مرور جديدة", "Set a new password"),
    "auth.verify_sent": ("أرسلنا رابط تأكيد البريد الإلكتروني.", "We sent an e-mail confirmation link."),
    "auth.verify_bad": ("رابط التأكيد غير صالح أو منتهٍ.", "The confirmation link is invalid or expired."),
    "auth.verified": ("تم تأكيد بريدك الإلكتروني.", "Your e-mail is confirmed."),
    "auth.verify_required": ("أكّد بريدك الإلكتروني أولًا للمتابعة.", "Confirm your e-mail address first to continue."),
    "auth.verify_banner": ("بريدك الإلكتروني غير مؤكَّد بعد.", "Your e-mail address is not confirmed yet."),
    "auth.resend": ("إعادة إرسال الرابط", "Resend the link"),
    "auth.verified_state": ("مؤكَّد ✓", "confirmed ✓"),
    "auth.unverified_state": ("غير مؤكَّد", "not confirmed"),
    "auth.2fa_expired": ("انتهت مهلة التحقق، سجّل الدخول من جديد.", "Verification timed out; please sign in again."),

    # ---- two-factor ---------------------------------------------------------------
    "2fa.title": ("المصادقة الثنائية", "Two-factor authentication"),
    "2fa.sub": ("طبقة حماية إضافية برمز يتجدد كل 30 ثانية من تطبيق المصادقة.", "An extra layer of protection with a code that changes every 30 seconds in an authenticator app."),
    "2fa.login_sub": ("أدخل الرمز من تطبيق المصادقة أو أحد رموز الطوارئ.", "Enter the code from your authenticator app, or a backup code."),
    "2fa.verify": ("تحقق", "Verify"), "2fa.on": ("مفعّلة", "enabled"), "2fa.off": ("غير مفعّلة", "off"),
    "2fa.codes_left": ("رموز الطوارئ المتبقية: {n}", "Backup codes left: {n}"),
    "2fa.required_note": ("المصادقة الثنائية إلزامية لحسابات الفريق ولا يمكن تعطيلها.", "Two-factor authentication is mandatory for staff accounts and cannot be disabled."),
    "2fa.disable": ("تعطيل المصادقة الثنائية", "Disable two-factor"),
    "2fa.step1": ("1) امسح الرمز بتطبيق المصادقة", "1) Scan the code with your authenticator app"),
    "2fa.step2": ("2) أدخل الرمز المكوّن من 6 أرقام للتأكيد", "2) Enter the 6-digit code to confirm"),
    "2fa.manual": ("أو أدخل هذا المفتاح يدويًا:", "Or enter this key manually:"),
    "2fa.enable": ("تفعيل", "Enable"), "2fa.start": ("بدء الإعداد", "Start setup"),
    "2fa.why_t": ("لماذا؟", "Why?"),
    "2fa.why_d": ("حتى لو سُرقت كلمة المرور لن يستطيع أحد الدخول دون جهازك.", "Even if your password is stolen, nobody can sign in without your device."),
    "2fa.codes_title": ("رموز الطوارئ", "Backup codes"),
    "2fa.codes_sub": ("احفظها الآن في مكان آمن؛ تظهر مرة واحدة فقط ويصلح كل رمز لاستخدام واحد.", "Save them now somewhere safe; they are shown once and each works a single time."),
    "2fa.disabled": ("تم تعطيل المصادقة الثنائية.", "Two-factor authentication disabled."),
    "val.2fa_code": ("الرمز غير صحيح.", "The code is not correct."),
    "val.video_url": ("رابط يوتيوب أو فيميو (https) فقط.", "Only https YouTube or Vimeo links are allowed."),

    # ---- manual payments --------------------------------------------------------------------
    "pay.title": ("الدفع", "Payment"), "pay.go": ("إتمام الدفع", "Complete payment"),
    "pay.how": ("طريقة الدفع", "How to pay"), "pay.submit": ("إرسال بيانات الدفع", "Submit payment details"),
    "pay.submitted": ("تم إرسال بيانات الدفع وستراجعها الإدارة.", "Payment details sent; the academy will review them."),
    "pay.submitted_note": ("بانتظار مراجعة الإدارة لتأكيد الدفع.", "Waiting for the academy to verify the payment."),
    "pay.rejected_note": ("تعذّر تأكيد الدفع. صحّح المرجع وأعد الإرسال.", "The payment could not be confirmed. Correct the reference and resubmit."),
    "pay.confirmed_note": ("تم تأكيد الدفع وتفعيل طلبك. شكرًا لك.", "Payment confirmed and your request is active. Thank you."),
    "pay.cancelled_note": ("أُلغي هذا الطلب.", "This request was cancelled."),
    "pay.ref_hint": ("رقم الحوالة أو إيصال الدفع كما ظهر لك.", "The transfer number or receipt reference you were given."),
    "pay.confirm": ("تأكيد الدفع", "Confirm payment"), "pay.reject": ("رفض", "Reject"),
    "pay.s.awaiting": ("بانتظار الدفع", "Awaiting payment"), "pay.s.submitted": ("بانتظار المراجعة", "Awaiting review"),
    "pay.s.confirmed": ("مؤكَّد", "Confirmed"), "pay.s.rejected": ("مرفوض", "Rejected"), "pay.s.cancelled": ("ملغى", "Cancelled"),
    "pay.m.bank_transfer": ("حوالة بنكية", "Bank transfer"), "pay.m.cash": ("نقدًا", "Cash"),
    "pay.m.wallet": ("محفظة إلكترونية", "E-wallet"), "pay.m.other": ("أخرى", "Other"),
    "pay.k.course": ("دورة", "Course"), "pay.k.workshop": ("ورشة", "Workshop"), "pay.k.consultation": ("استشارة", "Consultation"),
    "f.method": ("طريقة الدفع", "Payment method"), "f.reference": ("رقم الحوالة / المرجع", "Transfer number / reference"),
    "f.note": ("ملاحظة", "Note"), "f.code": ("الرمز", "Code"), "f.video_url": ("رابط فيديو (يوتيوب/فيميو)", "Video link (YouTube/Vimeo)"),
    "ws.pending": ("حُجز مقعدك مؤقتًا بانتظار الدفع.", "Your seat is held pending payment."),
    "ws.pending_note": ("المقعد محجوز مؤقتًا حتى تؤكّد الإدارة الدفع.", "Seat held until the academy confirms payment."),
    "consult.booked_pay": ("تم إرسال طلب الحجز. أكمل بيانات الدفع ليراجعها الفريق.", "Booking request sent. Complete the payment details so the team can review."),

    # ---- certificates ---------------------------------------------------------------------------
    "cert.title": ("شهادة إتمام", "Certificate of completion"), "cert.get": ("احصل على شهادتك", "Get your certificate"),
    "cert.not_ready": ("أكمل جميع الدروس أولًا لتحصل على الشهادة.", "Complete all lessons first to get the certificate."),
    "cert.print": ("طباعة / حفظ PDF", "Print / save as PDF"), "cert.awarded": ("تشهد أكاديمية أفقيا بأن", "Ufuqia Academy certifies that"),
    "cert.completed": ("أتمّ/ت بنجاح دورة", "has successfully completed the course"),
    "cert.verify_at": ("للتحقق من صحتها:", "Verify authenticity at:"),
    "cert.verify_title": ("التحقق من شهادة", "Certificate verification"),
    "cert.valid": ("شهادة صالحة صادرة عن المنصة.", "A valid certificate issued by this platform."),
    "cert.invalid": ("لم نجد شهادة بهذا الرمز.", "No certificate was found for this code."),
    "cert.code": ("رمز الشهادة", "Certificate code"), "cert.holder": ("الاسم", "Holder"),
    "cert.sample_note": ("نموذج تجريبي لدورة خيالية — ليست شهادة معتمدة.", "Demo certificate for a fictional course — not an accredited credential."),

    # ---- admin additions ---------------------------------------------------------------------------
    "admin.nav.payments": ("المدفوعات", "Payments"), "admin.nav.outbox": ("صندوق البريد", "E-mail outbox"),
    "admin.k.payments": ("مدفوعات بانتظار المراجعة", "Payments to review"),
    "admin.payments_note": ("لا تُعالَج أي معاملات إلكترونية: يدفع الطالب خارج المنصة ويدخل المرجع، وأنتم تؤكّدون بعد التحقق من حسابكم.",
                            "No online transactions are processed: students pay outside the platform and enter a reference; you confirm after checking your own account."),
    "admin.confirm_payment": ("تأكيد أنك استلمت هذه الدفعة؟ سيُفعَّل الطلب.", "Confirm you received this payment? The request will be activated."),
    "admin.confirm_reject": ("رفض هذه الدفعة؟", "Reject this payment?"),
    "admin.err.payment_final": ("تم البت في هذه الدفعة مسبقًا.", "This payment has already been decided."),
    "admin.mail_on": ("إرسال البريد مفعّل (SMTP).", "E-mail sending is enabled (SMTP)."),
    "admin.mail_off": ("إرسال البريد غير مهيّأ: الرسائل تُسجَّل هنا فقط. اضبط MAIL_SERVER و MAIL_FROM لإرسالها فعليًا.", "E-mail sending is not configured: messages are only recorded here. Set MAIL_SERVER and MAIL_FROM to really send them."),
    "admin.outbox_note": ("للمالك فقط: قد تحتوي الرسائل على روابط أحادية الاستخدام.", "Owner only: messages may contain one-time links."),
    "content.payment_instructions": ("تعليمات الدفع (بيانات الحساب)", "Payment instructions (account details)"),
})


def translate(key, lang, **kw):
    pair = T.get(key)
    if pair is None:
        return key
    text = pair[0] if lang == "ar" else pair[1]
    if kw:
        try:
            return text.format(**kw)
        except (KeyError, IndexError):
            return text
    return text
