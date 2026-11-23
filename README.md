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
scrypt password hashing · TOTP 2FA (mandatory for staff in production) · CSRF on all POSTs (Flask-WTF) · WTForms validation + length limits · SQLAlchemy
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

## What changed in v2 (closing the earlier limitations)
| Area | Now |
|---|---|
| Payments | **Manual-payment ledger** (`Payment`): paid courses/workshops/consultations create a payment request; the student pays offline (bank transfer, cash, e-wallet), enters the reference, and staff **confirm or reject** in *Control panel → Payments*. Confirming activates the enrolment / releases the workshop seat. Instructions text is editable in *Site content*. Paid workshop seats are held (`pending`) until confirmed. |
| E-mail | SMTP via `MAIL_*` variables. **E-mail verification**, **self-service password reset** (1-hour, single-use signed links), staff alerts (`MAIL_ADMIN_TO`), booking/payment notices. Every message is also stored in an owner-only **outbox**; without SMTP it works in "record only" mode. |
| Lessons | Text **plus video embeds** (YouTube / Vimeo links only, rebuilt from the parsed ID; CSP `frame-src` allow-list). No file uploads or video hosting. |
| Certificates | Issued at 100 % lesson completion, printable (save as PDF), unique code, public verification page `/verify/<code>`. Certificates for the fictional sample courses are labelled *not accredited*. |
| 2FA | **TOTP** (RFC 6238, verified against the RFC test vector) with QR code, one-time backup codes, replay protection, attempt limit and 5-minute window. Optional for students, **mandatory for staff** when `REQUIRE_STAFF_2FA` is on (default in production). |
| Rate limits | Redis storage supported and tested (two app instances share one counter). Required on Vercel. |

## Environment variables
All variables are listed, with comments, in **`.env.example`** (the single source of truth). Required in production:
`APP_ENV=production`, `SECRET_KEY`, `DATABASE_URL` (PostgreSQL), `RATELIMIT_STORAGE_URI` (Redis), `PUBLIC_BASE_URL`,
`TRUSTED_HOSTS`, `TRUSTED_PROXY_COUNT=1` (behind Vercel/nginx), and for real e-mail `MAIL_SERVER`, `MAIL_FROM`, `MAIL_USERNAME`, `MAIL_PASSWORD`.
Never commit real values; set them in the host's dashboard.

## Deploying to Vercel
The repo is Vercel-ready (`api/index.py`, `vercel.json`, `.vercelignore`, `.python-version`, pinned `requirements.txt`).
Vercel's filesystem is read-only/ephemeral, so **SQLite cannot be used** (the app refuses to start in production on Vercel with SQLite) and
rate-limit counters need Redis.

1. Create a PostgreSQL database (Neon / Supabase / Vercel Postgres) and a Redis database (Upstash / Vercel KV) and copy their URLs.
2. Import the GitHub repository in Vercel (*Add New → Project*). Framework preset: *Other*.
3. Add the environment variables above (Project → Settings → Environment Variables), for *Production* (and Preview if wanted).
   Generate `SECRET_KEY` once and keep it identical everywhere.
4. Create the schema and owner **from your computer**, pointing at the production database (serverless functions do not run migrations):
   ```bash
   export FLASK_APP=wsgi.py DATABASE_URL='postgresql://…'   # production URL
   flask init-db
   OWNER_EMAIL=you@example.com flask create-owner           # password typed at the hidden prompt
   ```
   (`flask seed` only if you want the fictional demo content.)
5. Deploy, open `/admin/login`, sign in and complete the mandatory 2FA enrolment (*account → Two-factor*).
6. Add your domain, then set `PUBLIC_BASE_URL` and `TRUSTED_HOSTS` to it.

> The Vercel configuration was written from Vercel's documented Python-runtime conventions and the entry point was exercised locally
> (boots, health check, production guards), but a real Vercel build could not be run from the development sandbox.

## Verification performed
`pytest` (116 tests) passes on **SQLite** and on **PostgreSQL 16** (`TEST_DATABASE_URL`), on Python 3.13 and on Python 3.12 from a clean venv
using only `requirements.txt`; migrations were applied to a populated SQLite database and to PostgreSQL; Redis-shared rate limiting was run against a real Redis;
pages were screenshotted in Chromium (AR/EN, desktop/mobile) with no console/CSP errors.

## Remaining limitations (honest list)
* **No online payment processing.** Payments are tracked manually (see above); no card/gateway integration and no transaction is ever charged.
* **E-mail needs your SMTP account** to actually be sent; until `MAIL_SERVER`/`MAIL_FROM` are set, mails are only recorded in the owner outbox
  (verification is then not enforced, and reset links must be handed over by the owner).
* **Video is embed-only** (YouTube/Vimeo); no uploads or self-hosted video, no quizzes. Certificates are simple printable pages (no digital signature).
* TOTP secrets are stored unencrypted in the database (protect DB access/backups); the TOTP/backup-code checks cannot protect a compromised server.
* The footer contact e-mail and the payment-account details are placeholders until you edit them in *Site content*.
* A real Vercel deployment still requires your own accounts, database, Redis and secrets (see steps above).
