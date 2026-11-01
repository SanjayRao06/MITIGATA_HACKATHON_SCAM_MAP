"""Scenario runner: fires realistic fake-attack and real-scam reports at the server and grades it.

This is our own version of the judges' test tool. It resets the server, sends hundreds of
reports with timestamps relative to NOW,
then asks /lookup, /map and /alerts what they think and prints a PASS/FAIL table.

Every number, UPI ID, reporter id and IP prefix is generated at random on each run, so nothing
in the server can be "tuned" to these exact values (no hardcoded test values). Only the public
verified list and the area list from the brief are used as fixed values.

Usage (from the repo root):
    python tools/scenarios.py --base http://localhost:8000
    python tools/scenarios.py --base http://localhost:8000 --latency 200
    python tools/scenarios.py --seed 7      # same numbers every run: handy for demos
After the table it prints "Try these on the website": the numbers/IDs each scenario used and the
answer the website should show for each, so you can check the same cases by hand.
Exit code: 0 if every check passed, 1 if any failed.
"""

import argparse
import http.client
import json
import random
import statistics
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, urlparse

IST = timezone(timedelta(hours=5, minutes=30))
AREAS_FILE = Path(__file__).resolve().parents[1] / "server" / "app" / "data" / "areas.json"

# Each alert/map scenario gets its OWN area, so one scenario's reports can't change another's result.
PIN_SPAMMER = "560010"      # Rajajinagar
PIN_WIFI = "560066"         # Whitefield     - 22 fake accounts (must not fire alerts)
PIN_BAKERY = "560038"       # Indiranagar    - 40 friends bomb a bakery (must not fire alerts)
PIN_OLD = "560024"          # Hebbal         - only month-old reports (must not be on the map)
PIN_SPIKE = "560103"        # Bellandur      - sudden jump today (must fire SPIKE)
PIN_STEADY = "560037"       # Marathahalli   - same rate every day (must NOT fire SPIKE)
PIN_NEWTYPE = "560100"      # Electronic City - first job-offer reports (must fire NEW_TYPE)
RESERVED = {PIN_SPAMMER, PIN_WIFI, PIN_BAKERY, PIN_OLD, PIN_SPIKE, PIN_STEADY, PIN_NEWTYPE}
# Real campaigns spread over these Bengaluru areas (none of the reserved ones).
CAMPAIGN_PINS = ["560102", "560034", "560076", "560011", "560078", "560003", "560070", "560064"]

# Words the app must never use about an identifier.
BANNED_WORDS = ("scammer", "fraudster", "is a fraud", "criminal", "cheat")
# Fields that must never appear in lookup evidence.
FORBIDDEN_EVIDENCE_KEYS = {"reporter_id", "reporter_hash", "ip_prefix", "ip_hash", "note"}
LOOKUP_BUDGET_MS = 500  # answers under half a second


# ----------------------------------------------------------------------------- talking to a server
class HttpServer:
    """Sends real HTTP requests to a running server (local uvicorn or the deployed URL)."""

    def __init__(self, base: str):
        # On Windows, "localhost" tries IPv6 (::1) first and waits ~2 s before falling back to
        # 127.0.0.1, where uvicorn listens. That would add 2 s to every request and wrongly fail
        # the latency check, so we talk to 127.0.0.1 directly.
        self.base = base.rstrip("/").replace("://localhost", "://127.0.0.1", 1)
        self.url = urlparse(self.base)
        self.conn = None              # ONE kept-open connection, like a test tool's session
        self.last_server_ms = None    # the server's own time for the last request (Server-Timing header)

    def _connect(self):
        """Open the kept-open connection (https for the live server, http on the laptop)."""
        cls = http.client.HTTPSConnection if self.url.scheme == "https" else http.client.HTTPConnection
        self.conn = cls(self.url.hostname, self.url.port, timeout=60)

    def request(self, method: str, path: str, body: dict | None = None):
        """In: method, path (with query string), optional JSON body. Out: (status, parsed JSON or None).

        Reuses one connection: opening a new encrypted connection per request (what urllib does)
        adds a full handshake to every call and would make the latency check measure that, not us.
        """
        data = json.dumps(body).encode() if body is not None else None
        for attempt in (1, 2):                      # one retry if the server closed the idle connection
            if self.conn is None:
                self._connect()
            try:
                self.conn.request(method, self.url.path + path, body=data,
                                  headers={"content-type": "application/json"})
                resp = self.conn.getresponse()
                status, raw = resp.status, resp.read()
                break
            except (http.client.HTTPException, OSError):
                self.conn.close()
                self.conn = None
                if attempt == 2:
                    raise
        timing = resp.getheader("Server-Timing") or ""
        self.last_server_ms = float(timing.split("dur=", 1)[1].split(";")[0].split(",")[0]) if "dur=" in timing else None
        try:
            return status, json.loads(raw or b"null")
        except ValueError:
            return status, None


# ----------------------------------------------------------------------------- one run's state
class Run:
    """Everything one scenario run needs: the server, random generators, and the results table."""

    def __init__(self, server, seed: int | None = None):
        self.server = server
        self.rng = random.Random(seed)
        self.tag = "%04x" % self.rng.randrange(16 ** 4)   # makes this run's ids unique
        self.counter = 0
        self.results = []          # rows: (scenario, check, expected, got, passed)
        self.lookup_ms = []        # every lookup's round-trip time, for the latency check
        self.server_ms = []        # the server's own time per lookup (Server-Timing header), when it sends one
        self.areas = {a["pincode"]: a for a in json.loads(AREAS_FILE.read_text(encoding="utf-8"))}
        self.used_prefixes = set()
        self.showcase = []         # rows: (scenario, type, value, what the website should show)

    def remember(self, scenario: str, identifier_type: str, value: str, expect: str) -> None:
        """Note an identifier worth checking by hand on the website (printed after the table)."""
        self.showcase.append((scenario, identifier_type, value, expect))

    # ---- small generators -------------------------------------------------------------------
    def next_id(self, prefix: str) -> str:
        """A unique id like 'r_3fa2_0007' (prefix + run tag + counter)."""
        self.counter += 1
        return f"{prefix}_{self.tag}_{self.counter:04d}"

    def person(self) -> str:
        """A brand-new reporter_id (a new fake 'person')."""
        return self.next_id("r")

    def network(self) -> str:
        """A brand-new ip_prefix like '103.47.12' that no one else in this run uses."""
        while True:
            p = f"{self.rng.randint(11, 223)}.{self.rng.randint(0, 255)}.{self.rng.randint(0, 255)}"
            if p not in self.used_prefixes:
                self.used_prefixes.add(p)
                return p

    def phone(self) -> str:
        """A random, valid-looking 10-digit Indian mobile number, normalized: '+91XXXXXXXXXX'."""
        while True:
            body = str(self.rng.randint(6, 9)) + "".join(str(self.rng.randint(0, 9)) for _ in range(9))
            if len(set(body)) >= 4:                     # avoid junk-looking numbers the server rejects
                return "+91" + body

    def upi(self) -> str:
        """A random UPI ID, normalized (lower case), e.g. 'refundhelp482@okicici'."""
        name = self.rng.choice(["refund", "kyc", "prize", "support", "help", "cashback"])
        bank = self.rng.choice(["okaxis", "okicici", "oksbi", "ybl", "paytm"])
        return f"{name}{self.rng.choice(['', '.', '_'])}desk{self.rng.randint(100, 9999)}@{bank}"

    @staticmethod
    def phone_formats(normalized: str) -> list[str]:
        """The 4 ways people type one number; all must give the same answer."""
        d = normalized[3:]
        return [f"+91 {d[:5]} {d[5:]}", "0" + d, f"{d[:5]}-{d[5:]}", "91" + d]

    @staticmethod
    def ts(hours_ago: float) -> str:
        """A time `hours_ago` hours before now in the API's format, e.g. 2026-10-31T14:00:00+05:30."""
        return (datetime.now(IST) - timedelta(hours=hours_ago)).isoformat(timespec="seconds")

    # ---- notes: real people write differently; fakes copy-paste ------------------------------
    REAL_OPENERS = [
        "Got a call around {h} pm", "Yesterday evening someone called me", "My father received a call",
        "Mujhe aaj subah call aaya", "A lady called my wife", "I got a WhatsApp video call at {h}",
        "Received an SMS late night", "Kal raat ek message aaya",
    ]
    REAL_DETAILS = {
        "digital-arrest": ["man in police uniform said my Aadhaar was used for drug parcel",
                           "they said CBI case is filed and I cannot leave the house",
                           "bola arrest warrant nikla hai, Skype pe aao abhi",
                           "kept me on video for {n} hours and asked me not to tell family"],
        "upi-refund-qr": ["said scan the QR to receive refund of {n} rupees",
                          "asked me to enter UPI PIN to get cashback, money went out",
                          "refund ke naam pe QR bheja, paise kat gaye"],
        "otp-call": ["asked for the OTP to stop my card being blocked",
                     "said bank KYC pending, share the 6 digit code"],
        "fake-kyc-link": ["link looked exactly like the bank site, asked for card number",
                          "said account will freeze tonight, update KYC on this link"],
        "job-offer": ["offered work from home liking videos, then asked deposit of {n}",
                      "telegram task job, first paid 200 then wanted {n} rupees",
                      "part time job ka offer, registration fee maanga"],
        "lottery-prize": ["said I won a car in lucky draw, pay GST of {n} first"],
    }
    REAL_ENDINGS = [
        "I disconnected and blocked the number.", "Lost {n} rupees before I realised.",
        "Reported on 1930 also.", "My neighbour got the same call last week.",
        "Did not share anything, just warning others.", "Bank said they never call like this.",
        "Please be careful, very convincing.", "",
    ]

    def real_note(self, scam_type: str) -> str:
        """A personal, varied note built from random pieces (so no two real notes are copies)."""
        pick = self.rng.choice
        details = self.REAL_DETAILS.get(scam_type, self.REAL_DETAILS["otp-call"])
        text = f"{pick(self.REAL_OPENERS)}, {pick(details)}. {pick(self.REAL_ENDINGS)}"
        return text.format(h=self.rng.randint(1, 11), n=self.rng.choice([2, 3, 5000, 12000, 49999]))

    # ---- talking to the server ---------------------------------------------------------------
    def report(self, identifier_type: str, identifier_value: str, hours_ago: float, pincode: str,
               reporter_id: str, ip_prefix: str, **extra) -> dict:
        """Build one report body exactly in the API's shape."""
        area = self.areas[pincode]
        body = {
            "report_id": self.next_id("sc"),
            "occurred_at": self.ts(hours_ago),
            "reported_at": self.ts(max(0.0, hours_ago - self.rng.uniform(0.05, 0.5))),
            "reporter_id": reporter_id, "ip_prefix": ip_prefix,
            "channel": "Phone call", "scam_type": "digital-arrest",
            "identifier_type": identifier_type, "identifier_value": identifier_value,
            "pincode": pincode, "locality": area["locality"], "city": area["city"],
            "note": "", "has_screenshot": False, "amount_lost_inr": 0,
        }
        body.update(extra)
        return body

    def send(self, body: dict) -> int:
        """POST one report; return the status code (201 stored, 400 junk, 429 rate-limited)."""
        status, _ = self.server.request("POST", "/reports", body)
        return status

    def lookup(self, identifier_type: str, value: str):
        """GET /lookup with the value URL-encoded (as the test tool does). Records the time taken."""
        start = time.perf_counter()
        status, data = self.server.request("GET", f"/lookup?type={identifier_type}&value={quote(value, safe='')}")
        self.lookup_ms.append((time.perf_counter() - start) * 1000)
        if getattr(self.server, "last_server_ms", None) is not None:
            self.server_ms.append(self.server.last_server_ms)
        return status, data or {}

    def get(self, path: str):
        """GET any other endpoint (/map, /alerts). Out: (status, JSON dict)."""
        status, data = self.server.request("GET", path)
        return status, data if isinstance(data, dict) else {}

    def check(self, scenario: str, what: str, expected: str, got, passed: bool) -> None:
        """Add one row to the results table."""
        self.results.append((scenario, what, expected, str(got), bool(passed)))

    def endpoint_check(self, scenario: str, what: str, expected: str, status: int, ok_fn) -> None:
        """Check a /map or /alerts reply; a 404 means the endpoint isn't built yet."""
        if status != 200:
            note = " (not built yet)" if status == 404 else ""
            self.check(scenario, what, expected, f"HTTP {status}{note}", False)
        else:
            got, passed = ok_fn()
            self.check(scenario, what, expected, got, passed)


# ----------------------------------------------------------------------------- helpers for checks
def alert_types(data: dict, kind: str) -> list[dict]:
    """All alerts of one type ('SPIKE' / 'NEW_TYPE') from an /alerts reply."""
    return [a for a in data.get("alerts", []) if a.get("type") == kind]


def masked(value) -> bool:
    """True if a display_value is hidden (contains X or *), like 98XXXXX210 or r***@okaxis."""
    return isinstance(value, str) and ("X" in value or "*" in value)


# ----------------------------------------------------------------------------- the scenarios
def scenario_junk(run: Run) -> None:
    """Junk numbers, bad areas and impossible times must be rejected with 400."""
    name = "junk"
    person, net = run.person(), run.network()
    cases = [
        ("phone 12345", run.report("phone", "12345", 1, "560102", person, net)),
        ("phone 'test'", run.report("phone", "test", 1, "560102", person, net)),
        ("phone 9999999999", run.report("phone", "9999999999", 1, "560102", person, net)),
        ("url 'notaurl'", run.report("url", "notaurl", 1, "560102", person, net)),
        ("upi 'ravi'", run.report("upi", "ravi", 1, "560102", person, net)),
        ("unknown pincode 999999", dict(run.report("phone", run.phone(), 1, "560102", person, net),
                                        pincode="999999")),
        ("occurred_at 2 days in future", run.report("phone", run.phone(), -48, "560102", person, net)),
    ]
    for label, body in cases:
        status = run.send(body)
        run.check(name, f"POST {label}", "400", status, status == 400)
    status, _ = run.lookup("phone", "12345")
    run.check(name, "lookup phone 12345", "400", status, status == 400)


def scenario_spammer(run: Run) -> None:
    """One person reports the same number 6 times in under an hour."""
    name = "spammer x6"
    number, person, net = run.phone(), run.person(), run.network()
    statuses = [run.send(run.report("phone", number, 0.9 - i * 0.15, PIN_SPAMMER, person, net,
                                    scam_type="otp-call", note="scam call, fraud"))
                for i in range(6)]
    run.remember(name, "phone", number, "Suspicious, 1 person, hidden (4th-6th reports got 429)")
    status, data = run.lookup("phone", number)
    run.check(name, "verdict", "not KNOWN_SCAM", data.get("verdict"), data.get("verdict") != "KNOWN_SCAM")
    run.check(name, "distinct_reporters", "1", data.get("distinct_reporters"), data.get("distinct_reporters") == 1)
    run.check(name, "display_value masked", "masked", data.get("display_value"), masked(data.get("display_value")))
    run.check(name, "rate limit after 3 in 60 min", "429 seen", statuses, 429 in statuses)


def scenario_wifi_farm(run: Run) -> None:
    """22 fake accounts on one Wi-Fi (same ip_prefix) report one number in ~90 min."""
    name = "wifi-farm 22 ids"
    number, net = run.phone(), run.network()
    for i in range(22):
        run.send(run.report("phone", number, 1.5 - i * 0.06, PIN_WIFI, run.person(), net,
                            scam_type="investment-group",
                            note=run.rng.choice(["", "scam", "fraud number", "fake investment group"])))
    run.remember(name, "phone", number, "Suspicious, hidden: 22 accounts on one Wi-Fi count as 1")
    _, data = run.lookup("phone", number)
    run.check(name, "verdict", "not KNOWN_SCAM", data.get("verdict"), data.get("verdict") != "KNOWN_SCAM")
    run.check(name, "distinct_reporters", "<= 1", data.get("distinct_reporters"),
              (data.get("distinct_reporters") or 0) <= 1)
    run.check(name, "display_value masked", "masked", data.get("display_value"), masked(data.get("display_value")))
    status, alerts = run.get(f"/alerts?pincode={PIN_WIFI}")
    run.endpoint_check(name, "fakes fire no alert", "alerts == []", status,
                       lambda: (alerts.get("alerts"), alerts.get("alerts") == []))


def scenario_bakery(run: Run) -> None:
    """40 friends of a rival report a real bakery.

    Signature: all brand-new accounts, a burst inside 2 hours, one area, copy-paste or
    empty notes, nothing lost, no screenshots. They are on different home networks, so the
    same-Wi-Fi rule alone can't catch them; it takes note similarity + coordination.
    We run it twice: on an unlisted bakery number, and on the verified Fresh Bakes number.
    """
    name = "bakery-bomb 40"
    copy_paste = "This bakery is cheating customers, fake number, do not call or pay them!!"
    fake_notes = [copy_paste, copy_paste, copy_paste, "", "", "scam", "fraud"]
    nets = [run.network() for _ in range(25)]       # friends at home: many different networks

    def bomb(identifier_type: str, value: str, count: int) -> None:
        for i in range(count):
            run.send(run.report(identifier_type, value, 2.0 - i * (2.0 / count), PIN_BAKERY,
                                run.person(), run.rng.choice(nets), scam_type="fake-customer-care",
                                channel="Phone call", note=run.rng.choice(fake_notes)))

    # 1) Unlisted bakery number: must not become KNOWN_SCAM and must stay hidden.
    bakery = run.phone()
    bomb("phone", bakery, 40)
    run.remember(name, "phone", bakery, "Suspicious, hidden: the 40 friends' wave is held back")
    run.remember(name, "phone", "+91 80 4100 2233", "Verified business (Fresh Bakes), even after 15 fake reports")
    _, data = run.lookup("phone", bakery)
    run.check(name, "verdict (unlisted bakery)", "not KNOWN_SCAM", data.get("verdict"),
              data.get("verdict") != "KNOWN_SCAM")
    run.check(name, "display_value masked", "masked", data.get("display_value"), masked(data.get("display_value")))

    # 2) The verified Fresh Bakes number from the brief: verified always wins (+3 bonus).
    bomb("phone", "+91 80 4100 2233", 15)
    _, data = run.lookup("phone", "+91 80 4100 2233")
    run.check(name, "verdict (verified Fresh Bakes)", "VERIFIED_BUSINESS", data.get("verdict"),
              data.get("verdict") == "VERIFIED_BUSINESS")

    # 3) Fakes must not set off any alert in the bakery's area (+2 bonus).
    status, alerts = run.get(f"/alerts?pincode={PIN_BAKERY}")
    run.endpoint_check(name, "fakes fire no alert", "alerts == []", status,
                       lambda: (alerts.get("alerts"), alerts.get("alerts") == []))


def scenario_real_campaign(run: Run) -> None:
    """A real scam wave: 8 unrelated people, 6 networks, own words, many areas, some money lost.

    This must NOT be stopped by the trust rules.
    """
    name = "real campaign 8"
    number = run.phone()
    nets = [run.network() for _ in range(6)]
    for i in range(8):
        lost = run.rng.choice([0, 0, 15000, 49999]) if i % 2 else 0
        run.send(run.report("phone", number, 70 - i * 8.5, CAMPAIGN_PINS[i % len(CAMPAIGN_PINS)],
                            run.person(), nets[i % 6], scam_type="digital-arrest",
                            note=run.real_note("digital-arrest"), has_screenshot=(i % 3 == 0),
                            amount_lost_inr=lost))
    run.remember(name, "phone", number, "Known scam, number shown in full, digital arrest")
    _, data = run.lookup("phone", number)
    run.check(name, "verdict", "KNOWN_SCAM", data.get("verdict"), data.get("verdict") == "KNOWN_SCAM")
    run.check(name, "distinct_reporters", ">= 3", data.get("distinct_reporters"),
              (data.get("distinct_reporters") or 0) >= 3)
    run.check(name, "display_value shown in full", number, data.get("display_value"),
              data.get("display_value") == number)

    # Every way of typing the number gives the same verdict.
    verdicts = {run.lookup("phone", f)[1].get("verdict") for f in run.phone_formats(number)}
    run.check(name, "4 phone formats agree", "1 verdict", sorted(map(str, verdicts)), len(verdicts) == 1)

    # Privacy: no reporter/IP/note in evidence, careful wording.
    keys = {k for ev in data.get("evidence", []) for k in ev}
    run.check(name, "evidence has no reporter/ip/note", "none", sorted(keys & FORBIDDEN_EVIDENCE_KEYS) or "none",
              not (keys & FORBIDDEN_EVIDENCE_KEYS))
    text = json.dumps(data).lower()
    bad = [w for w in BANNED_WORDS if w in text]
    run.check(name, "no accusing words", "none", bad or "none", not bad)

    # The map shows the area at the brief's own map point, never a reporter location.
    pin = CAMPAIGN_PINS[0]
    status, mp = run.get(f"/map?pincode={pin}&days=7&radius_km=2")

    def map_ok():
        mine = [c for c in mp.get("clusters", []) if c.get("pincode") == pin]
        area = run.areas[pin]
        good = bool(mine) and mine[0].get("lat") == area["lat"] and mine[0].get("lng") == area["lng"]
        return (mine[0] if mine else "no cluster"), good
    run.endpoint_check(name, f"/map {pin} has cluster at area point", "cluster, lat/lng from areas.json",
                       status, map_ok)


def scenario_real_upi(run: Run) -> None:
    """A smaller real wave on a UPI ID: 5 people, 5 networks, typed in different cases."""
    name = "real UPI 5"
    upi = run.upi()
    for i in range(5):
        typed = upi.upper() if i % 2 else upi        # 'REFUND...@OKAXIS' must match 'refund...@okaxis'
        run.send(run.report("upi", typed, 40 - i * 7, CAMPAIGN_PINS[(i + 3) % len(CAMPAIGN_PINS)],
                            run.person(), run.network(), channel="UPI request", scam_type="upi-refund-qr",
                            note=run.real_note("upi-refund-qr"), amount_lost_inr=run.rng.choice([0, 4999])))
    run.remember(name, "upi", upi.upper(), "Known scam (typed in CAPITALS, still matches)")
    _, data = run.lookup("upi", upi)
    run.check(name, "verdict", "KNOWN_SCAM", data.get("verdict"), data.get("verdict") == "KNOWN_SCAM")
    run.check(name, "display_value shown in full", upi, data.get("display_value"), data.get("display_value") == upi)


def scenario_small_real(run: Run) -> None:
    """Only 2 real people reported it: SUSPICIOUS and still hidden."""
    name = "small real 2"
    number = run.phone()
    for i in range(2):
        run.send(run.report("phone", number, 10 + i * 20, CAMPAIGN_PINS[i + 4], run.person(), run.network(),
                            scam_type="otp-call", note=run.real_note("otp-call")))
    run.remember(name, "phone", number, "Suspicious, 2 people, hidden like 98XXXXX210")
    _, data = run.lookup("phone", number)
    run.check(name, "verdict", "SUSPICIOUS", data.get("verdict"), data.get("verdict") == "SUSPICIOUS")
    run.check(name, "display_value masked", "masked like 98XXXXX210", data.get("display_value"),
              masked(data.get("display_value")))


def scenario_lookup_basics(run: Run) -> None:
    """Never-reported numbers and the brief's verified list."""
    name = "lookup basics"
    status, data = run.lookup("phone", run.phone())
    run.check(name, "unreported number", "200 NO_REPORTS", f"{status} {data.get('verdict')}",
              status == 200 and data.get("verdict") == "NO_REPORTS")
    for id_type, value in [("phone", "1930"), ("phone", "1800 1600"), ("sender_id", "VM-HDFCBK"),
                           ("url", "https://cybercrime.gov.in/"), ("upi", "FreshBakes@okaxis")]:
        _, data = run.lookup(id_type, value)
        run.check(name, f"verified {value}", "VERIFIED_BUSINESS", data.get("verdict"),
                  data.get("verdict") == "VERIFIED_BUSINESS")


def scenario_old_reports(run: Run) -> None:
    """4 real reports from 30 days ago: they must never appear on the 7-day map."""
    name = "old reports 30d"
    number = run.phone()
    for i in range(4):
        run.send(run.report("phone", number, 30 * 24 + i * 5, PIN_OLD, run.person(), run.network(),
                            scam_type="courier-customs", note=run.real_note("otp-call")))
    run.remember(name, "phone", number, "Has reports, but Hebbal is NOT on the map (30 days old)")
    status, mp = run.get(f"/map?pincode={PIN_OLD}&days=7&radius_km=2")
    run.endpoint_check(name, f"/map {PIN_OLD} (days=7)", "no cluster for the area", status,
                       lambda: ([c for c in mp.get("clusters", []) if c.get("pincode") == PIN_OLD] or "none",
                                not [c for c in mp.get("clusters", []) if c.get("pincode") == PIN_OLD]))


def _real_area_reports(run: Run, pincode: str, hours_ago_list, types) -> None:
    """Helper: one genuine person per report, each about a different scam number, in one area."""
    for i, hours_ago in enumerate(hours_ago_list):
        scam_type = types[i % len(types)]
        run.send(run.report("phone", run.phone(), hours_ago, pincode, run.person(), run.network(),
                            scam_type=scam_type, note=run.real_note(scam_type),
                            amount_lost_inr=run.rng.choice([0, 0, 2000])))


def scenario_spike(run: Run) -> None:
    """~2 real reports/day for a week, then 10 today: SPIKE."""
    name = "spike area"
    types = ["otp-call", "fake-kyc-link"]
    prior = [24 + d * 24 + h for d in range(7) for h in (5, 15)]        # 14 reports, days 1..7 ago
    today = [1 + i * 2 for i in range(10)]                              # 10 reports in last 21 h
    _real_area_reports(run, PIN_SPIKE, prior + today, types)
    status, alerts = run.get(f"/alerts?pincode={PIN_SPIKE}")
    run.endpoint_check(name, "SPIKE fired", "SPIKE (10 today vs 2/day)", status,
                       lambda: (alert_types(alerts, "SPIKE") or "none", bool(alert_types(alerts, "SPIKE"))))


def scenario_steady(run: Run) -> None:
    """6 real reports every day for 8 days: busy but normal, so NO alert."""
    name = "steady area"
    types = ["otp-call", "fake-kyc-link"]
    times = [d * 24 + 1 + h * 3.5 for d in range(8) for h in range(6)]  # 48 reports, 6 per day
    _real_area_reports(run, PIN_STEADY, times, types)
    status, alerts = run.get(f"/alerts?pincode={PIN_STEADY}")
    run.endpoint_check(name, "no SPIKE / NEW_TYPE", "alerts == []", status,
                       lambda: (alerts.get("alerts"), alerts.get("alerts") == []))


def scenario_new_type(run: Run) -> None:
    """30 days of OTP/KYC reports, then the area's first job-offer reports today: NEW_TYPE."""
    name = "new-type area"
    history = [d * 24 + 6 for d in range(2, 31)]                        # 29 reports, days 2..30 ago
    _real_area_reports(run, PIN_NEWTYPE, history, ["otp-call", "fake-kyc-link"])
    _real_area_reports(run, PIN_NEWTYPE, [2, 6, 11], ["job-offer"])    # 3 people, 3 networks, today
    status, alerts = run.get(f"/alerts?pincode={PIN_NEWTYPE}")

    def ok():
        new = [a for a in alert_types(alerts, "NEW_TYPE") if a.get("scam_type") == "job-offer"]
        return (new or alerts.get("alerts")), bool(new) and not alert_types(alerts, "SPIKE")
    run.endpoint_check(name, "NEW_TYPE job-offer, no SPIKE", "NEW_TYPE job-offer", status, ok)


def scenario_dispute(run: Run) -> None:
    """4 real people report a number, then its owner disputes it (bonus).

    Before: KNOWN_SCAM. After the dispute: challenged=true, never KNOWN_SCAM, and the number is
    hidden again while it is under review.
    """
    name = "dispute"
    number = run.phone()
    for i in range(4):
        run.send(run.report("phone", number, 30 + i * 6, CAMPAIGN_PINS[i], run.person(), run.network(),
                            channel="Phone call", scam_type="fake-customer-care",
                            note=run.real_note("otp-call")))
    _, before = run.lookup("phone", number)
    run.check(name, "verdict before dispute", "KNOWN_SCAM", before.get("verdict"),
              before.get("verdict") == "KNOWN_SCAM")
    status, reply = run.server.request("POST", "/challenges", {
        "identifier_type": "phone", "identifier_value": number, "claimant_name": "Demo Sweets",
        "contact_email": "owner@example.com", "proof_note": "Shop licence and GST certificate."})
    reply = reply if isinstance(reply, dict) else {}
    run.check(name, "POST /challenges", "201 under_review", f"{status} {reply.get('status')}",
              status == 201 and reply.get("status") == "under_review")
    _, after = run.lookup("phone", number)
    run.check(name, "after: challenged, not KNOWN_SCAM", "challenged=True, SUSPICIOUS",
              f"challenged={after.get('challenged')}, {after.get('verdict')}",
              after.get("challenged") is True and after.get("verdict") != "KNOWN_SCAM")
    run.check(name, "after: number hidden again", "masked", after.get("display_value"),
              masked(after.get("display_value")))
    run.remember(name, "phone", number, "Suspicious + 'Under review' badge, hidden (was Known scam)")


# Each other city gets its own mix of scam types, so every city's dashboard looks different.
OTHER_CITY_MIX = {
    "400050": ("Mumbai", ["investment-group", "digital-arrest", "courier-customs", "upi-refund-qr"]),
    "110016": ("Delhi", ["digital-arrest", "loan-app-harassment", "sextortion", "otp-call"]),
    "500081": ("Hyderabad", ["job-offer", "investment-group", "fake-kyc-link"]),
    "600020": ("Chennai", ["electricity-disconnection", "otp-call", "courier-customs"]),
    "411014": ("Pune", ["job-offer", "fake-customer-care", "upi-refund-qr"]),
    "700091": ("Kolkata", ["lottery-prize", "otp-call", "fake-kyc-link"]),
    "380015": ("Ahmedabad", ["investment-group", "upi-refund-qr", "lottery-prize"]),
    "302017": ("Jaipur", ["electricity-disconnection", "digital-arrest", "loan-app-harassment"]),
    "226010": ("Lucknow", ["fake-kyc-link", "lottery-prize", "otp-call"]),
    "682030": ("Kochi", ["job-offer", "courier-customs", "fake-customer-care"]),
}
# The channel a scam type usually comes through (so the demo data reads naturally).
TYPE_CHANNEL = {
    "digital-arrest": "Phone call", "otp-call": "Phone call", "fake-customer-care": "Phone call",
    "electricity-disconnection": "SMS or WhatsApp", "fake-kyc-link": "Fake website",
    "job-offer": "SMS or WhatsApp", "investment-group": "SMS or WhatsApp", "lottery-prize": "SMS or WhatsApp",
    "courier-customs": "Phone call", "loan-app-harassment": "Phone call", "sextortion": "SMS or WhatsApp",
    "upi-refund-qr": "UPI request",
}


def scenario_other_cities(run: Run) -> None:
    """Demo data for the 10 non-Bengaluru cities, so every city's dashboard and map have something to show.

    Per city: one wave per scam type in its mix (4-6 unrelated people, own networks, own words, spread
    over 2 weeks, some money lost), plus a few one-off reports. These are all REAL-looking reports, so
    they count; the fake-report attacks stay in the Bengaluru scenarios above.
    """
    name = "other cities"
    for pin, (city, types) in OTHER_CITY_MIX.items():
        # Every area we know in this city (the brief's one + our extra localities), so the map shows several points.
        pins = [p for p, a in run.areas.items() if a["city"] == city]
        for k, scam_type in enumerate(types):
            # 1) A wave: 4-6 people on one number (UPI ID for UPI scams), spread over ~2 weeks.
            id_type = "upi" if scam_type == "upi-refund-qr" else "phone"
            value = run.upi() if id_type == "upi" else run.phone()
            people = run.rng.randint(4, 6)     # 4+: still Known scam if two notes happen to look alike
            start = run.rng.uniform(2, 110)                          # hours ago of the newest report
            for i in range(people):
                run.send(run.report(id_type, value, start + i * run.rng.uniform(6, 30), run.rng.choice(pins),
                                    run.person(), run.network(), channel=TYPE_CHANNEL[scam_type],
                                    scam_type=scam_type, note=run.real_note(scam_type),
                                    has_screenshot=run.rng.random() < 0.4,
                                    amount_lost_inr=run.rng.choice([0, 0, 2500, 18000, 75000])))
            if k == 0:
                run.remember(name, id_type, value, f"Known scam in {city} ({scam_type})")
        # 2) A few one-off reports on different numbers (each only one person: masked, Suspicious).
        for _ in range(run.rng.randint(4, 8)):
            scam_type = run.rng.choice(types)
            run.send(run.report("phone", run.phone(), run.rng.uniform(1, 230), run.rng.choice(pins), run.person(), run.network(),
                                channel=TYPE_CHANNEL[scam_type], scam_type=scam_type,
                                note=run.real_note(scam_type)))

    # 3) Check: every one of these cities now has reports on its dashboard this week or last week.
    empty = []
    for pin, (city, _) in OTHER_CITY_MIX.items():
        _, st = run.get(f"/stats?city={quote(city)}")
        if not (st.get("reports_this_week") or st.get("reports_last_week")):
            empty.append(city)
    run.check(name, "dashboard has data in 10 more cities", "no empty city", empty or "none", not empty)


def check_latency(run: Run, extra: int) -> None:
    """Lookups must answer in under 500 ms. Optionally fire `extra` more lookups."""
    for _ in range(extra):
        run.lookup("phone", run.phone())
    times = sorted(run.lookup_ms)
    if not times:
        return
    p95 = lambda xs: xs[min(len(xs) - 1, int(len(xs) * 0.95))]
    trip = f"round trip p95 {p95(times):.0f} ms"
    # Graded on the server's OWN time when the server reports it: the round trip from a laptop to
    # the cloud also contains the network, which our code can't change (it is still printed).
    if run.server_ms:
        own = sorted(run.server_ms)
        run.check("latency", f"/lookup p95 over {len(own)} calls (server's own time)", f"< {LOOKUP_BUDGET_MS} ms",
                  f"server {p95(own):.0f} ms; {trip}", p95(own) < LOOKUP_BUDGET_MS)
    else:
        run.check("latency", f"/lookup p95 over {len(times)} calls", f"< {LOOKUP_BUDGET_MS} ms",
                  f"{p95(times):.0f} ms (max {times[-1]:.0f})", p95(times) < LOOKUP_BUDGET_MS)


SCENARIOS = [scenario_junk, scenario_spammer, scenario_wifi_farm, scenario_bakery, scenario_real_campaign,
             scenario_real_upi, scenario_small_real, scenario_lookup_basics, scenario_old_reports,
             scenario_spike, scenario_steady, scenario_new_type, scenario_dispute, scenario_other_cities]


# ----------------------------------------------------------------------------- running + printing
def run_all(server, seed: int | None = None, latency_extra: int = 0, reset: bool = True) -> Run:
    """Reset the server, run every scenario, and return the Run with its results table."""
    run = Run(server, seed)
    # 1) Start clean, so area counts for /map and /alerts only contain this run's reports.
    if reset:
        status, _ = server.request("POST", "/admin/reset")
        if status != 200:
            raise SystemExit(f"POST /admin/reset failed with HTTP {status}; is the server running?")
    # 2) Every scenario sends its reports, then checks the answers.
    for scenario in SCENARIOS:
        scenario(run)
    # 3) Speed check last, using every lookup made above.
    check_latency(run, latency_extra)
    return run


def print_table(run: Run) -> None:
    """Print the PASS/FAIL table (plain ASCII, so it works in any Windows console)."""
    headers = ("Scenario", "Check", "Expected", "Got", "Result")
    rows = [(s, c, e, g if len(g) <= 60 else g[:57] + "...", "PASS" if p else "FAIL")
            for s, c, e, g, p in run.results]
    widths = [max(len(h), *(len(r[i]) for r in rows)) for i, h in enumerate(headers)]
    line = "-+-".join("-" * w for w in widths)
    print(" | ".join(h.ljust(w) for h, w in zip(headers, widths)))
    print(line)
    for r in rows:
        print(" | ".join(v.ljust(w) for v, w in zip(r, widths)))
    passed = sum(1 for r in run.results if r[4])
    print(line)
    print(f"{passed}/{len(run.results)} checks passed")


def print_showcase(run: Run) -> None:
    """Print the identifiers to try by hand on the website, with the answer each should give."""
    print("\nTry these on the website (Check page) - what you should see:")
    width = max(len(r[2]) for r in run.showcase)
    for scenario, id_type, value, expect in run.showcase:
        print(f"  {id_type:<6} {value.ljust(width)}  {expect}   [{scenario}]")
    print(f"  {'phone':<6} {'12345'.ljust(width)}  Error: not a valid number   [junk]")
    print("\nMap and alerts (Map page, Bengaluru):")
    print("  Bellandur        SPIKE alert: 10 reports today vs about 2 a day before")
    print("  Electronic City  NEW_TYPE alert: first job-offer reports in 30 days")
    print("  Marathahalli     busy every day, but NO alert (normal for that area)")
    print("  Whitefield       22 fake accounts: no alert, not on the map")
    print("  Indiranagar      40 friends' wave: no alert, not on the map")
    print("  Hebbal           only month-old reports: NOT on the map")


def is_local(base: str) -> bool:
    """True when the base URL points at this computer."""
    return urlparse(base).hostname in ("localhost", "127.0.0.1", "::1")


def main(argv=None) -> int:
    """Command-line entry point. Returns the process exit code."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base", default="http://localhost:8000", help="server address")
    parser.add_argument("--seed", type=int, default=None, help="repeat an exact run")
    parser.add_argument("--latency", type=int, default=0, metavar="N", help="also fire N extra lookups")
    parser.add_argument("--allow-remote-reset", action="store_true",
                        help="required for a non-local --base: the run WIPES that server's reports")
    args = parser.parse_args(argv)

    # The run starts with POST /admin/reset. On the deployed server that deletes the live data,
    # so we only do it there when asked explicitly.
    if not is_local(args.base) and not args.allow_remote_reset:
        print(f"Refusing: this run deletes every report on {args.base}.\n"
              "Add --allow-remote-reset if that is really what you want.")
        return 2

    print(f"Running {len(SCENARIOS)} scenarios against {args.base} ...")
    run = run_all(HttpServer(args.base), seed=args.seed, latency_extra=args.latency)
    print_table(run)
    print_showcase(run)
    return 0 if all(r[4] for r in run.results) else 1


if __name__ == "__main__":
    sys.exit(main())
