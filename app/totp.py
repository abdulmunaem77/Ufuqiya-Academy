"""RFC 6238 TOTP (SHA-1, 6 digits, 30 s) using only the standard library, plus backup codes."""
import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

from flask import current_app

STEP = 30


def new_secret():
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _code(secret, step):
    key = base64.b32decode(secret + "=" * (-len(secret) % 8), casefold=True)
    digest = hmac.new(key, struct.pack(">Q", step), hashlib.sha1).digest()
    off = digest[-1] & 0x0F
    return f"{(struct.unpack('>I', digest[off:off + 4])[0] & 0x7FFFFFFF) % 1_000_000:06d}"


def verify(secret, code, last_step=0, now=None, window=1):
    """Return the matched time-step (store it to block replay) or None."""
    code = "".join(ch for ch in (code or "") if ch.isdigit())
    if len(code) != 6:
        return None
    current = int((now if now is not None else time.time()) // STEP)
    for step in range(current - window, current + window + 1):
        if step > last_step and hmac.compare_digest(_code(secret, step), code):
            return step
    return None


def provisioning_uri(email, secret, issuer="WAHJ Academy"):
    return f"otpauth://totp/{quote(issuer)}:{quote(email)}?secret={secret}&issuer={quote(issuer)}&digits=6&period=30"


def qr_svg(uri):
    import segno
    return segno.make(uri, error="m").svg_inline(scale=5, dark="#062446", light="#FFFFFF", border=2)


# ---- backup codes ------------------------------------------------------------------
def _digest(code):
    key = current_app.config["SECRET_KEY"].encode()
    return hmac.new(key, code.strip().lower().replace("-", "").encode(), hashlib.sha256).hexdigest()


def new_backup_codes(n=8):
    alphabet = "abcdefghjkmnpqrstuvwxyz23456789"
    codes = ["".join(secrets.choice(alphabet) for _ in range(10)) for _ in range(n)]
    return codes, "\n".join(_digest(c) for c in codes)


def consume_backup_code(stored, code):
    """Return the new stored string without the used code, or None if no match."""
    d = _digest(code)
    items = [x for x in (stored or "").split("\n") if x]
    for x in items:
        if hmac.compare_digest(x, d):
            items.remove(x)
            return "\n".join(items)
    return None
