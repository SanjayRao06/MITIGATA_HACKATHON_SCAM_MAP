# 00 — PRD (source of truth)

Faithful Markdown copy of `docs/reference/PRD_Community_Scam_Map.pdf`
("Community Scam Map: Student Brief", Oct 29, 2026, @Prasanth). **This document outranks every
other doc in this repo.** If any doc in `docs/01–09` disagrees with this file, this file wins —
fix the other doc. Section IDs like `[PRD §A.3]` are used across the other docs to point here.
If something here looks garbled, check the PDF.

---

## [PRD §1] Overview
Build an app where people warn each other about scam phone numbers, UPI IDs and links, and check
one before they trust it. Read the brief once end to end before writing any code.

## [PRD §2] The problem
Ravi's father gets a video call from a man in a police uniform who says a parcel with drugs was
found in his name and he must pay to avoid arrest. He stays on the call for three hours and loses
₹2 lakh. This is a "digital arrest" scam, and it is fake. Ravi tells his family; nobody else hears.
The next day the same number calls Priya across the city. She has no way to check whether anyone
has already reported it.
Scams reach people daily through calls, SMS, WhatsApp, QR codes and UPI payment requests. Missing:
a simple, trusted place to ask "Has anyone reported this number, UPI ID or link as a scam?"

## [PRD §3] What you will build
An Android app or mobile website, plus a server behind it. Five features; first four required,
fifth is bonus.

| # | Feature | Example | Must work like this |
|---|---|---|---|
| 1 | Report a scam | Ravi taps "Phone call", "Just now", pastes the number and posts | Takes under 60 seconds. Saves the area, like "HSR Layout", never the exact address. |
| 2 | Look it up | Priya pastes a number and sees "Reported by 7 people near you" | Answers in under half a second with one of four results: Known scam, Suspicious, No reports, Verified business. |
| 3 | Scam map | Shows that HSR Layout has 12 scam reports this week | Shows only the last 7 days, grouped by area. |
| 4 | Alerts | "Scam reports near you doubled today" | Fires only when something is unusual, never for every report. |
| 5 | Dispute (bonus) | A bakery says "that is our real number" | The number is marked as under review. |

The same number can be typed many ways: `+91 98765 43210`, `09876543210`, `98765-43210`. The app
must treat all of these as one number.

## [PRD §4] The tricky part: fake reports
Building the features is the easy half. People will misuse the app. If you simply count reports,
these tricks work:
- **Report-bombing.** A rival shop asks 40 friends to report a real bakery's number as a scam.
- **Fake accounts.** One person makes 22 accounts from the same Wi-Fi and reports one number.
- **Spamming.** One person reports the same number six times in an hour.
- **Junk.** Someone types "12345" or "test" as the number.

If any of these work, an innocent bakery gets labelled a scam. You need **trust rules**: rules that
decide how much each report should count. Ideas from the brief:
- A new user's report counts less than one from a user whose earlier reports turned out to be right.
- Many reports from the same internet connection within a short time count as one person.
- One person reporting many times is still one person.
- A report with a personal description counts more than a copy-pasted one.
- Junk numbers are rejected straight away.

Caution: a real scam campaign can also cause a sudden wave of reports. The difference: real reports
come from many different, unrelated people writing in their own words. Rules must stop the fakes
without missing the real scams. On judging day they load test reports with all these tricks into
your server. Make your own fake reports while building to check the rules stop them.

## [PRD §5] Privacy rules
Breaking any of these disqualifies the team.
1. **Keep reporters anonymous.** Never store or show a reporter's name, phone number or exact
   location. Save the area only.
2. **Hide numbers until they are confirmed.** Show `98XXXXX210` until at least 3 different people
   have reported it. One angry person should not be able to label someone publicly.
3. **Say "reported", not "scammer".** Write "Reported by 7 people near you", never "This person is a fraud".
4. **Don't dig up personal data.** No collecting names or details from social media or
   people-search websites.
5. **No personal data in logs.**

## [PRD §6] Ship it: a server and a licence
Scenario: a bank buys the app and runs it on its own server; it must stop working if the bank
stops paying (like a prepaid plan when the recharge runs out).

**Step 1 — real server.** Run the server on a cloud machine with a public web address (e.g.
`https://yourteam-scammap.onrender.com`), not a laptop. Free options like Render, Railway, Fly.io
or a free cloud VM are fine. Use HTTPS.

**Step 2 — licence file.** A small file saying who may use the app and until when:
```json
{"licensee": "Demo Bank", "expires_at": "2026-11-15T10:05:00+05:30", "signature": "MEUCIQDx7k..."}
```
The signature stops people editing the date. Create it with a private key that stays on your
laptop. The server checks it with the matching public key, built into the code. If anyone changes
the date, the check fails. Libraries like PyNaCl (Python) or jsonwebtoken (Node.js) make this a few lines.

**Step 3 — check it on every request** (e.g. every request or every few minutes):
- **Valid:** everything works.
- **Expired:** every request except `/health` and `/license` gets `403 {"error": "LICENSE_EXPIRED"}`.
  The app shows "Licence expired. Contact your provider." **Do not delete any data.**
- **Renewed:** when a new licence file is uploaded through `POST /license`, everything works again
  **without restarting the server**.

**What judges will ask you to show, live:**
1. The app working, and `GET /license` showing who it is licensed to and when it expires.
2. You upload a licence that expires in 5 minutes.
3. After 5 minutes, a lookup fails and the app shows the expired screen.
4. You upload a new licence, and the app works again within a minute, with old data still there.

**Bonus thinking:** if someone sets the server clock back a year — save the latest time the server
has seen and refuse if the clock ever goes backwards.

## [PRD §7] What we give you
No access to Mitigata systems needed. Everything is in the Appendix:
- **API rules:** addresses, inputs and replies. The judges' test tool uses these.
- **Area codes:** the 25 areas the test tool uses, with map points.
- **Verified numbers and scam types:** numbers that must show "Verified business", plus scam type
  and channel names.

There is no practice data and no test tool to download. Write your own test reports, including
fake ones, and run them against your server. Public helplines such as **1930** and
**cybercrime.gov.in** can be used directly in the app.

## [PRD §8] How you are scored — 100 points + up to 7 bonus
Rows 1–4 are scored by a test tool against the live server; rows 5–7 by a judge watching.

| # | What we check | Pts | How we check it | Full marks when | Zero when |
|---|---|---|---|---|---|
| 1 | Stops fake reports | 20 | Test tool loads reports full of tricks: 40 friends reporting a real bakery, 22 fake accounts on one Wi-Fi, one person reporting six times, junk like "12345". Checks none makes a number "Known scam". | Every trick is stopped | One person reporting many times can make a number "Known scam" |
| 2 | Lookup gives the right answer | 15 | Real scams → "Known scam", unreported → "No reports", `+91 98765 43210` and `09876543210` give the same answer, answers under half a second. | Right answers, every format matches, fast | Most answers are wrong |
| 3 | Map and alerts | 10 | An area with a sudden jump gets an alert, a normal area does not, a new kind of scam gets an alert, month-old reports are not on the map. | Both work | Neither works |
| 4 | Privacy | 15 | Numbers with fewer than 3 reporters are hidden; the map never shows a person's location. A judge reads the result screen: "Reported by 7 people near you" is good; "This person is a fraud" loses up to 5 points. | Hidden numbers, anonymous reporters, careful wording | A reporter can be identified: disqualified |
| 5 | Server and licence | 15 | Four-step licence demo live on your server. | All four steps work on an https address with no restart | Only runs on a laptop, or nothing stops it |
| 6 | Easy to report | 15 | Judge reports a scam on a phone with a stopwatch, then tries it in Hindi or using only icons. | Under 60 seconds, usable in Hindi or from icons | Over 2 minutes, or a login before the form |
| 7 | Demo and code | 10 | Judge runs the project from the README, reads how trust rules and licence are explained, listens to the pitch. | Easy to run, clear README, clear pitch | It cannot be run |

Part marks between full and zero (e.g. a licence demo that needs a restart ≈ half).
**Bonus (up to 7):** 3 if verified business and helpline numbers show "Verified business"; 2 for the
dispute feature; 2 if fake reports never set off an alert.
**Tie-break:** more bonus points first, then faster report time.
**Judges use different data:** a new, secret set of reports on judging day. Code like
`if number == "+919876543210": return "SUSPICIOUS"` fails, and they check for it. Build real rules.
**Automatic disqualification:** a reporter can be identified, exact locations are stored, personal
data is scraped, or the code was written before the event.

## [PRD §9] Suggested 24-hour plan (only a suggestion)
Strong recommendation: put something on a real server in the first two hours.
| Stage | What to do |
|---|---|
| 1 | Read the brief incl. appendix. Deploy a "hello world" to the cloud server. |
| 2 | Build report and lookup with a real database. Make all number formats match. |
| 3 | Build trust rules. Test with your own fake reports after every change. |
| 4 | Map, alerts and number masking. |
| 5 | Licence file, licence check and "Licence expired" screen. |
| 6 | Put everything on the server. Practise the licence demo three times. |
| 7 | Hindi or icon-based report screen, README and pitch. |

## [PRD §10] What to submit
- Code in a Git repository
- Server's public web address, working during judging
- The app: an APK file, a mobile website link, or both
- A README explaining how to run it, how the trust rules work, and how the licence works
- A demo video of up to 3 minutes
- Two licence files ready for the demo: one that expires in 5 minutes and one long one

## [PRD §11] Tips
- Keep a small set of your own test reports, real-looking and fake, and run it after every change.
- Explain your trust rules in the README. Judges will ask why a fake-reported number was not labelled a scam.
- Keep the report screen short. Nobody fills a long form after a scam call.
- Never put the private licence key in the Git repository.

## [PRD §12] Common mistakes
- Leaving server setup to the last hour.
- Showing full phone numbers that only one person has reported.
- Checking the licence only when the server starts, so it never expires during the demo.
- Deleting data when the licence expires. Lock it, don't delete it.

## [PRD §13] Questions (FAQ)
- **AI tools / ChatGPT-style APIs?** Yes, e.g. to understand free-text reports. Trust rules must be
  your own and explainable.
- **App or website?** Either. A mobile website must work well on a phone.
- **Any language or framework?** Yes; follow the API rules so the test tool can talk to the server.
- **Need Mitigata's code?** No.
- **Where to ask questions?** The hackathon channel.

---

# Appendix

## [PRD §A] API rules
The test tool talks to these seven addresses. Use them exactly as written, JSON in and out. Extra
fields in replies are fine. The server also needs `GET /license` and `POST /license` (§6).

| # | Address | What it does |
|---|---|---|
| 1 | GET /health | Says the server is alive |
| 2 | POST /reports | Receives one scam report |
| 3 | GET /lookup | Checks a number, UPI ID, link or SMS sender |
| 4 | GET /map | Lists scam reports by area for the last 7 days |
| 5 | GET /alerts | Lists alerts for an area |
| 6 | POST /admin/reset | Deletes all reports, so the judges start clean |
| 7 | POST /challenges | A business disputes a number (bonus) |

### [PRD §A.0] Six rules the test tool relies on
1. **Time comes from the report.** Times look like `2026-10-27T18:21:04+05:30`. Work out "last 7 days"
   and "last 24 hours" from each report's `occurred_at`, compared with the server's clock.
2. **The reporter comes from the report.** The test tool runs on one laptop but pretends to be
   hundreds of people. Treat `reporter_id` and `ip_prefix` in the report as the reporter's identity,
   not the laptop's real address.
3. **One identifier, many ways of typing it.** Store each in a single standard form:
   - **Phone:** `+91` and 10 digits. `+91 98765 43210`, `09876543210`, `98765-43210` and
     `919876543210` all become `+919876543210`.
   - **UPI ID:** lower case, no spaces. `Ravi12@OKAXIS` becomes `ravi12@okaxis`.
   - **Link:** `https://`, no `www.`, nothing after `?`, no `/` at the end.
     `http://www.sbi-kyc.in/pay?utm=sms` becomes `https://sbi-kyc.in/pay`.
   - **SMS sender:** the 6-letter code, without the 2-letter prefix the phone adds. `VM-HDFCBK`,
     `AD-HDFCBK` and `HDFCBK` are all `HDFCBK`.
4. **Slowing someone down is fine.** If you rate-limit a reporter, reply `429`. Not counted against you.
5. **No login on these seven addresses.** The test tool sends no password or key.
6. **Reset must work** on the server you show the judges.

### [PRD §A.1] GET /health
Reply `200` with `{"ok": true}`.

### [PRD §A.2] POST /reports
The test tool sends:
```json
{
  "report_id": "rep_000123",
  "occurred_at": "2026-10-27T18:21:04+05:30",
  "reported_at": "2026-10-27T18:40:04+05:30",
  "reporter_id": "r_7c2d91aa",
  "ip_prefix": "103.21.58",
  "channel": "Phone call",
  "scam_type": "digital-arrest",
  "identifier_type": "phone",
  "identifier_value": "+91 98765 43210",
  "pincode": "560102",
  "locality": "HSR Layout",
  "city": "Bengaluru",
  "note": "Video call from a man in police uniform...",
  "has_screenshot": false,
  "amount_lost_inr": 0
}
```
`identifier_type` is `phone`, `upi`, `url` or `sender_id`. `channel` and `scam_type` come from
Appendix C. The note may be English, Hindi or Hinglish, or empty.
Reply:
- `201` with `{"report_id": "...", "case_id": "...", "merged": true}`. `merged` is true when the
  report joined an existing report about the same identifier.
- `400` with `{"error": "..."}` when the identifier, area code or time is not valid. Some test
  reports are junk on purpose; rejecting them is correct.
- `429` when slowing this reporter down.

### [PRD §A.3] GET /lookup
Example: `GET /lookup?type=phone&value=%2B91%2098765%2043210` (value is URL-encoded).
```json
{
  "verdict": "KNOWN_SCAM",
  "report_count": 7,
  "distinct_reporters": 7,
  "first_seen": "2026-10-14T09:12:00+05:30",
  "last_seen": "2026-10-27T18:21:04+05:30",
  "scam_type": "digital-arrest",
  "display_value": "+919876543210",
  "evidence": [
    {"occurred_at": "2026-10-27T18:21:04+05:30", "channel": "Phone call",
     "scam_type": "digital-arrest", "pincode": "560102"}
  ],
  "challenged": false
}
```
- `verdict` is exactly one of `KNOWN_SCAM`, `SUSPICIOUS`, `NO_REPORTS`, `VERIFIED_BUSINESS`.
- `distinct_reporters` counts different people after your trust rules. One person reporting six times is 1.
- `display_value` is what the app would show. Hide it until at least 3 different people have
  reported it: `98XXXXX210` for a phone, `r***@okaxis` for a UPI ID, `sbi***.in/...` for a link,
  `HD****` for a sender.
- `evidence` never includes who reported, their IP or their note.
- A number nobody reported is `200` with `NO_REPORTS`, not `404`. A value that cannot be valid,
  like `12345`, is `400`.

### [PRD §A.4] GET /map
Example: `GET /map?pincode=560102&days=7&radius_km=2`. If `days` is missing use 7; if `radius_km`
is missing use 2.
```json
{
  "clusters": [
    {"pincode": "560102", "locality": "HSR Layout", "city": "Bengaluru", "count": 12,
     "top_scam_type": "digital-arrest", "severity": "CRIT", "lat": 12.9116, "lng": 77.6473}
  ]
}
```
One cluster per area within the radius that has reports in the window. Use the area's map point
from Appendix B, never a reporter's location. `severity` is `CRIT`, `HIGH` or `MED`, on your own scale.

### [PRD §A.5] GET /alerts
Example: `GET /alerts?pincode=560102`
```json
{"alerts": [
  {"type": "SPIKE", "pincode": "560102", "window": "24h", "count": 10, "baseline_per_day": 2.0},
  {"type": "NEW_TYPE", "pincode": "560102", "scam_type": "job-offer", "window": "24h"}
]}
```
- `SPIKE`: reports in the last 24 hours are at least double the daily average of the 7 days
  before, and at least 5.
- `NEW_TYPE`: a scam type reported in the last 24 hours that was not seen in that area in the 30 days before.
- No alerts means `{"alerts": []}`. Fake reports your trust rules ignored should not set off alerts.

### [PRD §A.6] POST /admin/reset
Delete every report and reply `200`.

### [PRD §A.7] POST /challenges (bonus)
```json
{"identifier_type": "phone", "identifier_value": "+91 80 4100 2233",
 "claimant_name": "Fresh Bakes", "contact_email": "owner@example.com",
 "proof_note": "GST certificate and shop licence attached."}
```
Reply `201` with `{"challenge_id": "...", "status": "under_review"}`. After that, a lookup on that
number shows `"challenged": true` and is never `KNOWN_SCAM` while under review.

## [PRD §B] Area codes
The test tool's reports use these 25 areas. The server must accept them, and the map must place
each area at the point given, never at a reporter's own location. You may add more areas.
(Machine-readable copy: `server/app/data/areas.json`.)

| Area code | Area | City | Latitude | Longitude |
|---|---|---|---|---|
| 560102 | HSR Layout | Bengaluru | 12.9116 | 77.6473 |
| 560038 | Indiranagar | Bengaluru | 12.9784 | 77.6408 |
| 560034 | Koramangala | Bengaluru | 12.9352 | 77.6245 |
| 560066 | Whitefield | Bengaluru | 12.9698 | 77.7500 |
| 560076 | BTM Layout | Bengaluru | 12.9166 | 77.6101 |
| 560011 | Jayanagar | Bengaluru | 12.9299 | 77.5826 |
| 560037 | Marathahalli | Bengaluru | 12.9591 | 77.6974 |
| 560103 | Bellandur | Bengaluru | 12.9260 | 77.6762 |
| 560100 | Electronic City | Bengaluru | 12.8452 | 77.6602 |
| 560078 | JP Nagar | Bengaluru | 12.9077 | 77.5851 |
| 560003 | Malleshwaram | Bengaluru | 13.0035 | 77.5709 |
| 560010 | Rajajinagar | Bengaluru | 12.9915 | 77.5520 |
| 560024 | Hebbal | Bengaluru | 13.0358 | 77.5970 |
| 560064 | Yelahanka | Bengaluru | 13.1007 | 77.5963 |
| 560070 | Banashankari | Bengaluru | 12.9250 | 77.5468 |
| 400050 | Bandra West | Mumbai | 19.0596 | 72.8295 |
| 110016 | Hauz Khas | Delhi | 28.5494 | 77.2001 |
| 500081 | Madhapur | Hyderabad | 17.4486 | 78.3908 |
| 600020 | Adyar | Chennai | 13.0012 | 80.2565 |
| 411014 | Viman Nagar | Pune | 18.5679 | 73.9143 |
| 700091 | Salt Lake Sector V | Kolkata | 22.5790 | 88.4290 |
| 380015 | Satellite | Ahmedabad | 23.0260 | 72.5085 |
| 302017 | Malviya Nagar | Jaipur | 26.8570 | 75.8080 |
| 226010 | Gomti Nagar | Lucknow | 26.8540 | 80.9990 |
| 682030 | Kakkanad | Kochi | 10.0159 | 76.3419 |

## [PRD §C] Verified numbers, scam types and channels
**Verified numbers.** A lookup on any of these must say `VERIFIED_BUSINESS`, never a scam (+3 bonus).
The last three are made-up local shops for testing. (Machine-readable: `server/app/data/verified.json`.)

| Type | Value | Belongs to |
|---|---|---|
| phone | 1930 | National Cybercrime Helpline |
| phone | 1909 | TRAI Do Not Disturb |
| phone | 1800 1600 | HDFC Bank customer care |
| phone | 1800 2600 | HDFC Bank customer care |
| phone | 1800 1080 | ICICI Bank customer care |
| phone | 1800 1234 | State Bank of India customer care |
| phone | 1800 2100 | State Bank of India customer care |
| phone | 1860 419 5555 | Axis Bank customer care |
| phone | 1860 266 2666 | Kotak Mahindra Bank customer care |
| sender_id | HDFCBK | HDFC Bank SMS sender |
| sender_id | ICICIB | ICICI Bank SMS sender |
| sender_id | SBIINB | State Bank of India SMS sender |
| sender_id | AXISBK | Axis Bank SMS sender |
| sender_id | KOTAKB | Kotak Mahindra Bank SMS sender |
| url | https://cybercrime.gov.in | National Cyber Crime Reporting Portal |
| url | https://sancharsaathi.gov.in | Sanchar Saathi |
| phone | +91 80 4100 2233 | Fresh Bakes, Indiranagar (made up) |
| phone | +91 80 2553 0190 | Koramangala Pharmacy (made up) |
| upi | freshbakes@okaxis | Fresh Bakes, Indiranagar (made up) |

`1800 1600` is a toll-free number, not a 10-digit mobile. Phone rules must accept short helplines
like `1930` and toll-free numbers starting `1800` or `1860`.

**Scam types.** The `scam_type` field is one of these. Use them for report options and to show the
right safety advice. (Machine-readable: `server/app/data/scam_types.json`.)

| scam_type | What it is |
|---|---|
| digital-arrest | Digital arrest video call: fake police say you are under arrest |
| fake-kyc-link | Fake KYC update link that copies a bank's page |
| upi-refund-qr | UPI refund QR scam: "scan to receive" actually sends money |
| investment-group | WhatsApp investment group with fake profits |
| courier-customs | Parcel held at customs, "pay a fine" |
| job-offer | Work-from-home task job that asks for deposits |
| lottery-prize | Lottery or prize win that needs a fee |
| loan-app-harassment | Instant loan app that threatens your contacts |
| electricity-disconnection | "Power cut tonight" SMS |
| fake-customer-care | Fake customer care number from a search result |
| otp-call | OTP or card verification call |
| sextortion | Video call extortion |

Accept any other value too; treat it as "other" rather than rejecting the report.

**Report channels.** The `channel` field is one of: `Phone call`, `SMS or WhatsApp`, `QR code`,
`Fake website`, `UPI request`, `Something else`.
