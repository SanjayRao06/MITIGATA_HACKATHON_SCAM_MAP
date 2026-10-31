# PROGRESS — Community Scam Map (Mitigata CyberForge)

> **What this file is:** the team's single reference: the full step-by-step plan, what's done, how to
> test it, the decisions we made, and the judging-day checklist.
> **Source of truth for *what* to build:** `docs/00-prd.md` (the organisers' brief). This file decides *order* and *status*.
> **How to update:** tick `[x]` tasks as they finish, update the status table, and add an entry to the
> **Done log** (§10) with how to test it. Report format: `docs/10-working-agreement.md`.

## Contents
1. [Quick reference](#1-quick-reference)
2. [Status at a glance](#2-status-at-a-glance)
3. [Score map](#3-score-map-prd-8)
4. [Step-by-step plan](#4-step-by-step-plan)
5. [Always-on rules](#5-always-on-rules-every-phase)
6. [Submission checklist](#6-submission-checklist-prd-10)
7. [Judging-day runbook](#7-judging-day-runbook)
8. [Decisions we made (and why)](#8-decisions-we-made-and-why)
9. [Risks and open questions](#9-risks-and-open-questions)
10. [Done log](#10-done-log-newest-first)

---

## 1. Quick reference
| What | Where |
|---|---|
| Live server | https://mitigata-hackathon-scam-map.onrender.com |
| Clickable API tester | `/docs` on the live server or http://localhost:8000/docs |
| Repo | https://github.com/SanjayRao06/MITIGATA_HACKATHON_SCAM_MAP |
| Database console (Neon) | https://console.neon.tech/app/projects/winter-hill-45116684 (Tables / SQL Editor) |
| Sample requests (copy-paste) | `tools/samples/demo_examples.txt` |
| Attack/real-scam test runner | `tools/scenarios.py` |
| Brief / rules / scoring | `docs/00-prd.md` (§3 features, §5 privacy, §6 licence, §8 scoring, §A API) |

**Run it locally (PowerShell):**
```powershell
cd "C:\Users\Avi Verma\Documents\Code\Scam_Map\server"
.venv\Scripts\python -m pytest -q                                      # all tests
.venv\Scripts\python -m uvicorn app.main:app --reload --no-access-log  # server on :8000
```
**One local server, one database (`dev.db`), with demo data in it.** Load or refresh the demo data from the
repo root. This WIPES dev.db's reports (the licence stays), then you add your own reports on top:
```powershell
server\.venv\Scripts\python tools\scenarios.py --seed 7     # 46/46 + "Try these on the website" list
```
(`--seed 7` = same numbers every time. A first run on a fresh dev.db needs the licence once:
`server\.venv\Scripts\python tools\upload_license.py licenses\long.json`.)
**Git routine:** `git pull` before you start → work → `git add . ; git commit -m "..." ; git push`.
Never commit `.env.local`, `.neon`, `private.key`, `licenses/`, `dev.db` (already gitignored).

---

## 2. Status at a glance
| Phase | Feature | Points | Owner | Status | Next action |
|---|---|---|---|---|---|
| P0 | Foundation: deploy, normalizer, DB, `/reports`, `/lookup`, `/admin/reset` | row 2, B1 | both | ✅ done & live | — |
| P1 | Fake reports: scenarios + **trust rules** + 429 rate limit | 20 + 2 | **Avi** | ✅ all trust checks pass (35/42 overall; the 7 left are P3 map/alerts) | — |
| P2 | **Licence** + 2 licence files | 15 | **Sanjay** | ✅ done on live (2026-11-01: lock with 403, unlock with no restart, website auto-locks without reload; long valid until 2027-10-31) | README licence section (P8); make the 5-min file fresh on demo day |
| P3 | **Map + alerts** APIs | 10 + 2 | **Avi** | ✅ 42/42 scenario checks (16/16 random runs) | — |
| P4 | **Disputes** (`/challenges`) | +2 | **Avi** | ✅ done | — |
| P5 | **Privacy + speed audit** | protects 15 + 15 | **Avi** | ⬜ | after P4 |
| P6 | **Frontend** (all 9 pages) + **Hindi + icons** | 15 | **Avi** | 🟡 built & live; needs a real-phone stopwatch test | test on a phone (EN, HI, icons) |
| P7 | **Ops**: keep-awake, frontend deploy, live run of all scenarios | protects all | **Sanjay** | 🟡 UptimeRobot on | 7.2–7.6 |
| P8 | **README + video + pitch + rehearsal** | 10 | **both** (split below) | ⬜ | grows as we go; finish last |
| P9 | Extras: Hindi voice (Sarvam), explain panel, lookalike domains, QR | tie-break | whoever is free | ⬜ | only if time |
Legend: ⬜ not started · 🟡 in progress · ✅ done

**Order and why:** P1 first, because it's the biggest score (20) and map/alerts must count only *trusted*
reports. P2 is demo-critical and must be proven on the live https server early, so it starts in parallel.
Then P3, P4, P5 close the API. P6 runs in parallel against the live API. P7 before judging. P8 last
(but the README grows with every phase). P9 only after everything else.

### Team split: two groups that can work independently
| | **Group A: Avi, "server brain"** | **Group B: Sanjay, "licence, app and delivery"** |
|---|---|---|
| Phases | P1 trust rules + 429 · P3 map + alerts · **P6 frontend + Hindi + icons** · P4 disputes · P5 privacy/speed audit | P2 licence · P7 ops · P8 video + rehearsal lead |
| Points | 20 + 10 + 15 (privacy) + 2 + 2 + 3 (done) | 15 + 15 + 10 (README/pitch shared) |
| Files you own | `server/app/trust.py`, `lookup.py`, `reports.py`, `geo.py`, `alerts.py`, `challenges` code, **everything in `web/`**; their tests; `tools/scenarios.py` updates | `server/app/license.py`, `tools/keygen.py`, `tools/make_license.py`, `licenses/` (gitignored), Render + UptimeRobot settings |
| README sections | Trust rules + attack table, privacy, map/alerts, API examples | Licence + 4-step demo, run instructions, frontend, architecture, pitch |
**Why this split works:** the API shapes are fixed by the PRD, so Sanjay can build the app against the
live server today without waiting. Licence code lives in its own file. The only shared file is
`server/app/main.py`, where each person adds a few lines (Sanjay: one middleware line + `/license` routes;
Avi: `/map`, `/alerts`, `/challenges` routes).
**Rules to avoid clashes:** `git pull` before starting and before pushing · small, frequent commits ·
don't edit the other group's files. If you must touch `main.py`, keep it to adding lines and push soon ·
run `pytest -q` before every push · tell the other person when you change anything in the API replies.
**Hand-offs:** Avi → Sanjay: the `/map` + `/alerts` reply shapes (already fixed in [PRD §A.4–A.5]) and
the extra `message` / `masked` fields in `/lookup`. Sanjay → Avi: the licence middleware (all of Avi's
tests must still pass with a valid test licence loaded).

---

## 3. Score map ([PRD §8])
| Row | What they check | Pts | Checked by | Our phase | Status |
|---|---|---|---|---|---|
| 1 | Stops fake reports: bakery ×40, 22 accounts on one Wi-Fi, 1 person ×6, junk → none become "Known scam" | 20 | Test tool | P1 | ✅ all four stopped (15/15 random runs) |
| 2 | Lookup right answer; all formats match; < 0.5 s | 15 | Test tool | P0 ✅, P1, P5 | ✅ |
| 3 | Map + alerts: spike → alert, normal → none, new type → alert, month-old not on map | 10 | Test tool | P3 | ✅ |
| 4 | Privacy: < 3 reporters hidden, map never shows a person's location, careful wording. **Reporter identifiable = disqualified** | 15 | Test tool + judge | P0 ✅, P5, P6 | backend ✅ |
| 5 | Server + licence: 4-step live demo on https, **no restart** | 15 | Judge | P2 | ✅ |
| 6 | Easy to report: phone + stopwatch < 60 s; works in **Hindi or icons only**; **no login** | 15 | Judge | P6 | 🟡 built, not yet timed on a phone |
| 7 | Demo + code: runs from README; trust rules + licence explained; pitch | 10 | Judge | P8 | ❌ |
| B1 | Verified businesses/helplines → "Verified business" | +3 | Test tool | P0 | ✅ |
| B2 | Dispute feature | +2 | Test tool | P4 | ✅ |
| B3 | Fake reports never set off an alert | +2 | Test tool | P1 + P3 | ✅ |
**Tie-break:** more bonus points, then **faster report time** (P6 counts twice).
**Automatic disqualification:** reporter identifiable · exact locations stored · personal data scraped · code written before the event.
**Judges use secret data** and check for hardcoded values like `if number == "+91..."`.

---

## 4. Step-by-step plan

### P0 — Foundation ✅ (done & live)
- [x] FastAPI app, `GET /health`, privacy-safe request logging (uvicorn access log off)
- [x] Deployed to Render (free, Singapore) + Neon Postgres (free, Singapore), env vars set
- [x] Normalizer for phone / UPI / link / SMS sender + junk rejection (`normalize.py`)
- [x] Reference data loader: 25 areas, verified list, scam types, channels (`reference.py`)
- [x] Database tables: reports, identifiers, reporters, challenges, license, clock_guard (`db.py`)
- [x] `POST /reports` with 400 rules, hashed reporter/IP, `case_id`, `merged`, duplicate `report_id` = retry
- [x] `GET /lookup`: 4 verdicts, verified wins, masking < 3 people, evidence without reporter data, careful wording
- [x] `POST /admin/reset` (keeps licence)
- [x] 422 → 400 everywhere; `/docs` shows real codes and an editable example body
- [x] Neon keep-alive ping every 4 min, **off by default** to save free compute hours: set `KEEP_DB_AWAKE=1` on Render around judging day
- [x] `tools/scenarios.py` attack/real-scam runner (teammate) + sample requests txt

### P1 — Fake reports: trust rules (20 pts + 2 bonus) · read docs/03
**Goal:** none of the 4 tricks makes a number KNOWN_SCAM, and real campaigns still do.
- [x] 1.1 Scenario runner `tools/scenarios.py` (42 checks; today 29 PASS)
- [x] 1.2 `trust.py` skeleton: one function `assess(reports) -> {effective, distinct_reporters, verdict inputs, trusted ids, explain}`; constants at the top (tunable)
- [x] 1.3 **L1 same person:** group by reporter hash; each counts once per number
- [x] 1.4 **Rate limit → 429:** > 3 reports per reporter per hour, > 20 per day, **timed by the report's own `reported_at`/`occurred_at`**, not arrival time
- [x] 1.5 **L2 same network:** same `ip_prefix` hash + same number + within 24 h → 1 effective person
- [x] 1.6 **L3 notes:** normalize text; near-duplicate notes (3-word shingles, Jaccard ≥ 0.8) merge into one source; empty ×1.0, generic short ("scam") ×0.8, personal ≥ 8 words ×1.2
- [x] 1.7 **L4 coordination score** (last 48 h): burst, newness, low network/area/text diversity, no loss + no screenshot → ≥ 0.6 ⇒ new accounts ×0.2 and KNOWN_SCAM blocked
- [x] 1.8 **L5 reputation:** new 0.6 → proven up to 1.0; reporters of verified numbers 0.3
- [x] 1.9 **Verdict:** KNOWN_SCAM needs effective ≥ 3.0 AND ≥ 3 distinct networks AND coordination < 0.6 AND not challenged; `distinct_reporters` = people after trust rules (drives masking)
- [x] 1.10 Store a per-report **`trusted`** flag (feeds P3 map/alerts)
- [x] 1.11 Fix: duplicate `report_id` counts as a retry only if reporter + identifier also match
- [x] 1.12 `GET /debug/explain?type=&value=` (behind an env flag; hashed data only) for the demo
- [x] 1.13 Unit tests per layer + full scenario run; then deploy and re-check on live
**Done when:** all trust rows in `scenarios.py` PASS **and** every real-campaign row stays PASS.
**Judges test:** load the 4 tricks from [PRD §4] into the live server, then look up the targets: none may be KNOWN_SCAM.

### P2 — Licence (15 pts) · read docs/05
**Goal:** the 4-step demo works live on https with no restart.
- [x] 2.1 `tools/keygen.py` → `private.key` (gitignored, laptop only); paste the public key into `license.py`
- [x] 2.2 `tools/make_license.py --licensee "Demo Bank" --minutes 5` / `--days 30` → JSON with Ed25519 signature
- [x] 2.3 `license.py`: verify signature over canonical JSON (all fields except `signature`); load from DB (re-read every 30 s)
- [x] 2.4 Middleware on **every** request except `/health`, `/license` (+ the website's own page/files, so the expired screen can load) → expired / missing / bad / clock tampered ⇒ 403 `{"error":"LICENSE_EXPIRED"}`
- [x] 2.5 `GET /license` → licensee, expires_at, valid, status, seconds_left, server_time
- [x] 2.6 `POST /license` → bad signature 400; good ⇒ swap in memory + save to DB, **no restart**
- [x] 2.7 **Never delete data** on expiry (lock only); reset keeps the licence
- [x] 2.8 Clock-rollback guard: remember the latest time seen (memory + DB); clock goes back > 2 min ⇒ locked, even after a restart
- [x] 2.9 Tests: tampered date → 400; valid → 200; expired → 403 (health/license still 200); renew → 200 with data intact; rollback → 403
- [x] 2.10 Upload a long licence to the live server; rehearse the 4 steps live (**right after the push deploys, see Done log**)
- [x] 2.11 Prepare **2 licence files** for submission: `licenses/long.json` (Demo Bank, 1 year) + `licenses/short.json` (5 min, **regenerate at demo time**)
**Done when:** steps 1–4 below work on the live URL.
**Judges test (live):** ① `GET /license` shows licensee + expiry → ② upload a 5-min licence → ③ after 5 min a lookup fails and the app shows the expired screen → ④ upload a new licence → works again within a minute, old data still there ([PRD §6]).

### P3 — Map + alerts (10 pts + 2 bonus) · read docs/06
**Goal:** correct clusters and alerts from **trusted** reports only.
- [x] 3.1 `geo.py`: area lookup, haversine distance, clusters within `radius_km` (default 2), `days` (default 7)
- [x] 3.2 `GET /map`: one cluster per area with reports in the window; count, top scam type, severity (≥10 CRIT, ≥5 HIGH, else MED); **lat/lng from Appendix B only**; unknown pincode → 400
- [x] 3.3 `alerts.py` **SPIKE:** last 24 h ≥ 5 AND ≥ 2 × (previous 7 days ÷ 7); output `count`, `baseline_per_day`
- [x] 3.4 **NEW_TYPE:** a scam type in last 24 h not seen in that area in the 30 days before (decide: need ≥ 2 independent reports; document it)
- [x] 3.5 `GET /alerts?pincode=` → `{"alerts": []}` when nothing unusual
- [x] 3.6 Only trusted reports count (fakes never cause alerts → +2)
- [x] 3.7 Tests: radius cases (2 km = only own area; 4 km adds Bellandur + Koramangala), month-old excluded, spike / steady / new-type
**Done when:** all map/alert rows in `scenarios.py` PASS.
**Judges test:** spike area → SPIKE; steady area → none; new scam type → NEW_TYPE; 30-day-old reports absent from `/map`.

### P4 — Disputes (+2 bonus) · read docs/01 §7
- [x] 4.1 `POST /challenges`: normalize identifier (junk → 400), require claimant name + email, create case if new
- [x] 4.2 Save challenge (`under_review`), set `challenged = true` → 201 `{challenge_id, status:"under_review"}`
- [x] 4.3 Lookup: `challenged: true`, never KNOWN_SCAM (downgrade to SUSPICIOUS), message "A business disputed these reports - under review"; verified stays verified
- [x] 4.4 Claimant name/email/proof never logged or returned
- [x] 4.5 Tests (KNOWN_SCAM → challenge → SUSPICIOUS + challenged)
**Judges test:** challenge a number, then lookup shows `challenged: true` and isn't KNOWN_SCAM ([PRD §A.7]).

### P5 — Privacy + speed audit (protects 15 + 15) · read docs/04
- [x] 5.1 Banned-words test over `server/` and `web/` strings: scammer, fraud, criminal, "this person is"
- [x] 5.2 DB audit: no raw reporter_id / IP / name / phone / lat-lng columns
- [x] 5.3 Log audit: hit every endpoint; logs show only method, path, status, ms
- [x] 5.4 Masking check in API **and** UI (1 and 2 reporters hidden, 3 shown)
- [~] 5.5 Latency: p95 lookup < 500 ms over 200 calls on the **live** server. Run `python tools/latency_check.py --base <live url>` (read-only). Result 2026-11-01 from Avi's laptop: lookup median 237 ms, p95 480-610 ms; `/health` (no DB) is just as slow, so our code adds ~0 ms and the p95 is network jitter to Render Singapore. Still to do: check the server-side ms in Render logs, and try from another network (phone hotspot)
- [x] 5.6 Grep for hardcoded identifiers outside `data/verified.json`
**Done when:** every box in docs/04's checklist is ticked.
_Status 2026-11-01: 5.1-5.4 and 5.6 done locally (`server/tests/test_privacy_audit.py`, 16 tests; 225 tests pass in all). 5.5 local p95 = 17 ms over 200 lookups; the live run (`scenarios.py --latency 200`, needs the team's OK) is still open._

### P6 — Frontend + Hindi + icons (15 pts + tie-break) · read docs/07 · can start now in parallel
**Goal:** a judge reports a scam on a phone in < 60 s (target < 30 s), also in Hindi or icons only, no login.
**Design decisions (2026-10-31):** palette **Sage & Cream**: bg `#F6F1E4`, cards `#FFFDF7`, primary sage `#4F6F52`,
accent gold `#C9A227`, text `#22302A`, borders `#E5DECC`; results red `#B5452F` / amber `#D99A1E` / grey `#8A8577` /
verified `#2E8B57`. Style **clean civic** (flat, thin borders, radius 12, line icons, no gradients). Fonts: Fraunces/Literata
headings, Source Sans 3 body, Noto Sans Devanagari. **Responsive** (phone + laptop). Pages: Home, Report, Check,
Map, Dashboard, Safety guide, How it works & privacy, Business dispute, Licence expired.
Prompts: `docs/11-stitch-prompts.md`. Exports go to `web/stitch/`.
- [x] 6.1 Design screens in **Google Stitch** (9 pages, mobile + desktop) using `docs/11-stitch-prompts.md`; export to `web/stitch/`
- [x] 6.2 Project setup in `web/` (Vite + React or plain JS); API base URL in one config constant
- [x] 6.3 **i18n from day one:** `en.json` + `hi.json`, every visible string from them; EN | हिंदी toggle
- [x] 6.4 **Home:** two big buttons (Check a number / Report a scam) + helpline strip (1930 tel: link, cybercrime.gov.in)
- [x] 6.5 **Report (one screen):** channel icon tiles (exact PRD strings) → when chips (Just now / Today / Yesterday) → paste box with auto-detected type chip → area dropdown (remembered; optional "use my location" converted **on the phone** to nearest area, coordinates discarded) → optional scam-type icons, note, amount → Submit → "Thanks. Reported anonymously." + 1930
- [x] 6.6 **Icons-only path:** every choice is an icon with a label; works without reading
- [x] 6.7 Anonymous `reporter_id` = random UUID in localStorage; never ask for name or phone; **no login**
- [x] 6.8 **Lookup:** paste box → colour card (red KNOWN_SCAM / amber SUSPICIOUS / grey NO_REPORTS / green VERIFIED), masked value, "Reported by N people near you", last seen, **safety advice for the scam type**, "Under review" badge if challenged
- [x] 6.9 **Map / heatmap:** Leaflet + OpenStreetMap with a light Google-Maps-like style (free, no card); circles at area points sized/coloured by count and severity from `/map`; alerts banner from `/alerts`
- [x] 6.10 **Licence expired** full screen (EN + HI) on any 403 `LICENSE_EXPIRED`; polls `/license` every 20 s and recovers
- [ ] 6.11 UI groups the 12 scam types visually (e.g. Calls / Bank & KYC / Money & UPI / Jobs & offers) but sends the exact PRD values
- [x] 6.12 Hidden stopwatch (form open → submit) logged to console for rehearsal
- [ ] 6.13 Serve the built site from our server (or Vercel/Netlify) and test on a real phone on mobile data
- [x] 6.14 If the site is hosted separately from the API: enable CORS on the server for that site's address only
- [x] 6.15 `ip_prefix` for real app users: the browser can't know it, so send `"web"` and let the server derive the first 3 parts of the caller's IP **and hash it immediately** (test tool keeps sending its own)
- [x] 6.17 Dashboard page + small stats endpoint (`GET /stats`: 7-day totals, per-day counts, top types, top areas)
- [x] 6.18 Safety guide, How it works & privacy, Business dispute pages (dispute form posts to P4 `/challenges`)
- [x] 6.16 Safety-advice text per scam type in `en.json` + `hi.json` (e.g. "Police never arrest anyone on a video call", "Banks never ask for your OTP", "Receiving money never needs a PIN or QR scan")
**Done when:** stopwatch < 60 s on a real phone in English, Hindi and icons-only; expired screen appears on 403.
**Judges test:** they report on a phone with a stopwatch, then again in Hindi or using only icons (> 2 min or a login before the form = 0).

### P7 — Ops: keep it alive and proven (protects every live check)
- [x] 7.1 **UptimeRobot** monitor → `/health` every 5 min (Render free plan sleeps after ~15 min)
- [ ] 7.2 Confirm auto-deploy on push is on (Render → Settings)
- [ ] 7.3 Deploy the frontend; check it works on the live https URL from a phone
- [ ] 7.4 Run `scenarios.py` against the live server once (`--allow-remote-reset`), then reset
- [x] 7.5 Long licence uploaded on live; `GET /license` valid through judging day
- [ ] 7.6 Check Neon free compute hours. Keep-alive is off unless `KEEP_DB_AWAKE=1`: set it on Render the day before judging

### P8 — README, video, pitch, rehearsal (10 pts) · read docs/09
- [ ] 8.1 README: what it is, live URL, run locally in 3 commands, every endpoint with copy-paste examples
- [ ] 8.2 README: **trust rules** with the attack table (why the bakery wasn't labelled; why real campaigns pass)
- [ ] 8.3 README: **licence** explained (private/public key, signature, check on every request, renew without restart, clock guard) + the 4-step demo commands
- [ ] 8.4 README: privacy choices (hashing, area only, masking, logs), architecture diagram, decisions
- [ ] 8.5 README: "Judge's self-test" section: scenarios a judge can run alone (use `demo_examples.txt` + `scenarios.py`)
- [ ] 8.6 Pitch (2 min): Ravi's father / Priya story → how it works → trust rules → licence → privacy → how a bank deploys it
- [ ] 8.7 Demo video ≤ 3 min (report, lookup formats, attack stopped, map/alert, licence expiry + renew)
- [ ] 8.8 Rehearse the full demo **3 times** on the live server (docs/09)
- [ ] 8.9 Demo data loader: one command that fills the live server with a lively, realistic set (busy areas, a spike, a new type, a few verified lookups) right after reset, for the map and alerts part of the demo

### P9 — Extras (only after P1–P8 are done)
- [ ] 9.1 Hindi **voice** reporting via Sarvam (phone side only; optional; never inside trust rules; nothing logged)
- [ ] 9.2 Explain panel in the UI ("why this verdict")
- [ ] 9.3 Lookalike-domain detection (e.g. `sbi-kyc.in` vs `sbi.co.in`)
- [ ] 9.4 QR scan for UPI IDs · share-target from SMS app
- [ ] 9.5 Organiser logs replay at the venue (if they give us logs): parse → replay → check verdicts look sane

---

## 5. Always-on rules (every phase)
**Privacy ([PRD §5]; any slip disqualifies)**
1. Never store or show a reporter's name, phone or exact location. Area only (pincode/locality/city from our list).
2. Mask identifiers until ≥ 3 distinct reporters **after trust rules** (`98XXXXX210`, `r***@okaxis`, `sbi***.in/...`, `HD****`).
3. Say "reported", never "scammer / fraud / criminal / this person is".
4. No scraping of social media or people-search sites.
5. Nothing personal in logs: method, path, status, ms only.

**Contract:** paths, field names, status codes and verdict strings exactly as [PRD §A]. No auth on the 7 endpoints.
**No hardcoded test values:** only `server/app/data/verified.json` may list identifiers.
**Time:** windows use each report's `occurred_at` vs the server clock; output in IST `+05:30`.
**Speed:** lookup < 0.5 s (indexed reads, Singapore, DB kept awake); report flow < 60 s.
**Scam categories:** the PRD's 12 `scam_type`s and 6 channels as-is; unknown → `other` / `Something else`.
**Secrets:** private licence key, `.env.local`, DB password never in git.
**Every phase ends with:** tests pass → PROGRESS updated → pushed → checked on the live server.

---

## 6. Submission checklist ([PRD §10])
- [ ] Code in the Git repo (no private key, no `.env.local`)
- [ ] Public server URL working (and kept awake) during judging
- [ ] The app: mobile website link (APK optional)
- [ ] README: how to run, how the trust rules work, how the licence works
- [ ] Demo video ≤ 3 minutes
- [ ] Two licence files: one expiring in 5 minutes (generate at demo time) + one long one

---

## 7. Judging-day runbook
**T-1 day**
- [ ] Render env var `KEEP_DB_AWAKE=1` (keeps Neon awake so lookups stay < 0.5 s)

**T-30 min**
- [ ] `/health` warm on the live URL; UptimeRobot green
- [ ] `GET /license` shows the long licence, valid
- [ ] `POST /admin/reset`, then load demo data
- [ ] Phone on mobile data, site bookmarked, language EN
- [ ] Laptop: `private.key`, `tools/make_license.py`, `licenses/long.json`, terminal open
- [ ] Backup screen recording of the full demo

**Live run (~8–10 min). Start the 5-min licence first and demo the rest while it runs down.**
1. Licence status → generate + upload the 5-min licence ("clock's ticking")
2. Report on the phone with a stopwatch (< 30 s), then in Hindi / icons only
3. Lookup: same number in 3 formats → same answer; masked (2 people) vs shown (3+); `HDFCBK` / 1930 → verified
4. Attacks: run the scenarios → bakery / Wi-Fi farm / spammer not KNOWN_SCAM; real campaign KNOWN_SCAM
5. Map + alerts: spike area SPIKE, new type NEW_TYPE, quiet area none, fakes caused none
6. Dispute → `challenged: true`, never KNOWN_SCAM
7. After 5 min: lookup → expired screen; `/health` still 200
8. Upload the long licence → works within a minute, same data
9. Privacy recap: hashed ids, area only, masking, a log line
10. Pitch close

**Questions to have answers for:** why wasn't the bakery labelled · what if a real scam comes in a burst ·
what stops editing the licence date · what if the clock is set back · how is lookup kept fast.

---

## 8. Decisions we made (and why)
| Decision | Why |
|---|---|
| Render + Neon, both free, Singapore | No card allowed; Singapore is closest to India for the 0.5 s lookup |
| Laptop uses SQLite and ignores Neon's URL | Local tests or a local reset can never wipe the judges' live data |
| Lookups count reports live (2 indexed queries) | Always correct when the test tool sends reports in parallel; still milliseconds |
| Neon keep-alive ping every 4 min + UptimeRobot for Render | Free tiers sleep; waking costs 1–60 s |
| Reporter id and IP prefix stored only as HMAC hashes | Can still count "same person / same network", but a DB dump reveals nobody |
| Locality/city taken from our area list, not the request | Nobody can slip an exact address into the DB |
| Verified list always wins | Rival report-bombing can't label a real bank or bakery (+3 bonus) |
| Rate-limit windows use report timestamps, not arrival | The test tool replays weeks of reports in seconds |
| Duplicate `report_id` = retry, not counted again | Retries can't inflate counts (P1 tightens it to same reporter + number) |
| `type` ignores case/spaces; 422 converted to 400 | PRD wants 400; strictness only loses real lookups |
| Junk phone rules: repeated digit, rising run, bad short codes | PRD junk examples; falling runs allowed (PRD's own 9876543210) |
| Use the PRD's 12 scam types, no new categories | The test tool sends exactly those; UI may group them |
| Leaflet + OpenStreetMap instead of Google Maps | Google Maps needs billing; same look with a light style |
| Hindi + icons built into the frontend from the start | Required for full marks in row 6, not optional |
| Disputes don't lower reporters' reputation | Anyone can file a dispute (no approval step), so a scammer could punish honest reporters. Only an upheld dispute should, and we have no review step |
| A dispute never clears a number | It only softens the label to "under review"; reports and counts stay visible |
| Sarvam (AI) only as an optional phone-side extra | Trust rules must be our own and explainable; outside calls are slow/fragile |
| Server refuses an already-expired licence (`LICENSE_ALREADY_EXPIRED`) | An expired file must never unlock anything; the 5-min demo file is made fresh right before the demo |
| Website checks `/license` every 15 s + a timer for the expiry second | The page locks by itself when the licence ends, no click or reload needed |

---

## 9. Risks and open questions
| Risk / question | Plan |
|---|---|
| Render free plan sleeps → slow first request | UptimeRobot (P7.1) + warm-up before judging |
| Network from the judges' laptop to Singapore eats the 0.5 s budget | Keep server time tiny; measure live p95 (P5.5) |
| Neon free compute hours used by keep-alive | Check usage (P7.6); turn keep-alive off overnight if needed |
| Trust rules too strict → real scams missed | `scenarios.py` real-campaign rows must stay PASS after every change |
| Repo owned by teammate → only they can change Render settings | Keep them in the loop for deploy settings and env vars |
| Database password was shared in chat | Optional: reset it in Neon and update `.env.local` + Render |
| NEW_TYPE in an area with no history fires on one report | Decide in P3 (require ≥ 2 independent reports) and document |

---

## 10. Done log (newest first)
Each entry: what was built (simple words), files touched, how to test it, known gaps.

### P2 — Licence finished on live — 2026-11-01
**What was built (simple terms):**
- The expired screen no longer shows a "Call 1930" button (1930 is for scam victims, not licence errors).
- The website watches the licence by itself (`watchLicence()` in `server/web/app.js`): it asks `/license`
  every 15 s and sets a timer for the exact expiry second, so an open page locks without a reload.
- Proven on the live https server: a 5-minute licence locked the API (403 LICENSE_EXPIRED), the long
  licence unlocked it with no restart, and the website locked and recovered by itself (checked by Avi).
- Decision: an already-expired licence is always refused.

**Files touched:** `server/web/index.html`, `server/web/app.js`, `PROGRESS.md`

**How to test it** (PowerShell, project root, `$P = "server\.venv\Scripts\python"`):
```powershell
& $P tools\make_license.py --licensee "Demo Bank" --minutes 5 --out licenses\short.json
& $P tools\upload_license.py licenses\short.json --live   # leave the site open: it locks by itself at expiry
& $P tools\upload_license.py licenses\long.json --live    # always finish with this; screen clears in ~20 s
```
**Known gaps / next:** README licence section (P8).

### P6 round 2 — Website feedback fixes — 2026-11-01
**What was built (simple terms):**
- **Check:** pick the type first (Phone / UPI ID / Link / SMS sender), then the box shows the matching example and
  keyboard. If you paste something that's clearly another type, the tab switches for you. The result card shows the exact
  verdict label (Known scam / Suspicious / No reports / Verified business), "Reported by N people" ("near you" when the
  reports are within 10 km of your saved area), first/last reported, and a "Dispute these reports" link.
- **Report:** "Something else" for channel and scam type opens a short "please say what" box (stored, never shown).
  "Pick date & time" for an exact time. Step 3 renamed to "Their number, UPI ID or link", with type tabs pre-picked from
  the channel. Proof: Screenshot / Screen recording / Call recording chips (files are NOT uploaded, for privacy). Single
  centred column; the side "Stay safe" box moved to the thanks screen, matched to the scam type.
- **Map:** only "Last 7 days" and "Last 24 hours" (30-day option removed, [PRD §3]); the map no longer slides over the top bar.
- **Dispute:** renamed "Dispute a report", now in the top bar, first in the More menu, a card on Home, and linked from results.
  A disputed number is **hidden again** while under review (server change in `lookup.py`).
- **Scenarios:** new dispute scenario (46 checks) and a "Try these on the website" list printed after the table.
  `--seed 7` gives the same numbers every run.
- **Ops:** the Neon keep-alive is now opt-in (`KEEP_DB_AWAKE=1`) to save Neon's free compute hours.

**Files touched:** `server/web/app.js`, `i18n.js`, `app.css`, `index.html`; `server/app/lookup.py`, `reports.py`, `db.py`
(new columns `channel_other`, `scam_type_other`, auto-added at start-up), `main.py`; `tools/scenarios.py`; `server/tests/test_challenges.py`.

**How to test it:** `pytest -q` → 209 passed. A local server needs a licence first (dev.db has none): get
`licenses/long.json` from Sanjay, start the server, run `python tools/upload_license.py licenses/long.json`, then
`python tools/scenarios.py --seed 7` → 46/46, and try the printed list on http://localhost:8000.

**Known gaps:** no evidence file upload (decision: privacy + storage); voice input (P9) not built.

### P2 — Licence — 2026-10-31
**What was built (simple terms):**
- The server now works only while it holds a signed, unexpired licence. Every request except `/health` and
  `/license` is checked (in memory, microseconds); otherwise → 403 `{"error":"LICENSE_EXPIRED"}`. Data is never deleted.
  The website's page (`/`) and files (`/static/…`) stay open so the expired screen can load; all its data calls are locked.
- `GET /license` shows licensee, expiry, status (`VALID` / `EXPIRED` / `MISSING` / `CLOCK_TAMPERED`) and seconds left.
  `POST /license` swaps in a new licence instantly (no restart) and saves it in the DB, so redeploys keep it.
- Signing: Ed25519 (PyNaCl). The private key `private.key` stays on Sanjay's laptop (git-ignored); the server only
  has the public key. Editing any field of a licence (date, name) → 400 `INVALID_SIGNATURE`. A genuine but already
  expired file → 400 `LICENSE_ALREADY_EXPIRED` (current licence stays, so a stale upload can't lock the server).
- Bonus: clock guard. The latest time seen is kept in memory and in the `clock_guard` table. If the clock goes back
  more than 2 minutes (e.g. a year, to stretch the licence) → locked, even after a restart. Fixing the clock unlocks it.
- Optional `LICENSE_JSON` env var: installed automatically if the DB has no licence yet.

**Files touched:**
- `server/app/license.py` — verify, middleware, GET/POST `/license`, DB sync every 30 s, clock guard
- `server/app/main.py` — 4 lines: import, middleware, router
- `tools/keygen.py`, `tools/make_license.py`, `tools/upload_license.py` (upload / show / `--tamper-test` / `--live`), `tools/preload_live_licence.py` (licence into Neon before push)
- `.gitignore` — `*.db`
- `server/tests/test_license.py` (27 tests), `server/tests/licence_testkit.py` (throwaway test key)
- `server/tests/conftest.py` — every test starts with a valid test licence (all other tests still pass)

**How to test it (PowerShell, repo root):**
```powershell
cd server; .venv\Scripts\python -m pytest -q; cd ..     # expected: 207 passed
# local server on a throwaway DB (2nd window):  cd server; $env:DATABASE_URL="sqlite:///./scenarios.db"; .venv\Scripts\python -m uvicorn app.main:app --no-access-log
$P = "server\.venv\Scripts\python"
& $P tools\upload_license.py --show                     # status MISSING; any lookup -> 403
& $P tools\upload_license.py licenses\long.json         # step 1: VALID, "Demo Bank"
& $P tools\make_license.py --licensee "Demo Bank" --minutes 1 --out licenses\short.json
& $P tools\upload_license.py licenses\short.json        # step 2: seconds_left ~60
# step 3: after 1 min -> curl.exe "http://127.0.0.1:8000/lookup?type=phone&value=1930"  -> 403 LICENSE_EXPIRED
& $P tools\upload_license.py licenses\long.json         # step 4: VALID again, old data still there
```
Proven locally 2026-10-31: all 4 steps, tampered date → 400, and `scenarios.py` 42/42 behind the licence.

Tamper check in one command (expected `PASS`): `& $P tools\upload_license.py licenses\long.json --tamper-test`

**Going live (no lock window):** the new code locks every request until a licence exists, so put the licence
into Neon **before** pushing; the new server reads it on its first request:
```powershell
& $P tools\preload_live_licence.py            # once, before git push (writes only the `license` row)
git push                                       # Render redeploys
& $P tools\upload_license.py --show --live    # after deploy: VALID, Demo Bank
& $P tools\upload_license.py licenses\long.json --tamper-test --live   # PASS
```
Licence files aren't secret (they're signed, not encrypted), but the private key is. Back up `private.key` safely;
without it nobody can make new licences.

**For the frontend (Avi):** the expired screen already works with this (403 `LICENSE_EXPIRED` → screen; it recovers
once a data call succeeds). If you add new website paths outside `/` and `/static/`, add them to `OPEN_PATHS` /
`OPEN_PREFIXES` in `license.py`. Any CORS should be added with `app.add_middleware` so it wraps the licence check.

**Known gaps / next:** 2.10 live upload + rehearsal on the https URL; licence section of the README (P8).

### P6 — Website (all pages, EN/HI, phone + laptop) — 2026-10-31
**What was built (simple terms):**
- A full website served by our own server at `/`: Home, Check, Report (+ success), Scam map, Dashboard,
  Safety guide, How it works, "Is this your number?" (dispute), More menu, and a Licence-expired screen.
- **Design:** layouts from the Google Stitch export, colours from **our** Sage & Cream palette (Stitch had
  drifted to mint). Phone first, plus a laptop layout from 900 px (top nav, two columns).
- **Report in < 30 s, no login:** channel tiles → when chips → paste box with auto-detected type → area
  (search or "Use my location", converted to the nearest area on the phone and the coordinates thrown away) → send.
  Optional details: scam-type icons, note, money lost, "I have a screenshot".
- **Check:** coloured result card (red / amber / grey / green), masked value, safety advice for the scam
  type, "under review" badge, recent reports (no reporter data), 1930 button.
- **Map:** Leaflet + OpenStreetMap (free, no key), softened to the cream palette. Circles at the AREA points
  sized and coloured by severity, an area list with search, city and time-range chips, live alerts.
- **Dashboard:** this week vs last week, reports per day, top scam types, most affected areas, alerts.
- **English | हिंदी** everywhere (toggle, or `?lang=hi` in a link), with safety advice for all 12 scam types.
- **Privacy:** anonymous random id in the browser only, no name or phone ever. Server text is escaped.
  The website sends `ip_prefix: "web"` and the server derives the network from the connection and hashes it at once.
- **Licence:** any 403 `LICENSE_EXPIRED` shows the full-screen message, which re-checks every 20 s and recovers.
- **Removed from the Stitch design on purpose:** accusing wording ("fraudulent", "धोखाधड़ी"), claims of being an official body
  (Ministry/registry), a profile/login icon, and made-up numbers.
- **Backend additions:** `GET /meta` (areas, scam types, channels, cities) and `GET /stats` (dashboard numbers,
  trusted reports only).

**Files touched:**
- `server/web/index.html`, `app.css`, `app.js`, `i18n.js`, `icons.js` (new): the website, no build step
- `server/app/stats.py` (new): `/stats`
- `server/app/main.py`: `/meta`, `/stats`, website at `/` + `/static/`, "web" ip_prefix handling
- `server/tests/test_web.py` (new, 12 tests incl. a banned-words check on the website text, English and Hindi)
- `docs/design/stitch/`: the Stitch screenshots + notes on what we changed

**How to test it (PowerShell):**
```powershell
cd "C:\Users\Avi Verma\Documents\Code\Scam_Map\server"
.venv\Scripts\python -m pytest -q                       # expected: 180 passed
.venv\Scripts\python -m uvicorn app.main:app --reload --no-access-log
```
Open **http://localhost:8000**. To see busy maps and dashboards, fill it first (this wipes dev.db):
```powershell
cd "C:\Users\Avi Verma\Documents\Code\Scam_Map"
server\.venv\Scripts\python tools\scenarios.py --base http://localhost:8000
```
Then:
- **Check:** `1800 1600` (green) and `12345` (error).
- **Report:** a number, then Check it.
- **Map:** Bengaluru shows a SPIKE in Bellandur.
- **Dashboard.**
- **Hindi:** the EN | हिंदी toggle.
- **Phone size:** browser DevTools → device toolbar (iPhone / Pixel).
- **Stopwatch:** open DevTools Console; each sent report logs `[stopwatch] report sent in N s`.

**Known gaps / next:**
- Test on a real phone over mobile data, with a stopwatch, in English, Hindi and icons only (6.13).
- A separate "icons-only" mode isn't built. Every choice is an icon with a short label, which should satisfy
  "using only icons", but check with the team.
- The 12 scam types are shown as one icon grid (not grouped).

### P4 — Disputes (POST /challenges) — 2026-10-31
**What was built (simple terms):**
- `POST /challenges`: a business says "that's our real number".
  - It checks the identifier (any format; junk → 400), a business name and an email (missing or invalid → 400).
  - It saves the dispute as `under_review`, marks the number as challenged, and replies
    `201 {"challenge_id": "chal_N", "status": "under_review"}`.
  - It works even if nobody has reported the number yet.
- `/lookup` on a disputed number: `"challenged": true` and **never KNOWN_SCAM** (SUSPICIOUS instead), with the
  message "A business has disputed these reports - under review". Reports are kept. Verified numbers stay verified.
- Claimant name, email and proof are never logged or returned. `/admin/reset` clears disputes.
- Decision: disputes do **not** lower reporters' reputation. Anyone can file one (there's no approval step),
  so it would let a scammer punish honest reporters.

**Files touched:**
- `server/app/challenges.py` (new): `validate_challenge()` + `save_challenge()`
- `server/app/main.py`: `POST /challenges` route with an editable example in `/docs`
- `server/tests/test_challenges.py` (new, 14 tests)
- `tools/samples/demo_examples.txt`: Example 8 (dispute by hand)

**How to test it (PowerShell):**
```powershell
cd "C:\Users\Avi Verma\Documents\Code\Scam_Map\server"
.venv\Scripts\python -m pytest -q                       # expected: 168 passed
.venv\Scripts\python -m uvicorn app.main:app --reload --no-access-log
```
In `http://localhost:8000/docs`:
1. Send Example 1 (3 reports).
2. `GET /lookup` 9876543210 → KNOWN_SCAM.
3. `POST /challenges` with Example 8.
4. `GET /lookup` again → SUSPICIOUS + `challenged: true`.

**Known gaps / next:**
- No admin screen to approve or reject disputes (status stays `under_review`). That's enough for [PRD §A.7].
- Next: `/stats` for the dashboard, frontend plumbing (P6), P5 audit.

### P3 — Map + alerts — 2026-10-31
**What was built (simple terms):**
- `GET /map?pincode=&days=7&radius_km=2`: one cluster per area within the radius that has reports in the
  last N days. It shows count, most common scam type and severity (CRIT ≥ 10, HIGH ≥ 5, else MED; one level
  higher for digital-arrest / sextortion / a loss ≥ ₹50,000). The **map point is always the area's point from
  the brief**, never a reporter's location. With no pincode it lists every area (for the app's city view).
- `GET /alerts?pincode=`:
  - **SPIKE:** last 24 h ≥ 5 AND ≥ 2 × the daily average of the 7 days before
  - **NEW_TYPE:** a scam type in the last 24 h not seen in that area in the 30 days before. One report is enough
    in an area with recent history; a quiet area waits for a 2nd independent report so the very first report
    doesn't sound an alarm.
  - Nothing unusual → `{"alerts": []}`
- Both count **only trusted reports** (one per independent source from the P1 trust rules), so fake
  waves never move the map or fire alerts (+2 bonus).
- At start-up the server re-checks the `trusted` flag on every stored report, so older data (saved before
  the flag existed) is counted correctly after a deploy.

**Files touched:**
- `server/app/geo.py` (new): areas, haversine distance, radius, clusters, severity
- `server/app/alerts.py` (new): SPIKE + NEW_TYPE per area
- `server/app/assessment.py`: `refresh_all_trusted_flags()` (start-up re-check)
- `server/app/main.py`: `/map`, `/alerts` routes + input checks (unknown pincode / bad days / bad radius → 400)
- `server/tests/test_map_alerts.py` (new, 19 tests)
- `tools/samples/demo_examples.txt`: Example 7 (map + alerts by hand)

**How to test it (PowerShell):**
```powershell
cd "C:\Users\Avi Verma\Documents\Code\Scam_Map\server"
.venv\Scripts\python -m pytest -q                       # expected: 154 passed
$env:DATABASE_URL = "sqlite:///./scenarios.db"
.venv\Scripts\python -m uvicorn app.main:app --port 8000 --no-access-log
```
In a 2nd window, from the repo root:
```powershell
server\.venv\Scripts\python tools\scenarios.py --base http://localhost:8000 --latency 200
# expected: 42/42 checks passed (spike → SPIKE, steady → none, new type → NEW_TYPE,
#           month-old not on map, fakes fire no alert, lookup p95 ~30 ms)
```
Then in `http://localhost:8000/docs`, while that data is still loaded:
- `GET /alerts`, pincode `560103` (Bellandur) → SPIKE
- pincode `560100` (Electronic City) → NEW_TYPE job-offer
- pincode `560037` (Marathahalli) → `[]` (busy but normal)
- `GET /map`, pincode `560102`, radius_km `5` → clusters at the areas' own points
- `GET /map`, pincode `560024` (Hebbal) → no cluster (its reports are 30 days old)
- By hand: Example 7 in `tools/samples/demo_examples.txt`.

**Known gaps / next:**
- Severity thresholds and the NEW_TYPE "2 reports in a quiet area" rule are our own choices. Explain them in the README.
- Next: P4 disputes (`POST /challenges`).

### P1 — Trust rules + rate limit — 2026-10-31
**What was built (simple terms):**
- The server now counts **independent people**, not reports. Five layers decide how much each report counts:
  - **L1** one reporter = one person
  - **L2** same Wi-Fi (`ip_prefix`) on the same number within 24 h = one source
  - **L3** copy-paste notes = one source (personal story ×1.2, empty ×1.0, "scam" ×0.9, copy-paste ×0.8)
  - **L4** coordination score from 6 warning signs (burst, all new accounts, few networks, one area,
    empty/duplicate notes, nobody lost money). A score ≥ 0.6 means brand-new accounts count ×0.2 and KNOWN_SCAM is blocked
  - **L5** reputation (new 0.6, track record 0.8 / 1.0, reported a verified business 0.3)
- **KNOWN_SCAM** now needs ≥ 3 trusted sources (weight ≥ 0.5) from ≥ 3 networks, no coordination, no dispute.
  `distinct_reporters` = trusted sources, and that number also decides masking.
- **429 rate limit:** more than 3 reports in an hour or 20 in a day from one reporter, measured with the
  reports' own times (the test tool replays weeks in seconds). 429 reports are not stored.
- Each report gets a `trusted` flag (one per trusted source). P3's map and alerts will count only these,
  so fakes never move the map or fire alerts.
- Duplicate `report_id`: a retry only if the reporter and the number also match; otherwise it's stored as a new report.
- `GET /debug/explain?type=&value=` shows each layer's effect as counts and scores only. It's off unless
  the server has `EXPLAIN_ENABLED=1`.

**Files touched:**
- `server/app/trust.py` (new): all trust rules as pure functions + rate-limit check; constants at the top
- `server/app/assessment.py` (new): loads one identifier's reports + reporter history, runs the rules, stores `trusted` flags
- `server/app/reports.py`: 429, stricter retry check, flags reporters of verified numbers, refreshes trust after each report
- `server/app/lookup.py`: verdict/masking from the trust rules; `explain()`
- `server/app/main.py`: 429 reply, `/debug/explain`, 429 listed on the docs page
- `server/app/db.py`: `reports.trusted` column + automatic upgrade for existing databases (Neon)
- `server/tests/test_trust.py` (new, 18 tests); `server/tests/test_api_basic.py` updated (genuine notes, 429)

**How to test it (PowerShell):**
```powershell
cd "C:\Users\Avi Verma\Documents\Code\Scam_Map\server"
.venv\Scripts\python -m pytest -q                       # expected: 135 passed
$env:DATABASE_URL = "sqlite:///./scenarios.db"; $env:EXPLAIN_ENABLED = "1"
.venv\Scripts\python -m uvicorn app.main:app --port 8000 --no-access-log
```
In a 2nd window, from the repo root:
```powershell
server\.venv\Scripts\python tools\scenarios.py --base http://localhost:8000
# expected: 35/42 checks passed; every FAIL is a /map or /alerts row (P3)
```
**By hand in `/docs`:**
- Send the spammer body from `tools/samples/demo_examples.txt` 4+ times with times inside the same hour
  (change `report_id` each time). The 4th gets **429**.
- Send 3 reports with the **same note** from 3 reporter_ids and it stays SUSPICIOUS (copy-paste = one source).
  With different notes, networks and areas it becomes KNOWN_SCAM.
- Open `/debug/explain?type=phone&value=...` to see why.

**What to look for:**
- Scenario rows: spammer 429 + distinct 1, Wi-Fi farm distinct 1, bakery masked, real campaigns KNOWN_SCAM.
- Ran 15 random seeds: 0 trust failures.

**Known gaps / next:**
- Thresholds are first guesses tuned on our scenarios. Re-check them if the organisers' sample logs look different.
- Not yet run against the live server's database (scenarios wipe data, so only with `--allow-remote-reset`
  when the team agrees).
- Next: P3 map + alerts (count only `trusted` reports).

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
