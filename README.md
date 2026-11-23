# أكاديمية أفقيا · Ufuqia Academy — Training & Consulting

A bilingual (Arabic RTL / English LTR) learning platform: online courses, live workshops,
consultation booking, student dashboard and a role-based owner control panel.
Stack: **Python Flask · HTML/CSS/JS · SQLite (dev) → PostgreSQL (prod)**.

> All sample courses, instructors, workshops, consultations and testimonials are **fictional**
> and flagged `is_sample` (visible "Sample" labels + a site notice). Replace them from the control panel.

## Features
Public: home, courses (categories, search, level/price filters, sort, pagination), workshops, consultation
booking, about, contact/inquiry form. Student: register/login/logout, account & password change, dashboard
with enrolments and lesson-by-lesson progress, workshop registration/cancel, booking cancel.
Admin (`/admin`): courses + lessons, categories, instructors, workshops (+registrations), consulting services
and bookings, students, enrolments, editable site copy, testimonials, contact messages, team & roles,
read-only audit log, statistics.
Roles: `owner` (everything) · `admin` · `editor` (courses/workshops/content) · `support`
(students/enrolments/bookings/messages) · `student`. Enforced server-side on every route.

## Quick start (development)
```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env            # then edit: set OWNER_EMAIL (and optionally SECRET_KEY)
export FLASK_APP=wsgi.py
flask init-db                   # applies migrations (creates instance/ufuqia.db)
flask seed                      # fictional sample content (optional)
flask create-owner              # prompts for the password (hidden); see below
flask run                       # http://127.0.0.1:5000   admin: /admin/login
python -m pytest                # test suite
```

### Secure owner setup
`owner_config.py` reads `OWNER_EMAIL`, `OWNER_NAME`, `OWNER_INITIAL_PASSWORD` from the environment only; nothing is
hard-coded and `.env` is git-ignored. Recommended: leave `OWNER_INITIAL_PASSWORD` empty and type the password at the
prompt (≥ 12 chars, letters + digits). If you do provide it in the environment, the account is flagged
**must change password** and the value stops working at first login — remove it from `.env` afterwards.
The command refuses to create a second owner unless `--allow-additional` is passed. The owner role cannot be
granted or edited from the web UI. The admin URL is **not** a secret: security rests on authentication, RBAC
checks, CSRF, rate limits and lock-out.

## Security summary
scrypt password hashing · CSRF on all POSTs (Flask-WTF) · WTForms validation + length limits · SQLAlchemy
parameterised queries (LIKE wildcards escaped) · HttpOnly/SameSite cookies (`Secure` in production), session
regeneration on login/logout, strong session protection · account lock-out (5 failures → 15 min) with generic
errors and timing equalisation · Flask-Limiter on login, admin login, register, contact, enrol/book ·
strict CSP (no inline JS/CSS), `X-Frame-Options`, `nosniff`, HSTS (prod), `no-store` for signed-in pages ·
generic error pages (details only in logs) · open-redirect guard · ownership checks (no IDOR) · append-only audit log.

## Configuration (`.env`, see `.env.example`)
`APP_ENV`, `SECRET_KEY` (**required in production**), `DATABASE_URL`, `RATELIMIT_STORAGE_URI`,
`TRUSTED_PROXY_COUNT`, `ACADEMY_TIMEZONE` (default `Asia/Riyadh`; times are stored in UTC),
`DEFAULT_CURRENCY`, `SHOW_SAMPLE_NOTICE`.

## Deployment (Linux, gunicorn + nginx)
1. `python -m venv .venv && pip install -r requirements.txt "psycopg[binary]" redis`
2. PostgreSQL: create DB/user; set `DATABASE_URL=postgresql+psycopg://user:pass@host/ufuqia`.
3. `.env`: `APP_ENV=production`, a random `SECRET_KEY`, `RATELIMIT_STORAGE_URI=redis://localhost:6379`
   (needed when running more than one worker), `TRUSTED_PROXY_COUNT=1`.
4. `flask init-db && flask create-owner` (add `flask seed` only for a demo).
5. `gunicorn -w 3 -b 127.0.0.1:8000 wsgi:app` under systemd; nginx terminates **HTTPS** and proxies to it with
   `X-Forwarded-For/Proto/Host`. Serve `/static/` directly if desired.
6. Schema changes: edit `app/models.py` → `flask db migrate -m "..."` → review → `flask db upgrade`.
   Migration `migrations/versions/*` uses portable types, so the same history runs on SQLite and PostgreSQL.
   (The initial migration was generated against SQLite and tested there only — run `flask init-db` on a
   staging PostgreSQL first.)

## Project layout
```
app/            factory, models, forms, i18n (all UI strings), security, cli, seed
app/blueprints/ main · auth · courses · workshops · consult · student · admin
app/templates/  Jinja templates (public, admin, partials/macros)   app/static/  css js img fonts (self-hosted Tajawal, OFL)
migrations/     Alembic history        tests/  pytest suite        owner_config.py  config.py  wsgi.py
```

## Known limitations (honest list)
* **No payment gateway.** Free courses activate instantly; paid courses/workshops/consultations are recorded as
  *pending* and staff confirm payment manually (admin → Enrolments / Bookings). No transactions are processed.
* **No e-mail sending**, therefore no e-mail verification and no self-service password reset (an owner can issue a
  one-time temporary password from *Team & roles*). Contact/booking notifications are viewed in the panel.
* Lesson content is text only (no video hosting/uploads); no certificates; no 2FA for staff (recommended next step).
* Rate-limit storage defaults to per-process memory; use Redis in multi-worker production.
* The contact e-mail shown in the footer is a placeholder — edit it under *Site content*.
* Tested: SQLite + Chromium screenshots (desktop/mobile, AR/EN) and the pytest suite. PostgreSQL was not run here.
