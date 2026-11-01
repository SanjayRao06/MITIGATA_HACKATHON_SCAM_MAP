# Community Scam Map

**Check a phone number, UPI ID, link or SMS sender before you trust it. Report a scam in under 30 seconds, anonymously, in English or Hindi.**

| | |
|---|---|
| 🌐 **Website** | https://mitigata-hackathon-scam-map.onrender.com |
| 🧪 **API playground (/docs)** | https://mitigata-hackathon-scam-map.onrender.com/docs |
| 📱 **Works on** | Phones and desktops: any modern browser, no app to install (mobile-first, with a wider layout on laptops) |
| 🗂️ **Demo walkthrough** | [`tools/samples/demo_examples.txt`](tools/samples/demo_examples.txt) |

---

## 1. The pitch

Ravi's father got a video call from a man in a police uniform. "Digital arrest." He was kept on camera
for three hours and told not to tell anyone. The same number had called Priya in Koramangala the day
before, but there was nowhere to check it.

**Scam Map is that place.** Anyone can look a number up before picking up or paying, and anyone who
gets scammed can warn their neighbours in four taps, with no login and no name.

The hard part is that **anyone can also file fake reports**: a rival can get 40 friends to report an
honest bakery. So we never just count reports. We count **independent people**, and a set of trust rules
catches spammers, fake accounts and organised waves, while real scams reported by real strangers still
get flagged. Reporters stay anonymous, numbers stay hidden until three independent people agree, and a
bank can run the whole thing under a signed licence that locks and unlocks without a restart.

---

## 2. How it works, in one picture

```
 Phone / laptop browser  ──┐
   (the website)           │      ┌─────────────────────────────┐      ┌──────────────┐
                           ├────► │  FastAPI server (Python)    │ ───► │  Postgres DB │
 /docs (API playground) ───┘      │  trust rules · licence ·    │      │  (Neon)      │
   or the judges' test tool       │  map · alerts · privacy     │      └──────────────┘
                                  └─────────────────────────────┘
```

**The website and `/docs` talk to the same server and the same database.** A report sent from either
one shows up on the other straight away. Refresh the Map or Dashboard page to see new counts.

### Two ways to send reports

| | The website | `/docs` |
|---|---|---|
| Who it's for | Real people on a phone | Testing, and the judges' test tool |
| Who you are | **One** anonymous person: the browser makes a random ID, and the server reads your real network | **Anyone**: each report carries its own `reporter_id` (the person) and `ip_prefix` (their network) |
| Use it to show | Normal reports, Hindi, icons only, Check, Map, Dashboard | **Many different people** from one laptop, e.g. 22 accounts on one Wi-Fi or 40 friends on 40 networks |

So: **send fake waves through `/docs`, then look the number up on the website** to see what we decided.

**Using `/docs`:** open it → click an endpoint (e.g. `POST /reports`) → **Try it out** → paste a body →
**Execute** → read **Server response**.

---

## 3. Test every feature (judge's checklist)

The live server already has **demo data** loaded, so you can check these straight away.
Use the website's **Check** page, or `GET /lookup` in `/docs`.

### Lookups

| Type this | Type | You should see | What it shows |
|---|---|---|---|
| `6759898347` | Phone | **Known scam**, number shown in full | A real scam wave: 8 unrelated people |
| `CASHBACK.DESK1286@OKICICI` | UPI ID | **Known scam** | Real UPI scam; capitals don't matter |
| `7650201462` | Phone | Suspicious, 2 people, `76XXXXX462` | Hidden until **3** independent people report it |
| `7462819482` | Phone | Suspicious, **1 person** | 🛑 Spammer: one person reported 6 times |
| `8797543231` | Phone | Suspicious, **1 person** | 🛑 22 fake accounts on one Wi-Fi |
| `8121547280` | Phone | Suspicious, hidden | 🛑 40 friends report-bombing a bakery |
| `+91 80 4100 2233` | Phone | **Verified business** | 🛑 Fake reports against a verified bakery |
| `12345` | Phone | Error: not a valid number | 🛑 Junk input |
| `6095235420` | Phone | Suspicious + **Under review**, hidden | A business disputed it |
| `HDFCBK` · `1930` | SMS sender · Phone | **Verified business** | The verified list from the brief |
| `9123498765` | Phone | No reports | Never reported |

On any result, open **"Why this result?"** to see which trust rules applied (counts only, never who reported),
or tap **🔊 Read aloud** to hear the result in English or Hindi. It uses the phone's own voice; if the phone has
no Hindi voice, our server makes the audio (`GET /speak`, a Microsoft neural voice). Only the on-screen verdict
and safety advice are spoken, never the number (long numbers are refused), and the text is never logged.

**Number formats:** `+91 98765 43210`, `09876543210`, `98765-43210` and `919876543210` are the same number.
UPI IDs ignore capitals. Links ignore `http`, `www.` and `?tracking`. `VM-HDFCBK` is the same sender as `HDFCBK`.

### Map and alerts (Map page → Bengaluru → Last 7 days)

| Area | You should see |
|---|---|
| Bellandur | 🔴 **SPIKE** alert: many more reports today than usual |
| Electronic City | 🆕 **NEW_TYPE** alert: a scam type new to the area |
| Marathahalli | Busy every day, but **no alert**: that's normal for it |
| Whitefield, Indiranagar | **No alert**: the fake waves there count for nothing |
| Hebbal | **Not on the map**: its reports are a month old |

Other cities (Mumbai, Delhi, Hyderabad …) have data too: switch city on the Map or the **Dashboard**.

### Report a scam yourself (website, on a phone)

1. Tap the yellow **+**, pick how they contacted you, when, paste their number, pick your area, submit.
   No login. Usually under 30 seconds.
2. **Hindi:** tap **हिंदी** at the top. **Icons only:** every step has a picture, and the 📋 Paste
   and 📍 location buttons mean no typing.
3. **Check** that number → *Suspicious · Reported by 1 person · hidden*.
4. Report **4 times in an hour** from the same browser → the 4th says *"You've sent several reports
   in a short time"* (rate limit).

### Send fake waves yourself (/docs)

[`tools/samples/demo_examples.txt`](tools/samples/demo_examples.txt) has ready-to-paste steps for 10
examples: a real scam, the spammer, 8 accounts on one Wi-Fi, report-bombing, a verified business, junk,
formats, map, alerts and a dispute. Each `POST /reports` line is one report, and the arrow shows the
expected answer (e.g. `201 201 201 429 429 429`). For fresh times and numbers, run
`python tools/make_demo_examples.py` first.

---

## 4. Trust rules: how we stop fake reports

Every report about a number goes through five layers. The answer counts **trusted sources**, not reports.

| Rule | What it does | Stops |
|---|---|---|
| **L1 Same person** | All reports from one `reporter_id` count as one | Spammer reporting 6 times |
| **L2 Same network** | Same `ip_prefix` + same number within 24 h = one source | 22 accounts on one Wi-Fi |
| **L3 Copy-paste** | Nearly identical notes merge into one source; personal stories count more | Friends pasting the same text |
| **L4 Organised wave** | 3+ people scored on 6 warning signs: a burst inside 2 h, all brand-new accounts, few networks, one area, empty or copied notes, nobody lost money. A high score means new accounts count ×0.2 and it **can't** be Known scam. **Exception:** if 80%+ of the people wrote their own unique words from their own networks, it's a real wave of independent voices, not an organised one | 40 friends report-bombing |
| **L5 Reputation** | New reporters count 0.6, people with a track record up to 1.0; anyone who reported a verified business drops to 0.3 | Repeat troublemakers |

**The verdict:**
- **Known scam** needs **3+ trusted sources from 3+ different networks**, no organised wave, and no open dispute.
- Fewer than that → **Suspicious**, and the number stays **hidden**.
- On the brief's verified list → always **Verified business**.

**Also:**
- Junk (`12345`, `test`, unknown area, a future date) → **400**, never stored.
- More than **3 reports an hour** (or 20 a day) from one person → **429**.
- Fake reports never count towards the map or alerts, and alerts count **people**, not reports
  (one person reporting five different numbers is still one person).

**Why a real scam still gets through:** real victims are different people on different networks, in
different areas, writing in their own words, and some lost money. So the organised-wave score stays low,
even when a real scam produces a sudden burst of reports. And if a real burst hits one neighbourhood
in one hour, the independent-voices exception (different networks + own words) still lets it through.

---

## 5. The licence: lock and unlock live, no restart

A licence is a small file saying **who** may use the server and **until when**, **signed** with our private key:

```json
{"licensee": "Demo Bank", "expires_at": "2027-10-31T21:41:15+05:30", "issued_at": "...", "signature": "..."}
```

- **It can't be forged.** The server only holds the **public** key, so it can check a licence but never
  create one. Change one character (say, the year) and the signature fails → `400 INVALID_SIGNATURE`.
- **It's checked on every request**, not just at startup. Only `/health` and `/license` stay open.
- **When it ends, the site locks.** Every other address returns `403 LICENSE_EXPIRED`, and the website
  shows *"Licence expired. Contact your provider."* by itself, with no reload. **No data is deleted.**
- **Renewing works instantly.** Upload a new licence and the site unlocks within seconds, with no restart.
- **Old or rolled-back licences don't work.** An already-expired file is refused (`LICENSE_ALREADY_EXPIRED`),
  and setting the server clock back locks it (`CLOCK_TAMPERED`).

### Test it

**Without our key (any judge), in `/docs`.** The two licence files come with our submission; they are
never in Git.
1. `GET /license` → shows the current licence: `VALID`, Demo Bank.
2. `POST /license` → paste the contents of `long.json` → `200`.
3. `POST /license` → paste it again with `expires_at` changed to `2099…` → `400 INVALID_SIGNATURE`.
   `GET /license` is unchanged.

**The full 4-step demo** (on our laptop, which holds the private key; PowerShell):
```powershell
$P = "server\.venv\Scripts\python"
& $P tools\upload_license.py --show --live                                                  # 1. VALID
& $P tools\make_license.py --licensee "Demo Bank" --minutes 5 --out licenses\short.json    # 2. make a 5-minute licence
& $P tools\upload_license.py licenses\short.json --live                                     #    and upload it
#   wait 5 minutes: the website locks by itself; /lookup -> 403; /health -> 200            # 3. expired
& $P tools\upload_license.py licenses\long.json --live                                      # 4. renewed, same data
```

---

## 6. Privacy

- **No reporter identity is stored.** `reporter_id` and `ip_prefix` are kept only as one-way hashes.
- **Area only.** We never store an address or exact location. The map shows the area's own point.
- **Hidden numbers.** A number is shown like `98XXXXX210` until 3 independent people have reported it.
- **Careful words.** The site says "reported", never "scammer" or "fraud".
- **Logs** hold only method, path, status and milliseconds. Never numbers, IPs or notes.

---

## 7. Run it yourself

```bash
cd server
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt        # Linux/Mac: .venv/bin/pip
.venv/Scripts/python -m uvicorn app.main:app --port 8000
```
Open http://localhost:8000 and http://localhost:8000/docs. A fresh local database has no licence, so
upload `licenses/long.json` first: `python tools/upload_license.py licenses/long.json`.

**Load the demo data and grade every scenario** (from the repo root):
```bash
python tools/scenarios.py --base http://localhost:8000 --seed 7
```
This sends the full-size attacks (22 accounts, 40 friends, the spammer, junk) plus real scam waves, and
prints a PASS/FAIL table: **47/47 checks pass**.

**Run the tests:** `cd server && .venv/Scripts/python -m pytest -q` (255 tests).

---

## 8. What's where

```
server/app/         the server: main.py (routes) · trust.py (trust rules) · lookup.py · reports.py
                    normalize.py · privacy.py · license.py · geo.py, alerts.py · challenges.py · stats.py
server/app/data/    areas, verified identifiers, scam types, channels
server/web/         the website (plain JavaScript, English + Hindi)
server/tests/       255 tests (pytest)
tools/              scenarios.py (attacks + demo data) · make_demo_examples.py · latency_check.py
                    keygen.py · make_license.py · upload_license.py (licence signing and upload)
tools/samples/      demo_examples.txt (copy-paste walkthrough for /docs)
render.yaml         hosting settings
```

Hosted on Render (Singapore) with a Neon Postgres database, and auto-deployed on every push.
