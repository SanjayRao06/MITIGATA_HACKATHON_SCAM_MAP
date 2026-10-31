# Community Scam Map

Check a phone number, UPI ID, link or SMS sender **before** you trust it, and report a scam in under
30 seconds, anonymously. Built for the Mitigata CyberForge hackathon.

- **Live server + website:** https://mitigata-hackathon-scam-map.onrender.com
- **API docs (try every endpoint in the browser):** https://mitigata-hackathon-scam-map.onrender.com/docs
- **Stack:** Python 3.11 · FastAPI · SQLAlchemy · Postgres (Neon) in production, SQLite on a laptop ·
  Ed25519 licence (PyNaCl) · plain-JavaScript mobile website · Leaflet + OpenStreetMap · English + Hindi

What makes it hard is not storing reports. It is **not getting fooled by fake ones**, never exposing
the people who report, and a licence that can lock and unlock the server live. Those three are the
sections below.

---

## 1. Run it in 3 commands

```bash
cd server && python -m venv .venv && .venv/Scripts/pip install -r requirements.txt   # (Linux/Mac: .venv/bin/pip)
.venv/Scripts/python -m uvicorn app.main:app --port 8000                              # website: http://localhost:8000
.venv/Scripts/python -m pytest -q                                                     # 226 tests
```

On a laptop it uses a local SQLite file (`server/dev.db`) and never the production database, so local
tests can't touch live data. A fresh database has no licence, so upload one first (section 4).

Fill it with realistic demo data (fake attacks, real scam waves, a spike, a new scam type, a dispute,
and reports in 11 cities) and grade the server, from the repo root:

```bash
python tools/scenarios.py --base http://localhost:8000 --seed 7
```

It prints a PASS/FAIL table (47 checks) and a "Try these on the website" list.

---

## 2. The API (the 7 endpoints the test tool uses + the licence)

| Endpoint | What it does |
|---|---|
| `GET /health` | `{"ok": true}`. Never locked |
| `POST /reports` | Stores one report → `201 {"report_id", "case_id", "merged"}`; `400` junk; `429` rate-limited |
| `GET /lookup?type=&value=` | Verdict: `KNOWN_SCAM`, `SUSPICIOUS`, `NO_REPORTS` or `VERIFIED_BUSINESS` |
| `GET /map?pincode=&days=7&radius_km=2` | Areas with reports in the last 7 days, at the area's own map point |
| `GET /alerts?pincode=` | `SPIKE` (sudden jump) and `NEW_TYPE` (scam type new to the area) |
| `POST /admin/reset` | Deletes every report so the judges start clean (keeps the licence) |
| `POST /challenges` | A business disputes a number → `201 under_review` |
| `GET /license`, `POST /license` | Licence status / upload a new licence. Never locked |

Any value format works: `+91 98765 43210`, `09876543210`, `98765-43210` and `919876543210` are the same
phone; UPI IDs ignore case; links drop `www.`, `?tracking` and the trailing `/`; `VM-HDFCBK` = `HDFCBK`.

```bash
curl "https://mitigata-hackathon-scam-map.onrender.com/lookup?type=phone&value=%2B91%2098765%2043210"
curl "https://mitigata-hackathon-scam-map.onrender.com/lookup?type=sender_id&value=VM-HDFCBK"   # VERIFIED_BUSINESS
```

Copy-paste report bodies for `/docs` are in `tools/samples/demo_examples.txt`.

---

## 3. Trust rules: how fake reports are stopped (`server/app/trust.py`)

The test tool sends real scams **and** organised fake reports. A count of reports would be fooled
by the first person with 20 phones. So every identifier's reports go through five layers, and the
answer counts **trusted sources**, not reports.

| Layer | Rule | Why |
|---|---|---|
| **L1 Same person** | All reports from one `reporter_id` = one source | Reporting 6 times doesn't make it 6 people |
| **L2 Same network** | Same `ip_prefix` + same identifier within 24 h = one source | 22 accounts on one Wi-Fi are one household, not 22 victims |
| **L3 Copy-paste** | Notes that are nearly identical (word overlap ≥ 0.8) merge into one source. Personal stories weigh ×1.2, generic ("scam") ×0.9, copy-paste ×0.8 | Real victims describe what happened in their own words |
| **L4 Coordination** | With 3+ people, score 6 warning signs: burst inside 2 h, all brand-new accounts, few networks, one area, empty/duplicate notes, nobody lost money. Score ≥ 0.6 = organised: new accounts count ×0.2 and `KNOWN_SCAM` is blocked | A report-bombing wave looks the same every time; a real wave is varied |
| **L5 Reputation** | New reporter 0.6 · history on other numbers 0.8 / 1.0 · someone who reported a verified business 0.3 | People with a record of real reports count more |

A source is **trusted** at weight ≥ 0.5.
**KNOWN_SCAM** needs ≥ 3 trusted sources from ≥ 3 different networks, no coordination, and no open
dispute. Fewer → **SUSPICIOUS**. The brief's verified list (`server/app/data/verified.json`) always
wins → **VERIFIED_BUSINESS**. Rate limit: more than 3 reports an hour or 20 a day from one reporter →
`429`, using each report's own time (the test tool replays weeks in seconds).

**What our attack scenarios show** (`tools/scenarios.py`, all PASS):

| Scenario | What is sent | Result |
|---|---|---|
| Spammer | 1 person, same number 6× in an hour | 3 stored, then `429`; counts as 1 person |
| Wi-Fi farm | 22 fake accounts on one network, 90 min | 1 source → not KNOWN_SCAM, no alert |
| Bakery bomb | 40 "friends" on 25 home networks, 2 h, copy-paste or empty notes, one area | Coordination score high → not KNOWN_SCAM, hidden, no alert |
| Verified bakery | 15 fake reports on Fresh Bakes (verified) | VERIFIED_BUSINESS |
| **Real campaign** | 8 unrelated people, 6 networks, own words, many areas, some money lost | **KNOWN_SCAM, shown in full** |
| Real UPI | 5 people, typed in different cases | KNOWN_SCAM |
| Small real | 2 real people | SUSPICIOUS, hidden |
| Junk | `12345`, unknown pincode, future time | `400` |

**Why wasn't the bakery labelled?** The 40 reports came from brand-new accounts, inside 2 hours, in
one area, with copy-pasted or empty notes and nobody losing money. That is 5 of the 6 coordination
signs. **Why does a real campaign still pass?** Its reporters use different networks, areas and words
and some lost money, so the coordination score stays low even when reports arrive close together.

---

## 4. The licence: lock and unlock live, no restart (`server/app/license.py`)

A licence file says who may use the server and until when, **signed** with our private key:

```json
{"licensee": "Demo Bank", "expires_at": "2026-11-15T10:05:00+05:30", "issued_at": "...", "signature": "<base64>"}
```

- **Signature (Ed25519):** we sign every field except the signature, as sorted, compact JSON. The
  server holds only the **public** key, so it can check a licence but never make one. Change one
  character (say, the date) and the signature fails → `400 INVALID_SIGNATURE`.
- **Checked on every request** (middleware), except `/health` and `/license`. When the licence has
  ended, every other path returns `403 {"error": "LICENSE_EXPIRED"}`. **Nothing is deleted**: the data
  is locked, not removed.
- **Renew without restart:** `POST /license` with a new file takes effect at once. The licence is saved
  in the database, so restarts and redeploys keep it.
- **Already-expired files are refused** (`400 LICENSE_ALREADY_EXPIRED`), so an old file can't unlock anything.
- **Clock rollback guard:** the server remembers the latest time it has seen. If the clock jumps back
  more than 2 minutes, it locks (`CLOCK_TAMPERED`), so setting the clock back doesn't revive a licence.
- **The website** checks `/license` every 15 s plus a timer for the exact expiry second, so an open
  page shows "Licence expired. Contact your provider." by itself, and clears by itself after a renewal.

**The 4-step demo** (PowerShell, repo root, on the laptop that holds `private.key`):

```powershell
$P = "server\.venv\Scripts\python"
& $P tools\upload_license.py --show --live                                            # 1. status: long licence, VALID
& $P tools\make_license.py --licensee "Demo Bank" --minutes 5 --out licenses\short.json
& $P tools\upload_license.py licenses\short.json --live                               # 2. 5-minute licence active
#   ...wait 5 minutes: the website locks by itself, lookups return 403, /health is still 200   3. expired
& $P tools\upload_license.py licenses\long.json --live                                # 4. renewed, same data, no restart
```

Drop `--live` to run against `http://127.0.0.1:8000`. The two licence files for submission are
`licenses/long.json` (valid until 2027-10-31) and a 5-minute file made **right before** the demo (a
file made earlier would already be expired). The private key and licence files are never in Git.

---

## 5. Privacy (`server/app/privacy.py`)

Any slip here is disqualification, so each rule is enforced in code **and** tested
(`server/tests/test_privacy_audit.py`).

- **No reporter identity stored.** `reporter_id` and `ip_prefix` are stored only as HMAC-SHA256 hashes
  with a server secret. We can still tell "same person / same network", but a database dump reveals nobody.
- **Area only.** Locality and city come from our area list (`server/app/data/areas.json`), never from
  the request. The map uses the area's point, never a person's location.
- **Masking.** An identifier is shown as `98XXXXX210`, `r***@okaxis`, `sbi***.in/...` or `HD****` until
  at least 3 **trusted** people have reported it, and again while a dispute is under review.
- **Careful wording.** We say "reported", never "scammer" or "fraud".
- **Logs** hold only method, path (no query string), status and milliseconds. Uvicorn's access log is
  off because it prints IPs and full URLs. No bodies, identifiers, IPs or notes are logged.
- **Never returned:** notes, the "something else" texts, reporter or network data, and a dispute's
  claimant name, email and proof.

---

## 6. Map and alerts (`server/app/geo.py`, `server/app/alerts.py`)

- **Map:** areas within the radius with **trusted** reports in the last 7 days (each report's own time).
  Severity: CRIT ≥ 10, HIGH ≥ 5, else MED, raised a level for digital arrest, sextortion or a loss ≥ ₹50,000.
- **SPIKE:** ≥ 5 reports in the last 24 h **and** ≥ 2× the area's daily average over the 7 days before.
  A busy area that is always busy gets no alert.
- **NEW_TYPE:** a scam type not seen in the area for 30 days (2 reports needed if the area has no history).
- Fake waves don't count, so they can't set off alerts.

---

## 7. Speed

Lookup must answer in under 0.5 s. Every reply carries a `Server-Timing` header with the server's own
time. Over 200 live lookups the server took **7 ms median, 10 ms p95**; the rest of the round trip is
the network. Check it yourself (read-only, safe on live):

```bash
python tools/latency_check.py --base https://mitigata-hackathon-scam-map.onrender.com
```

---

## 8. Judge's self-test

1. **Formats:** look up one number as `+91 98765 43210`, `09876543210` and `98765-43210` → same answer.
2. **Verified:** `HDFCBK` (sender_id) or `1930` (phone) → `VERIFIED_BUSINESS`.
3. **Masking:** report a new number from 2 different `reporter_id` + `ip_prefix` → SUSPICIOUS, masked.
   A third, different person → KNOWN_SCAM, shown in full.
4. **Spam:** the same `reporter_id` 6 times in an hour → 3× `201`, then `429`; still 1 reporter.
5. **Wi-Fi farm:** 5 different `reporter_id`s with one `ip_prefix` → counts as 1.
6. **Dispute:** `POST /challenges` on a KNOWN_SCAM number → `challenged: true`, no longer KNOWN_SCAM, masked again.
7. **Everything at once:** `python tools/scenarios.py --base http://localhost:8000` → 47/47 PASS.
   (Against a deployed server add `--allow-remote-reset`: it starts with `POST /admin/reset`.)

---

## 9. Layout

```
server/app/      main.py (routes) · normalize.py · reports.py · trust.py + assessment.py · lookup.py
                 geo.py + alerts.py · challenges.py · stats.py · privacy.py · license.py · data/*.json
server/web/      the website (index.html, app.js, i18n.js EN/HI, icons.js, app.css), served at "/"
server/tests/    pytest, one file per area (226 tests)
tools/           scenarios.py (attack + real-scam checks, demo data) · latency_check.py
                 keygen.py · make_license.py · upload_license.py · samples/demo_examples.txt
docs/            00-prd.md (the brief) and design notes per topic
```

**Hosting:** Render free web service (Singapore) + Neon free Postgres (Singapore), auto-deploy on push.
UptimeRobot pings `/health` every 5 minutes so the free server doesn't fall asleep.
