"""GET /stats logic: numbers for the app's Dashboard page ("This week in your city").

Like /map and /alerts it counts only TRUSTED reports (one per independent source), so fake waves
don't inflate the dashboard. It only returns area-level counts: no identifiers, no reporters.
Days are calendar days in India time (IST), because that is what a user means by "Tuesday".
"""

from collections import Counter, defaultdict
from datetime import timedelta

from sqlalchemy import select

from app import reference
from app.alerts import build_alerts
from app.db import engine, reports
from app.geo import severity, HIGH_HARM_TYPES, HIGH_LOSS_INR
from app.timeutil import IST, now_utc

DAYS = 7


def _ist_date(dt):
    """The India-time calendar date of a stored naive-UTC datetime."""
    return (dt + timedelta(hours=5, minutes=30)).date()


def cities() -> list[str]:
    """Cities that have areas in our list, in a stable order (Bengaluru first, as in the brief)."""
    seen = []
    for area in reference.AREAS.values():
        if area["city"] not in seen:
            seen.append(area["city"])
    return seen


def build_stats(city: str | None) -> dict:
    """Dashboard numbers for one city (or all of India when city is None).

    Out: totals this week vs last week, reports per day for 7 days, top scam types, most affected
    areas with their week-on-week change, and the latest alerts in that city.
    """
    # 1) Which areas count?
    areas = [a for a in reference.AREAS.values() if city is None or a["city"] == city]
    pins = [a["pincode"] for a in areas]
    now = now_utc()
    week_ago, two_weeks_ago = now - timedelta(days=DAYS), now - timedelta(days=2 * DAYS)

    # 2) Trusted reports for the last two weeks (this week + last week, for the trend arrows).
    with engine.connect() as conn:
        rows = conn.execute(select(reports.c.pincode, reports.c.scam_type, reports.c.occurred_at,
                                   reports.c.amount_lost_inr)
                            .where(reports.c.pincode.in_(pins), reports.c.trusted.is_(True),
                                   reports.c.occurred_at > two_weeks_ago)).all()
    this_week = [r for r in rows if r.occurred_at > week_ago]
    last_week = [r for r in rows if r.occurred_at <= week_ago]

    # 3) Reports per day for the last 7 India-time days (oldest first, zero-filled).
    today = (now + timedelta(hours=5, minutes=30)).date()
    days = [today - timedelta(days=i) for i in range(DAYS - 1, -1, -1)]
    per_day_counter = Counter(_ist_date(r.occurred_at) for r in this_week)
    per_day = [{"date": d.isoformat(), "weekday": d.strftime("%a"), "count": per_day_counter.get(d, 0)}
               for d in days]

    # 4) Top scam types this week.
    types = Counter(r.scam_type for r in this_week)
    total = len(this_week)
    top_types = [{"scam_type": t, "count": c, "share": round(c / total, 3)} for t, c in types.most_common(6)]

    # 5) Most affected areas, with change vs last week and severity (same scale as /map).
    by_area, by_area_last = defaultdict(list), Counter(r.pincode for r in last_week)
    for r in this_week:
        by_area[r.pincode].append(r)
    top_areas = []
    for pin, found in by_area.items():
        area = reference.get_area(pin)
        high_harm = bool(HIGH_HARM_TYPES & {r.scam_type for r in found}) or \
            any(r.amount_lost_inr >= HIGH_LOSS_INR for r in found)
        top_areas.append({
            "pincode": pin, "locality": area["locality"], "city": area["city"], "count": len(found),
            "last_week": by_area_last.get(pin, 0),
            "top_scam_type": Counter(r.scam_type for r in found).most_common(1)[0][0],
            "severity": severity(len(found), high_harm),
        })
    top_areas.sort(key=lambda a: -a["count"])

    # 6) Alerts in these areas right now.
    alerts = [a for a in build_alerts(None) if a["pincode"] in set(pins)]

    return {
        "city": city or "All India",
        "cities": cities(),
        "generated_at": now.replace(tzinfo=None).isoformat(),
        "reports_this_week": total,
        "reports_last_week": len(last_week),
        "areas_affected": len(by_area),
        "alerts_now": len(alerts),
        "most_reported_type": top_types[0]["scam_type"] if top_types else None,
        "per_day": per_day,
        "top_types": top_types,
        "top_areas": top_areas[:10],
        "alerts": alerts,
    }


__all__ = ["build_stats", "cities", "IST"]
