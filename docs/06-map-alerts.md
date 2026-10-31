# 06 — Map & alerts (10 pts + 2 bonus)

Only **trusted** reports (docs/03) are counted here. `now` = server clock.

## GET /map?pincode=&days=7&radius_km=2
1. Centre = area of `pincode` from `data/areas.json` (unknown → 400).
2. Candidate areas = all areas with haversine distance(centre, area) ≤ radius_km (centre included).
3. For each candidate: trusted reports with `now − days ≤ occurred_at ≤ now`.
4. Emit a cluster only if count > 0: pincode, locality, city, count, top_scam_type (mode),
   severity, lat/lng **from areas.json**.
5. Severity (our scale, document in README): count ≥ 10 → CRIT, ≥ 5 → HIGH, else MED.
   (Optional: bump one level if any digital-arrest/sextortion or amount lost > ₹50k.)
Month-old reports must never appear (days defaults to 7).

## GET /alerts?pincode=
Let `last24 = trusted reports in (now−24h, now]` for that pincode.
**SPIKE**
- `prior7 = trusted reports in (now−8d, now−24h]`; `baseline_per_day = prior7 / 7`
- Fire if `len(last24) ≥ 5` AND `len(last24) ≥ 2 × baseline_per_day`.
- Output `{"type":"SPIKE","pincode","window":"24h","count":len(last24),"baseline_per_day":round(.,2)}`
**NEW_TYPE**
- For each scam_type in last24 (exclude `"other"`): if no trusted report of that type in that pincode
  during (now−31d, now−24h] → `{"type":"NEW_TYPE","pincode","scam_type","window":"24h"}`.
- Edge: an area with zero history — a single report of any type would fire NEW_TYPE. Decide:
  require ≥ 2 trusted reports (from ≥ 2 clusters) of the new type to reduce noise from one person.
  Document whichever we choose.
No alerts → `{"alerts": []}`.

## Tests
- Area with 10 trusted reports today and ~2/day before → SPIKE
- Area with steady 2/day → no SPIKE
- First job-offer reports in an area with 30 days of other types → NEW_TYPE
- 40-friend fake burst → no SPIKE (weights < 0.5 → untrusted)
- Report with occurred_at 30 days ago → not on /map
- radius (computed with haversine): HSR→Bellandur 3.52 km, →Koramangala 3.60, →BTM 4.07, →JP Nagar 6.76.
  So the **default radius 2 km returns only the requested area**; radius 4 adds Bellandur + Koramangala;
  radius 5 adds BTM. Test these exact cases. The frontend map should request a large radius
  (e.g. 15 km for the city view) to show many clusters.
