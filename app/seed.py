"""Fictional sample content.  EVERYTHING here is invented for demonstration:
instructors, courses, workshops, consultations and testimonials all carry
``is_sample=True`` and are shown with a visible "sample" label in the UI."""
from datetime import timedelta
from decimal import Decimal

from .extensions import db
from .models import (Category, ConsultationService, Course, Instructor, Lesson, Testimonial,
                     Workshop, utcnow)

CATEGORIES = [
    ("artificial-intelligence", "الذكاء الاصطناعي", "Artificial Intelligence",
     "من الأساسيات إلى التطبيقات العملية في العمل.", "From fundamentals to practical use at work."),
    ("technology", "التقنية", "Technology",
     "برمجة وأمن وأنظمة بأسلوب تطبيقي.", "Programming, security and systems, hands-on."),
    ("digital-marketing", "التسويق الرقمي", "Digital Marketing",
     "استراتيجيات ومحتوى وقياس نتائج.", "Strategy, content and measurable results."),
    ("professional-development", "التطوير المهني", "Professional Development",
     "مهارات القيادة والتواصل وإدارة المشاريع.", "Leadership, communication and project skills."),
]

INSTRUCTORS = [  # all fictional
    ("د. سلمى الراشد", "Dr. Salma Al-Rashid", "خبيرة ذكاء اصطناعي (شخصية تجريبية)", "AI specialist (sample persona)",
     "ملف تعريفي خيالي لأغراض العرض فقط.", "A fictional profile created for demonstration only."),
    ("م. خالد النعيمي", "Eng. Khaled Al-Nuaimi", "مهندس برمجيات وأمن (شخصية تجريبية)", "Software & security engineer (sample persona)",
     "ملف تعريفي خيالي لأغراض العرض فقط.", "A fictional profile created for demonstration only."),
    ("أ. ليلى المنصور", "Layla Al-Mansour", "استشارية تسويق رقمي (شخصية تجريبية)", "Digital marketing consultant (sample persona)",
     "ملف تعريفي خيالي لأغراض العرض فقط.", "A fictional profile created for demonstration only."),
    ("د. يوسف الحداد", "Dr. Youssef Al-Haddad", "مدرب تطوير مهني (شخصية تجريبية)", "Professional development coach (sample persona)",
     "ملف تعريفي خيالي لأغراض العرض فقط.", "A fictional profile created for demonstration only."),
]

# (slug, cat_idx, inst_idx, title_ar, title_en, sum_ar, sum_en, level, price, hours, featured, lessons)
COURSES = [
    ("generative-ai-everyday-work", 0, 0, "الذكاء الاصطناعي التوليدي للعمل اليومي", "Generative AI for Everyday Work",
     "تعلّم كيف توظّف أدوات الذكاء الاصطناعي لرفع إنتاجيتك بأمان ومسؤولية.",
     "Learn to use AI assistants to raise your productivity — safely and responsibly.", "beginner", 0, 6, True,
     [("ما هو الذكاء الاصطناعي التوليدي؟", "What is generative AI?"),
      ("كتابة التعليمات الفعّالة", "Writing effective prompts"),
      ("أتمتة المهام المكتبية", "Automating office tasks"),
      ("الخصوصية والاستخدام المسؤول", "Privacy and responsible use")]),
    ("machine-learning-foundations-python", 0, 0, "أساسيات تعلّم الآلة بلغة بايثون", "Machine Learning Foundations with Python",
     "من البيانات إلى النموذج: مسار عملي لفهم تعلّم الآلة وبناء أول نموذج.",
     "From data to model: a practical path to understanding ML and building your first model.", "intermediate", 120, 20, True,
     [("إعداد بيئة بايثون", "Setting up Python"), ("تنظيف البيانات واستكشافها", "Cleaning and exploring data"),
      ("نماذج التصنيف والانحدار", "Classification and regression"), ("تقييم النموذج وتحسينه", "Evaluating and improving a model")]),
    ("web-development-fundamentals", 1, 1, "أساسيات تطوير الويب", "Web Development Fundamentals",
     "ابنِ صفحات ويب متجاوبة باستخدام HTML وCSS وJavaScript من الصفر.",
     "Build responsive web pages with HTML, CSS and JavaScript from scratch.", "beginner", 90, 24, True,
     [("بنية صفحة HTML", "Anatomy of an HTML page"), ("التنسيق مع CSS", "Styling with CSS"),
      ("التصميم المتجاوب", "Responsive layout"), ("التفاعل مع JavaScript", "Interactivity with JavaScript")]),
    ("cybersecurity-essentials-teams", 1, 1, "أساسيات الأمن السيبراني للفرق", "Cybersecurity Essentials for Teams",
     "عادات وإجراءات بسيطة تحمي بيانات فريقك من أكثر الهجمات شيوعًا.",
     "Simple habits and procedures that protect your team from the most common attacks.", "beginner", 80, 8, False,
     [("فهم التهديدات الشائعة", "Understanding common threats"), ("كلمات المرور والمصادقة", "Passwords and authentication"),
      ("التصيّد الاحتيالي", "Recognising phishing"), ("الاستجابة للحوادث", "Responding to incidents")]),
    ("social-media-strategy-from-zero", 2, 2, "استراتيجية وسائل التواصل الاجتماعي من الصفر", "Social Media Strategy from Zero",
     "حدّد جمهورك وابنِ خطة محتوى واضحة وقِس أثرها.",
     "Define your audience, build a clear content plan and measure its impact.", "beginner", 0, 5, False,
     [("تحديد الجمهور والهدف", "Defining audience and goal"), ("تخطيط المحتوى", "Planning content"),
      ("التفاعل وبناء المجتمع", "Engagement and community"), ("قياس الأداء", "Measuring performance")]),
    ("search-content-marketing", 2, 2, "التسويق عبر البحث والمحتوى", "Search & Content Marketing",
     "اجذب زوارًا مؤهلين عبر محركات البحث ومحتوى يخدم احتياج القارئ.",
     "Attract qualified visitors through search engines and reader-first content.", "intermediate", 100, 12, True,
     [("أساسيات تحسين محركات البحث", "SEO fundamentals"), ("بحث الكلمات المفتاحية", "Keyword research"),
      ("كتابة محتوى يجيب عن الأسئلة", "Writing content that answers questions"), ("لوحة قياس بسيطة", "A simple measurement dashboard")]),
    ("project-management-in-practice", 3, 3, "إدارة المشاريع عمليًا", "Project Management in Practice",
     "خطّط وانفّذ وتابع مشاريعك بأدوات وأساليب مرنة قابلة للتطبيق فورًا.",
     "Plan, run and track projects with flexible methods you can apply immediately.", "intermediate", 110, 14, False,
     [("تعريف النطاق والأهداف", "Defining scope and goals"), ("الجدولة وتقدير الجهد", "Scheduling and estimation"),
      ("إدارة المخاطر", "Managing risk"), ("التواصل مع أصحاب المصلحة", "Stakeholder communication")]),
    ("professional-communication-presentation", 3, 3, "مهارات التواصل والعرض المهني", "Professional Communication & Presentation",
     "اعرض أفكارك بثقة ووضوح في الاجتماعات والعروض.",
     "Present your ideas with confidence and clarity in meetings and pitches.", "beginner", 60, 6, True,
     [("هيكلة الرسالة", "Structuring your message"), ("لغة الجسد والصوت", "Body language and voice"),
      ("شرائح تخدم الفكرة", "Slides that serve the idea"), ("التعامل مع الأسئلة الصعبة", "Handling tough questions")]),
]

SAMPLE_NOTE_AR = "\n\n(محتوى تجريبي خيالي لأغراض العرض — ليس دورة حقيقية.)"
SAMPLE_NOTE_EN = "\n\n(Fictional sample content for demonstration — not a real course.)"


def seed_sample_content():
    cats = []
    for i, (slug, ar, en, dar, den) in enumerate(CATEGORIES):
        c = Category(slug=slug, name_ar=ar, name_en=en, description_ar=dar, description_en=den, position=i)
        db.session.add(c)
        cats.append(c)
    insts = []
    for na, ne, ta, te, ba, be in INSTRUCTORS:
        i = Instructor(name_ar=na, name_en=ne, title_ar=ta, title_en=te, bio_ar=ba, bio_en=be, is_sample=True)
        db.session.add(i)
        insts.append(i)
    db.session.flush()

    for (slug, ci, ii, ta, te, sa, se, level, price, hours, feat, lessons) in COURSES:
        course = Course(
            slug=slug, category_id=cats[ci].id, instructor_id=insts[ii].id, title_ar=ta, title_en=te,
            summary_ar=sa, summary_en=se,
            description_ar=f"{sa}\n\nستتعلّم عبر دروس قصيرة وتمارين تطبيقية تنتهي بمشروع صغير تطبّق فيه ما تعلّمته." + SAMPLE_NOTE_AR,
            description_en=f"{se}\n\nYou will learn through short lessons and hands-on exercises that end with a small project." + SAMPLE_NOTE_EN,
            level=level, price=Decimal(price), duration_hours=hours, is_featured=feat, is_published=True, is_sample=True)
        db.session.add(course)
        db.session.flush()
        for n, (la, le) in enumerate(lessons, 1):
            db.session.add(Lesson(
                course_id=course.id, position=n, title_ar=la, title_en=le, minutes=12 + n * 3,
                body_ar=f"هذا نص تجريبي لدرس «{la}». يُستبدل بالمحتوى الحقيقي من لوحة التحكم.",
                body_en=f"This is placeholder sample text for the lesson “{le}”. Replace it with real content from the control panel."))

    now = utcnow().replace(hour=14, minute=0, second=0, microsecond=0)  # 14:00 UTC
    workshops = [
        ("prompt-engineering-live-lab", 0, 9, "مختبر مباشر: هندسة التعليمات للذكاء الاصطناعي", "Live Lab: Prompt Engineering", 0, 40,
         "ورشة تفاعلية نطبّق فيها أساليب كتابة التعليمات على حالات عمل حقيقية.",
         "An interactive session applying prompt-writing techniques to realistic work cases."),
        ("build-landing-page-in-90-minutes", 1, 16, "ابنِ صفحة هبوط في 90 دقيقة", "Build a Landing Page in 90 Minutes", 25, 25,
         "نبني صفحة هبوط متجاوبة معًا خطوة بخطوة.", "We build a responsive landing page together, step by step."),
        ("content-calendar-workshop", 2, 24, "ورشة تقويم المحتوى الشهري", "Monthly Content Calendar Workshop", 30, 30,
         "نخطّط شهرًا كاملًا من المحتوى بأدوات بسيطة.", "Plan a full month of content with simple tools."),
        ("confident-presenting", 3, 35, "العرض بثقة: تمارين مباشرة", "Presenting with Confidence: Live Practice", 20, 20,
         "تمارين عملية وتغذية راجعة فورية على عروضك.", "Practical drills and instant feedback on your presentations."),
        ("intro-to-data-literacy", 0, -20, "مدخل إلى الثقافة البيانية (منتهية)", "Intro to Data Literacy (past session)", 0, 50,
         "ورشة سابقة تظهر في الأرشيف.", "A previous session shown in the archive."),
    ]
    for slug, ii, days, ta, te, price, cap, sa, se in workshops:
        db.session.add(Workshop(
            slug=slug, instructor_id=insts[ii].id, title_ar=ta, title_en=te, summary_ar=sa, summary_en=se,
            description_ar=sa + "\n\nتُقام عبر الإنترنت وتُرسل تفاصيل الدخول للمسجّلين." + SAMPLE_NOTE_AR.replace("دورة", "ورشة"),
            description_en=se + "\n\nHeld online; joining details are sent to registered participants." + SAMPLE_NOTE_EN.replace("course", "workshop"),
            starts_at=now + timedelta(days=days), duration_minutes=90, capacity=cap, price=Decimal(price),
            is_published=True, is_sample=True))

    services = [
        ("ai-adoption-strategy-session", 0, "جلسة استراتيجية لتبنّي الذكاء الاصطناعي", "AI Adoption Strategy Session", 60, 60,
         "نحدّد معك أولويات استخدام الذكاء الاصطناعي في فريقك أو مشروعك.", "We map the AI priorities for your team or project."),
        ("career-skills-planning", 3, "تخطيط المسار المهني والمهارات", "Career & Skills Planning", 45, 40,
         "خطة واضحة للمهارات التي تحتاجها لهدفك المهني.", "A clear plan for the skills your career goal needs."),
        ("digital-marketing-audit", 2, "مراجعة التسويق الرقمي", "Digital Marketing Audit", 60, 55,
         "تقييم سريع لحضورك الرقمي مع توصيات قابلة للتنفيذ.", "A quick review of your digital presence with actionable advice."),
        ("training-needs-assessment", 3, "تقييم الاحتياج التدريبي للمؤسسات", "Training Needs Assessment for Organisations", 90, 120,
         "نحلّل فجوات المهارات ونقترح برنامجًا تدريبيًا مناسبًا.", "We analyse skill gaps and propose a fitting training programme."),
    ]
    for slug, ii, ta, te, dur, price, sa, se in services:
        db.session.add(ConsultationService(slug=slug, instructor_id=insts[ii].id, title_ar=ta, title_en=te,
                                           summary_ar=sa, summary_en=se, duration_minutes=dur,
                                           price=Decimal(price), is_published=True, is_sample=True))

    for aa, ae, ra, re_, ta, te in [
        ("متعلّم تجريبي ١", "Sample learner 1", "شخصية خيالية", "Fictional persona",
         "هذا نص تجريبي يوضّح شكل شهادات المتعلّمين. ليس رأيًا حقيقيًا.",
         "Sample text showing how learner testimonials will look. Not a real opinion."),
        ("متعلّمة تجريبية ٢", "Sample learner 2", "شخصية خيالية", "Fictional persona",
         "نص تجريبي آخر لأغراض التصميم فقط.", "Another placeholder text for design purposes only."),
        ("مؤسسة تجريبية", "Sample organisation", "شخصية خيالية", "Fictional persona",
         "نص تجريبي يمثّل رأي جهة متدرّبة. يُستبدل بآراء حقيقية موثّقة بموافقة أصحابها.",
         "Placeholder representing an organisation's feedback. Replace with genuine, consented testimonials."),
    ]:
        db.session.add(Testimonial(author_ar=aa, author_en=ae, role_ar=ra, role_en=re_, text_ar=ta, text_en=te,
                                   is_published=True, is_sample=True))
    db.session.commit()
