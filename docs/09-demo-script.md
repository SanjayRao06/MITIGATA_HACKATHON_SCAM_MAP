# 09 — Demo script, pitch and video (judging day)

All commands: PowerShell, repo root, `$P = "server\.venv\Scripts\python"`, `$U = "https://mitigata-hackathon-scam-map.onrender.com"`.
Live run order and checklists are also in PROGRESS.md §7 (runbook).

## T-1 day
- [ ] Render → Environment: `KEEP_DB_AWAKE=1` (Neon stays awake: no slow first lookup)
- [ ] Load fresh demo data (the map only shows the last 7 days):
      `& $P tools\scenarios.py --base $U --seed 7 --allow-remote-reset` → `47/47 checks passed`
- [ ] `& $P tools\latency_check.py --base $U` → server's own time ~10 ms

## T-30 min
- [ ] Open `$U` once (wakes Render); UptimeRobot green
- [ ] `& $P tools\upload_license.py --show --live` → long licence, VALID
- [ ] Reload demo data (command above) and keep its "Try these on the website" list open
- [ ] Phone on mobile data, site bookmarked, language EN
- [ ] Laptop: `private.key`, `licenses\long.json`, terminal open
- [ ] Backup screen recording of the full demo on the laptop

## Live run (~8–10 min). Start the 5-minute licence FIRST, demo the rest while it runs down
1. **Licence status:** `--show --live` (Demo Bank, 2027). Then
   `& $P tools\make_license.py --licensee "Demo Bank" --minutes 5 --out licenses\short.json` and
   `& $P tools\upload_license.py licenses\short.json --live`. "The clock is ticking."
2. **Report** on the phone with a stopwatch: how they contacted you → when → their number → area → Submit (< 30 s).
   Repeat in Hindi, then using only the icons.
3. **Lookup:** the same number in 3 formats → same answer. A number with 2 reporters → Suspicious, masked;
   3+ → Known scam, shown in full. `HDFCBK` / `1930` → Verified business. Point at the wording ("reported").
4. **Attacks:** from the try-list: the bakery (40 friends), the Wi-Fi farm (22 accounts), the spammer → none
   is Known scam. The real campaign → Known scam. Line: "we stop fakes without missing real scams."
5. **Map + alerts (Bengaluru):** Bellandur SPIKE · Electronic City NEW_TYPE · Marathahalli busy but no alert ·
   Whitefield / Indiranagar fakes: no alert · Hebbal month-old reports: not on the map. Then the Dashboard for
   Mumbai / Delhi to show other cities.
6. **Dispute:** "Dispute a report" on a Known-scam number → "Under review", hidden again, never Known scam.
7. **Expiry** (after 5 min): leave the site open → "Licence expired. Contact your provider." appears by itself.
   `curl $U/health` still 200.
8. **Renew:** `& $P tools\upload_license.py licenses\long.json --live` → screen clears within ~20 s, same data.
9. **Privacy recap (30 s):** hashed reporter ids, area only, masking until 3 people, a log line has only method/path/status/ms.
10. **Pitch close** (below).

## Pitch (2 minutes)
1. **The story (20 s).** "Ravi's father got a video call from a 'police officer'. Digital arrest. He was kept on
   camera for three hours. The same number had called Priya in Koramangala the day before. Nobody could warn him."
2. **What it does (20 s).** Check any number, UPI ID, link or SMS sender before you trust it. Report one in under
   30 seconds, in English or Hindi, no name or phone needed. See which scams are active in your area this week.
3. **Why you can trust it (30 s).** Anyone can file fake reports, so we never count reports, we count independent
   people. One person, one Wi-Fi, copy-pasted text, a sudden wave of new accounts: each is caught by a rule we
   can explain. The bakery bombed by 40 friends stays clean; a real scam reported by 8 strangers is flagged.
4. **Privacy (15 s).** We store no names, no phone numbers of reporters, no locations: hashes and the area only.
   A number stays masked until three independent people have reported it.
5. **Licence (15 s).** A bank deploys it under a signed licence. It cannot be forged or extended by editing it,
   and when it ends the service locks without deleting anything, then unlocks the moment it is renewed.
6. **Close (20 s).** "A bank can offer this to its customers tomorrow: every lookup is a scam stopped before the
   money moves."

## Video (≤ 3 minutes), shot list
| Time | Shot |
|---|---|
| 0:00–0:15 | The story (one line on screen), Home page on a phone |
| 0:15–0:45 | Report on the phone with a stopwatch visible (< 30 s), then the same in Hindi |
| 0:45–1:15 | Lookup: 3 formats same answer; masked vs shown; Verified business |
| 1:15–1:45 | Attacks: bakery / Wi-Fi farm / spammer not Known scam; real campaign Known scam (scenarios table) |
| 1:45–2:10 | Map with SPIKE / NEW_TYPE; Dashboard for another city |
| 2:10–2:45 | Licence: 5-minute licence uploaded → site locks by itself → long licence → unlocks (cut the wait) |
| 2:45–3:00 | Privacy one-liner + close |

## Likely judge questions
- **Why wasn't the bakery labelled?** New accounts, a 2-hour burst, one area, copy-paste or empty notes, nobody
  lost money: 5 of 6 coordination signs. The verified Fresh Bakes number is always Verified business.
- **What if a real scam comes in a burst?** Bursts alone don't block it: real reporters differ in network, area
  and words, and some lost money, so the coordination score stays low.
- **What stops editing the licence date?** The Ed25519 signature covers every field; the server only has the
  public key, so it can check licences but not create them.
- **What if the clock is set back?** The server remembers the latest time it has seen; a jump back of more than
  2 minutes locks it.
- **How is lookup kept fast?** Two indexed queries per lookup; the server's own time is ~10 ms (Server-Timing
  header). The rest is network.
- **Why not let one person's report show the number?** One angry person could then label anyone publicly.

## Submission checklist ([PRD §10])
Repo (no private key) · public HTTPS URL, kept awake · mobile website link · README · ≤ 3-min video ·
licence files: `licenses/long.json` + a 5-minute one generated at demo time.
