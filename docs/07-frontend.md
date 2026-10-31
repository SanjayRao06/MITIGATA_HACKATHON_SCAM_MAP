# 07 — Frontend (mobile website) — 15 pts for ease of reporting

Judge test: report a scam with a stopwatch (< 60 s, target < 30 s), then try in Hindi or icons only.
**No login before the form.** Phone-first layout (360–414 px wide), big tap targets (≥ 48 px).

## Screens
1. **Home** — two giant buttons: "Check a number" / "Report a scam". Language toggle EN | हिंदी.
   Helpline strip: "Lost money? Call 1930" (tel: link) + cybercrime.gov.in.
2. **Report** (single screen, no scrolling if possible)
   - Channel: 6 icon tiles sending these exact strings: `Phone call`, `SMS or WhatsApp`, `QR code`,
     `Fake website`, `UPI request`, `Something else`
   - When: chips "Just now" / "Today" / "Yesterday" (default Just now → occurred_at = now)
   - What: one paste box; auto-detect type (phone / UPI has @ / url has . or http / 6 letters = sender);
     show detected type as a chip the user can change
   - Area: dropdown of areas (search by name/pincode), remembered from last time; optional
     "Use my location" → nearest area computed on device, coordinates discarded
   - Optional: scam-type icon row, note box, "lost money?" amount
   - Submit → success card: "Thanks. Reported anonymously." + "Lost money? Call 1930"
3. **Lookup** — paste box → result card:
   - colour by verdict: KNOWN_SCAM red, SUSPICIOUS amber, NO_REPORTS grey, VERIFIED_BUSINESS green
   - masked display_value, "Reported by N people near you", last seen, scam type
   - safety advice for that scam type (from scam_types.json) + 1930 button
   - "challenged" badge: "Under review — a business disputed this"
4. **Map** — Leaflet + OSM tiles, circles at area points sized by count, coloured by severity;
   alerts banner on top ("Scam reports near HSR Layout doubled today").
5. **Licence expired** — full screen, EN+HI, shown on any 403 LICENSE_EXPIRED; polls /license.

## i18n
`web/src/i18n/en.json`, `hi.json` — every visible string comes from these. Icons always have labels.
Respect banned words (docs/04).

## Implementation notes
- `reporter_id`: random UUID in localStorage (try/catch). `ip_prefix`: the real client can't know it —
  the frontend sends `"web"`; server may derive from request IP's first 3 octets *for real users only*
  (hash immediately). Test tool supplies its own.
- API base URL from one config constant.
- Measure: add a hidden timer (form open → submit) logged to console for rehearsal.
