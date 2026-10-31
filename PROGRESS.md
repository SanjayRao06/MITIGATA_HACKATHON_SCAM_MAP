# PROGRESS — the plan, what's built, and how to test it

This file is the **team's plan and status board** (it replaces the step order in
`docs/08-implementation-plan.md`). Source of truth for *what* to build: `docs/00-prd.md`.
Claude Code: after each phase, tick it here and add an entry to the **Done log** at the bottom
(format in `docs/10-working-agreement.md`). Newest entry first.

**Live server:** https://mitigata-hackathon-scam-map.onrender.com (`/docs` for clickable tests)
**Sample requests:** `tools/samples/demo_examples.txt`

---

## Score map: where the 100 + 7 points come from ([PRD §8])
| Row | What they check | Pts | How | Covered by phase |
|---|---|---|---|---|
| 1 | Stops fake reports (bakery ×40, 22 accounts on one Wi-Fi, 1 person ×6, junk) | 20 | Test tool | P1 (+ done: junk, same person) |
| 2 | Lookup right answer, all formats match, < 0.5 s | 15 | Test tool | ✅ done; P1 keeps it right, P10 keeps it fast |
| 3 | Map + alerts (spike → alert, normal → none, new type → alert, month-old not on map) | 10 | Test tool | P3 |
| 4 | Privacy (masking, no reporter location, careful wording) — **a slip = disqualified** | 15 | Test tool + judge | ✅ backend done; P4 audit; P5 UI |
| 5 | Server + licence: 4-step live demo on https, no restart | 15 | Judge | P2 |
| 6 | Easy to report: < 60 s on a phone with a stopwatch, in **Hindi or icons only**, no login | 15 | Judge | P5 + P6 |
| 7 | Demo + code: runs from README, trust rules + licence explained, pitch | 10 | Judge | P7 |
| B1 | Verified business / helplines show "Verified business" | +3 | Test tool | ✅ done |
| B2 | Dispute feature | +2 | Test tool | P4 |
| B3 | Fake reports never set off an alert | +2 | Test tool | P1 + P3 (trusted-only counting) |
**Tie-break:** more bonus points, then **faster report time** (P5/P6 matter twice).

---

## Status board
| Phase | Feature | Points | Status |
|---|---|---|---|
| — | Skeleton + deploy, normalizer, DB, `POST /reports`, `GET /lookup`, `POST /admin/reset` | (row 2, B1) | ✅ done & live |
| P1 | Fake-report scenarios script + **trust rules** + 429 rate limit | 20 + 2 | 🟡 scenarios script ✅ (29/42 pass); trust rules next |
| P2 | **Licence** (sign, check every request, 403, upload renews, clock guard) + 2 licence files | 15 | ⬜ |
| P3 | **Map + alerts** APIs (`/map`, `/alerts`: SPIKE + NEW_TYPE, trusted reports only) | 10 + 2 | ⬜ |
| P4 | **Disputes** (`POST /challenges`) + **privacy audit** + latency check | 2 + protects 15 | ⬜ |
| P5 | **Frontend** (Report, Lookup, Map/heatmap, Licence-expired screen) — teammate can start now | 15 | ⬜ (parallel) |
| P6 | **Hindi + icons-only** report flow (build into P5, not after) | part of 15 | ⬜ (with P5) |
| P7 | **README + demo video + pitch + rehearsal ×3** + submission checklist | 10 | ⬜ |
| P8 | Extras if time: Hindi voice report (Sarvam), explain panel, lookalike domains, QR scan | tie-break | ⬜ |
| — | Keep-awake: UptimeRobot → `/health` every 5 min | protects all | ⬜ (do before judging) |
| always | **Privacy** + **speed** rules apply to every phase (see "Always-on rules") | 15 + 15 | ongoing |
(⬜ not started · 🟡 in progress · ✅ done)

**Why this order:** P1 is the biggest single score and the hardest, and the map/alerts (P3) must
count only *trusted* reports, so trust comes first. P2 is mechanical but demo-critical and must be
proven on the live https server early. P5/P6 don't block the backend, so a teammate builds them in
parallel against the live API from now on. P7 last, but the README grows as we go.

---

## Phases in detail

### P1 — Fake reports: scenarios + trust rules (20 pts + 2 bonus) · docs/03
**Build**
- `tools/scenarios.py`: sends realistic fake + real report sets (times relative to now) and prints
  PASS/FAIL: spammer ×6, 22 accounts one `ip_prefix`, 40-friend bakery burst (copy-paste/empty
  notes, ₹0, no screenshots, one area), junk, real campaign (8 people / 6 networks / own words /
  some money lost), small real (2 people). Run it after every rule change ([PRD §11]).
- `trust.py` layers: L1 same `reporter_id` = 1 + **429** (>3/h, >20/day, timed by report times);
  L2 same `ip_prefix` + same number within 24 h = 1 person; L3 near-identical notes merge, empty /
  generic notes weigh less, personal notes more; L4 coordination score (burst, new accounts, low
  network/area/text diversity, no loss/no screenshot) → penalty + blocks KNOWN_SCAM; L5 new users
  0.6, proven reporters up to 1.0, reporters of verified/disputed numbers 0.3.
- Per-report `trusted` flag (used by map + alerts). Fix: duplicate `report_id` only counts as a
  retry if reporter + identifier also match.
**Done when** every scenario PASSES (fakes never KNOWN_SCAM, real campaign is KNOWN_SCAM).
**Judges test** the 4 tricks from [PRD §4] against the live server; any trick making KNOWN_SCAM costs points.

### P2 — Licence (15 pts) · docs/05
**Build** `tools/keygen.py` (private key stays on laptop, gitignored), `tools/make_license.py`
(`--minutes 5`, `--days 30`), `license.py` (Ed25519 verify, middleware on **every** request except
`/health` + `/license`, `GET/POST /license`, stored in DB, clock-rollback guard). Expired → 403
`{"error":"LICENSE_EXPIRED"}`, **data never deleted**; new upload works **without restart**.
**Done when** the 4-step demo works on the live https URL. Make the two submission licence files.
**Judges test** live: `GET /license` → upload 5-min licence → wait → lookup 403 + app expired
screen → upload new licence → works again within a minute, old data still there ([PRD §6]).

### P3 — Map + alerts (10 pts + 2 bonus) · docs/06
**Build** `GET /map?pincode=&days=7&radius_km=2` (one cluster per area in radius with reports in
window, **area centre from Appendix B, never a reporter's location**, severity CRIT/HIGH/MED);
`GET /alerts?pincode=` with **SPIKE** (last 24 h ≥ 2× daily average of the 7 days before AND ≥ 5)
and **NEW_TYPE** (type in last 24 h not seen in that area in the 30 days before). Trusted reports only.
**Heatmap** = the frontend drawing `/map` clusters with colour/size by count (P5) — the API stays as the PRD says.
**Judges test** spike area → alert; steady area → none; new scam type → alert; month-old reports not on map.

### P4 — Disputes + privacy audit (2 bonus, protects 15) · docs/01 §7, docs/04
**Build** `POST /challenges` → 201 `{challenge_id, status:"under_review"}`; lookup then shows
`challenged:true` and is never KNOWN_SCAM. Audit: banned-words test (scammer/fraud/criminal),
DB has no raw reporter/IP/lat-lng columns, logs show nothing personal, p95 lookup < 500 ms over 200 calls.
**Judges test** dispute a number → lookup `challenged:true`, not KNOWN_SCAM ([PRD §A.7]).

### P5 + P6 — Frontend, Hindi, icons (15 pts + tie-break) · docs/07
**Build** a mobile website (design in Google Stitch, then code it), served by our server:
- **Report** in < 60 s, **no login**: tap channel icon → paste identifier → pick scam type (icons) →
  area (pick from list, or GPS converted **on the phone** to nearest area; coordinates never sent) → post.
  Anonymous `reporter_id` = random id in localStorage.
- **Lookup**: paste → colour card by verdict, careful wording, masked value, safety advice for the scam type.
- **Map**: Leaflet + OpenStreetMap (free, no card; Google Maps needs billing) with a Google-Maps-like
  light style; heat circles per area from `/map`; alerts banner from `/alerts`.
- **Licence expired** full screen on any 403 `LICENSE_EXPIRED`, auto-recovers.
- **EN/HI toggle** from day one (all text in i18n files) + **icons-only** report path.
- Helplines **1930** and **cybercrime.gov.in** visible.
**Judges test** stopwatch report on a phone, then again in Hindi or icons only (> 2 min or a login = 0).

### P7 — README, video, pitch, submission (10 pts) · docs/09
**Build** README a judge can follow alone: run locally + live URL, every endpoint with copy-paste
examples, **trust rules with the attack table** (why the bakery wasn't labelled), **licence explained**
+ 4-step demo, privacy choices, architecture. 3-min video. Rehearse the licence demo ×3 on live.
**Submission checklist ([PRD §10]):** Git repo · public server URL (awake) · app link · README ·
≤ 3-min video · **2 licence files** (5-min + long) · private key NOT in repo.

### P8 — Extras (only after P1–P7)
Hindi voice report via Sarvam (phone side only, optional, never in trust rules), explain panel,
lookalike-domain detection, UPI QR scan.

---

## Always-on rules (every phase)
**Privacy ([PRD §5] — any slip disqualifies):** never store/show reporter name, phone, exact location
(area only) · mask until ≥ 3 distinct reporters after trust rules · say "reported", never
"scammer/fraud" · no scraping of personal data · nothing personal in logs.
**Speed:** lookup < 0.5 s (indexed reads, Singapore region, DB kept awake) · report flow < 60 s.
**Contract:** endpoint paths, fields, status codes and verdict strings exactly as [PRD §A].
**No hardcoded test values** — only `data/verified.json` may list identifiers.
**Scam categories:** use the PRD's 12 `scam_type`s + 6 channels as-is (unknown → "other").
The UI may group them (e.g. "Bank/KYC", "Calls", "Money/UPI") but the API values don't change.

---

## Done log (newest first)
Each entry: what was built (simple words), files touched, how to test it, known gaps.

### Step 3 — Test harness / scenario runner — 2026-10-31
**What was built (simple terms):**
- `tools/scenarios.py`, our own copy of the judges' test tool. It wipes the server, sends ~230 realistic
  reports (timestamps relative to now), then asks `/lookup`, `/map` and `/alerts` what they think and
  prints a PASS/FAIL table (42 checks).
- Attacks it tries ([PRD §4]): one person ×6 in an hour, 22 accounts on one Wi-Fi, 40 friends bombing a
  bakery (new accounts, 2-hour burst, copy-paste/empty notes, ₹0, many home networks), and junk input.
- Things that must still work: a real 8-person campaign (own words, 6 networks, many areas, some ₹ lost),
  a real UPI wave, 2 real people (must stay hidden), verified numbers, never-reported numbers, 4 phone
  formats agreeing, no reporter data in evidence, no accusing words, lookups under 500 ms.
- Map/alerts areas: a spike area, a steady busy area, a new-scam-type area, and 30-day-old reports. Each
  scenario uses its own pincode so they can't affect each other.
- Every phone/UPI/reporter/IP value is random per run, so nobody can tune the server to them.
  Safety: on a non-local `--base` it refuses to run (it would wipe live data) unless `--allow-remote-reset`.

**Files touched:**
- `tools/scenarios.py` — the runner (standard library only, no installs needed)
- `server/tests/test_scenarios.py` — 6 tests: runner completes; junk/real/verified/small checks always PASS; remote-reset guard
- `.gitignore` — ignore `scenarios.db` (throwaway database for runs)

**How to test it (PowerShell):**
```powershell
cd server
.venv\Scripts\python -m pytest -q                       # expected: 117 passed
# start a server on a throwaway database (so dev.db is not wiped):
$env:DATABASE_URL = "sqlite:///./scenarios.db"
.venv\Scripts\python -m uvicorn app.main:app --port 8000 --no-access-log
```
In a 2nd window, from the repo root:
```powershell
server\.venv\Scripts\python tools\scenarios.py --base http://localhost:8000 --latency 200
# expected now: "29/42 checks passed", exit code 1; takes ~10 s
```

**What to look for:**
- PASS today: all junk → 400, spammer stays SUSPICIOUS (distinct 1), real campaigns → KNOWN_SCAM unmasked,
  2 people → SUSPICIOUS masked, verified list, lookup p95 ≈ 30 ms locally.
- FAIL today, on purpose: wifi-farm and bakery-bomb → KNOWN_SCAM (naive counting, fixed by Step 4),
  no 429 for the spammer (Step 4), every `/map` and `/alerts` check → "HTTP 404 (not built yet)" (Step 6).
- Goal: Step 4 turns the trust FAILs green WITHOUT turning any real-campaign row red; Step 6 does the rest.

**Known gaps / next:**
- On Windows, `localhost` costs ~2 s per request (IPv6 tried first); the runner uses `127.0.0.1` instead.
- Don't run it against the Render URL casually: it deletes every report there.
- Next: Step 4, the trust engine (docs/03).


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

**Demo samples (added 2026-10-31):**
- `tools/samples/demo_examples.txt`: copy-paste report bodies (full PRD format) and lookups, each with
  its expected result: a real scam by 3 people, a spammer, UPI, fake link, verified numbers, junk.
  Use it with `/docs`. Change the dates if you use it on another day (future times get a 400).

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
