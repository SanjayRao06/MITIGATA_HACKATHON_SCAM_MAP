"""Tests: POST /challenges and how /lookup treats a disputed number."""

import logging
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
IST = timezone(timedelta(hours=5, minutes=30))
NOTES = ["man in police uniform on video call said my aadhaar was linked to a drug parcel",
         "mujhe bola arrest warrant hai aur skype pe aana padega abhi turant",
         "they kept my father on a video call for three hours and asked for money"]


def ts(hours_ago: float) -> str:
    return (datetime.now(IST) - timedelta(hours=hours_ago)).isoformat(timespec="seconds")


def make_known_scam(value: str = "+91 98765 43210") -> None:
    """3 genuine people (own ids, networks, words, areas) -> KNOWN_SCAM."""
    for i in range(3):
        r = client.post("/reports", json={
            "occurred_at": ts(2 + i * 5), "reporter_id": f"real_{i}", "ip_prefix": f"10.{i}.0",
            "channel": "Phone call", "scam_type": "digital-arrest", "identifier_type": "phone",
            "identifier_value": value, "pincode": ["560102", "560034", "560076"][i], "note": NOTES[i]})
        assert r.status_code == 201


def challenge(**overrides) -> dict:
    body = {"identifier_type": "phone", "identifier_value": "+91 98765 43210",
            "claimant_name": "Sharma Sweets", "contact_email": "owner@example.com",
            "proof_note": "GST certificate attached"}
    body.update(overrides)
    return body


def look(value: str, id_type: str = "phone") -> dict:
    return client.get("/lookup", params={"type": id_type, "value": value}).json()


@pytest.fixture(autouse=True)
def clean():
    assert client.post("/admin/reset").status_code == 200


def test_challenge_reply_shape():
    r = client.post("/challenges", json=challenge())
    assert r.status_code == 201
    assert r.json()["status"] == "under_review"
    assert r.json()["challenge_id"].startswith("chal_")


def test_known_scam_becomes_under_review():
    make_known_scam()
    assert look("9876543210")["verdict"] == "KNOWN_SCAM"
    client.post("/challenges", json=challenge(identifier_value="09876543210"))   # any format works
    body = look("+91 98765 43210")
    assert body["challenged"] is True
    assert body["verdict"] == "SUSPICIOUS"                     # never KNOWN_SCAM while under review
    assert "under review" in body["message"].lower()
    assert body["report_count"] == 3                           # reports are kept, not deleted


def test_dispute_on_unreported_number():
    client.post("/challenges", json=challenge(identifier_value="9123456780"))
    body = look("9123456780")
    assert body["verdict"] == "NO_REPORTS" and body["challenged"] is True


def test_later_reports_cannot_make_it_known_scam():
    client.post("/challenges", json=challenge())
    make_known_scam()
    assert look("9876543210")["verdict"] == "SUSPICIOUS"


def test_verified_number_stays_verified():
    client.post("/challenges", json=challenge(identifier_value="+91 80 4100 2233", claimant_name="Fresh Bakes"))
    body = look("+91 80 4100 2233")
    assert body["verdict"] == "VERIFIED_BUSINESS"


def test_other_types_work():
    r = client.post("/challenges", json=challenge(identifier_type="upi", identifier_value="Shop.Pay@OKAXIS"))
    assert r.status_code == 201
    assert look("shop.pay@okaxis", "upi")["challenged"] is True


@pytest.mark.parametrize("override", [
    {"identifier_value": "12345"}, {"identifier_type": "email"}, {"claimant_name": ""},
    {"claimant_name": None}, {"contact_email": "not-an-email"}, {"contact_email": ""},
])
def test_bad_challenges_are_400(override):
    r = client.post("/challenges", json=challenge(**override))
    assert r.status_code == 400 and "error" in r.json()


def test_claimant_details_never_returned_or_logged(caplog):
    logger = logging.getLogger("scam_map")
    logger.addHandler(caplog.handler)
    try:
        r = client.post("/challenges", json=challenge(claimant_name="Secret Bakery Owner",
                                                      contact_email="secret.owner@example.com",
                                                      proof_note="licence number XYZ-123"))
        lookup_text = client.get("/lookup", params={"type": "phone", "value": "9876543210"}).text
    finally:
        logger.removeHandler(caplog.handler)
    for secret in ["Secret Bakery Owner", "secret.owner@example.com", "XYZ-123"]:
        assert secret not in r.text
        assert secret not in lookup_text
        assert secret not in caplog.text


def test_reset_clears_disputes():
    client.post("/challenges", json=challenge())
    client.post("/admin/reset")
    assert look("9876543210")["challenged"] is False


def test_disputed_number_is_hidden_again():
    """While under review the number is masked, even with 3+ trusted people (privacy first)."""
    make_known_scam()
    assert look("9876543210")["display_value"] == "+919876543210"
    client.post("/challenges", json=challenge())
    body = look("9876543210")
    assert body["display_value"] == "98XXXXX210" and body["masked"] is True


def test_something_else_texts_are_stored_but_never_returned():
    """channel_other / scam_type_other (website's "Something else" boxes) are kept, never shown."""
    from sqlalchemy import select
    from app.db import engine, reports
    r = client.post("/reports", json={
        "occurred_at": ts(1), "reporter_id": "r_other", "ip_prefix": "10.9.9", "channel": "Something else",
        "channel_other": "  Telegram  ", "scam_type": "other", "scam_type_other": "fake rent deposit " * 10,
        "identifier_type": "phone", "identifier_value": "9123456780", "pincode": "560102"})
    assert r.status_code == 201
    with engine.connect() as conn:
        row = conn.execute(select(reports.c.channel_other, reports.c.scam_type_other)).first()
    assert row.channel_other == "Telegram" and len(row.scam_type_other) == 60
    assert "Telegram" not in client.get("/lookup", params={"type": "phone", "value": "9123456780"}).text
