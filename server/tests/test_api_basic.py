"""Step 2 tests: POST /reports, GET /lookup, POST /admin/reset, end to end.

Each test starts from an empty database (the `clean` fixture calls /admin/reset).
Times are generated relative to "now", like the judges' test tool does.
"""

from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.privacy import mask

client = TestClient(app)
IST = timezone(timedelta(hours=5, minutes=30))


def ts(hours_ago: float = 1) -> str:
    """A report time `hours_ago` hours before now, in the PRD's format."""
    return (datetime.now(IST) - timedelta(hours=hours_ago)).isoformat(timespec="seconds")


def report(**overrides) -> dict:
    """A valid report body (from [PRD §A.2]); override any field per test."""
    body = {
        "report_id": None, "occurred_at": ts(2), "reported_at": ts(1),
        "reporter_id": "r_aaaa0001", "ip_prefix": "103.21.58",
        "channel": "Phone call", "scam_type": "digital-arrest",
        "identifier_type": "phone", "identifier_value": "+91 98765 43210",
        "pincode": "560102", "locality": "HSR Layout", "city": "Bengaluru",
        "note": "Video call from a man in police uniform", "has_screenshot": False,
        "amount_lost_inr": 0,
    }
    body.update(overrides)
    if body["report_id"] is None:
        body.pop("report_id")
    return body


def look(id_type: str, value: str):
    """GET /lookup with the value URL-encoded, as the test tool sends it."""
    return client.get(f"/lookup?type={id_type}&value={quote(value)}")


@pytest.fixture(autouse=True)
def clean():
    """Empty database before every test."""
    assert client.post("/admin/reset").status_code == 200


# ---------------------------------------------------------------- POST /reports
def test_report_created_then_merged():
    r1 = client.post("/reports", json=report(report_id="rep_1"))
    assert r1.status_code == 201
    assert r1.json()["report_id"] == "rep_1" and r1.json()["merged"] is False
    # Same number typed differently -> same case, merged=true.
    r2 = client.post("/reports", json=report(report_id="rep_2", reporter_id="r_b",
                                             identifier_value="09876543210"))
    assert r2.status_code == 201
    assert r2.json()["merged"] is True
    assert r2.json()["case_id"] == r1.json()["case_id"]


def test_same_report_id_twice_is_not_double_counted():
    client.post("/reports", json=report(report_id="rep_dup"))
    client.post("/reports", json=report(report_id="rep_dup"))
    assert look("phone", "9876543210").json()["report_count"] == 1


@pytest.mark.parametrize("override", [
    {"identifier_value": "12345"},                 # junk phone
    {"identifier_value": "test"},                  # junk text
    {"identifier_type": "email"},                  # unknown type
    {"pincode": "999999"},                         # not one of our 25 areas
    {"occurred_at": "yesterday"},                  # not a time
    {"occurred_at": ts(-5)},                       # 5 hours in the future
    {"occurred_at": ts(24 * 400)},                 # over a year old
    {"reported_at": ts(10), "occurred_at": ts(2)}, # reported before it happened
    {"reporter_id": ""},                           # identity missing
    {"ip_prefix": None},
])
def test_invalid_reports_are_400(override):
    r = client.post("/reports", json=report(**override))
    assert r.status_code == 400
    assert "error" in r.json()


def test_broken_json_is_400():
    r = client.post("/reports", content=b"{not json", headers={"content-type": "application/json"})
    assert r.status_code == 400


def test_unknown_channel_and_scam_type_are_accepted():
    r = client.post("/reports", json=report(channel="Carrier pigeon", scam_type="alien-invasion"))
    assert r.status_code == 201
    body = look("phone", "9876543210").json()
    assert body["evidence"][0]["channel"] == "Something else"
    assert body["scam_type"] == "other"


# ---------------------------------------------------------------- GET /lookup
def test_unknown_number_is_no_reports_not_404():
    r = look("phone", "+91 91234 56780")
    assert r.status_code == 200
    assert r.json()["verdict"] == "NO_REPORTS"
    assert r.json()["report_count"] == 0


def test_type_ignores_case_and_spaces():
    assert client.get("/lookup?type=Phone&value=1800%201600").json()["verdict"] == "VERIFIED_BUSINESS"
    assert client.get("/lookup?type=%20PHONE%20&value=1800%201600").json()["verdict"] == "VERIFIED_BUSINESS"
    assert client.post("/reports", json=report(identifier_type="Phone")).status_code == 201


def test_impossible_lookup_value_is_400():
    assert look("phone", "12345").status_code == 400
    assert client.get("/lookup?type=phone").status_code == 400
    assert client.get("/lookup?type=nope&value=x").status_code == 400


def test_all_formats_give_the_same_answer():
    for i in range(3):
        client.post("/reports", json=report(reporter_id=f"r_{i}", ip_prefix=f"10.0.{i}"))
    answers = [look("phone", v).json() for v in
               ["+91 98765 43210", "09876543210", "98765-43210", "919876543210"]]
    assert all(a == answers[0] for a in answers)


def test_two_people_suspicious_and_masked():
    client.post("/reports", json=report(reporter_id="r_1"))
    client.post("/reports", json=report(reporter_id="r_2"))
    body = look("phone", "9876543210").json()
    assert body["verdict"] == "SUSPICIOUS"
    assert body["distinct_reporters"] == 2
    assert body["display_value"] == "98XXXXX210"


def test_three_people_known_scam_and_unmasked():
    for i in range(3):
        client.post("/reports", json=report(reporter_id=f"r_{i}", ip_prefix=f"10.0.{i}"))
    body = look("phone", "9876543210").json()
    assert body["verdict"] == "KNOWN_SCAM"
    assert body["distinct_reporters"] == 3
    assert body["display_value"] == "+919876543210"
    assert body["first_seen"].endswith("+05:30")


def test_one_person_six_times_is_one_person():
    for i in range(6):
        client.post("/reports", json=report(report_id=f"rep_s{i}", reporter_id="r_spam"))
    body = look("phone", "9876543210").json()
    assert body["report_count"] == 6
    assert body["distinct_reporters"] == 1
    assert body["verdict"] != "KNOWN_SCAM"


@pytest.mark.parametrize("id_type,value", [
    ("phone", "1930"), ("phone", "1800 1600"), ("phone", "+91 80 4100 2233"),
    ("sender_id", "VM-HDFCBK"), ("url", "https://www.cybercrime.gov.in/"),
    ("upi", "FreshBakes@okaxis"),
])
def test_verified_always_wins(id_type, value):
    # Even after 5 different people report it, a verified number stays VERIFIED_BUSINESS.
    for i in range(5):
        client.post("/reports", json=report(reporter_id=f"r_{i}", ip_prefix=f"10.0.{i}",
                                            identifier_type=id_type, identifier_value=value))
    body = look(id_type, value).json()
    assert body["verdict"] == "VERIFIED_BUSINESS"
    assert "Verified business" in body["message"]


def test_evidence_never_leaks_reporter_ip_or_note():
    client.post("/reports", json=report(reporter_id="r_secret", ip_prefix="49.36.1",
                                        note="my neighbour Sunil told me"))
    r = look("phone", "9876543210")
    for leak in ["r_secret", "49.36.1", "Sunil", '"note"']:
        assert leak not in r.text
    # Evidence items carry exactly these four fields and nothing else.
    assert set(r.json()["evidence"][0]) == {"occurred_at", "channel", "scam_type", "pincode"}


def test_wording_never_accuses():
    for i in range(3):
        client.post("/reports", json=report(reporter_id=f"r_{i}", ip_prefix=f"10.0.{i}"))
    msg = look("phone", "9876543210").json()["message"].lower()
    assert "reported" in msg
    for word in ["scammer", "fraud", "criminal"]:
        assert word not in msg


# ---------------------------------------------------------------- masking formats
@pytest.mark.parametrize("id_type,value,expected", [
    ("phone", "+919876543210", "98XXXXX210"),
    ("phone", "18001600", "18XXX600"),
    ("upi", "ravi12@okaxis", "r***@okaxis"),
    ("url", "https://sbi-kyc.in/pay", "sbi***.in/..."),
    ("sender_id", "HDFCBK", "HD****"),
])
def test_mask_formats_match_prd(id_type, value, expected):
    assert mask(id_type, value) == expected


# ---------------------------------------------------------------- reset
def test_reset_deletes_everything():
    client.post("/reports", json=report())
    r = client.post("/admin/reset")
    assert r.status_code == 200 and r.json()["deleted_reports"] == 1
    assert look("phone", "9876543210").json()["verdict"] == "NO_REPORTS"
