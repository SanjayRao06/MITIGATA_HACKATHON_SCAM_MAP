"""Tests: the "Why this result?" reasons in GET /lookup (`why` field).

Checks that every verdict explains itself with the right reason codes (real scam, one person
reporting many times, a Wi-Fi farm, verified, no reports, disputed), and that the reasons hold
counts only: no ids, hashes, notes or times (privacy).
"""

from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.test_api_basic import real_report, report

client = TestClient(app)

# The only things a reason may contain: its code and small whole numbers.
ALLOWED_KEYS = {"code", "n", "reports", "people", "networks", "need_people", "need_networks"}


def why(id_type: str, value: str) -> tuple[str, list[dict]]:
    """Look a value up; return (verdict, why list)."""
    body = client.get(f"/lookup?type={id_type}&value={quote(value)}").json()
    return body["verdict"], body["why"]


def codes(reasons: list[dict]) -> list[str]:
    return [w["code"] for w in reasons]


@pytest.fixture(autouse=True)
def clean():
    assert client.post("/admin/reset").status_code == 200


def test_no_reports_explains_itself():
    verdict, w = why("phone", "9123456780")
    assert verdict == "NO_REPORTS" and codes(w) == ["no_reports"]


def test_verified_number_says_it_is_on_the_list_and_reports_were_set_aside():
    for i in range(4):
        client.post("/reports", json=real_report(i, identifier_value="1930"))
    verdict, w = why("phone", "1930")
    assert verdict == "VERIFIED_BUSINESS"
    assert codes(w) == ["verified_list", "verified_reports_ignored"]
    assert w[1]["n"] == 4


def test_real_scam_meets_the_bar():
    for i in range(3):
        client.post("/reports", json=real_report(i))
    verdict, w = why("phone", "9876543210")
    assert verdict == "KNOWN_SCAM"
    assert codes(w)[0] == "received" and codes(w)[-1] == "bar_met"
    indep = next(x for x in w if x["code"] == "independent")
    assert indep["people"] == 3 and indep["networks"] == 3


def test_one_person_many_times_is_explained_as_one_person():
    for i in range(3):   # 3 stored (a 4th inside the hour would be 429)
        client.post("/reports", json=report(report_id=f"s{i}", reporter_id="r_spam"))
    verdict, w = why("phone", "9876543210")
    assert verdict == "SUSPICIOUS"
    assert {"code": "same_person", "n": 2} in w
    assert w[0] == {"code": "received", "reports": 3, "people": 1}
    assert codes(w)[-1] == "bar_not_met"


def test_wifi_farm_is_explained_as_same_network():
    for i in range(22):   # 22 accounts, one Wi-Fi, a few minutes apart
        client.post("/reports", json=report(report_id=f"w{i}", reporter_id=f"r_farm{i}", ip_prefix="49.36.12",
                                            note="fake number do not trust"))
    verdict, w = why("phone", "9876543210")
    assert verdict == "SUSPICIOUS"
    assert "same_network" in codes(w)
    assert next(x for x in w if x["code"] == "same_network")["n"] >= 21
    assert "independent_none" in codes(w)   # never "0 people" next to a card saying "1 person"
    assert codes(w)[-1] == "bar_not_met"


def test_disputed_number_says_under_review():
    for i in range(3):
        client.post("/reports", json=real_report(i))
    r = client.post("/challenges", json={"identifier_type": "phone", "identifier_value": "9876543210",
                                         "claimant_name": "Asha Bakery", "contact_email": "owner@example.com",
                                         "proof_note": "GST certificate attached"})
    assert r.status_code in (200, 201)
    verdict, w = why("phone", "9876543210")
    assert verdict == "SUSPICIOUS" and codes(w)[-1] == "challenged"


def test_reasons_hold_counts_only():
    for i in range(3):
        client.post("/reports", json=real_report(i))
    client.post("/reports", json=report(report_id="x1", reporter_id="r_x", ip_prefix="10.0.0"))
    _, w = why("phone", "9876543210")
    for reason in w:
        assert set(reason) <= ALLOWED_KEYS, reason
        assert all(isinstance(v, int) for k, v in reason.items() if k != "code"), reason


def test_every_reason_code_has_english_and_hindi_text():
    """The website shows `why_<code>` from i18n.js; a code without text would silently vanish."""
    from pathlib import Path
    i18n = (Path(__file__).resolve().parents[1] / "web" / "i18n.js").read_text(encoding="utf-8")
    all_codes = ["verified_list", "verified_reports_ignored", "no_reports", "received", "same_person",
                 "same_network", "copy_paste", "coordinated", "low_weight", "independent", "independent_none", "bar_met",
                 "bar_not_met", "challenged"]
    for code in all_codes:
        assert i18n.count(f"why_{code}:") == 2, code   # once in en, once in hi
