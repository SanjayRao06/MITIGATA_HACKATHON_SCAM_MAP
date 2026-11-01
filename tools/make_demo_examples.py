"""Writes tools/samples/demo_examples.txt: copy-paste requests for a live walkthrough in /docs.

Run it right before a demo or screen recording:
    python tools/make_demo_examples.py
Every time is relative to NOW (alerts only look at the last 24 hours, so old dates would stop
working) and every number/UPI ID is fresh (so running the walkthrough twice, or on the live server
next to the demo data, never mixes counts).

It covers every case in the brief: a real scam reported by 3 people in different formats, the
four fake-report tricks of [PRD §4] (spamming, 22 fake accounts on one Wi-Fi, 40 friends
report-bombing, junk), a verified business, the map, both alert types, a dispute and the licence.
server/tests/test_demo_examples.py replays every example against the server and checks that each
"expect" line is really what comes back, on an empty database and on one full of demo data.
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


def get(path: str, say: str, demo_data_only: bool = False, **expect) -> dict:
    """expect keys: status, has_area, no_area, alert (type expected), no_alerts (True)."""
    return {"kind": "get", "path": path, "say": say, "expect": expect, "demo_only": demo_data_only}


def challenge(body: dict, status: int, say: str) -> dict:
    return {"kind": "challenge", "body": body, "status": status, "say": say}


# ----------------------------------------------------------------------------- the walkthrough
def build(now: datetime | None = None, seed: int | None = None) -> list[dict]:
    """In: the time to build around (default: now). Out: a list of sections, each with steps."""
    m = Maker(now or datetime.now(IST), seed)
    t = m.tag
    s = []

    # 1) A real scam: 3 unrelated people, 3 formats, own words, different areas and networks.
    real = m.phone()
    a = m.report(f"+91 {real[:5]} {real[5:]}", 9, "560102", f"r_ravi_{t}", "103.21.58", screenshot=True,
                 note="Video call from a man in police uniform saying a parcel with drugs was in my name")
    b = m.report("0" + real, 6, "560034", f"r_priya_{t}", "49.36.12", lost=15000,
                 note="They kept my father on a video call for 3 hours and asked him to transfer money")
    c = m.report(f"{real[:5]}-{real[5:]}", 3, "560038", f"r_amit_{t}", "117.99.4",
                 note="Mujhe bola arrest warrant hai, Skype pe aao abhi")
    s.append({"title": "1. A REAL SCAM: 3 different people, 3 ways of typing the number", "intro": [
        "Different people, different networks and areas, each in their own words: this is what a real",
        "scam looks like, so it must become KNOWN_SCAM. One person alone must stay hidden ([PRD §5])."],
        "steps": [
        post(a, 201, "Report A (Ravi, HSR Layout)  -> 201, merged: false"),
        lookup("phone", real, "after A", verdict="SUSPICIOUS", people=1, masked=True),
        post(b, 201, "Report B (Priya, Koramangala, number typed with a 0)  -> 201, merged: true"),
        lookup("phone", real, "after A+B", verdict="SUSPICIOUS", people=2, masked=True),
        post(c, 201, "Report C (Amit, Indiranagar, number typed with a dash)  -> 201, merged: true"),
        lookup("phone", real, "after A+B+C: 3 people, now shown in full", verdict="KNOWN_SCAM", people=3, masked=False),
        lookup("phone", "91" + real, "same number typed another way -> same answer", verdict="KNOWN_SCAM", people=3),
    ]})

    # 2) Spamming: one person, same number, 6 times inside an hour ([PRD §4]).
    spam = m.phone()
    spam_bodies = [m.report(spam, 1.0 - i * 0.12, "560010", f"r_angry_{t}", "1.2.3", channel="SMS or WhatsApp",
                            scam_type="lottery-prize", note="scam") for i in range(6)]
    s.append({"title": "2. FAKE: SPAMMING - one person reports the same number 6 times in an hour", "intro": [
        "Same reporter_id every time. Rule L1: one person counts once. Rate limit: more than 3 reports",
        "an hour from one person -> 429 (using each report's own time)."],
        "steps": [post(spam_bodies[0], 201, "1st  -> 201")]
        + [post(spam_bodies[i], 201 if i < 3 else 429, f"{i + 1}{'nd' if i == 1 else 'rd' if i == 2 else 'th'}"
                f"  -> {'201' if i < 3 else '429 RATE_LIMITED'}", compact=True) for i in range(1, 6)]
        + [lookup("phone", spam, "only 3 stored, and they are ONE person", verdict="SUSPICIOUS", people=1, count=3, masked=True)],
    })

    # 3) Fake accounts: many reporter_ids on one Wi-Fi (same ip_prefix) ([PRD §4]: 22 accounts).
    farm = m.phone()
    farm_notes = ["fraud call", "this number is fake", "cheater", "scam call", "do not pick up", "fake caller",
                  "beware", "they lie"]
    farm_bodies = [m.report(farm, 1.5 - i * 0.18, "560066", f"r_farm{i + 1}_{t}", "49.200.10", scam_type="otp-call",
                            note=farm_notes[i]) for i in range(8)]
    s.append({"title": "3. FAKE: ONE WI-FI, MANY ACCOUNTS - 8 accounts, same ip_prefix, 90 minutes", "intro": [
        "Different reporter_id each time but the SAME ip_prefix (one house / one Wi-Fi). Rule L2: same",
        "network + same number within 24 h = ONE source. (The judges' version uses 22 accounts; the",
        "scenario runner tools/scenarios.py sends exactly 22.)"],
        "steps": [post(farm_bodies[0], 201, "account 1  -> 201")]
        + [post(b2, 201, f"account {i + 2}  -> 201", compact=True) for i, b2 in enumerate(farm_bodies[1:])]
        + [lookup("phone", farm, "8 accounts = 1 source", verdict="SUSPICIOUS", people=1, masked=True),
           get("/alerts?pincode=560066", "fakes set off no alert in Whitefield", no_alerts=True)],
    })

    # 4) Report-bombing: friends on different networks, copy-paste notes, one area, one burst ([PRD §4]).
    bakery = m.phone()
    paste = "This bakery is cheating customers, fake number, do not call or pay them!!"
    bomb_notes = [paste, paste, paste, "", paste, "scam", paste, ""]
    bomb_bodies = [m.report(bakery, 1.0 - i * 0.1, "560010", f"r_friend{i + 1}_{t}", f"{60 + i}.{10 + i}.{i + 3}",
                            scam_type="fake-customer-care", note=bomb_notes[i]) for i in range(8)]
    s.append({"title": "4. FAKE: REPORT-BOMBING - 8 friends of a rival report a real bakery", "intro": [
        "Each friend has their own account and home network, so rules L1/L2 don't catch them. What does:",
        "L3 copy-pasted notes merge into one source, and L4 coordination (brand-new accounts, all within",
        "an hour, one area, copy-paste/empty notes, nobody lost money) blocks KNOWN_SCAM. (Judges: 40 friends.)"],
        "steps": [post(bomb_bodies[0], 201, "friend 1  -> 201")]
        + [post(b2, 201, f"friend {i + 2}  -> 201", compact=True) for i, b2 in enumerate(bomb_bodies[1:])]
        + [lookup("phone", bakery, "8 reports, but NOT Known scam, and still hidden", not_verdict="KNOWN_SCAM", masked=True),
           get("/alerts?pincode=560010", "fakes set off no alert in Rajajinagar (+2 bonus)", no_alerts=True)],
    })

    # 5) Bombing a VERIFIED business: verified always wins (+3 bonus).
    vb = [m.report("+91 80 4100 2233", 0.9 - i * 0.2, "560038", f"r_rival{i + 1}_{t}", f"88.{i + 1}.7",
                   scam_type="fake-customer-care", note=paste) for i in range(3)]
    s.append({"title": "5. FAKE: REPORTING A VERIFIED BUSINESS (Fresh Bakes, from the brief's verified list)", "intro": [
        "The verified list wins over any number of reports. Reporting a verified business also lowers",
        "those reporters' trust (L5) for their other reports."],
        "steps": [post(vb[0], 201, "rival 1  -> 201")]
        + [post(b2, 201, f"rival {i + 2}  -> 201", compact=True) for i, b2 in enumerate(vb[1:])]
        + [lookup("phone", "+91 80 4100 2233", "still Verified business", verdict="VERIFIED_BUSINESS")],
    })

    # 6) Junk and bad input ([PRD §4] 'Junk', [PRD §A.2]).
    j = dict(a, report_id=f"demo_{t}_j1", reporter_id=f"r_junk_{t}", identifier_value="12345")
    j2 = dict(a, report_id=f"demo_{t}_j2", reporter_id=f"r_junk_{t}", identifier_value="test")
    j3 = dict(a, report_id=f"demo_{t}_j3", reporter_id=f"r_junk_{t}", identifier_value=m.phone(), pincode="999999")
    j4 = dict(a, report_id=f"demo_{t}_j4", reporter_id=f"r_junk_{t}", identifier_value=m.phone(),
              occurred_at=m.ts(-24 * 30), reported_at=m.ts(0))
    odd = m.phone()
    j5 = m.report(odd, 2, "560102", f"r_odd_{t}", "14.15.16", scam_type="alien-attack",
                  note="Some new kind of trick I have not seen before")
    s.append({"title": "6. FAKE: JUNK AND BAD INPUT - rejected straight away", "intro": [
        "Junk numbers are refused with 400 and never stored. An unknown scam type is NOT rejected: it is",
        "kept as \"other\" (the brief says so)."],
        "steps": [
        post(j, 400, "number \"12345\"  -> 400", compact=True),
        post(j2, 400, "number \"test\"  -> 400", compact=True),
        post(j3, 400, "unknown pincode 999999  -> 400", compact=True),
        post(j4, 400, "occurred_at a month in the FUTURE  -> 400", compact=True),
        post(j5, 201, "unknown scam_type \"alien-attack\"  -> 201 (saved as \"other\")", compact=True),
        lookup("phone", "12345", "lookup of junk  -> 400 (not a valid number)"),
    ]})

    # 7) Every identifier type + the verified list + never reported.
    upi = f"Refund.Help{m.rng.randint(100, 999)}@OKAXIS"
    url_host = f"sbi-kyc{m.rng.randint(10, 99)}.in"
    u = m.report(upi, 5, "560076", f"r_neha_{t}", "59.88.1", id_type="upi", channel="UPI request",
                 scam_type="upi-refund-qr", screenshot=True, lost=4999,
                 note="Said scan this QR to receive refund, money went out instead")
    w = m.report(f"http://www.{url_host}/pay?utm=sms", 4, "560011", f"r_kiran_{t}", "106.51.7", id_type="url",
                 channel="Fake website", scam_type="fake-kyc-link", screenshot=True,
                 note="SMS said KYC expired, link looked exactly like SBI")
    s.append({"title": "7. UPI IDs, LINKS, SMS SENDERS, VERIFIED NUMBERS, NEVER REPORTED", "intro": [
        "Every format is stored in one standard form ([PRD §A.0] rule 3)."],
        "steps": [
        post(u, 201, f"UPI ID typed in capitals  -> 201"),
        lookup("upi", upi.lower(), "looked up in small letters -> same UPI ID, hidden like r***@okaxis",
               verdict="SUSPICIOUS", masked=True),
        post(w, 201, "link with http, www and ?utm  -> 201"),
        lookup("url", f"{url_host}/pay", "looked up without https/www/?utm -> same link, hidden like sbi***.in/...",
               verdict="SUSPICIOUS", masked=True),
        lookup("sender_id", "VM-HDFCBK", "SMS sender with the phone's prefix -> HDFCBK", verdict="VERIFIED_BUSINESS"),
        lookup("phone", "1930", "cybercrime helpline", verdict="VERIFIED_BUSINESS"),
        lookup("phone", "1800 1600", "HDFC Bank toll-free", verdict="VERIFIED_BUSINESS"),
        lookup("upi", "freshbakes@okaxis", "Fresh Bakes' UPI", verdict="VERIFIED_BUSINESS"),
        lookup("phone", m.phone(), "a valid number nobody reported -> 200 NO_REPORTS (not 404)", verdict="NO_REPORTS"),
    ]})

    # 8) Map: last 7 days only, area points only.
    old = m.phone()
    o = m.report(old, 24 * 30, "560024", f"r_old_{t}", "21.22.23", scam_type="otp-call",
                 note="Got this call last month asking for my card OTP")
    s.append({"title": "8. MAP - only the last 7 days, only area points", "intro": [
        "Clusters use the AREA's map point from the brief, never a person's location. Severity: CRIT >= 10,",
        "HIGH >= 5, else MED; one level higher for digital arrest / sextortion / a loss >= 50,000."],
        "steps": [
        get("/map?pincode=560102", "HSR Layout cluster (default 7 days, 2 km)", has_area="560102"),
        get("/map?pincode=560102&radius_km=5", "also nearby areas with reports (Koramangala, BTM ...)", has_area="560034"),
        post(o, 201, "a report from 30 days ago, in Hebbal  -> 201 (stored)"),
        get("/map?pincode=560024&radius_km=1", "Hebbal is NOT on the map: month-old reports don't count", no_area="560024"),
        get("/map?pincode=999999", "unknown area  -> 400", status=400),
    ]})

    # 9) Alerts: NEW_TYPE now; SPIKE from the demo data.
    n1 = m.report(m.phone(), 1.2, "560064", f"r_nt1_{t}", "77.1.1", channel="SMS or WhatsApp",
                  scam_type="electricity-disconnection", lost=3000,
                  note="SMS said power will be cut tonight, pay the pending bill on this number")
    n2 = m.report(m.phone(), 0.6, "560064", f"r_nt2_{t}", "77.2.2", channel="Phone call",
                  scam_type="electricity-disconnection", screenshot=True,
                  note="Caller claimed to be from BESCOM and asked me to pay 1,800 immediately")
    s.append({"title": "9. ALERTS - something unusual in an area", "intro": [
        "NEW_TYPE: a scam type the area hasn't had in 30 days. SPIKE: >= 5 reports in 24 h AND at least",
        "double the area's daily average of the week before. Only trusted reports count, so fakes never",
        "set one off (sections 3 and 4)."],
        "steps": [
        post(n1, 201, "1st electricity-bill scam in Yelahanka  -> 201"),
        post(n2, 201, "2nd, different person, network and words  -> 201"),
        get("/alerts?pincode=560064", "NEW_TYPE electricity-disconnection in Yelahanka", alert="NEW_TYPE"),
        get("/alerts?pincode=560103", "with the demo data loaded: SPIKE in Bellandur (10 today vs ~2 a day)",
            demo_data_only=True, alert="SPIKE"),
        get("/alerts?pincode=560037", "with the demo data loaded: Marathahalli is busy every day -> no alert",
            demo_data_only=True, no_alerts=True),
    ]})

    # 10) Dispute ([PRD §A.7], bonus).
    s.append({"title": "10. DISPUTE - \"that is our real number\" (bonus)", "intro": [
        "Anyone can file a dispute. It never deletes reports; the number is shown as \"under review\",",
        "hidden again, and can't be KNOWN_SCAM until reviewed. The claimant's details are never shown or logged."],
        "steps": [
        challenge({"identifier_type": "phone", "identifier_value": "0" + real, "claimant_name": "Sharma Sweets",
                   "contact_email": "owner@example.com", "proof_note": "GST certificate and shop licence attached."},
                  201, "dispute the number from section 1  -> 201 {challenge_id, status: under_review}"),
        lookup("phone", real, "challenged: true, no longer KNOWN_SCAM, hidden again, reports still counted",
               not_verdict="KNOWN_SCAM", challenged=True, masked=True, count=3),
        challenge({"identifier_type": "phone", "identifier_value": real, "claimant_name": "Sharma Sweets",
                   "contact_email": "not-an-email", "proof_note": "x"}, 400, "bad email  -> 400"),
    ]})
    return s


# ----------------------------------------------------------------------------- writing the file
def render(sections: list[dict], now: datetime) -> str:
    """Turn the sections into the plain-text walkthrough."""
    out = [
        "COMMUNITY SCAM MAP - DEMO WALKTHROUGH (copy-paste into /docs)",
        "=" * 64,
        f"Generated {now.strftime('%Y-%m-%d %H:%M')} IST. Times are relative to then: alerts only look at the",
        "last 24 hours, so run  python tools/make_demo_examples.py  again right before you use it.",
        "",
        f"Where:  {LIVE}/docs   (or http://localhost:8000/docs)",
        "How:    POST /reports  -> Try it out -> paste ONE body -> Execute -> look at \"Server response\"",
        "        GET /lookup    -> Try it out -> fill \"type\" and \"value\" -> Execute",
        "        GET /map, GET /alerts, POST /challenges the same way",
        "Order:  do the sections in order, each body ONCE (resending the same report_id counts once).",
        "Server: the numbers are fresh every time, so you do NOT need to reset. On the live server the",
        "        demo data stays (that's what makes the SPIKE in section 9 work). Never reset live",
        "        right before judging unless you reload the demo data:",
        "        python tools/scenarios.py --base <url> --seed 7 --allow-remote-reset",
        "Words:  verdicts are KNOWN_SCAM / SUSPICIOUS / NO_REPORTS / VERIFIED_BUSINESS; \"hidden\" means",
        "        display_value is masked like 98XXXXX210 (fewer than 3 trusted people).",
        "",
    ]
    for sec in sections:
        out += ["", "-" * 64, sec["title"], "-" * 64] + sec["intro"] + [""]
        for st in sec["steps"]:
            if st["kind"] == "report":
                out.append(f"POST /reports   {st['say']}")
                body = json.dumps(st["body"], ensure_ascii=False) if st["compact"] else json.dumps(st["body"], indent=2, ensure_ascii=False)
                out += [body, ""]
            elif st["kind"] == "challenge":
                out += [f"POST /challenges   {st['say']}", json.dumps(st["body"], indent=2, ensure_ascii=False), ""]
            elif st["kind"] == "lookup":
                e = st["expect"]
                want = []
                if "verdict" in e:
                    want.append(e["verdict"])
                if "not_verdict" in e:
                    want.append("NOT " + e["not_verdict"])
                if "people" in e:
                    want.append(f"distinct_reporters {e['people']}")
                if "count" in e:
                    want.append(f"report_count {e['count']}")
                if "challenged" in e:
                    want.append("challenged: true")
                if "masked" in e:
                    want.append("hidden" if e["masked"] else "shown in full")
                arrow = ", ".join(want) if want else "400"
                out += [f"GET /lookup   type = {st['type']}   value = {st['value']}",
                        f"   -> {arrow}   ({st['say']})", ""]
            else:
                out += [f"GET {st['path']}", f"   -> {st['say']}", ""]
    out += ["", "-" * 64, "11. LICENCE (on the laptop with private.key, PowerShell, repo root)", "-" * 64,
            '$P = "server\\.venv\\Scripts\\python"',
            "& $P tools\\upload_license.py --show --live                     # VALID, long licence",
            '& $P tools\\make_license.py --licensee "Demo Bank" --minutes 5 --out licenses\\short.json',
            "& $P tools\\upload_license.py licenses\\short.json --live         # 5 minutes left",
            "   wait 5 min -> the website locks by itself; /lookup -> 403 LICENSE_EXPIRED; /health still 200",
            "& $P tools\\upload_license.py licenses\\long.json --live          # unlocked, same data, no restart",
            "ALWAYS finish with the long licence.", ""]
    return "\n".join(out)


def main() -> int:
    now = datetime.now(IST).replace(microsecond=0)
    OUT.write_text(render(build(now), now), encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)} (times relative to {now.strftime('%H:%M')} IST)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
