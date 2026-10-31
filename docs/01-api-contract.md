# 01 — API contract (from brief Appendix A — follow exactly)

JSON in, JSON out. Extra fields in replies are fine. **No login** on these endpoints.
Times look like `2026-10-27T18:21:04+05:30`.

| # | Method + path | Purpose |
|---|---|---|
| 1 | GET /health | alive check (works even when licence expired) |
| 2 | POST /reports | receive one report |
| 3 | GET /lookup | check an identifier |
| 4 | GET /map | clusters by area, last N days |
| 5 | GET /alerts | alerts for an area |
| 6 | POST /admin/reset | delete all reports |
| 7 | POST /challenges | business disputes an identifier (bonus) |
| – | GET /license, POST /license | see docs/05 |

## Rules the test tool relies on
1. Windows ("last 7 days", "last 24h") use each report's `occurred_at` vs server clock.
2. Reporter identity = `reporter_id` + `ip_prefix` **from the body**, never the real client IP.
3. Store identifiers in one standard form (docs/02).
4. Rate-limiting a reporter → 429 (not penalised).
5. No auth.
6. Reset must work on the demo server.

## 1. GET /health → 200 `{"ok": true}`

## 2. POST /reports
Request:
```json
{"report_id":"rep_000123","occurred_at":"2026-10-27T18:21:04+05:30",
 "reported_at":"2026-10-27T18:40:04+05:30","reporter_id":"r_7c2d91aa",
 "ip_prefix":"103.21.58","channel":"Phone call","scam_type":"digital-arrest",
 "identifier_type":"phone","identifier_value":"+91 98765 43210",
 "pincode":"560102","locality":"HSR Layout","city":"Bengaluru",
 "note":"Video call from a man in police uniform...","has_screenshot":false,"amount_lost_inr":0}
```
- `identifier_type` ∈ phone | upi | url | sender_id
- `channel`, `scam_type`: see `data/scam_types.json`. Unknown scam_type → store as `"other"`, do NOT reject.
- `note` may be English / Hindi / Hinglish / empty.

Replies:
- 201 `{"report_id":"...","case_id":"...","merged":true}` — `merged` true if identifier already had a case.
- 400 `{"error":"..."}` — invalid identifier, unknown pincode, invalid/absurd time.
- 429 `{"error":"RATE_LIMITED"}` — slowing this reporter.

## 3. GET /lookup?type=phone&value=%2B91%2098765%2043210 (value URL-encoded)
```json
{"verdict":"KNOWN_SCAM","report_count":7,"distinct_reporters":7,
 "first_seen":"2026-10-14T09:12:00+05:30","last_seen":"2026-10-27T18:21:04+05:30",
 "scam_type":"digital-arrest","display_value":"+919876543210",
 "evidence":[{"occurred_at":"...","channel":"Phone call","scam_type":"digital-arrest","pincode":"560102"}],
 "challenged":false}
```
- `verdict` exactly one of: `KNOWN_SCAM`, `SUSPICIOUS`, `NO_REPORTS`, `VERIFIED_BUSINESS`.
- `distinct_reporters` = people **after trust rules** (one person ×6 = 1).
- `display_value` masked until distinct_reporters ≥ 3 (formats in docs/04).
- `evidence` never contains reporter, IP or note.
- Never reported → 200 `NO_REPORTS`. Impossible value (e.g. `12345`) → 400.
- Must respond < 500 ms.

## 4. GET /map?pincode=560102&days=7&radius_km=2 (defaults days=7, radius_km=2)
```json
{"clusters":[{"pincode":"560102","locality":"HSR Layout","city":"Bengaluru","count":12,
  "top_scam_type":"digital-arrest","severity":"CRIT","lat":12.9116,"lng":77.6473}]}
```
One cluster per area within radius that has reports in window. lat/lng from `data/areas.json` only.

## 5. GET /alerts?pincode=560102
```json
{"alerts":[
 {"type":"SPIKE","pincode":"560102","window":"24h","count":10,"baseline_per_day":2.0},
 {"type":"NEW_TYPE","pincode":"560102","scam_type":"job-offer","window":"24h"}]}
```
None → `{"alerts": []}`. Definitions in docs/06.

## 6. POST /admin/reset → 200. Deletes every report (and derived aggregates, reporter reputation, challenges). Keeps licence.

## 7. POST /challenges
```json
{"identifier_type":"phone","identifier_value":"+91 80 4100 2233","claimant_name":"Fresh Bakes",
 "contact_email":"owner@example.com","proof_note":"GST certificate and shop licence attached."}
```
→ 201 `{"challenge_id":"...","status":"under_review"}`. Afterwards lookup shows `"challenged": true`
and verdict is **never** KNOWN_SCAM while under review.

## Licence-expired behaviour
Every path except `/health` and `/license` → 403 `{"error":"LICENSE_EXPIRED"}`.
