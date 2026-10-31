# 09 — Demo script (judging day)

## T-30 min checklist
- [ ] `curl <url>/health` warm; `GET /license` shows long licence valid
- [ ] `POST /admin/reset` then `python tools/scenarios.py --seed-demo --base <url>` (lively map/alerts)
- [ ] Phone on mobile data, site bookmarked, language set to EN
- [ ] Laptop: `private.key`, `tools/make_license.py`, `licenses/long.json`, terminal ready
- [ ] Backup screen recording of the full demo on the laptop

## Live run (~8–10 min) — start the 5-min licence FIRST, demo other things during the wait
1. **Licence status** — `GET /license` (Demo Bank, expiry). Run
   `python tools/make_license.py --minutes 5 > licenses/short.json` + upload. "Clock's ticking."
2. **Report** — on phone with stopwatch: channel → Just now → paste → area → Submit (< 30 s).
   Repeat quickly in Hindi / icons only.
3. **Lookup** — same number in 3 formats → same answer. Masked (2 reporters, SUSPICIOUS) vs
   unmasked (≥3, KNOWN_SCAM). `HDFCBK` / 1930 → VERIFIED_BUSINESS. Point at the wording.
4. **Attacks (highlight)** — `python tools/scenarios.py --attacks --base <url>` live;
   lookups on bakery / wifi-farm / spam targets → not KNOWN_SCAM; show explain panel.
   Then `--real-campaign` → KNOWN_SCAM. Line: "we stop fakes without missing real scams."
5. **Map + alerts** — spike area SPIKE, new-type NEW_TYPE, quiet area none, fakes caused none,
   month-old reports absent.
6. **Dispute** — challenge Fresh Bakes-style number → challenged:true, never KNOWN_SCAM.
7. **Expiry** — after 5 min: lookup on phone → "Licence expired" screen; `/health` still 200.
8. **Renew** — upload `licenses/long.json` → app works within a minute, no restart, same counts.
9. **Privacy recap (30 s)** — hashed reporter ids, area-only, masking, show a log line.
10. **Pitch close** — Ravi's father / Priya story → how a bank deploys this.

## Likely judge questions — have answers ready
- Why wasn't the bakery labelled? → coordination score + note dedup numbers from explain
- What if a real scam comes in a burst? → diversity of networks/areas/text keeps weight high
- What stops editing the licence date? → Ed25519 signature over canonical bytes
- What if they set the clock back? → clock_guard high-water mark
- How do you keep lookup fast? → summary row per identifier, single indexed read

## Submission checklist
Repo (no private key) · public HTTPS URL · APK and/or mobile link · README · ≤3-min video ·
licence files (long pre-made; 5-min generated at demo time)
