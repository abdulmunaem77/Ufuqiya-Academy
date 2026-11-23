import pytest

from app.models import Course
from conftest import login, post


@pytest.mark.parametrize("url", ["/", "/about", "/contact", "/courses/", "/workshops/", "/consultations/",
                                 "/login", "/register", "/admin/login", "/healthz", "/robots.txt"])
def test_public_pages_ok_both_languages(client, url):
    for lang in ("ar", "en"):
        client.get(f"/lang/{lang}")
        r = client.get(url)
        assert r.status_code == 200, (url, lang)
        if url not in ("/healthz", "/robots.txt"):
            html = r.get_data(as_text=True)
            assert f'lang="{lang}"' in html and f'dir="{"rtl" if lang == "ar" else "ltr"}"' in html


def test_rtl_default_and_switch(client):
    assert 'dir="rtl"' in client.get("/").get_data(as_text=True)
    client.get("/lang/en")
    assert 'dir="ltr"' in client.get("/").get_data(as_text=True)


def test_language_switch_rejects_bad_code_and_open_redirect(client):
    assert client.get("/lang/xx").status_code == 404
    r = client.get("/lang/en?next=https://evil.example/")
    assert r.headers["Location"].endswith("/")
    assert "evil.example" not in r.headers["Location"]
    r = client.get("/lang/en?next=//evil.example")
    assert "evil.example" not in r.headers["Location"]


def test_initial_categories_exist(client):
    client.get("/lang/en")
    html = client.get("/courses/").get_data(as_text=True)
    for name in ("Artificial Intelligence", "Technology", "Digital Marketing", "Professional Development"):
        assert name in html


def test_search_filter_and_sort(client):
    client.get("/lang/en")
    assert "Generative AI" in client.get("/courses/?q=generative").get_data(as_text=True)
    html = client.get("/courses/?q=zzzznomatch").get_data(as_text=True)
    assert "No matching courses" in html
    html = client.get("/courses/?category=technology").get_data(as_text=True)
    assert "Web Development" in html and "Generative AI" not in html
    assert "Generative AI" in client.get("/courses/?price=free").get_data(as_text=True)
    assert "Machine Learning" not in client.get("/courses/?price=free").get_data(as_text=True)
    assert client.get("/courses/?level=bogus&sort=bogus&page=-5&price=x").status_code == 200


def test_search_is_injection_safe(client):
    for payload in ["' OR 1=1 --", "%", "_", "\\", "'; DROP TABLE courses;--", "<script>alert(1)</script>"]:
        r = client.get("/courses/", query_string={"q": payload})
        assert r.status_code == 200
        assert "<script>alert(1)</script>" not in r.get_data(as_text=True)
    assert Course.query.count() == 8


def test_wildcard_search_not_match_all(client):
    client.get("/lang/en")
    assert "No matching courses" in client.get("/courses/?q=%25").get_data(as_text=True)


def test_course_detail_and_404(client):
    assert client.get("/courses/web-development-fundamentals").status_code == 200
    assert client.get("/courses/nope").status_code == 404
    assert client.get("/workshops/nope").status_code == 404


def test_unpublished_course_hidden(client, app):
    from app.extensions import db
    c = Course.query.first()
    c.is_published = False
    db.session.commit()
    assert client.get(f"/courses/{c.slug}").status_code == 404
    assert c.title_en not in client.get("/courses/").get_data(as_text=True)


def test_contact_form_and_honeypot(client, app):
    from app.models import ContactMessage
    page = "/contact"
    r = post(client, "/contact", {"name": "Sara", "email": "sara@example.com", "topic": "general",
                                  "message": "Hello, a question please."}, page=page)
    assert r.status_code == 302 and ContactMessage.query.count() == 1
    post(client, "/contact", {"name": "Bot", "email": "b@example.com", "topic": "general",
                              "message": "buy now buy now", "website": "http://spam"}, page=page)
    assert ContactMessage.query.count() == 1  # honeypot dropped silently
    r = post(client, "/contact", {"name": "", "email": "bad", "topic": "general", "message": "x"}, page=page)
    assert r.status_code == 200 and "ContactMessage" not in r.get_data(as_text=True)
    assert ContactMessage.query.count() == 1


def test_sample_content_is_labelled(client):
    client.get("/lang/en")
    html = client.get("/").get_data(as_text=True)
    assert "fictional" in html.lower() and "Sample" in html
