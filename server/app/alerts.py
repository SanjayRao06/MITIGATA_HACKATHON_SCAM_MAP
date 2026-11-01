"""GET /alerts logic: tell people only when something UNUSUAL happens in an area ([PRD §A.5]).

Two kinds of alert, both counting only TRUSTED reports (so fake waves never fire one, +2 bonus):
- SPIKE:    reports in the last 24 h are at least double the daily average of the 7 days before,
            AND at least 5. ("Scam reports near you doubled today.")
- NEW_TYPE: a scam type reported in the last 24 h that wasn't seen in that area in the 30 days
            before. In an area with recent history, one trusted report of a never-seen type is
            news. In an area with no history we wait for a second independent report, so the very
            first report in a quiet area doesn't sound an alarm ("never for every report", [PRD §3]).
Both count PEOPLE, not reports: inside a window each reporter counts once, so one person
reporting several different numbers can't fake a spike or a new type ("one person reporting many
times is still one person", [PRD §4]).
Times: each report's `occurred_at` vs the server clock ([PRD §A.0] rule 1).
"""

from collections import Counter
from datetime import timedelta

from sqlalchemy import select

from app import reference
from app.db import engine, reports
from app.timeutil import now_utc

WINDOW = timedelta(hours=24)
BASELINE_DAYS = 7
NEW_TYPE_LOOKBACK_DAYS = 30
SPIKE_MIN_COUNT = 5
SPIKE_FACTOR = 2.0
NEW_TYPE_MIN_WITH_HISTORY = 1       # area had trusted reports in the 30 days before
NEW_TYPE_MIN_NO_HISTORY = 2         # brand-new area: wait for a 2nd independent report
IGNORED_TYPES = {"other"}           # "other" is a catch-all, not a new kind of scam


def one_per_person(rows: list) -> list:
    """Keep each reporter's earliest report only. In/out: report rows with reporter_hash, occurred_at.

    Why: trusted flags are worked out per number, so one person who reported 3 different numbers
    has 3 trusted reports. For an AREA count that is still one person.
    """
    first = {}
    for r in sorted(rows, key=lambda r: r.occurred_at):
        first.setdefault(r.reporter_hash, r)
    return list(first.values())


def area_alerts(pincode: str, rows: list, now) -> list[dict]:
    """Alerts for one area. In: that area's trusted reports (pincode, scam_type, occurred_at, reporter_hash)."""
    area = reference.get_area(pincode)
    # 1) Today's window counts each person once; the baseline counts each person once per day.
    last24 = one_per_person([r for r in rows if now - WINDOW < r.occurred_at <= now + timedelta(minutes=10)])
    prior7 = []
    for d in range(BASELINE_DAYS):
        day_end = now - WINDOW - timedelta(days=d)
        prior7 += one_per_person([r for r in rows if day_end - timedelta(days=1) < r.occurred_at <= day_end])
    history = [r for r in rows
               if now - WINDOW - timedelta(days=NEW_TYPE_LOOKBACK_DAYS) < r.occurred_at <= now - WINDOW]
    out = []

    # 2) SPIKE: today vs the normal daily level of the week before.
    baseline = len(prior7) / BASELINE_DAYS
    if len(last24) >= SPIKE_MIN_COUNT and len(last24) >= SPIKE_FACTOR * baseline:
        out.append({"type": "SPIKE", "pincode": pincode, "window": "24h", "count": len(last24),
                    "baseline_per_day": round(baseline, 2),
                    "locality": area["locality"],
                    "message": f"Scam reports near {area['locality']} are much higher than usual today"})

    # 3) NEW_TYPE: a kind of scam this area hasn't seen in the last 30 days.
    seen_before = {r.scam_type for r in history}
    needed = NEW_TYPE_MIN_WITH_HISTORY if history else NEW_TYPE_MIN_NO_HISTORY
    # Count people per type (last24 already holds one report per person, so this is a head count).
    for scam_type, count in sorted(Counter(r.scam_type for r in last24).items()):
        if scam_type in IGNORED_TYPES or scam_type in seen_before or count < needed:
            continue
        label = reference.SCAM_TYPES.get(scam_type, scam_type)
        out.append({"type": "NEW_TYPE", "pincode": pincode, "scam_type": scam_type, "window": "24h",
                    "count": count, "locality": area["locality"],
                    "message": f"New kind of scam reported near {area['locality']}: {label}"})
    return out


def build_alerts(pincode: str | None) -> list[dict]:
    """Alerts for one area (or every area when pincode is None)."""
    now = now_utc()
    since = now - WINDOW - timedelta(days=NEW_TYPE_LOOKBACK_DAYS)
    pins = [pincode] if pincode else list(reference.AREAS)
    with engine.connect() as conn:
        rows = conn.execute(select(reports.c.pincode, reports.c.scam_type, reports.c.occurred_at,
                                   reports.c.reporter_hash)
                            .where(reports.c.pincode.in_(pins), reports.c.trusted.is_(True),
                                   reports.c.occurred_at > since)).all()
    by_pin = {}
    for r in rows:
        by_pin.setdefault(r.pincode, []).append(r)
    out = []
    for pin in pins:
        out.extend(area_alerts(pin, by_pin.get(pin, []), now))
    return out
