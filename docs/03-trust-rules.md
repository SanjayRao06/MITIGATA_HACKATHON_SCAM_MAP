# 03 — Trust rules (20 pts + 2 bonus) — the heart of the project

**Principle:** don't count reports, count *independent humans*. A fake wave is one source
wearing many masks; a real scam wave is many unrelated people writing in their own words.
All numbers below are starting values — keep them in `trust.py` as named constants and tune
with `tools/scenarios.py`. **Never special-case a specific identifier.**

## Attacks we must stop (the test tool loads these)
| Attack | Signature in data | Layer that stops it |
|---|---|---|
| Spammer: 1 person × 6 reports | same `reporter_id`, same identifier | L1 dedup + 429 |
| 22 fake accounts, one Wi-Fi | many `reporter_id`, same `ip_prefix`, short time | L2 network collapse |
| 40 friends report a real bakery | many new ids, burst, copy-paste/empty notes, same locality, ₹0 lost | L3 notes + L4 coordination |
| Junk ("12345", "test") | invalid identifier | normalizer → 400 |
And must NOT stop: a real campaign (many ids, many ip_prefixes, varied notes/areas/times, some ₹ lost).

## Pipeline per identifier (recompute on every new report — data per identifier is small)
### L0 Junk → 400 (docs/02)
### L1 Same person
- Group reports by `reporter_id`. Each reporter counts at most once per identifier.
- Rate limit: >3 reports from one `reporter_id` in 60 min (any identifier) → 429, not stored;
  >20 per day → 429.
- **Measure rate-limit windows with the report's own timestamps** (`reported_at`, falling back to
  `occurred_at`), never with server arrival time. Why ([PRD §A.0] rule 1): the test tool replays
  weeks of reports in a few seconds from one laptop. If we used arrival time, a real reporter
  who reported 4 different numbers across a month would get a 429 on their 4th report, and we'd
  lose a real report. Reports with the same timestamps (true spam) are still caught.
### L2 Same network
- Within one identifier, reporters sharing an `ip_prefix` whose reports fall within 24h of each
  other merge into one **cluster** (= one effective person).
### L3 Note similarity
- Normalize note (lowercase, strip punctuation/digits). Empty note = neutral.
- Compare notes across clusters with Jaccard similarity on 3-word shingles (or simhash).
  Similarity ≥ 0.8 → merge those clusters (copy-paste = one source).
- Note quality multiplier per cluster: personal/specific note (≥ ~8 words, unique) ×1.2,
  empty ×1.0, very short generic ("scam", "fraud") ×0.8.
### L4 Coordination score (0..1) for the whole set of reports on an identifier
Compute over reports in the last 48h. Signals (each 0..1), averaged:
- `burst`: share of reports inside the tightest 2-hour window
- `newness`: share of reporters with no earlier reports in our DB
- `low_net_diversity`: 1 − (distinct ip_prefixes / reporters)
- `low_area_diversity`: 1 − (distinct pincodes / reporters)
- `low_text_diversity`: share of empty or near-duplicate notes
- `no_loss`: share with amount_lost_inr == 0 and has_screenshot == false
If coordination ≥ 0.6 → multiply every new-reporter cluster's weight by 0.2.
(Real campaigns score low because net/area/text diversity is high.)
### L5 Reporter reputation (stored per hashed reporter_id)
- New reporter base weight 0.6; established (≥2 earlier reports on identifiers that became
  KNOWN_SCAM by others) up to 1.0.
- Reporter who reported a VERIFIED_BUSINESS or a successfully challenged identifier → 0.3.
### Effective count
`cluster_weight = max(member reputation) × note_multiplier × coordination_penalty`
`effective = Σ cluster_weight` ; `distinct_reporters = round(number of clusters with weight ≥ 0.5)`
(report this integer in /lookup; it's what masking uses).

## Verdict
1. In `data/verified.json` → `VERIFIED_BUSINESS` (always wins).
2. No stored reports → `NO_REPORTS`.
3. `effective ≥ 3.0` AND `distinct_ip_prefixes ≥ 3` AND `coordination < 0.6` AND not challenged → `KNOWN_SCAM`.
4. Otherwise → `SUSPICIOUS`.

## "Trusted" reports (used by map & alerts)
A report is *trusted* if its cluster weight ≥ 0.5 and it isn't a duplicate from the same
reporter. Only trusted reports feed /map counts and /alerts → fakes never trigger alerts (+2).

## Explainability (store it!)
Keep a per-identifier `explain` dict: raw reports, after-dedup, clusters, merged-by-network,
merged-by-note, coordination score + signals, final effective. Expose at
`GET /debug/explain?type=&value=` (dev only, hashed data, no notes/ids) and in README/pitch.

## Performance
Store a summary row per identifier (verdict, counts, first/last seen, top scam type) updated
on each POST /reports. /lookup = one indexed read → well under 500 ms.

## Tests to keep green (tools/scenarios.py)
spammer ×6 → not KNOWN_SCAM, distinct=1 · 22 ids one ip_prefix → distinct ≤ 1 · 40-friend
bakery burst → not KNOWN_SCAM, no SPIKE · real campaign 8 people / 6 nets / varied notes →
KNOWN_SCAM · 2 real people → SUSPICIOUS, masked · junk → 400.
