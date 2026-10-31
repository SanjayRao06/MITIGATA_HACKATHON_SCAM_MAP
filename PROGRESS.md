# PROGRESS — what's built and how to test it

Claude Code: after every step in `docs/08-implementation-plan.md`, append an entry using the
template below. Write for a teammate who has not read the code. Simple words, no jargon without
a one-line explanation. Newest entry at the top.

## Status board
| Step | Name | Status |
|---|---|---|
| 0 | Skeleton + deploy | ✅ https://mitigata-hackathon-scam-map.onrender.com |
| 1 | Reference data + normalizer | ✅ |
| 2 | DB + reports + naive lookup + reset | ✅ (local + Neon tested; live after push) |
| 3 | Test harness / scenarios | ⬜ |
| 4 | Trust engine | ⬜ |
| 5 | Licence | ⬜ |
| 6 | Map + alerts | ⬜ |
| 7 | Challenges + privacy hardening | ⬜ |
| 8 | Frontend | ⬜ |
| 9 | Organiser logs replay | ⬜ |
| 10 | Add-ons | ⬜ |
| 11 | README, video, rehearsal | ⬜ |
(⬜ not started · 🟡 in progress · ✅ done)

---

## Entry template (copy this for each step)

### Step N — <name> — <date/time>
**What was built (simple terms):**
- <2–5 bullets, each one sentence a non-coder could follow; say *why* it exists>

**Files touched:**
- `path` — what it does in one line

**How to test it:**
```bash
# 1) automated tests
pytest -q tests/test_xxx.py
# expected: N passed

# 2) try it by hand
curl -s -X POST localhost:8000/reports -H 'content-type: application/json' -d '{...}'
# expected: {"report_id":"...","case_id":"...","merged":false}
```

**What to look for / how to tell it's working:**
- <observable behaviour>

**Known gaps / next:**
- <anything not done yet, any number we may need to tune>

---
<!-- entries go below, newest first -->

### Step 2 — Database + reports + naive lookup + reset — 2026-10-31
**What was built (simple terms):**
- A database with tables for reports, identifiers (one row per number/UPI/link/sender; its id is
  the `case_id`), reporters, challenges, licence and clock guard. The laptop uses SQLite (`server/dev.db`),
  Render uses Neon Postgres, with the same code.
- `POST /reports` checks a report (bad identifier / unknown pincode / bad time / missing reporter → 400),
  saves it, and replies `201 {report_id, case_id, merged}`. Sending the same `report_id` twice doesn't double-count.
- `GET /lookup` normalizes the value (so all formats match) and answers with one of the 4 verdicts.
  It counts distinct people, hides the value until 3+ people report it, and lists evidence (time,
  channel, type, area only), plus a careful `message` like "Reported by 3 people - be careful".
- `POST /admin/reset` deletes all reports (plus identifiers, reporters, challenges). The licence is kept.
- Privacy: reporter id and IP prefix are stored only as HMAC hashes, and notes are never returned.
  Neon is pinged every 4 minutes so its free tier doesn't fall asleep (waking up would exceed 0.5 s).

**Files touched:**
- `server/app/db.py` — tables + engine; SQLite locally, `DATABASE_URL` (Neon) on Render
- `server/app/timeutil.py` — parse times → UTC for storage, print as IST `+05:30`
- `server/app/privacy.py` — added `hash_value()` (HMAC) and `mask()` (PRD formats)
- `server/app/reports.py` — `validate_report()` (400 rules) + `save_report()` (store, case_id, merged)
- `server/app/lookup.py` — `lookup()` verdict/masking/evidence; `count_people()` is the part Step 4 replaces
- `server/app/main.py` — routes `/reports`, `/lookup`, `/admin/reset`; 422→400; DB keep-alive
- `server/tests/conftest.py` — tests use a throwaway SQLite file (never dev.db or Neon)
- `server/tests/test_api_basic.py` — 34 end-to-end tests

**How to test it (PowerShell):**
```powershell
cd "C:\Users\Avi Verma\Documents\Code\Scam_Map\server"
.venv\Scripts\python -m pytest -q          # expected: 110 passed
.venv\Scripts\python -m uvicorn app.main:app --reload --no-access-log
```
In a 2nd PowerShell window:
```powershell
$u = "http://localhost:8000"     # or https://mitigata-hackathon-scam-map.onrender.com
$t = (Get-Date).AddHours(-1).ToString("yyyy-MM-ddTHH:mm:ss+05:30")
foreach ($i in 1..3) {
  $b = @{report_id="demo_$i"; occurred_at=$t; reporter_id="r_$i"; ip_prefix="10.0.$i"; channel="Phone call";
         scam_type="digital-arrest"; identifier_type="phone"; identifier_value="+91 98765 43210"; pincode="560102"} | ConvertTo-Json
  Invoke-RestMethod -Method Post "$u/reports" -ContentType "application/json" -Body $b
}
Invoke-RestMethod "$u/lookup?type=phone&value=09876543210"          # KNOWN_SCAM, +919876543210
Invoke-RestMethod "$u/lookup?type=phone&value=1800%201600"          # VERIFIED_BUSINESS
Invoke-RestMethod "$u/lookup?type=phone&value=12345"                # error 400
Invoke-RestMethod -Method Post "$u/admin/reset"                     # ok, deleted_reports 3
```
Or open `http://localhost:8000/docs` for clickable forms for every endpoint.

**What to look for:**
- After 1–2 reporters: `SUSPICIOUS`, `display_value` = `98XXXXX210`. After 3: `KNOWN_SCAM`, full number.
- `1800 1600`, `VM-HDFCBK` etc. stay `VERIFIED_BUSINESS` even if people report them.
- Server log lines show only method/path/status/ms (no numbers, no IPs).

**Known gaps / next:**
- **Counting is naive on purpose:** 3 different `reporter_id`s = KNOWN_SCAM, so 22 fake accounts on
  one Wi-Fi WILL still fool it. Steps 3 (scenario script) and 4 (trust engine) fix this.
- No rate limit (429) yet (Step 4). No `/challenges` endpoint yet (Step 7), but the table exists.
- Lookups count reports live (2 indexed queries) instead of keeping a running total. This is always correct
  under parallel reports; we can add a cached summary later if lookups get slow.
- Local runs deliberately ignore `.env.local`'s DATABASE_URL so laptop tests never touch the live DB.

### Step 1 — Reference data + normalizer — 2026-10-31
**What was built (simple terms):**
- A "normalizer" that turns the many ways people type a phone / UPI ID / link / SMS sender into
  ONE stored key, so "+91 98765 43210", "09876543210" and "98765-43210" all count as the same
  number. Junk like `12345`, `9999999999` or `notaurl` is rejected (the API will turn that into a 400).
- A loader for the reference data in `server/app/data/` (25 areas, verified businesses, channels,
  scam types). At startup it re-checks every verified entry with our normalizer, so the list and
  the code can never quietly disagree.
- Helpers that map an unknown channel to "Something else" and an unknown scam type to "other"
  (docs/02 says we store these, we don't reject them).

**Files touched:**
- `server/app/normalize.py` — `normalize(type, raw)` + one function per type; raises `InvalidIdentifier`
- `server/app/reference.py` — loads the JSON files; `get_area`, `get_verified`, `canonical_channel`, `canonical_scam_type`
- `server/tests/test_normalize.py` — every example from docs/02 plus edge cases (69 cases)
- `server/tests/test_reference.py` — areas count, verified lookups via different typings, fallbacks

**How to test it:**
```bash
cd server
.venv/Scripts/python -m pytest -q tests/test_normalize.py tests/test_reference.py -v
# expected: 72 passed

# try one by hand
.venv/Scripts/python -c "from app.normalize import normalize; print(normalize('url','http://www.sbi-kyc.in/pay?utm=sms'))"
# expected: https://sbi-kyc.in/pay
```

**What to look for / how to tell it's working:**
- All four phone formats in docs/02 print `+919876543210`; `1800 1600` prints `18001600`.
- `normalize('phone','12345')` raises `InvalidIdentifier`.

**Choices we made that docs/02 didn't spell out (review these):**
- A number typed with `+` must be `+91…`; other country codes (`+1 …`) are rejected.
- "Straight sequence" junk means *rising* digits only (`1234567890`, `2345678901`).
  We had to allow falling digits because docs/02's own example `9876543210` falls.
- URLs: only http/https are accepted. The port is dropped. In `user@host` links the real
  host (after the `@`) is used. Non-ASCII hosts are turned into punycode, so lookalike domains get their own key.
- Sender IDs: a trailing `-S/-P/-T/-G` is stripped only when it has a `-` or space before it.
- Short codes that look like junk (`123`, `1234`, `1111`) are rejected. Real helplines (1930, 1909, 112) still work.
- `+91 0 98765 43210` (country code plus the extra 0) is accepted as `+919876543210`.

**PRD review (2026-10-31), after `docs/00-prd.md` was added:**
- docs/01, 02, 05 and 06 match the PRD's API rules (§A). No contract changes were needed.
- docs/03: rate-limit windows now use the report's own timestamps, not arrival time. The test tool
  replays weeks of reports in seconds, so arrival time would wrongly block real reporters ([PRD §A.0] rule 1).
- `render.yaml`: region set to Singapore (closest to India), so lookups stay under 500 ms ([PRD §3]).
- CLAUDE.md now lists `docs/00-prd.md` as the top doc, plus the per-feature reporting format.
- Notes for Step 2: Render gives `postgres://…` URLs, which must be rewritten to
  `postgresql+psycopg://…` for SQLAlchemy. The test tool may send reports in parallel, so the
  identifier summary update must be safe against two requests at once.

**Known gaps / next:**
- Report-level validation (pincode, `occurred_at` window, missing reporter_id) belongs to Step 2. The helpers it needs already exist.

---

### Step 0 — Skeleton + deploy — 2026-10-31 ✅ live at https://mitigata-hackathon-scam-map.onrender.com
**What was built (simple terms):**
- A FastAPI server with one endpoint, `GET /health` → `{"ok": true}`, which deploy platforms and judges use to check we're alive.
- A privacy-safe request logger that writes one line per request: method, path, status, milliseconds.
  It never writes query strings, bodies or IPs. Uvicorn's own access log is switched off because it prints client IPs.
- If an endpoint crashes, the log records only the error *type* and path, never the data that caused it.
- `render.yaml`, a Render "blueprint" that creates one always-on web service plus managed Postgres.
- A Python 3.11 virtual environment at `server/.venv` with everything in `requirements.txt`.

**Files touched:**
- `server/requirements.txt` — FastAPI, uvicorn, SQLAlchemy 2, Pydantic 2, PyNaCl, psycopg, pytest, httpx
- `server/app/main.py` — builds the app, loads reference data, wires `/health` and the logger
- `server/app/privacy.py` — `setup_logging()` + `safe_logging_middleware` (masking/hashing come in Step 2)
- `server/pytest.ini`, `server/tests/conftest.py` — let `pytest` run from `server/`
- `server/tests/test_health.py` — /health shape, log has no query string/IP, uvicorn access log off
- `render.yaml` — deploy config (free plans, Singapore region, `--no-access-log`, health check)
- `.gitignore` — **removed** the 3 lines that ignored `server/app/data/*.json`. The server needs
  those files at startup, so a deploy from git would have crashed without them. They hold public data, not secrets.

**How to test it:**
```bash
cd server
.venv/Scripts/python -m pytest -q
# expected: 76 passed (1 harmless httpx deprecation warning)

.venv/Scripts/python -m uvicorn app.main:app --reload --no-access-log
# in another terminal:
curl -s localhost:8000/health
# expected: {"ok":true}
curl -s "localhost:8000/health?value=9876543210"
# server terminal shows:  ... INFO GET /health 200 2.8ms   (no number, no IP)
```

**Known gaps / next:**
- **Deployed 2026-10-31** on Render (free plan, Singapore, repo owned by a teammate). Check: `curl https://mitigata-hackathon-scam-map.onrender.com/health` → `{"ok":true}`. The root `/` returns 404 until the frontend is added (Step 8).
  Render's Blueprint flow asked us for card details, so we create the service by hand instead (no card):
  Render → **New → Web Service** → pick the repo → Region **Singapore** → Root Directory `server` →
  Build `pip install -r requirements.txt` →
  Start `uvicorn app.main:app --host 0.0.0.0 --port $PORT --no-access-log --proxy-headers` →
  Instance type **Free** → Health Check Path `/health` → env vars `PYTHON_VERSION=3.11.9`,
  `HASH_SECRET=<any long random string>`, `DATABASE_URL=<from Neon, see below>`.
  Database: free **Neon** Postgres. ✅ **Created 2026-10-31:** project `scam-map` (`winter-hill-45116684`),
  org Avi, region Singapore, branch `main`. The folder is linked via `.neon`, and the connection
  strings are in `.env.local`. Both files are git-ignored. For Render's `DATABASE_URL`, paste the
  **pooled** `DATABASE_URL` value from `.env.local`, not the `_UNPOOLED` one.
  Note: on purpose, the server never reads `.env.local` (laptop = SQLite, Render = Neon via its env var). Then check `https://<service>.onrender.com/health` from a phone.
- **Free plan only (team decision).** The free web service sleeps after ~15 min idle, and the first
  request after that takes 30–60 s. Fix: set up a free pinger (UptimeRobot or cron-job.org) to
  `GET /health` every 5–10 min, and open `/health` yourself just before judging. The disk is wiped
  on every restart, so all state must go in Postgres. Free Postgres expires after ~30 days.
- `DATABASE_URL` and `HASH_SECRET` are already set in `render.yaml`, but the code doesn't use them until Step 2.
