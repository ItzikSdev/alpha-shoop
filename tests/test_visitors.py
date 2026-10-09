"""Live visitors: privacy-safe event folding, source detection, the public beacon and the live view."""
import json

import pytest
from fastapi.testclient import TestClient

from src.visitors import beacon_app, events as E


def test_source_detection():
    assert E.source_of("https://l.facebook.com/", "https://s.com/?fbclid=1") == "facebook"
    assert E.source_of("", "https://s.com/?utm_source=instagram") == "instagram"
    assert E.source_of("https://www.google.com/") == "google"
    assert E.source_of("", "https://s.com/?ttclid=abc") == "tiktok"
    assert E.source_of("") == "direct"
    assert E.source_of("https://random-blog.net/post", "https://s.com/") == "other"
    assert E.source_of("https://s.com/collections", "https://s.com/products/x") == "direct"


def test_country_and_id_are_clean():
    assert E.clean_country("il") == "IL" and E.clean_country("XX") == "" and E.clean_country("<script>") == ""
    a, b = E.visitor_id("client-1"), E.visitor_id("client-1")
    assert a == b and len(a) == 12 and "client-1" not in a


def test_stage_only_moves_forward_and_purchase_is_kept():
    r = E.merge(None, "page_viewed", source="facebook", country="IL", now=100)
    r = E.merge(r, "product_viewed", source="direct", country="", now=110)
    r = E.merge(r, "page_viewed", source="direct", country="", now=120)
    assert r["stage"] == "product" and r["source"] == "facebook" and r["country"] == "IL"
    r = E.merge(r, "checkout_completed", source="direct", country="", now=130, total=49.9)
    assert r["stage"] == "purchased" and r["total"] == 49.9
    assert E.public_view("v", r, 130 + 100) is not None       # purchase still shown for 2 min
    assert E.public_view("v", r, 130 + 130) is None
    browsing = E.merge(None, "page_viewed", source="direct", country="", now=0)
    assert E.public_view("v", browsing, 299) and E.public_view("v", browsing, 301) is None


class FakeRedis:
    def __init__(self): self.d = {}
    async def get(self, k): return self.d.get(k)
    async def set(self, k, v, ex=None): self.d[k] = v


@pytest.fixture
def client(monkeypatch):
    fr = FakeRedis()
    monkeypatch.setattr(beacon_app, "_redis", fr)
    monkeypatch.setenv("VISITOR_BEACON_TOKEN", "tok")
    beacon_app._hits.clear()
    return TestClient(beacon_app.app), fr


def post(c, **kw):
    body = {"t": "tok", "cid": "abc", "ev": "page_viewed", "ref": "https://l.facebook.com/", "url": "https://shop.com/"}
    body.update(kw)
    return c.post("/v", content=json.dumps(body), headers={"content-type": "text/plain", "cf-ipcountry": "DE",
                                                           "x-forwarded-for": "9.9.9.9"})


def test_beacon_stores_privacy_safe_record(client):
    c, fr = client
    assert post(c).status_code == 204
    (key, raw), = fr.d.items()
    rec = json.loads(raw)
    assert key.startswith("vis:") and rec["source"] == "facebook" and rec["country"] == "DE"
    assert "9.9.9.9" not in raw and "abc" not in raw and "ref" not in rec and "url" not in rec


def test_beacon_rejects_bad_token_unknown_event_and_big_body(client):
    c, fr = client
    assert post(c, t="wrong").status_code == 403
    assert post(c, ev="evil_event").status_code == 204 and not fr.d
    assert c.post("/v", content="x" * 5000).status_code == 413
    assert c.post("/v", content="not json").status_code == 400


def test_beacon_rate_limit(client):
    c, _ = client
    codes = [post(c).status_code for _ in range(45)]
    assert 429 in codes and codes[0] == 204
