"""The demo walkthrough (tools/samples/demo_examples.txt) must be true, line by line.

tools/make_demo_examples.py builds the walkthrough; these tests send every request in it to the
server and check that each "->" expectation is what really comes back. Run on an empty database
(a laptop after reset) and on one full of demo data (the live server), because that is where the
screen recording happens.
"""

import sys
from pathlib import Path
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from app.main import app

TOOLS = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS))
import make_demo_examples as demo  # noqa: E402
import scenarios  # noqa: E402

from tests.test_scenarios import InProcessServer  # noqa: E402

client = TestClient(app)


def masked(value) -> bool:
    return isinstance(value, str) and ("X" in value or "*" in value)


def run_walkthrough(with_demo_data: bool) -> list[str]:
    """Send every step; return a list of the expectations that did NOT hold (empty = all good)."""
    problems = []
    for sec in demo.build(seed=11):
        for st in sec["steps"]:
            where = f"[{sec['title'][:40]}] {st.get('say', '')}"
            if st["kind"] in ("report", "challenge"):
                path = "/reports" if st["kind"] == "report" else "/challenges"
                r = client.post(path, json=st["body"])
                if r.status_code != st["status"]:
                    problems.append(f"{where}: HTTP {r.status_code}, expected {st['status']} ({r.text[:120]})")
            elif st["kind"] == "lookup":
                e = st["expect"]
                r = client.get(f"/lookup?type={st['type']}&value={quote(st['value'], safe='')}")
                if not e:                                 # no expectations written = must be refused
                    if r.status_code != 400:
                        problems.append(f"{where}: HTTP {r.status_code}, expected 400")
                    continue
                d = r.json()
                checks = {
                    "verdict": lambda v: d.get("verdict") == v,
                    "not_verdict": lambda v: d.get("verdict") != v,
                    "people": lambda v: d.get("distinct_reporters") == v,
                    "count": lambda v: d.get("report_count") == v,
                    "masked": lambda v: masked(d.get("display_value")) == v,
                    "challenged": lambda v: d.get("challenged") == v,
                }
                for key, want in e.items():
                    if not checks[key](want):
                        problems.append(f"{where}: {key} should be {want}, got {d}")
            else:
                if st["demo_only"] and not with_demo_data:
                    continue
                e = st["expect"]
                r = client.get(st["path"])
                if r.status_code != e.get("status", 200):
                    problems.append(f"{where}: HTTP {r.status_code}")
                    continue
                if r.status_code != 200:
                    continue
                d = r.json()
                areas = {c["pincode"] for c in d.get("clusters", [])}
                types = [x["type"] for x in d.get("alerts", [])]
                if "has_area" in e and e["has_area"] not in areas:
                    problems.append(f"{where}: {e['has_area']} missing from {sorted(areas)}")
                if "no_area" in e and e["no_area"] in areas:
                    problems.append(f"{where}: {e['no_area']} should not be on the map")
                if "alert" in e and e["alert"] not in types:
                    problems.append(f"{where}: expected a {e['alert']} alert, got {d}")
                if e.get("no_alerts") and types:
                    problems.append(f"{where}: expected no alerts, got {d}")
    return problems


def test_walkthrough_on_an_empty_server():
    client.post("/admin/reset")
    assert run_walkthrough(with_demo_data=False) == []


def test_walkthrough_on_top_of_the_demo_data():
    """Like the live server during a recording: the scenario demo data is loaded first."""
    scenarios.run_all(InProcessServer(), seed=7)
    assert run_walkthrough(with_demo_data=True) == []


def test_file_is_written_with_every_section(tmp_path, monkeypatch):
    monkeypatch.setattr(demo, "OUT", tmp_path / "demo.txt")
    monkeypatch.setattr(demo, "ROOT", tmp_path)
    demo.main()
    text = (tmp_path / "demo.txt").read_text(encoding="utf-8")
    for heading in ("REAL SCAM", "SPAMMING", "ONE WI-FI", "REPORT-BOMBING", "VERIFIED BUSINESS", "JUNK",
                    "MAP", "ALERTS", "DISPUTE", "LICENCE"):
        assert heading in text
