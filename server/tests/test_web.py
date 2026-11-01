"""P6 backend tests: the website is served, /meta and /stats work, and reports from the website
get their network worked out by the server (and only ever stored hashed)."""

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import db
from app.main import app
from app.privacy import hash_value

client = TestClient(app)
IST = timezone(timedelta(hours=5, minutes=30))
WEB = Path(__file__).resolve().parents[1] / "web"


def ts(hours_ago):
    return (datetime.now(IST) - timedelta(hours=hours_ago)).isoformat(timespec="seconds")


@pytest.fixture(autouse=True)
def clean():
    client.post("/admin/reset")


# ---------------------------------------------------------------- website files
def test_home_page_is_served():
    r = client.get("/")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]
    assert "/static/app.js" in r.text


@pytest.mark.parametrize("name", ["app.js", "app.css", "i18n.js", "icons.js"])
def test_static_files_are_served(name):
    assert client.get(f"/static/{name}").status_code == 200


def test_website_files_tell_browsers_to_check_for_updates():
    """After a deploy, phones must fetch the new app.js instead of an old saved copy."""
    for path in ["/", "/static/app.js", "/static/i18n.js"]:
        assert client.get(path).headers.get("cache-control") == "no-cache", path
    # Unchanged files still come back as a tiny 304, so the site stays fast.
    first = client.get("/static/app.js")
    again = client.get("/static/app.js", headers={"if-none-match": first.headers["etag"]})
    assert again.status_code == 304
    # API replies are untouched.
    assert "cache-control" not in client.get("/health").headers


def test_api_paths_still_win_over_the_website():
    assert client.get("/map").json().keys() == {"clusters"}
    assert client.get("/health").json() == {"ok": True}


def test_no_banned_words_in_website_text():
    # [PRD §5] rule 3: never "scammer" / "fraud" / "criminal" (or the Hindi word for fraud).
    banned = re.compile(r"scammer|fraud|criminal|this person is|धोखाधड़ी|धोखेबाज़", re.IGNORECASE)
    for f in ["index.html", "app.js", "i18n.js"]:
        text = (WEB / f).read_text(encoding="utf-8")
        assert not banned.search(text), f"banned word in {f}: {banned.search(text).group(0)}"


def test_every_english_key_has_hindi():
    text = (WEB / "i18n.js").read_text(encoding="utf-8")
    en = text[text.index("en: {"):text.index("hi: {")]
    hi = text[text.index("hi: {"):text.index("/* Scam types")]
    keys = lambda block: set(re.findall(r"(\w+):\s*\"", block))
    assert keys(en) - keys(hi) == set()


# ---------------------------------------------------------------- /meta and /stats
def test_meta_lists_areas_types_channels():
    m = client.get("/meta").json()
    assert len(m["areas"]) == 55 and "digital-arrest" in m["scam_types"]
    assert "Phone call" in m["channels"] and m["cities"][0] == "Bengaluru"


def _real(pin, hours_ago, i, scam_type="otp-call"):
    r = client.post("/reports", json={
        "occurred_at": ts(hours_ago), "reporter_id": f"st_{i}", "ip_prefix": f"10.{i}.1",
        "channel": "Phone call", "scam_type": scam_type, "identifier_type": "phone",
        "identifier_value": f"98{(4512367 + i * 7919) % 10000000:07d}{i % 10}", "pincode": pin,
        "note": f"they called me about my bank otp and kept asking for the code number {i}"})
    assert r.status_code == 201, r.text


def test_stats_counts_trusted_reports_by_city():
    _real("560102", 2, 1, "digital-arrest")
    _real("560102", 30, 2)
    _real("560034", 50, 3)
    _real("400050", 5, 4)            # Mumbai: not in Bengaluru's numbers
    _real("560102", 10 * 24, 5)      # last week, for the trend
    s = client.get("/stats", params={"city": "Bengaluru"}).json()
    assert s["reports_this_week"] == 3 and s["reports_last_week"] == 1
    assert s["areas_affected"] == 2
    assert len(s["per_day"]) == 7 and sum(d["count"] for d in s["per_day"]) == 3
    assert s["top_areas"][0]["pincode"] == "560102" and s["top_areas"][0]["count"] == 2
    assert {t["scam_type"] for t in s["top_types"]} == {"otp-call", "digital-arrest"}
    assert client.get("/stats").json()["reports_this_week"] == 4         # all India
    assert client.get("/stats", params={"city": "Atlantis"}).status_code == 400


def test_stats_reveal_no_identifiers_or_reporters():
    _real("560102", 2, 7)
    text = client.get("/stats").text
    assert "st_7" not in text and "+91" not in text           # no reporter id, no phone number
    assert "reporter" not in text and "identifier" not in text and "note" not in text


# ---------------------------------------------------------------- reports from the website
def test_web_reports_get_network_from_the_connection_and_store_only_a_hash():
    r = client.post("/reports", headers={"x-forwarded-for": "49.36.12.77, 10.0.0.1"}, json={
        "occurred_at": ts(1), "reporter_id": "w_browser1", "ip_prefix": "web",
        "channel": "Phone call", "identifier_type": "phone", "identifier_value": "9876501234", "pincode": "560102"})
    assert r.status_code == 201
    with db.engine.connect() as conn:
        stored = conn.execute(select(db.reports.c.ip_hash)).scalar_one()
    assert stored == hash_value("49.36.12")          # first 3 parts, hashed
    assert "49.36" not in stored
