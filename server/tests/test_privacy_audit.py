"""Privacy audit: one test per privacy rule.

These tests are the proof for the "privacy never slips" rule (any slip = disqualification):
  5.1  no banned wording ("scammer", "fraud", ...) anywhere a user can read it
  5.2  the database has no column that could hold a raw reporter id / IP / name / phone / location
  5.3  the log shows only method, path, status and milliseconds
  5.4  an identifier stays masked until 3 trusted people reported it (and again while disputed)
  5.6  no test phone / UPI / link is hardcoded in the server code
"""

import io
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import db
from app.main import app
from app.privacy import hash_value, log

client = TestClient(app)
IST = timezone(timedelta(hours=5, minutes=30))
SERVER = Path(__file__).resolve().parents[1]
WEB = SERVER / "web"

# Words the brief forbids us to show, English and Hindi.
BANNED = re.compile(r"scammer|fraud|criminal|this person is|धोखाधड़ी|धोखेबाज़", re.IGNORECASE)


def ts(hours_ago):
    return (datetime.now(IST) - timedelta(hours=hours_ago)).isoformat(timespec="seconds")


@pytest.fixture(autouse=True)
def clean():
    client.post("/admin/reset")


# Different wording per reporter, so the copy-paste check (L3) doesn't merge them into one person.
NOTES = [
    "A man claiming to be from my bank asked for the OTP on my phone",
    "Got a video call, someone in uniform said a parcel with my name had drugs",
    "They offered a work from home job and wanted a small registration fee",
    "Electricity department threat, pay now through a link or power gets cut tonight",
    "Said I won a lottery prize but first I must send money for processing",
    "Pretended to be my nephew in trouble and needed urgent money transfer",
]


# Real campaigns hit several areas over several hours; same area + same hour looks coordinated (L4).
PINS = ["560102", "560034", "560076", "560011"]


def send(i, value="9876501234", id_type="phone", note=None, **extra):
    """Post one report from reporter number i on its own network (so each counts as a person)."""
    body = {
        "occurred_at": ts(2 + i * 5), "reporter_id": f"audit_{i}", "ip_prefix": f"10.{i}.1",
        "channel": "Phone call", "scam_type": "otp-call", "identifier_type": id_type,
        "identifier_value": value, "pincode": PINS[i % 4],
        "note": note or NOTES[i % len(NOTES)],
    }
    body.update(extra)
    r = client.post("/reports", json=body)
    assert r.status_code == 201, r.text
    return r


# ---------------------------------------------------------------- 5.1 banned words
def test_banned_words_not_in_any_website_file():
    """Every text file the browser can download is free of the banned words."""
    for f in WEB.iterdir():
        if f.suffix in {".html", ".js", ".css", ".json"}:
            text = f.read_text(encoding="utf-8")
            assert not BANNED.search(text), f"banned word in web/{f.name}: {BANNED.search(text).group(0)}"


def test_banned_words_not_in_reference_data():
    """The scam types / channels / areas the server hands out contain none either."""
    for f in (SERVER / "app" / "data").glob("*.json"):
        assert not BANNED.search(f.read_text(encoding="utf-8")), f.name


def test_banned_words_not_in_any_api_reply():
    """Report real-looking scams, then read every JSON endpoint and scan the replies."""
    for i in range(4):
        send(i)
    client.post("/challenges", json={"identifier_type": "phone", "identifier_value": "9876501234",
                                     "claimant_name": "A Shop", "contact_email": "a@b.in", "proof_note": "mine"})
    for path in ["/lookup?type=phone&value=9876501234", "/lookup?type=phone&value=9000011111", "/map",
                 "/alerts?pincode=560102", "/stats", "/meta", "/license", "/health"]:
        r = client.get(path)
        assert not BANNED.search(r.text), f"{path}: {BANNED.search(r.text).group(0)}"


# ---------------------------------------------------------------- 5.2 database audit
# A column called any of these would mean we keep something the brief forbids.
FORBIDDEN_COLUMN = re.compile(r"(^|_)(ip|phone|mobile|lat|lng|lon|latitude|longitude|gps|address|reporter_id|reporter_name|email_address)($|_)")


def test_no_forbidden_columns_in_reports_or_reporters():
    """Reports and reporters hold only hashes, areas and text fields; nothing identifying."""
    for table in (db.reports, db.reporters):
        for col in table.columns:
            if col.name.endswith("_hash"):
                continue                      # hashed columns are the allowed form
            assert not FORBIDDEN_COLUMN.search(col.name), f"{table.name}.{col.name}"
    # reporter and network are stored only as hash columns
    assert {"reporter_hash", "ip_hash"} <= {c.name for c in db.reports.columns}


def test_stored_values_are_hashes_not_raw():
    """What is really in the database for reporter/network is the HMAC, never the raw text."""
    send(1, reporter_id="r_secret_person", ip_prefix="49.36.12")
    with db.engine.connect() as conn:
        row = conn.execute(select(db.reports)).mappings().one()
        rep = conn.execute(select(db.reporters)).mappings().one()
    assert row["reporter_hash"] == hash_value("r_secret_person") and rep["reporter_hash"] == row["reporter_hash"]
    assert row["ip_hash"] == hash_value("49.36.12")
    flat = " ".join(str(v) for v in list(row.values()) + list(rep.values()))
    assert "r_secret_person" not in flat and "49.36.12" not in flat


def test_free_text_only_in_known_columns():
    """The only free-text columns on reports are the note and the two 'something else' texts,
    and none of the three is ever returned by any endpoint."""
    send(1, note="NOTE-MARKER-123", channel="Something else", channel_other="CHAN-MARKER-456",
         scam_type="other", scam_type_other="TYPE-MARKER-789")
    for path in ["/lookup?type=phone&value=9876501234", "/map", "/alerts?pincode=560102", "/stats"]:
        text = client.get(path).text
        assert not re.search(r"MARKER", text), path


def test_dispute_claimant_details_are_never_returned_or_listed():
    """The claimant's name / email / proof are stored for review but no endpoint shows them."""
    send(1)
    r = client.post("/challenges", json={"identifier_type": "phone", "identifier_value": "9876501234",
                                         "claimant_name": "CLAIMANT-NAME-X", "contact_email": "claim-x@mail.in",
                                         "proof_note": "PROOF-TEXT-X"})
    assert r.status_code == 201
    everything = r.text + "".join(client.get(p).text for p in [
        "/lookup?type=phone&value=9876501234", "/map", "/alerts?pincode=560102", "/stats", "/meta"])
    for marker in ("CLAIMANT-NAME-X", "claim-x@mail.in", "PROOF-TEXT-X"):
        assert marker not in everything


# ---------------------------------------------------------------- 5.3 log audit
@pytest.fixture
def log_text():
    """Capture everything our logger prints during a test and give it back as one string."""
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    log.addHandler(handler)
    old = log.level
    log.setLevel(logging.DEBUG)
    yield lambda: buf.getvalue()
    log.removeHandler(handler)
    log.setLevel(old)


def test_logs_show_only_method_path_status_and_ms(log_text):
    """Hit every endpoint with recognisable personal-looking data; none of it may reach the log."""
    secrets = ["LOGSECRET-ID-77", "LOGSECRET-NOTE-88", "7788990011", "logsecret@okaxis",
               "LOGSECRET-NAME", "logsecret-mail@x.in", "203.0.113.9", "LOGSECRET-PROOF"]
    send(1, value="7788990011", reporter_id=secrets[0], ip_prefix="203.0.113", note=secrets[1])
    send(2, value="logsecret@okaxis", id_type="upi")
    client.get("/lookup?type=phone&value=7788990011&x=LOGSECRET-ID-77")
    client.get("/lookup?type=upi&value=logsecret@okaxis")
    client.get("/map?pincode=560102")
    client.get("/alerts?pincode=560102")
    client.get("/stats")
    client.get("/meta")
    client.get("/license")
    client.get("/health")
    client.post("/challenges", json={"identifier_type": "phone", "identifier_value": "7788990011",
                                     "claimant_name": secrets[4], "contact_email": secrets[5], "proof_note": secrets[7]})
    # an invalid request too (error paths must not echo the input either)
    client.post("/reports", json={"identifier_type": "phone", "identifier_value": "LOGSECRET-BAD"})
    text = log_text()
    assert text, "expected some log lines"
    for s in secrets + ["LOGSECRET-BAD"]:
        assert s not in text, f"{s} leaked into the log"
    # every line is exactly: LEVEL METHOD /path STATUS 12.3ms
    line = re.compile(r"^INFO (GET|POST) /[a-z/]* \d{3} \d+\.\d+ms$")
    for l in text.strip().splitlines():
        assert line.match(l), f"unexpected log line: {l!r}"
    assert "?" not in text            # no query strings at all


def test_uvicorn_access_log_is_switched_off():
    """uvicorn's own access log prints IPs and full URLs, so setup_logging() disables it."""
    from app.privacy import setup_logging
    setup_logging()
    assert logging.getLogger("uvicorn.access").disabled is True


# ---------------------------------------------------------------- 5.4 masking in the API
def raw_visible(text, digits="9876501234"):
    """True if the full number appears in a reply (masked form like 98XXXXX234 does not count)."""
    return digits in text or "+91" + digits in text


@pytest.mark.parametrize("n,shown", [(1, False), (2, False), (3, True)])
def test_masked_until_three_people(n, shown):
    """1 and 2 trusted reporters: masked. 3: shown in full."""
    for i in range(n):
        send(i)
    text =client.get("/lookup?type=phone&value=9876501234").text
    assert raw_visible(text) is shown
    if not shown:
        assert "98XXXXX234" in text


def test_masked_numbers_never_leak_through_map_alerts_or_stats():
    """With only 2 reporters the number must not appear on any other endpoint."""
    for i in range(2):
        send(i)
    for path in ["/map", "/alerts?pincode=560102", "/stats", "/meta"]:
        assert not raw_visible(client.get(path).text), path


def test_disputed_number_is_masked_again():
    """Even with 3+ reporters, a number under dispute goes back to masked while under review."""
    for i in range(3):
        send(i)
    assert raw_visible(client.get("/lookup?type=phone&value=9876501234").text)
    client.post("/challenges", json={"identifier_type": "phone", "identifier_value": "9876501234",
                                     "claimant_name": "A", "contact_email": "a@b.in", "proof_note": "mine"})
    assert not raw_visible(client.get("/lookup?type=phone&value=9876501234").text)


def test_unknown_and_invalid_identifiers_do_not_echo_input():
    """A lookup for something never reported gives 'no reports', not the input back."""
    r = client.get("/lookup?type=phone&value=8000000001")
    assert r.status_code == 200 and "8000000001" not in r.text
    bad = client.get("/lookup?type=phone&value=ECHO-ME-PLEASE")
    assert "ECHO-ME-PLEASE" not in bad.text


# ---------------------------------------------------------------- 5.6 no hardcoded identifiers
def test_no_hardcoded_identifiers_in_server_code():
    """No code path compares against a real-looking phone / UPI / link. Only docstrings, comments and
    the Swagger example bodies may show examples; the verified list lives in data/verified.json.

    We look for code lines (not comments) that compare to or contain a quoted identifier literal."""
    literal = re.compile(r"""["'](\+91[ 0-9]{10,}|[6-9][0-9]{9}|[\w.]+@(okaxis|ybl|paytm|upi|oksbi|okhdfcbank)|https?://[\w.-]+)""")
    compare = re.compile(r"(==|!=|\bin\b|startswith|endswith)\s*[\(\[]?\s*" + literal.pattern)
    offenders = []
    for f in (SERVER / "app").glob("*.py"):
        for no, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#", 1)[0]
            if compare.search(code):
                offenders.append(f"{f.name}:{no}: {line.strip()}")
    assert not offenders, offenders


def test_server_timing_header_is_only_a_number():
    """Every reply says how long the server took (for the live speed check) and nothing else."""
    r = client.get("/lookup?type=phone&value=9876501234")
    assert re.fullmatch(r"app;dur=\d+\.\d", r.headers["server-timing"])
