# 08 — Implementation plan (our order, not the brief's)

Why this order: deploy first (no last-hour surprises), build the **test harness before the trust
engine** (so every rule change is measured), and do the licence early-middle because it's
mechanical but demo-critical. Each step ends with: tests passing + `PROGRESS.md` updated.

Legend: 📄 docs to read · ✅ done when · 🧪 how to test

---
### Step 0 — Skeleton + deploy (≈1.5 h)
- FastAPI app with `/health`; `requirements.txt`; `.gitignore` (private.key, *.pem, licenses/, .env, dev.db)
- Custom logging middleware (method, path, status, ms) and uvicorn access log off
- Deploy to Render/Railway/Fly with managed Postgres; always-on instance
📄 CLAUDE.md · ✅ `https://<team>.<host>/health` → `{"ok":true}` from a phone
🧪 `curl https://<url>/health`

### Step 1 — Reference data + normalizer (≈1.5 h)
- Load `data/areas.json`, `verified.json`, `scam_types.json`
- `normalize.py` for phone/upi/url/sender_id with all examples from docs/02 as pytest cases
📄 02 · ✅ `pytest tests/test_normalize.py` all green
🧪 `pytest -q tests/test_normalize.py -v`

### Step 2 — Database + reports + naive lookup + reset (≈2 h)
- Tables: `reports`, `identifiers` (summary row), `reporters` (hashed id, reputation), `challenges`,
  `license`, `clock_guard`
- HMAC hashing of reporter_id / ip_prefix (privacy.py)
- POST /reports (validation → 400, store, case_id = identifier row id, merged flag)
- GET /lookup with naive counting (distinct hashed reporters) + VERIFIED override + masking
- POST /admin/reset
📄 01, 02, 04 · ✅ report → lookup works; 3 formats same answer; junk 400; verified works
🧪 `pytest tests/test_api_basic.py` + curl examples in PROGRESS.md

### Step 3 — Test harness / scenario generator (≈1.5 h)
- `tools/scenarios.py`: generates reports with realistic timestamps relative to now for:
  spammer, wifi-farm, bakery-bomb, junk, real-campaign, small-real (2 people), old reports (30 d),
  spike area, steady area, new-type area. Sends to `--base` URL, then asserts expected outcomes,
  prints a PASS/FAIL table.
- Expected now: several FAILs (naive counting) — that's the point.
📄 03, 06 · ✅ script runs end-to-end and prints table
🧪 `python tools/scenarios.py --base http://localhost:8000`

### Step 4 — Trust engine (≈3–4 h)
- `trust.py`: L1 dedup + rate limit (429), L2 network clusters, L3 note similarity, L4 coordination,
  L5 reputation, effective count, verdict, `trusted` flag per report, explain dict
- Recompute identifier summary on each report
- `GET /debug/explain` (dev only, behind env flag)
📄 03 · ✅ all trust scenarios PASS; unit tests per layer
🧪 `pytest tests/test_trust.py` + scenarios.py

### Step 5 — Licence (≈2 h)
- `tools/keygen.py`, `tools/make_license.py`, `tools/upload_license.sh`
- `license.py`: verify, middleware, GET/POST /license, persistence, clock guard
📄 05 · ✅ the 4-step demo works locally AND on the deployed URL without restart
🧪 `pytest tests/test_license.py`; manual 5-min demo (commands in PROGRESS.md)

### Step 6 — Map + alerts (≈2 h)
- `geo.py` (areas, haversine, clusters, severity), `alerts.py` (SPIKE, NEW_TYPE), trusted-only
📄 06 · ✅ map/alert scenarios PASS
🧪 `pytest tests/test_map_alerts.py` + scenarios.py

### Step 7 — Challenges + privacy hardening (≈1 h)
- POST /challenges; lookup shows challenged, never KNOWN_SCAM
- Banned-words test, log audit, DB column audit, latency check (< 500 ms p95 over 200 lookups)
📄 01, 04 · ✅ privacy checklist in docs/04 all ticked
🧪 `pytest tests/test_privacy.py`; `python tools/scenarios.py --latency`

### Step 8 — Frontend (≈4–5 h; can run in parallel from Step 2 by a teammate)
- Home, Report, Lookup, Map, Licence-expired; EN/HI; deploy (same server serving static, or Vercel/Netlify)
📄 07, 04 · ✅ report in < 30 s on a real phone; Hindi works; expired screen appears on 403
🧪 manual stopwatch run, checklist in PROGRESS.md

### Step 9 — Organiser logs replay (≈1 h, when on venue Wi-Fi)
- Download from `http://192.168.60.139` into `logs_raw/` (gitignored); inspect format
- `tools/replay_logs.py`: parse → shift timestamps to now → POST to server → summary
- Add any new trick patterns found to scenarios.py (generalized, never specific numbers)
✅ replay runs, no crashes, verdicts look sane · 🧪 `python tools/replay_logs.py logs_raw/<file> --base <url>`

### Step 10 — Add-ons if time (pick by value)
explain panel in UI · lookalike-domain detection · QR scan for UPI · share target · LLM note tagging

### Step 11 — README, video, demo rehearsal (≈2 h)
- README: run instructions, trust rules (with the attack table), licence explanation, privacy
- Rehearse docs/09 three times on the deployed server; record 3-min video
✅ a stranger can run it from the README; demo works 3/3 times
