import glob
import re

from app import forms
from app.i18n import CONTENT_KEYS, T
from app.models import (ALL_ROLES, BOOKING_STATUSES, ENROLL_STATUSES, LEVELS)

ROOT = __file__.rsplit("/tests/", 1)[0]


def used_static_keys():
    keys = set()
    for f in glob.glob(f"{ROOT}/app/templates/**/*.html", recursive=True):
        s = open(f, encoding="utf8").read()
        keys |= set(re.findall(r"""\bt\(\s*'([a-zA-Z0-9_.]+)'""", s))
        keys |= set(re.findall(r"""hint='([a-zA-Z0-9_.]+)'""", s))
        keys |= set(re.findall(r"""'((?:admin\.confirm_[a-z]+|dash\.cancel_confirm))'""", s))
    for f in glob.glob(f"{ROOT}/app/**/*.py", recursive=True):
        s = open(f, encoding="utf8").read()
        keys |= set(re.findall(r'''flash\(\s*"([a-zA-Z0-9_.]+)"''', s))
        keys |= set(re.findall(r'''"((?:val|admin\.err|err)\.[a-zA-Z0-9_.]+)"''', s))
    return {k for k in keys if not k.endswith(".")}


def test_every_static_key_has_both_languages():
    missing = sorted(k for k in used_static_keys() if k not in T)
    assert not missing, missing


def test_dynamic_keys(app):
    need = set()
    need |= {f"level.{x}" for x in LEVELS} | {f"status.{x}" for x in ENROLL_STATUSES + BOOKING_STATUSES}
    need |= {f"role.{x}" for x in ALL_ROLES} | {f"topic.{x}" for x in forms.TOPICS}
    need |= {f"content.{k}" for k in CONTENT_KEYS}
    from app.models import PAYMENT_KINDS, PAYMENT_STATUSES
    need |= {f"pay.s.{x}" for x in PAYMENT_STATUSES} | {f"pay.k.{x}" for x in PAYMENT_KINDS} | {f"pay.m.{x}" for x in forms.PAY_METHODS}
    need |= {"status.new", "status.read", "status.resolved", "status.disabled", "status.active"}
    with app.test_request_context():
        for name, cls in vars(forms).items():
            if isinstance(cls, type) and issubclass(cls, forms.FlaskForm) and name != "FlaskForm":
                need |= {f"f.{f.name}" for f in cls()}
    assert not sorted(k for k in need if k not in T), sorted(k for k in need if k not in T)
    # entity labels / columns
    from app.blueprints.admin import ENTITIES
    for e in ENTITIES.values():
        assert e.label in T and all(h in T for h, _ in e.columns)


def test_no_empty_translations():
    for k, (ar, en) in T.items():
        if k == "f.csrf_token":
            continue
        assert ar.strip() and en.strip(), k
        # placeholders must match across languages
        assert sorted(re.findall(r"{(\w+)}", ar)) == sorted(re.findall(r"{(\w+)}", en)), k
