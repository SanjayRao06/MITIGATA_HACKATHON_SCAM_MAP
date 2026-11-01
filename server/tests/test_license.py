"""Tests: licence signature, lock on expiry, renew without restart, clock-rollback guard.

Mirrors the judges' 4-step live demo plus edge cases. Instead of waiting
5 real minutes we move the server's clock (`license.clock`) forward. A valid test licence is
installed before every test by conftest.py.
"""

import base64
import json
import sys
from datetime import timedelta
from pathlib import Path
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient
from nacl.signing import SigningKey

from app import db, license, timeutil
from app.main import app
from tests import licence_testkit as kit

client = TestClient(app)
TOOLS = Path(__file__).resolve().parents[2] / "tools"


def lookup(value: str = "+91 98765 43210"):
    """GET /lookup for a phone number (any licensed endpoint would do)."""
    return client.get(f"/lookup?type=phone&value={quote(value)}")


def a_report(report_id: str = "lic_rep_1") -> dict:
    """A valid report body."""
    when = (timeutil.now_utc() - timedelta(hours=1)).isoformat() + "+00:00"
    return {"report_id": report_id, "occurred_at": when, "reporter_id": "r_lic", "ip_prefix": "10.1.2",
            "channel": "Phone call", "scam_type": "otp-call", "identifier_type": "phone",
            "identifier_value": "+91 98765 43210", "pincode": "560102", "note": "asked for OTP"}


@pytest.fixture
def clock(monkeypatch):
    """Lets a test move the server clock: clock.shift(minutes=6) or clock.shift(days=-365)."""
    real = timeutil.now_utc

    class Clock:
        def shift(self, **delta):
            fake_now = real() + timedelta(**delta)
            monkeypatch.setattr(license, "clock", lambda: fake_now)
            license.state.next_sync = 0.0   # force a DB sync on the next request, like a fresh minute
            return fake_now
    return Clock()


def forget_memory() -> None:
    """Pretend the server process just restarted: nothing in memory, everything must come from the DB."""
    license.state.licence = None
    license.state.raw_body = None
    license.state.last_seen = None
    license.state.next_sync = 0.0


# ----------------------------------------------------------------------------- demo step 1
def test_get_license_shows_who_and_until_when():
    r = client.get("/license")
    assert r.status_code == 200
    body = r.json()
    assert body["licensee"] == "Test Bank" and body["valid"] is True and body["status"] == "VALID"
    assert body["expires_at"].endswith("+05:30") and body["seconds_left"] > 0


def test_valid_licence_lets_everything_through():
    assert lookup().status_code == 200
    assert client.post("/reports", json=a_report()).status_code == 201


# ----------------------------------------------------------------------------- uploads (steps 2 and 4)
def test_upload_takes_effect_immediately():
    r = client.post("/license", json=kit.make(minutes=5, licensee="Demo Bank"))
    assert r.status_code == 200
    assert r.json()["licensee"] == "Demo Bank" and r.json()["status"] == "VALID"
    assert 0 < r.json()["seconds_left"] <= 300
    assert client.get("/license").json()["licensee"] == "Demo Bank"


def test_edited_expiry_is_rejected_and_old_licence_stays():
    lic = kit.make(minutes=5, licensee="Demo Bank")
    lic["expires_at"] = "2099-01-01T00:00:00+05:30"          # someone stretches the date by hand
    r = client.post("/license", json=lic)
    assert r.status_code == 400 and r.json() == {"error": "INVALID_SIGNATURE"}
    assert client.get("/license").json()["licensee"] == "Test Bank"   # unchanged
    assert lookup().status_code == 200


def test_edited_licensee_is_rejected():
    lic = kit.make()
    lic["licensee"] = "Another Bank"
    assert client.post("/license", json=lic).json() == {"error": "INVALID_SIGNATURE"}


def test_licence_signed_with_another_key_is_rejected():
    forged = kit.make(key=SigningKey.generate())
    assert client.post("/license", json=forged).json() == {"error": "INVALID_SIGNATURE"}


@pytest.mark.parametrize("body", [{}, {"licensee": "X"}, {"licensee": "", "expires_at": "x", "signature": "y"},
                                  {"licensee": "X", "expires_at": "not a date", "signature": "AAAA"}])
def test_malformed_licence_is_400(body):
    r = client.post("/license", json=body)
    assert r.status_code == 400 and r.json()["error"] in ("INVALID_LICENSE", "INVALID_SIGNATURE")


def test_garbage_signature_is_400():
    lic = kit.make()
    lic["signature"] = "not base64!!"
    assert client.post("/license", json=lic).json() == {"error": "INVALID_SIGNATURE"}


def test_already_expired_licence_is_refused_and_server_keeps_working():
    r = client.post("/license", json=kit.make(minutes=-1))
    assert r.status_code == 400 and r.json() == {"error": "LICENSE_ALREADY_EXPIRED"}
    assert lookup().status_code == 200


# ----------------------------------------------------------------------------- step 3: expiry locks
def test_expired_licence_locks_everything_except_health_and_license(clock):
    client.post("/license", json=kit.make(minutes=5))
    clock.shift(minutes=6)                                    # 5-minute licence, 6 minutes later
    locked = [lookup(), client.post("/reports", json=a_report("lic_rep_2")),
              client.get("/map?pincode=560102"), client.get("/alerts?pincode=560102"),
              client.post("/admin/reset"), client.post("/challenges", json={})]
    for r in locked:
        assert r.status_code == 403 and r.json() == {"error": "LICENSE_EXPIRED"}
    assert client.get("/health").json() == {"ok": True}
    status = client.get("/license").json()
    assert status["status"] == "EXPIRED" and status["valid"] is False and status["seconds_left"] == 0


def test_step4_renew_without_restart_and_data_is_still_there(clock):
    # 1) Data exists, then the licence runs out.
    assert client.post("/reports", json=a_report("lic_rep_3")).status_code == 201
    client.post("/license", json=kit.make(minutes=5))
    clock.shift(minutes=6)
    assert lookup().status_code == 403
    # 2) Upload a new licence (made "now", in the moved clock's terms) -> works again at once.
    renewed = kit.sign({"licensee": "Demo Bank",
                        "expires_at": timeutil.to_ist_str(license.clock() + timedelta(days=30))})
    assert client.post("/license", json=renewed).status_code == 200
    r = lookup()
    assert r.status_code == 200 and r.json()["report_count"] >= 1   # old data untouched


def test_missing_licence_is_locked():
    with db.engine.begin() as conn:
        conn.execute(db.license_table.delete())
    forget_memory()
    assert lookup().status_code == 403
    assert client.get("/license").json()["status"] == "MISSING"


def test_website_still_loads_when_expired_but_its_data_calls_do_not(clock):
    """The page + its files must load to SHOW the expired screen; the data behind it stays locked."""
    client.post("/license", json=kit.make(minutes=5))
    clock.shift(minutes=6)
    page = client.get("/")
    if page.status_code == 404:
        pytest.skip("website not present in this checkout")
    assert page.status_code == 200
    assert client.get("/static/app.js").status_code == 200
    for path in ("/meta", "/stats", "/lookup?type=phone&value=1930", "/docs", "/openapi.json"):
        assert client.get(path).status_code == 403, path


def test_options_preflight_is_never_locked(clock):
    client.post("/license", json=kit.make(minutes=5))
    clock.shift(minutes=6)
    assert client.options("/lookup").status_code != 403


# ----------------------------------------------------------------------------- persistence
def test_licence_survives_restart():
    client.post("/license", json=kit.make(licensee="Demo Bank"))
    forget_memory()                                           # new process, empty memory
    assert lookup().status_code == 200
    assert client.get("/license").json()["licensee"] == "Demo Bank"


def test_reset_keeps_the_licence():
    assert client.post("/admin/reset").status_code == 200
    assert client.get("/license").json()["status"] == "VALID"


def test_license_json_env_var_bootstraps_an_empty_database(monkeypatch):
    with db.engine.begin() as conn:
        conn.execute(db.license_table.delete())
    forget_memory()
    monkeypatch.setenv("LICENSE_JSON", json.dumps(kit.make(licensee="Env Bank")))
    assert lookup().status_code == 200
    assert client.get("/license").json()["licensee"] == "Env Bank"


# ----------------------------------------------------------------------------- clock guard (bonus)
def test_clock_set_back_a_year_locks(clock):
    assert lookup().status_code == 200                        # server has seen "now"
    clock.shift(days=-365)
    assert lookup().status_code == 403
    assert client.get("/license").json()["status"] == "CLOCK_TAMPERED"
    clock.shift(minutes=0)                                    # clock put right again -> unlocked
    assert lookup().status_code == 200


def test_small_clock_drift_is_fine(clock):
    assert lookup().status_code == 200
    clock.shift(minutes=-1)                                   # NTP nudging the clock back a little
    assert lookup().status_code == 200


def test_rollback_is_caught_even_after_a_restart(clock):
    assert lookup().status_code == 200                        # "now" is saved to the clock_guard table
    forget_memory()                                           # restart wipes memory...
    clock.shift(days=-365)                                    # ...and the clock is set back
    assert lookup().status_code == 403


# ----------------------------------------------------------------------------- laptop tools
def _load_tool(name: str):
    """Import a script from tools/ as a module."""
    sys.path.insert(0, str(TOOLS))
    try:
        return __import__(name)
    finally:
        sys.path.remove(str(TOOLS))


def test_make_license_tool_output_is_accepted_by_the_server(tmp_path):
    tool = _load_tool("make_license")
    key_file = tmp_path / "private.key"
    key_file.write_text(base64.b64encode(bytes(kit.TEST_KEY)).decode(), encoding="ascii")
    out = tmp_path / "long.json"
    assert tool.main(["--licensee", "Demo Bank", "--days", "30", "--key", str(key_file), "--out", str(out)]) == 0
    r = client.post("/license", content=out.read_bytes(), headers={"content-type": "application/json"})
    assert r.status_code == 200 and r.json()["licensee"] == "Demo Bank"


def test_tool_and_server_sign_the_same_bytes():
    tool = _load_tool("make_license")
    lic = {"licensee": "Bänk ✓", "expires_at": "2026-11-15T10:05:00+05:30", "issued_at": "x", "signature": "s"}
    assert tool.canonical_bytes(lic) == license.canonical_bytes(lic)


def test_keygen_refuses_to_overwrite(tmp_path):
    tool = _load_tool("keygen")
    key_file = tmp_path / "private.key"
    assert tool.main(["--out", str(key_file)]) == 0
    first = key_file.read_text()
    assert tool.main(["--out", str(key_file)]) == 1           # no --force -> refuses
    assert key_file.read_text() == first


def test_server_public_key_is_a_real_ed25519_key():
    assert len(base64.b64decode(license.PUBLIC_KEY_B64)) == 32
