"""Tests: the scenario runner (tools/scenarios.py) works end to end.

We run the whole script inside pytest against the app in memory (no real server needed).
Some scenarios are SUPPOSED to fail until the trust engine and map/alerts exist,
so here we only insist on the checks that must pass at every step: junk is rejected, real scams
are found, verified numbers stay verified, small cases stay hidden. Those are our regression guard:
if a later trust rule starts hiding real scams, these tests go red.
"""

import sys
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import scenarios  # noqa: E402 - needs the path set up above

client = TestClient(app)


class InProcessServer:
    """Same interface as scenarios.HttpServer, but calls the app directly through TestClient."""

    def request(self, method: str, path: str, body: dict | None = None):
        """In: method, path, optional JSON body. Out: (status, parsed JSON)."""
        resp = client.request(method, path, json=body)
        try:
            return resp.status_code, resp.json()
        except ValueError:
            return resp.status_code, None


# Scenarios whose every check must pass right now and forever after.
MUST_ALWAYS_PASS = {"junk", "real campaign 8", "real UPI 5", "small real 2", "lookup basics"}
# Checks that need /map, which may not exist yet (skip them in the guard until then).
NEEDS_LATER_STEP = ("/map",)


def test_runner_produces_a_full_table():
    """Every scenario runs without crashing and adds rows to the table."""
    run = scenarios.run_all(InProcessServer(), seed=1)
    names = {row[0] for row in run.results}
    assert MUST_ALWAYS_PASS <= names
    assert {"spammer x6", "wifi-farm 22 ids", "bakery-bomb 40", "spike area", "steady area",
            "new-type area", "old reports 30d", "latency"} <= names


def test_core_checks_always_pass():
    """Junk -> 400, real campaigns -> KNOWN_SCAM, verified -> VERIFIED_BUSINESS, 2 people -> hidden."""
    run = scenarios.run_all(InProcessServer(), seed=2)
    failures = [row for row in run.results
                if row[0] in MUST_ALWAYS_PASS and not row[4]
                and not any(k in row[1] for k in NEEDS_LATER_STEP)]
    assert failures == []


def test_verified_bakery_never_known_scam():
    """Even 15 bomb reports can't move the verified Fresh Bakes number off VERIFIED_BUSINESS."""
    run = scenarios.run_all(InProcessServer(), seed=3)
    row = next(r for r in run.results if r[1] == "verdict (verified Fresh Bakes)")
    assert row[4], row


def test_runs_use_fresh_random_identifiers():
    """Two runs never reuse the same numbers (no value the server could be tuned to)."""
    a, b = scenarios.Run(InProcessServer(), seed=10), scenarios.Run(InProcessServer(), seed=11)
    assert {a.phone() for _ in range(20)}.isdisjoint({b.phone() for _ in range(20)})
    assert a.tag != b.tag


def test_phone_formats_are_all_valid_for_the_server():
    """The 4 typings the runner sends all normalize to the same stored number."""
    from app.normalize import normalize
    run = scenarios.Run(InProcessServer(), seed=4)
    number = run.phone()
    assert {normalize("phone", f) for f in run.phone_formats(number)} == {number}


def test_remote_reset_needs_explicit_flag(capsys):
    """Pointing the runner at the live server without --allow-remote-reset refuses (exit 2)."""
    assert scenarios.main(["--base", "https://example.onrender.com"]) == 2
    assert "Refusing" in capsys.readouterr().out
