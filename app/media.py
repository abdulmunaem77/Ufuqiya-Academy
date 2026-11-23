"""Video embeds: only YouTube and Vimeo, rebuilt from a parsed ID (never echo user URLs)."""
import re
from urllib.parse import parse_qs, urlparse

_YT = re.compile(r"^[A-Za-z0-9_-]{11}$")
_VIMEO = re.compile(r"^\d{6,12}$")


def embed_url(url):
    try:
        u = urlparse((url or "").strip())
    except ValueError:
        return None
    if u.scheme != "https":
        return None
    host = (u.hostname or "").lower().removeprefix("www.")
    if host in ("youtube.com", "m.youtube.com"):
        vid = parse_qs(u.query).get("v", [""])[0]
        if not vid and u.path.startswith(("/embed/", "/shorts/")):
            vid = u.path.split("/")[2] if len(u.path.split("/")) > 2 else ""
        return f"https://www.youtube-nocookie.com/embed/{vid}" if _YT.match(vid) else None
    if host == "youtu.be":
        vid = u.path.lstrip("/")
        return f"https://www.youtube-nocookie.com/embed/{vid}" if _YT.match(vid) else None
    if host in ("vimeo.com", "player.vimeo.com"):
        vid = u.path.rstrip("/").split("/")[-1]
        return f"https://player.vimeo.com/video/{vid}" if _VIMEO.match(vid) else None
    return None
