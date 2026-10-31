# 02 — Normalization & validation

Idea: the same thing typed many ways must become ONE stored key. Write these as pure
functions in `server/app/normalize.py`: `normalize(type, raw) -> str` or raise `InvalidIdentifier`.
Invalid → endpoint returns 400. Unit-test every example below.

## Phone
1. Keep digits only (remember if it started with `+`).
2. Classify:
   | Input digits | Rule | Stored |
   |---|---|---|
   | 3–4 digits starting `1` (1930, 1909, 112) | short helpline | `1930` |
   | starts `1800` or `1860`, 8–13 digits | toll-free | `18001600`, `18604195555` |
   | 12 digits starting `91` | drop 91 | `+91` + 10 |
   | 11 digits starting `0` | drop 0 | `+91` + 10 |
   | 10 digits | as is | `+91` + 10 |
   | anything else (e.g. `12345`) | invalid | 400 |
3. The 10-digit body must start with 2–9 (6–9 mobile, 2–8 landline with STD code).
4. Reject junk: all same digit (`9999999999`), straight sequences (`1234567890`, `0123456789`).

Examples (all must pass):
- `+91 98765 43210`, `09876543210`, `98765-43210`, `919876543210` → `+919876543210`
- `+91 80 4100 2233` → `+918041002233` ; `080 2553 0190` → `+918025530190`
- `1800 1600` → `18001600` ; `1860 419 5555` → `18604195555` ; `1930` → `1930`
- `12345`, `test`, `` → 400

## UPI ID
lowercase, remove all whitespace, must match `^[a-z0-9._-]{2,256}@[a-z][a-z0-9]{1,63}$`.
- `Ravi12@OKAXIS` → `ravi12@okaxis` ; ` freshbakes @okaxis ` → `freshbakes@okaxis` ; `ravi` → 400

## Link (url)
1. Trim; if no scheme, assume `https://`.
2. Parse. Lowercase host. Strip leading `www.`. Host must contain a dot and only valid chars.
3. Force scheme `https`. Drop query (`?…`) and fragment (`#…`). Drop trailing `/` from path.
4. Result: `https://` + host + path.
- `http://www.sbi-kyc.in/pay?utm=sms` → `https://sbi-kyc.in/pay`
- `https://cybercrime.gov.in/` → `https://cybercrime.gov.in`
- `notaurl`, `http://` → 400
(Verified against the PDF: the domain is `sbi-kyc.in` with the hyphen. Never remove characters from the host.)

## SMS sender (sender_id)
1. Uppercase, keep letters/digits only (removes `-`).
2. If 8 chars and first 2 are letters → take last 6 (`VMHDFCBK` → `HDFCBK`, `AD-HDFCBK` → `HDFCBK`).
3. Must now be exactly 6 alphanumerics, else 400.
(Optional: if an extra trailing suffix like `-S`/`-P`/`-T` appears, strip it before step 1.)

## Other validation for POST /reports (→ 400)
- `pincode` must exist in `data/areas.json`.
- `occurred_at` parseable ISO-8601 with offset; not more than ~10 min in the future vs server clock;
  not older than e.g. 365 days. `reported_at` (if present) ≥ `occurred_at` − small tolerance.
- `identifier_type` must be one of the four.
- `channel` unknown → store `"Something else"`; `scam_type` unknown → store `"other"` (do NOT reject).
- Missing `reporter_id` or `ip_prefix` → 400.

## Lookup input
`/lookup` runs the same normalizer on `value`; invalid → 400; valid but unknown → 200 NO_REPORTS.
