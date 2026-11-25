"""In-app notifications (stored in the ``notifications`` table)."""
from .extensions import db
from .models import Notification


def notify(user_id, kind, title_ar, title_en, body_ar="", body_en="", url="", commit=False):
    db.session.add(Notification(user_id=user_id, kind=kind[:40], title_ar=title_ar[:200], title_en=title_en[:200],
                                body_ar=body_ar[:500], body_en=body_en[:500], url=url[:300]))
    if commit:
        db.session.commit()
