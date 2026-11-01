"""GET /map logic: how many scam reports each area had recently.

- Areas and their map points come ONLY from data/areas.json (the brief's Appendix B). We never
  store or show a reporter's own location.
- Only TRUSTED reports count (one per independent source, set by the trust rules), so a fake
  wave can't light up an area on the map.
- Time window uses each report's `occurred_at` against the server clock; default last 7 days,
  so month-old reports never appear.
"""

import math
from collections import Counter, defaultdict
from datetime import timedelta

from sqlalchemy import select

from app import reference
from app.db import engine, reports
from app.timeutil import now_utc

DEFAULT_DAYS = 7
DEFAULT_RADIUS_KM = 2.0
MAX_DAYS = 365
MAX_RADIUS_KM = 3000.0          # big enough for an all-India view from the app
# Severity scale (our own, the brief leaves it open): by trusted report count in the window.
SEVERITY_LEVELS = [(10, "CRIT"), (5, "HIGH"), (0, "MED")]
# Scams that cause the most harm bump an area up one level (and so does a big loss).
HIGH_HARM_TYPES = {"digital-arrest", "sextortion"}
HIGH_LOSS_INR = 50000


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Straight-line distance in km between two map points on the Earth's surface."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def areas_within(center: dict, radius_km: float) -> list[tuple[dict, float]]:
    """All areas whose map point is within radius_km of the centre area (centre included)."""
    out = []
    for area in reference.AREAS.values():
        d = haversine_km(center["lat"], center["lng"], area["lat"], area["lng"])
        if d <= radius_km + 1e-9:
            out.append((area, d))
    return out


def severity(count: int, high_harm: bool) -> str:
    """CRIT / HIGH / MED from the count, bumped one level for high-harm scams or big losses."""
    level = next(i for i, (minimum, _) in enumerate(SEVERITY_LEVELS) if count >= minimum)
    if high_harm and level > 0:
        level -= 1
    return SEVERITY_LEVELS[level][1]


def build_map(pincode: str | None, days: int, radius_km: float) -> list[dict]:
    """Clusters for /map.

    In: centre pincode (None = every area), window in days, radius in km.
    Out: one dict per area that has trusted reports in the window, biggest first.
    """
    # 1) Which areas are we looking at?
    if pincode is None:
        candidates = [(a, None) for a in reference.AREAS.values()]
    else:
        candidates = areas_within(reference.get_area(pincode), radius_km)
    pins = [a["pincode"] for a, _ in candidates]

    # 2) Trusted reports in those areas inside the time window (one indexed query).
    since = now_utc() - timedelta(days=days)
    with engine.connect() as conn:
        rows = conn.execute(select(reports.c.pincode, reports.c.scam_type, reports.c.amount_lost_inr)
                            .where(reports.c.pincode.in_(pins), reports.c.trusted.is_(True),
                                   reports.c.occurred_at >= since)).all()

    # 3) Group by area.
    by_pin = defaultdict(list)
    for r in rows:
        by_pin[r.pincode].append(r)

    # 4) One cluster per area with reports. Map point always from areas.json.
    clusters = []
    for area, dist in candidates:
        found = by_pin.get(area["pincode"])
        if not found:
            continue
        types = Counter(r.scam_type for r in found)
        high_harm = bool(HIGH_HARM_TYPES & set(types)) or any(r.amount_lost_inr >= HIGH_LOSS_INR for r in found)
        cluster = {
            "pincode": area["pincode"], "locality": area["locality"], "city": area["city"],
            "count": len(found), "top_scam_type": types.most_common(1)[0][0],
            "severity": severity(len(found), high_harm),
            "lat": area["lat"], "lng": area["lng"],
        }
        if dist is not None:
            cluster["distance_km"] = round(dist, 2)     # extra field, handy for the app
        clusters.append(cluster)
    clusters.sort(key=lambda c: (-c["count"], c.get("distance_km", 0)))
    return clusters
