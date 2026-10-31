# 04 — Privacy (15 pts; any slip that identifies a reporter = disqualification)

## The five rules from the brief
1. Reporters anonymous: never store/show name, phone, exact location. Area only.
2. Hide identifiers until ≥3 distinct reporters (after trust rules).
3. Say "reported", never "scammer"/"fraud".
4. No scraping of social media / people-search sites.
5. No personal data in logs.

## How we implement them
**Storage**
- `reporter_id` and `ip_prefix` stored only as `HMAC-SHA256(SERVER_SALT, value)` (salt from env var,
  not in repo). We still can group/compare them, but a DB dump reveals nothing.
- Store `pincode`, `locality`, `city` only. No lat/lng per report, ever. Map coords come from `data/areas.json`.
- `note` stored for similarity only; never returned by any endpoint.
- Challenges store claimant_name/email (business, not reporter) — never logged, never shown in lookup.

**Masking** (`privacy.mask(type, normalized)`), used whenever distinct_reporters < 3:
| Type | Normalized | Masked |
|---|---|---|
| phone (mobile/landline) | `+919876543210` | `98XXXXX210` (first 2 + 5 X + last 3 of the 10 digits) |
| phone (short/toll-free) | `18001600` | `18XXX600` (first 2, X's, last 3) |
| upi | `ravi12@okaxis` | `r***@okaxis` |
| url | `https://sbi-kyc.in/pay` | `sbi***.in/...` (first 3 of host + *** + TLD + `/...`) |
| sender_id | `HDFCBK` | `HD****` |
VERIFIED_BUSINESS identifiers may be shown in full (they are public business numbers).
Apply masking in every response that echoes an identifier, including the app UI.

**Wording** (in API messages and UI, EN + HI)
- Good: "Reported by 7 people near you", "Reported by many people — be careful",
  "Some reports, not confirmed", "No reports yet", "Verified business".
- Banned anywhere in code/UI strings: "scammer", "fraud", "criminal", "this person is".
  (Add a test that greps the web/ and server/ string files for these words.)

**Logging**
- Disable uvicorn's default access log (it prints client IP). Use our own middleware logging
  only: method, path (without query string), status, latency ms.
- Never log bodies, query strings, identifiers, notes, reporter ids, IPs, emails.
- Exceptions: log error type + endpoint, not payload.

**Frontend**
- GPS (if used) is converted on the phone to the nearest area from `areas.json`; coordinates are
  discarded and never sent.
- Anonymous `reporter_id` = random UUID kept in localStorage. No login, no phone number.

## Checklist before demo
- [ ] `grep -ri "fraud\|scammer" web server` → only in this banned-words test
- [ ] Inspect DB: no raw reporter_id / ip / lat / lng columns
- [ ] Hit every endpoint, read server logs: nothing personal
- [ ] Lookup with 1 and 2 reporters → masked; with 3 → full
