# 05 — Licence (15 pts)

## Concept
Wax seal analogy: the **private key** is the king's seal ring (stays on our laptop),
the **public key** is a picture of the seal (hardcoded in server code). A **signature** is
the seal pressed on exactly these bytes: `{licensee, expires_at}`. Change one character →
signature no longer verifies. Readable by anyone, forgeable by no one.
Algorithm: Ed25519 via PyNaCl.

## Licence file
```json
{"licensee":"Demo Bank","expires_at":"2026-11-15T10:05:00+05:30","signature":"<base64>"}
```
**Canonical bytes signed/verified:**
`json.dumps({"licensee":..,"expires_at":..}, sort_keys=True, separators=(",",":")).encode()`

## Tools (laptop only, in `tools/`)
- `keygen.py` → writes `private.key` (gitignored), prints public key base64 → paste into
  `server/app/license.py` as `PUBLIC_KEY_B64`.
- `make_license.py --licensee "Demo Bank" --minutes 5 > licenses/short.json`
  (`expires_at` = now + minutes, IST offset). Long one: `--days 30`.
- `upload_license.sh <file> <base_url>` → `curl -X POST <base>/license -H 'content-type: application/json' --data @<file>`

## Server behaviour (`server/app/license.py`)
- **State:** current licence held in memory; also persisted in DB table `license` (single row) so
  restarts/redeploys keep it. On startup load from DB; if none, from `LICENSE_JSON` env var (optional).
- **Verify:** check signature with public key; parse `expires_at`.
- **Middleware (runs on every request):**
  - path `/health` or `/license` → pass
  - no licence / bad signature / `now > expires_at` / clock tampered → 403 `{"error":"LICENSE_EXPIRED"}`
  - else pass
  Cost: in-memory comparison only (microseconds).
- **GET /license** → `{"licensee","expires_at","valid":bool,"status":"VALID|EXPIRED|MISSING|CLOCK_TAMPERED","seconds_left"}`
- **POST /license** → verify signature; bad → 400 `{"error":"INVALID_SIGNATURE"}`;
  good → swap in memory + save to DB → 200 with the GET body. **No restart.**
  Auth not needed: the signature is the authentication.
- **Never delete data on expiry.** Lock only.

## Clock-rollback guard (bonus thinking)
- Table `clock_guard` with `last_seen_utc`. On each check (throttle DB write to once/minute):
  if `now < last_seen_utc − 120s` → status CLOCK_TAMPERED (treated as expired);
  else `last_seen_utc = max(last_seen_utc, now)`.

## Frontend
Any API response 403 with `LICENSE_EXPIRED` → full-screen "Licence expired. Contact your provider."
(EN + HI). Poll `/license` every 20s while on that screen; auto-recover when valid.

## Tests
- tampered expires_at → 400 on upload
- valid future licence → endpoints 200
- expired licence → /lookup 403, /health 200, /license 200
- upload new valid → /lookup 200 again, data still present
- clock rollback simulated (monkeypatch now) → 403

## Demo gotcha
`expires_at` is absolute. Generate the 5-minute licence **at demo time**, not hours earlier.
