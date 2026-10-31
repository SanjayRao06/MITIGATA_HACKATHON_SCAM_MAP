"""GET /alerts logic: tell people only when something UNUSUAL happens in an area ([PRD §A.5]).

Two kinds of alert, both counting only TRUSTED reports (so fake waves never fire one, +2 bonus):
- SPIKE:    reports in the last 24 h are at least double the daily average of the 7 days before,
            AND at least 5. ("Scam reports near you doubled today.")
- NEW_TYPE: a scam type reported in the last 24 h that wasn't seen in that area in the 30 days
            before. In an area with recent history, one trusted report of a never-seen type is
            news. In an area with no history we wait for a second independent report, so the very
            first report in a quiet area doesn't sound an alarm ("never for every report", [PRD §3]).
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


def area_alerts(pincode: str, rows: list, now) -> list[dict]:
    """Alerts for one area. In: that area's trusted reports (pincode, scam_type, occurred_at)."""
    area = reference.get_area(pincode)
    last24 = [r for r in rows if now - WINDOW < r.occurred_at <= now + timedelta(minutes=10)]
    prior7 = [r for r in rows if now - WINDOW - timedelta(days=BASELINE_DAYS) < r.occurred_at <= now - WINDOW]
    history = [r for r in rows
               if now - WINDOW - timedelta(days=NEW_TYPE_LOOKBACK_DAYS) < r.occurred_at <= now - WINDOW]
    out = []

    # 1) SPIKE: today vs the normal daily level of the week before.
    baseline = len(prior7) / BASELINE_DAYS
    if len(last24) >= SPIKE_MIN_COUNT and len(last24) >= SPIKE_FACTOR * baseline:
        out.append({"type": "SPIKE", "pincode": pincode, "window": "24h", "count": len(last24),
                    "baseline_per_day": round(baseline, 2),
                    "locality": area["locality"],
                    "message": f"Scam reports near {area['locality']} are much higher than usual today"})

    # 2) NEW_TYPE: a kind of scam this area hasn't seen in the last 30 days.
    seen_before = {r.scam_type for r in history}
    needed = NEW_TYPE_MIN_WITH_HISTORY if history else NEW_TYPE_MIN_NO_HISTORY
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
        rows = conn.execute(select(reports.c.pincode, reports.c.scam_type, reports.c.occurred_at)
                            .where(reports.c.pincode.in_(pins), reports.c.trusted.is_(True),
                                   reports.c.occurred_at > since)).all()
    by_pin = {}
    for r in rows:
        by_pin.setdefault(r.pincode, []).append(r)
    out = []
    for pin in pins:
        out.extend(area_alerts(pin, by_pin.get(pin, []), now))
    return out
