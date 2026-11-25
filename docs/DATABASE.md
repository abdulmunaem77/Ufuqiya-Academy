# WAHJ Academy — database design

PostgreSQL in production, SQLite for local development. Schema history lives in `migrations/versions/` (Flask-Migrate / Alembic);
`flask init-db` applies it. Foreign keys, unique constraints, indexes and `CHECK` constraints are defined in `app/models.py` and
created by the migrations (verified on PostgreSQL 16: 15 named `ck_*` constraints).

| Domain | Tables | Notes |
|---|---|---|
| Accounts & roles | `users` | role ∈ owner/admin/editor/support/student (CHECK); scrypt hash; lock-out counters; TOTP columns; `email_verified` |
| Catalogue | `categories`, `instructors`, `courses`, `lessons` | bilingual `*_ar/*_en` columns; `price >= 0`, `duration > 0` |
| Learning | `enrollments`, `lesson_progress`, `certificates`, `reviews` | unique (user, course); status CHECK; review rating 1–5, one per user/course; certificate code unique |
| Workshops | `workshops`, `workshop_registrations` | `capacity > 0`; registration status CHECK; unique (user, workshop) |
| Consulting | `consultation_services`, `consultation_bookings` | booking status CHECK |
| Money (manual ledger) | `payments` | `amount >= 0`; kind/status CHECK; student reference; decided_by/decided_at. **No gateway; no automatic charging.** |
| Communication | `contact_messages`, `email_outbox`, `notifications` | outbox is owner-only; notifications are per user |
| Content & audit | `site_content`, `testimonials`, `audit_logs` | audit log is append-only (no UI/route edits it) |

Relationships (all `ON` the primary keys, enforced by FKs): `users 1─* enrollments *─1 courses`, `courses *─1 categories`, `courses *─1 instructors`,
`courses 1─* lessons`, `users 1─* lesson_progress *─1 lessons`, `users 1─* reviews *─1 courses`, `users 1─* certificates *─1 courses`,
`users 1─* workshop_registrations *─1 workshops`, `users 1─* consultation_bookings *─1 consultation_services`, `users 1─* payments`, `users 1─* notifications`.

All public pages read these tables at request time (no static data in templates). The fictional demo set is optional (`flask seed`) and every row is flagged `is_sample`.
Reviews and payments are never seeded.
