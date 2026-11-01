"""Writes tools/samples/demo_examples.txt: ONE walkthrough that shows every feature of Scam Map.

Run it right before a demo:
    python tools/make_demo_examples.py
Every time is relative to NOW (alerts only look at the last 24 hours, so old dates would stop
working) and every number/UPI ID is fresh (so running the walkthrough twice, or on the live server
next to the demo data, never mixes counts).

What it covers:
- Part A, on the website (your phone): normal reports of every kind (phone call, SMS sender, UPI,
  fake link, "something else", a picked date, Hindi, icons only), then Check / Map / Dashboard.
- Part B, the fake-report tricks of [PRD §4] (spamming, many accounts on one Wi-Fi, report-bombing,
  reporting a verified business, junk) next to a real scam. One phone can't pretend to be 8 people
  on 8 networks, so those reports are pasted into /docs; every RESULT is then checked on the website.
- Part C: map window, alerts, dispute, licence.
server/tests/test_demo_examples.py replays every checked step against the server, on an empty
database and on one full of demo data, so each "expect" line in the file is known to be true.
"""

import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tools" / "samples" / "demo_examples.txt"
AREAS = {a["pincode"]: a for a in json.loads((ROOT / "server" / "app" / "data" / "areas.json").read_text(encoding="utf-8"))}
IST = timezone(timedelta(hours=5, minutes=30))
LIVE = "https://mitigata-hackathon-scam-map.onrender.com"
WEB_VERDICT = {"KNOWN_SCAM": "Known scam", "SUSPICIOUS": "Suspicious", "NO_REPORTS": "No reports",
               "VERIFIED_BUSINESS": "Verified business"}


# ----------------------------------------------------------------------------- building blocks
class Maker:
    """Makes fresh numbers, ids and report bodies for one generated file."""

    def __init__(self, now: datetime, seed: int | None = None):
        self.now = now
        self.rng = random.Random(seed)
        self.tag = now.strftime("%d%H%M")        # report ids differ on every generated file
        self.n = 0

    def ts(self, hours_ago: float) -> str:
        """A time `hours_ago` before now, in the brief's format (2026-11-01T09:15:00+05:30)."""
        return (self.now - timedelta(hours=hours_ago)).isoformat(timespec="seconds")

    def phone(self) -> str:
        """A fresh 10-digit mobile number (not junk-looking, so the server accepts it)."""
        while True:
            body = str(self.rng.randint(7, 9)) + "".join(str(self.rng.randint(0, 9)) for _ in range(9))
            if len(set(body)) >= 5:
                return body

    def letters(self, n: int) -> str:
        return "".join(self.rng.choice("ABCDEFGHJKLMNPRSTUVWXYZ") for _ in range(n))

    def report(self, value: str, hours_ago: float, pincode: str, reporter: str, net: str, *,
               id_type: str = "phone", channel: str = "Phone call", scam_type: str = "digital-arrest",
               note: str = "", screenshot: bool = False, lost: int = 0) -> dict:
        """One POST /reports body exactly in the [PRD §A.2] shape."""
        self.n += 1
        area = AREAS[pincode]
        return {
            "report_id": f"demo_{self.tag}_{self.n:03d}",
            "occurred_at": self.ts(hours_ago), "reported_at": self.ts(max(0.0, hours_ago - 0.2)),
            "reporter_id": reporter, "ip_prefix": net,
            "channel": channel, "scam_type": scam_type,
            "identifier_type": id_type, "identifier_value": value,
            "pincode": pincode, "locality": area["locality"], "city": area["city"],
            "note": note, "has_screenshot": screenshot, "amount_lost_inr": lost,
        }


def post(body: dict, status: int, say: str, compact: bool = False) -> dict:
    return {"kind": "report", "body": body, "status": status, "say": say, "compact": compact}


def lookup(id_type: str, value: str, say: str, **expect) -> dict:
    """expect keys: verdict, not_verdict, people (distinct_reporters), count (report_count), masked, challenged."""
    return {"kind": "lookup", "type": id_type, "value": value, "say": say, "expect": expect}


def get(path: str, web: str, demo_data_only: bool = False, **expect) -> dict:
    """A /map or /alerts check. `web` = what to do and see on the website. expect keys: status,
    has_area, no_area, alert (type expected), no_alerts (True)."""
    return {"kind": "get", "path": path, "say": web, "expect": expect, "demo_only": demo_data_only}


def challenge(body: dict, status: int, say: str) -> dict:
    return {"kind": "challenge", "body": body, "status": status, "say": say}


def text(*lines: str) -> dict:
    """Plain instructions (website steps done by hand); not replayed by the test."""
    return {"kind": "text", "lines": list(lines)}


def hidden(id_type: str, value: str) -> str:
    """How the website shows a hidden identifier (same rule as server/app/privacy.py mask())."""
    if id_type == "phone":
        d = value[-10:]
        return d[:2] + "XXXXX" + d[-3:]
    if id_type == "upi":
        name, _, handle = value.lower().partition("@")
        return name[:1] + "***@" + handle
    return "partly hidden"


# ----------------------------------------------------------------------------- the walkthrough
def build(now: datetime | None = None, seed: int | None = None) -> list[dict]:
    """In: the time to build around (default: now). Out: a list of sections, each with steps."""
    m = Maker(now or datetime.now(IST), seed)
    t = m.tag
    s = []

    # ===== PART A: normal reports on the website (by hand, on a phone) ==============================
    w_call, w_sms, w_upi, w_link, w_other, w_hindi, w_icon = (m.phone(), m.letters(6), None, None,
                                                              m.phone(), m.phone(), m.phone())
    w_upi = f"kyc.update{m.rng.randint(100, 999)}@ybl"
    w_link = f"https://hdfc-reward{m.rng.randint(10, 99)}.in/claim"
    w_farm = m.phone()
    s.append({"values": {"call": w_call, "hindi": w_hindi, "icon": w_icon, "farm": w_farm},
              "title": "A1. NORMAL REPORTS ON THE WEBSITE (your phone, Report page)", "intro": [
        "WHERE: the website, Report page (bottom bar, yellow +). No login. Pick YOUR area in step 4,",
        "e.g. HSR Layout. Before you start, open the Map (Bengaluru, Last 7 days) and note your area's count.",
        "RATE LIMIT: one person may send at most 3 reports an hour (more -> 429). Each browser window is one",
        "anonymous person, so: R1-R3 in your NORMAL window, R4-R6 in a PRIVATE/incognito window, R7 in a",
        "second new private window (close the first one; a new private window = a new person)."],
        "steps": [text(
            f"R1  Phone call       | Just now        | {w_call}        | open 'Add details': type Digital arrest,",
            "                       note \"Fake police on video call said I am under arrest\", money lost 0, proof Screenshot",
            f"R2  SMS or WhatsApp  | Earlier today   | {w_sms}             (an SMS sender: tap Change -> SMS sender)",
            f"R3  QR code          | Yesterday       | {w_upi}     (UPI ID is picked automatically)",
            f"R4  Fake website     | Just now        | {w_link}",
            f"R5  Something else   | Pick date & time (2 days ago) | {w_other}   type how: \"Telegram message\";",
            "                       Add details -> scam type Something else -> \"crypto doubling offer\"",
            f"R6  In HINDI         | tap हिंदी at the top, then: फ़ोन कॉल | अभी-अभी | {w_hindi}",
            f"R7  ICONS ONLY       | copy {w_icon} first, then tap: phone tile -> flash -> Paste ->",
            "                       location (target icon) -> green button. Don't read any text. Time it.",
            "",
            "Expect after each: a green \"Thanks\" screen with safety advice for that scam type.",
            "Errors to show on purpose: number \"12345\" -> \"doesn't look like a valid phone number\";",
            "a date in the future -> error under step 2.",
        )]})
    s.append({"title": "A2. CHECK THEM (Check page) + MAP + DASHBOARD", "intro": [
        "WHERE: the website. Check page: pick the type tab first, then paste the value."],
        "steps": [text(
            f"CHECK  Phone {w_call}   -> Suspicious · Reported by 1 person · {hidden('phone', w_call)} (partly hidden",
            "                             until 3 different people report it) · advice for digital arrest",
            f"CHECK  SMS sender {w_sms}   -> Suspicious · Reported by 1 person",
            f"CHECK  UPI {w_upi.upper()}   -> same answer even in CAPITALS · {hidden('upi', w_upi)}",
            f"CHECK  Link {w_link.replace('https://', 'http://www.')}?utm=sms   -> same answer (http, www, ?utm ignored)",
            f"CHECK  Phone +91 {w_hindi[:5]} {w_hindi[5:]} and 0{w_hindi}   -> same answer for every format",
            "MAP    Bengaluru, Last 7 days -> your area's count went UP by the reports you sent",
            "       (refresh the Map page). Circles are at the AREA's point, never your location.",
            "DASHBOARD  Bengaluru -> reports this week, top areas, top scam types; switch to Mumbai/Delhi.",
            "SPAMMER ON THE WEBSITE: in your NORMAL window (already 3 reports this hour) report R1's number",
            "       again -> \"You've sent several reports in a short time\" (429), nothing saved.",
            f"       Check {w_call} still says Reported by 1 person.",
            f"WI-FI FARM ON THE WEBSITE: close all private windows. Then 3 times: open a NEW private window",
            f"       (= a new fake account) on the SAME Wi-Fi and report the SAME number {w_farm}.",
            f"       Check {w_farm} -> Reported by 1 person (not 3): same network + same number = one source.",
        )]})

    # ===== PART B: real scam vs the fake-report tricks (reports in /docs, results on the website) ===
    real = m.phone()
    a = m.report(f"+91 {real[:5]} {real[5:]}", 9, "560102", f"r_ravi_{t}", "103.21.58", screenshot=True,
                 note="Video call from a man in police uniform saying a parcel with drugs was in my name")
    b = m.report("0" + real, 6, "560034", f"r_priya_{t}", "49.36.12", lost=15000,
                 note="They kept my father on a video call for 3 hours and asked him to transfer money")
    c = m.report(f"{real[:5]}-{real[5:]}", 3, "560038", f"r_amit_{t}", "117.99.4",
                 note="Mujhe bola arrest warrant hai, Skype pe aao abhi")
    s.append({"title": "B1. A REAL SCAM: 3 different people, 3 ways of typing the number", "intro": [
        "WHERE: paste the reports in /docs (POST /reports), then CHECK on the website after each one.",
        "Different people, networks, areas and words = a real scam -> KNOWN_SCAM. One person alone stays hidden."],
        "steps": [
        post(a, 201, "Report A (Ravi, HSR Layout)  -> 201, merged: false"),
        lookup("phone", real, "after A", verdict="SUSPICIOUS", people=1, masked=True),
        post(b, 201, "Report B (Priya, Koramangala, number typed with a 0)  -> 201, merged: true"),
        lookup("phone", real, "after A+B", verdict="SUSPICIOUS", people=2, masked=True),
        post(c, 201, "Report C (Amit, Indiranagar, number typed with a dash)  -> 201, merged: true"),
        lookup("phone", real, "after A+B+C: 3 people, now shown in full", verdict="KNOWN_SCAM", people=3, masked=False),
        lookup("phone", "91" + real, "same number typed another way -> same answer", verdict="KNOWN_SCAM", people=3),
    ]})

    spam = m.phone()
    spam_bodies = [m.report(spam, 1.0 - i * 0.12, "560010", f"r_angry_{t}", "1.2.3", channel="SMS or WhatsApp",
                            scam_type="lottery-prize", note="scam") for i in range(6)]
    s.append({"title": "B2. FAKE: SPAMMING - one person reports the same number 6 times in an hour", "intro": [
        "WHERE: /docs (or on the website, see A2). Same reporter_id every time. Rule L1: one person counts",
        "once. Rate limit: more than 3 reports an hour from one person -> 429."],
        "steps": [post(spam_bodies[0], 201, "1st  -> 201")]
        + [post(spam_bodies[i], 201 if i < 3 else 429, f"{i + 1}{'nd' if i == 1 else 'rd' if i == 2 else 'th'}"
                f"  -> {'201' if i < 3 else '429 RATE_LIMITED'}", compact=True) for i in range(1, 6)]
        + [lookup("phone", spam, "only 3 stored, and they are ONE person", verdict="SUSPICIOUS", people=1, count=3, masked=True)],
    })

    farm = m.phone()
    farm_notes = ["fraud call", "this number is fake", "cheater", "scam call", "do not pick up", "fake caller",
                  "beware", "they lie"]
    farm_bodies = [m.report(farm, 1.5 - i * 0.18, "560066", f"r_farm{i + 1}_{t}", "49.200.10", scam_type="otp-call",
                            note=farm_notes[i]) for i in range(8)]
    s.append({"title": "B3. FAKE: ONE WI-FI, MANY ACCOUNTS - 8 accounts, same ip_prefix, 90 minutes", "intro": [
        "WHERE: /docs. Different reporter_id each time but the SAME ip_prefix (one house, one Wi-Fi).",
        "Rule L2: same network + same number within 24 h = ONE source. (Judges: 22 accounts.)"],
        "steps": [post(farm_bodies[0], 201, "account 1  -> 201")]
        + [post(b2, 201, f"account {i + 2}  -> 201", compact=True) for i, b2 in enumerate(farm_bodies[1:])]
        + [lookup("phone", farm, "8 accounts = 1 source", verdict="SUSPICIOUS", people=1, masked=True),
           get("/alerts?pincode=560066", "MAP page: no alert banner for Whitefield (fakes set off nothing)", no_alerts=True)],
    })

    bakery = m.phone()
    paste = "This bakery is cheating customers, fake number, do not call or pay them!!"
    bomb_notes = [paste, paste, paste, "", paste, "scam", paste, ""]
    bomb_bodies = [m.report(bakery, 1.0 - i * 0.1, "560010", f"r_friend{i + 1}_{t}", f"{60 + i}.{10 + i}.{i + 3}",
                            scam_type="fake-customer-care", note=bomb_notes[i]) for i in range(8)]
    s.append({"title": "B4. FAKE: REPORT-BOMBING - 8 friends of a rival report a real bakery", "intro": [
        "WHERE: /docs. Each friend has their own account AND network, so L1/L2 don't catch them. What does:",
        "L3 copy-pasted notes merge into one source; L4 coordination (brand-new accounts, all within an hour,",
        "one area, copy-paste/empty notes, nobody lost money) blocks KNOWN_SCAM. (Judges: 40 friends.)"],
        "steps": [post(bomb_bodies[0], 201, "friend 1  -> 201")]
        + [post(b2, 201, f"friend {i + 2}  -> 201", compact=True) for i, b2 in enumerate(bomb_bodies[1:])]
        + [lookup("phone", bakery, "8 reports, but NOT Known scam, and still hidden", not_verdict="KNOWN_SCAM", masked=True),
           get("/alerts?pincode=560010", "MAP page: no alert banner for Rajajinagar (+2 bonus: fakes never alert)",
               no_alerts=True)],
    })

    vb = [m.report("+91 80 4100 2233", 0.9 - i * 0.2, "560038", f"r_rival{i + 1}_{t}", f"88.{i + 1}.7",
                   scam_type="fake-customer-care", note=paste) for i in range(3)]
    s.append({"title": "B5. FAKE: REPORTING A VERIFIED BUSINESS (Fresh Bakes, on the brief's verified list)", "intro": [
        "WHERE: /docs (or report +91 80 4100 2233 on the website). The verified list always wins, and",
        "reporting a verified business lowers those reporters' trust (L5) for their other reports."],
        "steps": [post(vb[0], 201, "rival 1  -> 201")]
        + [post(b2, 201, f"rival {i + 2}  -> 201", compact=True) for i, b2 in enumerate(vb[1:])]
        + [lookup("phone", "+91 80 4100 2233", "still Verified business", verdict="VERIFIED_BUSINESS")],
    })

    j = dict(a, report_id=f"demo_{t}_j1", reporter_id=f"r_junk_{t}", identifier_value="12345")
    j2 = dict(a, report_id=f"demo_{t}_j2", reporter_id=f"r_junk_{t}", identifier_value="test")
    j3 = dict(a, report_id=f"demo_{t}_j3", reporter_id=f"r_junk_{t}", identifier_value=m.phone(), pincode="999999")
    j4 = dict(a, report_id=f"demo_{t}_j4", reporter_id=f"r_junk_{t}", identifier_value=m.phone(),
              occurred_at=m.ts(-24 * 30), reported_at=m.ts(0))
    odd = m.phone()
    j5 = m.report(odd, 2, "560102", f"r_odd_{t}", "14.15.16", scam_type="alien-attack",
                  note="Some new kind of trick I have not seen before")
    s.append({"title": "B6. FAKE: JUNK AND BAD INPUT - rejected straight away", "intro": [
        "WHERE: /docs (the website shows the same errors, see A1). Junk is refused with 400 and never stored.",
        "An unknown scam type is NOT rejected: it is kept as \"other\" (the brief says so)."],
        "steps": [
        post(j, 400, "number \"12345\"  -> 400", compact=True),
        post(j2, 400, "number \"test\"  -> 400", compact=True),
        post(j3, 400, "unknown pincode 999999  -> 400", compact=True),
        post(j4, 400, "occurred_at a month in the FUTURE  -> 400", compact=True),
        post(j5, 201, "unknown scam_type \"alien-attack\"  -> 201 (saved as \"other\")", compact=True),
        lookup("phone", "12345", "junk  -> error \"doesn't look like a valid phone number\" (API: 400)"),
    ]})

    upi = f"Refund.Help{m.rng.randint(100, 999)}@OKAXIS"
    url_host = f"sbi-kyc{m.rng.randint(10, 99)}.in"
    u = m.report(upi, 5, "560076", f"r_neha_{t}", "59.88.1", id_type="upi", channel="UPI request",
                 scam_type="upi-refund-qr", screenshot=True, lost=4999,
                 note="Said scan this QR to receive refund, money went out instead")
    w = m.report(f"http://www.{url_host}/pay?utm=sms", 4, "560011", f"r_kiran_{t}", "106.51.7", id_type="url",
                 channel="Fake website", scam_type="fake-kyc-link", screenshot=True,
                 note="SMS said KYC expired, link looked exactly like SBI")
    s.append({"title": "B7. UPI IDs, LINKS, SMS SENDERS, VERIFIED NUMBERS, NEVER REPORTED", "intro": [
        "WHERE: reports in /docs, checks on the website. Every format is stored in one standard form."],
        "steps": [
        post(u, 201, "UPI ID typed in capitals  -> 201"),
        lookup("upi", upi.lower(), "typed in small letters -> same UPI ID", verdict="SUSPICIOUS", masked=True),
        post(w, 201, "link with http, www and ?utm  -> 201"),
        lookup("url", f"{url_host}/pay", "typed without https/www/?utm -> same link", verdict="SUSPICIOUS", masked=True),
        lookup("sender_id", "VM-HDFCBK", "SMS sender with the phone's prefix -> HDFCBK", verdict="VERIFIED_BUSINESS"),
        lookup("phone", "1930", "cybercrime helpline", verdict="VERIFIED_BUSINESS"),
        lookup("phone", "1800 1600", "HDFC Bank toll-free", verdict="VERIFIED_BUSINESS"),
        lookup("upi", "freshbakes@okaxis", "Fresh Bakes' UPI", verdict="VERIFIED_BUSINESS"),
        lookup("phone", m.phone(), "a valid number nobody reported", verdict="NO_REPORTS"),
    ]})

    # ===== PART C: map window, alerts, dispute =====================================================
    old = m.phone()
    o = m.report(old, 24 * 30, "560024", f"r_old_{t}", "21.22.23", scam_type="otp-call",
                 note="Got this call last month asking for my card OTP")
    s.append({"title": "C1. MAP - only the last 7 days, only area points", "intro": [
        "WHERE: website Map page (refresh it after sending reports). Severity colour: CRIT >= 10, HIGH >= 5,",
        "else MED; one level higher for digital arrest / sextortion / a loss >= 50,000."],
        "steps": [
        get("/map?pincode=560102", "MAP page, Bengaluru, Last 7 days: HSR Layout is in the list (B1's report A)",
            has_area="560102"),
        get("/map?pincode=560102&radius_km=5", "nearby areas with reports show too (Koramangala, BTM ...)", has_area="560034"),
        post(o, 201, "a report from 30 days ago, in Hebbal  -> 201 (stored)"),
        get("/map?pincode=560024&radius_km=1", "MAP page: Hebbal is NOT on the map (month-old reports don't count)",
            no_area="560024"),
        text("MAP page: tap 'Last 24 hours' -> only today's reports; tap an area in the list -> map zooms there."),
    ]})

    n1 = m.report(m.phone(), 1.2, "560064", f"r_nt1_{t}", "77.1.1", channel="SMS or WhatsApp",
                  scam_type="electricity-disconnection", lost=3000,
                  note="SMS said power will be cut tonight, pay the pending bill on this number")
    n2 = m.report(m.phone(), 0.6, "560064", f"r_nt2_{t}", "77.2.2", channel="Phone call",
                  scam_type="electricity-disconnection", screenshot=True,
                  note="Caller claimed to be from BESCOM and asked me to pay 1,800 immediately")
    s.append({"title": "C2. ALERTS - something unusual in an area", "intro": [
        "WHERE: reports in /docs; the alert banners show on the website's Map and Home pages.",
        "NEW_TYPE: a scam type the area hasn't had in 30 days. SPIKE: >= 5 reports in 24 h AND at least double",
        "the area's daily average of the week before. Only trusted reports count, so fakes never alert (B3, B4)."],
        "steps": [
        post(n1, 201, "1st electricity-bill scam in Yelahanka  -> 201"),
        post(n2, 201, "2nd, different person, network and words  -> 201"),
        get("/alerts?pincode=560064", "MAP page banner: \"New kind of scam reported near Yelahanka: electricity bill\"",
            alert="NEW_TYPE"),
        get("/alerts?pincode=560103", "MAP page banner (demo data): \"Scam reports near Bellandur are much higher than usual\"",
            demo_data_only=True, alert="SPIKE"),
        get("/alerts?pincode=560037", "demo data: Marathahalli is busy every day -> NO banner", demo_data_only=True,
            no_alerts=True),
    ]})

    s.append({"title": "C3. DISPUTE - \"that is our real number\" (bonus)", "intro": [
        "WHERE: website, top bar 'Dispute a report' (or the link on a Check result), or /docs POST /challenges.",
        "It never deletes reports: the number shows \"Under review\", is hidden again and can't be Known scam",
        "until reviewed. The claimant's name and email are never shown or logged."],
        "steps": [
        text(f"WEBSITE: Dispute a report -> Phone -> {real} -> name Sharma Sweets -> email owner@example.com ->",
             "         proof \"GST certificate and shop licence\" -> Submit -> \"Under review\". Or in /docs:"),
        challenge({"identifier_type": "phone", "identifier_value": "0" + real, "claimant_name": "Sharma Sweets",
                   "contact_email": "owner@example.com", "proof_note": "GST certificate and shop licence attached."},
                  201, "dispute B1's number  -> 201 {challenge_id, status: under_review}"),
        lookup("phone", real, "was Known scam; now Under review, hidden again, still 3 reports",
               not_verdict="KNOWN_SCAM", challenged=True, masked=True, count=3),
        challenge({"identifier_type": "phone", "identifier_value": real, "claimant_name": "Sharma Sweets",
                   "contact_email": "not-an-email", "proof_note": "x"}, 400, "bad email  -> 400 (website: error under email)"),
    ]})
    return s


# ----------------------------------------------------------------------------- writing the file
def describe_lookup(st: dict) -> list[str]:
    """Website wording for a lookup (+ the API fields in brackets for /docs)."""
    e = st["expect"]
    label = {"phone": "Phone", "upi": "UPI ID", "url": "Link", "sender_id": "SMS sender"}[st["type"]]
    head = f"CHECK  {label} {st['value']}"
    if not e:
        return [head, f"   -> {st['say']}", ""]
    web, api = [], []
    if "verdict" in e:
        web.append(WEB_VERDICT[e["verdict"]]); api.append(e["verdict"])
    if "not_verdict" in e:
        web.append("NOT " + WEB_VERDICT[e["not_verdict"]]); api.append("not " + e["not_verdict"])
    if e.get("challenged"):
        web.append("Under review"); api.append("challenged: true")
    if "people" in e:
        web.append("Reported by 1 person" if e["people"] == 1 else f"Reported by {e['people']} people")
        api.append(f"distinct_reporters {e['people']}")
    if "count" in e:
        api.append(f"report_count {e['count']}")
    if "masked" in e:
        web.append(f"hidden ({hidden(st['type'], st['value'])})" if e["masked"] else "number shown in full")
        api.append("masked" if e["masked"] else "display_value in full")
    return [head, f"   -> {' · '.join(web)}   [{st['say']}]", f"      (API: {', '.join(api)})", ""]


def render(sections: list[dict], now: datetime) -> str:
    """Turn the sections into the plain-text walkthrough."""
    out = [
        "COMMUNITY SCAM MAP - FULL DEMO WALKTHROUGH",
        "=" * 72,
        f"Generated {now.strftime('%Y-%m-%d %H:%M')} IST. Times are relative to then (alerts only look at the last",
        "24 hours), so run  python tools/make_demo_examples.py  again right before you use it.",
        "",
        f"WEBSITE: {LIVE}   (phone, or F12 -> phone view)",
        f"/docs:   {LIVE}/docs   POST /reports -> Try it out -> paste ONE body -> Execute",
        "Why /docs for fakes: the website gives each phone ONE anonymous id and reads your real network, so",
        "one phone can't pretend to be 8 people on 8 networks. /docs lets us send those ids, like the judges' tool.",
        "",
        "Order: Part A (website), Part B (real scam vs every fake trick), Part C (map, alerts, dispute), licence.",
        "Each body ONCE. Numbers are fresh every time: NO reset needed, and the live demo data stays (it gives",
        "the SPIKE in C2). Words: 'hidden' = shown like 98XXXXX210 until 3 different people report it.",
        "",
        "PART A - NORMAL REPORTS ON THE WEBSITE",
    ]
    for sec in sections:
        if sec["title"].startswith("B1"):
            out += ["", "", "PART B - A REAL SCAM vs EVERY FAKE-REPORT TRICK ([PRD §4]) - reports in /docs, checks on the website"]
        if sec["title"].startswith("C1"):
            out += ["", "", "PART C - MAP, ALERTS, DISPUTE"]
        out += ["", "-" * 72, sec["title"], "-" * 72] + sec["intro"] + [""]
        for st in sec["steps"]:
            if st["kind"] == "text":
                out += st["lines"] + [""]
            elif st["kind"] == "report":
                out.append(f"/docs POST /reports   {st['say']}")
                body = json.dumps(st["body"], ensure_ascii=False) if st["compact"] else json.dumps(st["body"], indent=2, ensure_ascii=False)
                out += [body, ""]
            elif st["kind"] == "challenge":
                out += [f"/docs POST /challenges   {st['say']}", json.dumps(st["body"], indent=2, ensure_ascii=False), ""]
            elif st["kind"] == "lookup":
                out += describe_lookup(st)
            else:
                out += [st["say"], f"      (API: GET {st['path']})", ""]
    out += ["", "-" * 72, "LICENCE (laptop with private.key, PowerShell, repo root)", "-" * 72,
            '$P = "server\\.venv\\Scripts\\python"',
            "& $P tools\\upload_license.py --show --live                     # VALID, long licence",
            '& $P tools\\make_license.py --licensee "Demo Bank" --minutes 5 --out licenses\\short.json',
            "& $P tools\\upload_license.py licenses\\short.json --live         # 5 minutes left",
            "   leave the website open: after 5 min it locks by itself (\"Licence expired. Contact your provider.\")",
            "   /lookup -> 403 LICENSE_EXPIRED; /health still 200; nothing is deleted",
            "& $P tools\\upload_license.py licenses\\long.json --live          # unlocks within ~20 s, same data, no restart",
            "ALWAYS finish with the long licence.", ""]
    return "\n".join(out)


def render_cheatsheet(sections: list[dict], now: datetime) -> str:
    """The short reference used during the demo: 10 examples, where to run each, what to paste,
    and what to point at. Built from the same sections the test replays, so every line is true."""
    by = {sec["title"][:2]: sec for sec in sections}
    v = by["A1"]["values"]
    one = lambda st: json.dumps(st["body"], ensure_ascii=False)
    bodies = lambda code, kind="report": [one(st) for st in by[code]["steps"] if st["kind"] == kind]
    first_lookup = lambda code: next(st["value"] for st in by[code]["steps"] if st["kind"] == "lookup")
    real = first_lookup("B1")
    out = [
        "SCAM MAP - DEMO CHEAT SHEET (10 examples, mostly fake reports)",
        "=" * 70,
        f"Made {now.strftime('%Y-%m-%d %H:%M')} IST. Re-make right before the demo:  & $P tools\\make_demo_examples.py",
        f"WEBSITE  {LIVE}   (phone, or F12 -> phone view)",
        f"/docs    {LIVE}/docs   POST /reports -> Try it out -> paste ONE line -> Execute",
        "/docs lets us act as MANY people: each body has its own reporter_id (person) and ip_prefix",
        "(network), like the judges' test tool. The website always makes you ONE person on your real network.",
        "So: send fakes in /docs, then CHECK the number on the website and point at the result.",
        "Order tip: do 1 (real scam) and then 6 (report-bombing) back to back: fakes stopped, real scams kept.",
        "",
    ]

    def ex(n, title, where, show, lines):
        out.extend(["-" * 70, f"{n}. {title}", f"   Where: {where}", f"   Show:  {show}"] + lines + [""])

    ex(1, "REAL SCAM - 3 different people, 3 ways of typing the number", "/docs, Check after each report",
       f"Check {real}: hidden after 1 and 2 people -> Known scam, shown in full after 3", bodies("B1"))
    ex(2, "FAKE: SPAMMER - same person, same number, 6 times in an hour", "/docs",
       f"/docs replies 201 201 201 429 429 429; Check {first_lookup('B2')} -> Reported by 1 person, hidden",
       bodies("B2"))
    ex(3, "FAKE: SPAMMER ON A PHONE", "website",
       "after 3 reports in an hour from one browser, the next says \"You've sent several reports in a short time\"",
       [f"   Report {v['call']} four times from the same window (rate limit: 3 an hour per person)."])
    ex(4, "FAKE: ONE WI-FI, MANY ACCOUNTS - 8 accounts, same ip_prefix", "/docs",
       f"Check {first_lookup('B3')} -> Reported by 1 person (not 8), hidden; Map: no alert for Whitefield",
       bodies("B3"))
    ex(5, "FAKE: WI-FI FARM ON A PHONE", "website",
       f"Check {v['farm']} -> Reported by 1 person (not 3)",
       [f"   3 times: open a NEW private/incognito window on the SAME Wi-Fi, report {v['farm']}."])
    ex(6, "FAKE: REPORT-BOMBING - 8 friends, 8 networks, copy-pasted notes, one hour", "/docs",
       f"Check {first_lookup('B4')} -> NOT Known scam, still hidden; Map: no alert for Rajajinagar",
       bodies("B4"))
    ex(7, "FAKE: REPORTING A VERIFIED BUSINESS (Fresh Bakes)", "/docs",
       "Check +91 80 4100 2233 -> still Verified business", bodies("B5"))
    ex(8, "FAKE: JUNK - 12345, test, unknown pincode, date in the future", "/docs (and type 12345 on the website)",
       "400 for the first four, nothing saved; the 5th (unknown scam type) is kept as \"other\" -> 201",
       bodies("B6"))
    ex(9, "NORMAL REPORT - in Hindi, and with icons only", "website, Report page",
       "saved (green Thanks screen); Check -> Reported by 1 person; Map: your area's count +1",
       [f"   Hindi: tap हिंदी, फ़ोन कॉल -> अभी-अभी -> {v['hindi']} -> area -> submit",
        f"   Icons: copy {v['icon']}, then phone tile -> flash -> Paste -> location -> green button"])
    dispute = next(st for st in by["C3"]["steps"] if st["kind"] == "challenge")
    ex(10, "DISPUTE - \"that is our real number\" (number from example 1)", "website 'Dispute a report' (or /docs POST /challenges)",
       f"Check {real} -> Under review, hidden again, no longer Known scam",
       [f"   Website: Dispute a report -> Phone -> {real} -> Sharma Sweets -> owner@example.com -> submit",
        "   /docs POST /challenges: " + one(dispute)])
    out += ["-" * 70, "FINALE: the full-size attacks (22 accounts, 40 friends, spammer, junk) + real campaigns:",
            "   & $P tools\\scenarios.py --base http://localhost:8000 --seed 7     -> 47/47 PASS table",
            "LICENCE: make 5-min licence -> upload --live -> site locks by itself -> upload long.json --live", ""]
    return "\n".join(out)


def main() -> int:
    now = datetime.now(IST).replace(microsecond=0)
    OUT.write_text(render_cheatsheet(build(now), now), encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)} (times relative to {now.strftime('%H:%M')} IST)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
