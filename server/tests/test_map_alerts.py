"""P3 tests: GET /map and GET /alerts ([PRD §A.4], [PRD §A.5], docs/06).

Reports are sent through the real API, one genuine person per scam number (own id, own network,
own words), so they are trusted. Fake waves are sent the way an attacker would.
"""

import itertools
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update

from app import db, geo
from app.assessment import refresh_all_trusted_flags
from app.main import app

client = TestClient(app)
IST = timezone(timedelta(hours=5, minutes=30))
_n = itertools.count(1)

HSR, BELLANDUR, KORAMANGALA, BTM, JP_NAGAR = "560102", "560103", "560034", "560076", "560078"
NOTES = ["got a call saying my bank kyc is pending and they wanted the otp code",
         "sms said electricity will be cut tonight unless I pay on this link",
         "caller asked me to install an app to get refund then money went missing",
         "lady said I won a lucky draw car and must pay gst first to claim it"]


def ts(hours_ago: float) -> str:
    return (datetime.now(IST) - timedelta(hours=hours_ago)).isoformat(timespec="seconds")


def phone() -> str:
    """A fresh valid mobile number per call (never junk-looking)."""
    i = next(_n)
    return f"9{(812345670 + i * 7919) % 1000000000:09d}"


def real(pincode: str, hours_ago: float, scam_type: str = "otp-call", **extra):
    """One genuine report about a new number: trusted by the rules."""
    i = next(_n)
    body = {"occurred_at": ts(hours_ago), "reported_at": ts(max(0, hours_ago - 0.2)),
            "reporter_id": f"real_{i}", "ip_prefix": f"10.{i % 250}.{i // 250}",
            "channel": "Phone call", "scam_type": scam_type, "identifier_type": "phone",
            "identifier_value": phone(), "pincode": pincode, "note": NOTES[i % 4] + f" ({i})"}
    body.update(extra)
    r = client.post("/reports", json=body)
    assert r.status_code == 201, r.text


def clusters(**params):
    r = client.get("/map", params=params)
    assert r.status_code == 200, r.text
    return {c["pincode"]: c for c in r.json()["clusters"]}


def alerts(pincode):
    r = client.get("/alerts", params={"pincode": pincode})
    assert r.status_code == 200, r.text
    return r.json()["alerts"]


@pytest.fixture(autouse=True)
def clean():
    assert client.post("/admin/reset").status_code == 200


# ---------------------------------------------------------------- /map
def test_distances_match_docs():
    a = {p: geo.reference.get_area(p) for p in (HSR, BELLANDUR, KORAMANGALA, BTM, JP_NAGAR)}
    d = lambda x, y: geo.haversine_km(a[x]["lat"], a[x]["lng"], a[y]["lat"], a[y]["lng"])
    assert round(d(HSR, BELLANDUR), 2) == 3.52
    assert round(d(HSR, KORAMANGALA), 2) == 3.60
    assert round(d(HSR, BTM), 2) == 4.07
    assert round(d(HSR, JP_NAGAR), 2) == 6.76


def test_radius_controls_which_areas_appear():
    for pin in (HSR, BELLANDUR, KORAMANGALA, BTM, JP_NAGAR):
        real(pin, 5)
    assert set(clusters(pincode=HSR)) == {HSR}                                   # default 2 km
    assert set(clusters(pincode=HSR, radius_km=4)) == {HSR, BELLANDUR, KORAMANGALA}
    assert set(clusters(pincode=HSR, radius_km=5)) == {HSR, BELLANDUR, KORAMANGALA, BTM}
    assert JP_NAGAR in clusters(pincode=HSR, radius_km=7)


def test_cluster_shape_and_area_point():
    real(HSR, 3, scam_type="digital-arrest")
    c = clusters(pincode=HSR)[HSR]
    area = geo.reference.get_area(HSR)
    assert (c["lat"], c["lng"]) == (area["lat"], area["lng"])               # brief's point, never a reporter's
    assert c["locality"] == "HSR Layout" and c["city"] == "Bengaluru"
    assert c["count"] == 1 and c["top_scam_type"] == "digital-arrest"
    assert c["severity"] in {"CRIT", "HIGH", "MED"}
    assert not {"reporter_id", "ip_prefix", "note"} & set(c)


def test_month_old_reports_not_on_7_day_map():
    real(HSR, 30 * 24)
    assert clusters(pincode=HSR) == {}
    assert HSR in clusters(pincode=HSR, days=40)                             # a wider window sees it


def test_severity_scale():
    assert geo.severity(12, False) == "CRIT"
    assert geo.severity(6, False) == "HIGH"
    assert geo.severity(2, False) == "MED"
    assert geo.severity(2, True) == "HIGH"       # digital arrest / big loss bumps one level
    assert geo.severity(12, True) == "CRIT"


def test_map_without_pincode_lists_all_areas():
    real(HSR, 2)
    real("400050", 2)                                                        # Bandra West, Mumbai
    assert {HSR, "400050"} <= set(clusters())


@pytest.mark.parametrize("params", [{"pincode": "999999"}, {"pincode": HSR, "days": "abc"},
                                    {"pincode": HSR, "days": "0"}, {"pincode": HSR, "radius_km": "-1"}])
def test_map_bad_input_is_400(params):
    assert client.get("/map", params=params).status_code == 400


def test_fake_wave_is_not_on_map_and_fires_no_alert():
    number = phone()
    for i in range(22):                                   # 22 accounts on one Wi-Fi, within 90 min
        client.post("/reports", json={
            "occurred_at": ts(1.5 - i * 0.06), "reporter_id": f"farm_{i}", "ip_prefix": "1.1.1",
            "channel": "Phone call", "scam_type": "investment-group", "identifier_type": "phone",
            "identifier_value": number, "pincode": HSR, "note": ["", "scam", "fraud number"][i % 3]})
    assert HSR not in clusters(pincode=HSR) or clusters(pincode=HSR)[HSR]["count"] <= 1
    assert alerts(HSR) == []


# ---------------------------------------------------------------- /alerts
def test_spike_fires_when_today_doubles():
    for d in range(1, 8):                     # ~2 a day for the week before
        real(BELLANDUR, 24 * d + 5)
        real(BELLANDUR, 24 * d + 15)
    for i in range(10):                       # 10 today
        real(BELLANDUR, 1 + i * 2)
    spikes = [a for a in alerts(BELLANDUR) if a["type"] == "SPIKE"]
    assert spikes and spikes[0]["count"] == 10 and spikes[0]["baseline_per_day"] == 2.0
    assert spikes[0]["window"] == "24h" and spikes[0]["pincode"] == BELLANDUR


def test_steady_busy_area_has_no_alert():
    for d in range(8):
        for h in range(6):
            real(KORAMANGALA, d * 24 + 1 + h * 3.5)
    assert alerts(KORAMANGALA) == []


def test_spike_needs_at_least_five():
    for i in range(4):                        # 4 today, nothing before: doubled, but fewer than 5
        real(BTM, 1 + i)
    assert not [a for a in alerts(BTM) if a["type"] == "SPIKE"]


def test_new_type_fires_in_area_with_history():
    for d in range(2, 31, 2):
        real(JP_NAGAR, d * 24 + 6, scam_type="otp-call")
    real(JP_NAGAR, 3, scam_type="job-offer")
    new = [a for a in alerts(JP_NAGAR) if a["type"] == "NEW_TYPE"]
    assert [a["scam_type"] for a in new] == ["job-offer"]
    assert new[0]["window"] == "24h"


def test_new_type_in_quiet_area_waits_for_second_report():
    real(HSR, 2, scam_type="sextortion")
    assert alerts(HSR) == []                  # first ever report in a quiet area: no alarm
    real(HSR, 1, scam_type="sextortion")
    assert [a["scam_type"] for a in alerts(HSR) if a["type"] == "NEW_TYPE"] == ["sextortion"]


def test_one_person_on_many_numbers_fires_no_alert():
    # One reporter files 3 different numbers of a new type in a quiet area, then 3 more an hour
    # later (6 trusted reports, one per number). Alerts count people, so this is still one person:
    # no NEW_TYPE (quiet area needs 2 people) and no SPIKE (needs 5).
    for i in range(6):
        real(HSR, 1 + i * 0.4, scam_type="sextortion", reporter_id="one_busy_person",
             ip_prefix="10.200.1")
    assert alerts(HSR) == []


def test_spike_counts_people_not_reports():
    # 2 people each report 3 numbers today: 6 reports but only 2 people -> no SPIKE.
    for who in ("person_a", "person_b"):
        for i in range(3):
            real(BTM, 1 + i * 0.3, reporter_id=who, ip_prefix=f"10.201.{len(who)}{i}")
    assert not [a for a in alerts(BTM) if a["type"] == "SPIKE"]


def test_known_type_is_not_new():
    real(HSR, 5 * 24, scam_type="otp-call")
    real(HSR, 2, scam_type="otp-call")
    assert alerts(HSR) == []


def test_alerts_bad_and_empty():
    assert client.get("/alerts", params={"pincode": "999999"}).status_code == 400
    assert alerts(HSR) == []


# ---------------------------------------------------------------- startup re-check of trusted flags
def test_refresh_all_restores_trusted_flags():
    real(HSR, 3)
    with db.engine.begin() as conn:                       # simulate reports saved by an older version
        conn.execute(update(db.reports).values(trusted=False))
    assert clusters(pincode=HSR) == {}
    refresh_all_trusted_flags()
    assert clusters(pincode=HSR)[HSR]["count"] == 1
