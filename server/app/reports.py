"""POST /reports logic: check a report, then save it.

validate_report() turns the raw JSON into a clean dict or raises ReportError (-> HTTP 400).
save_report() stores it and returns the reply {report_id, case_id, merged}.
Rules come from [PRD §A.2] and docs/02 ("Other validation").
"""

import uuid
from datetime import timedelta

from sqlalchemy import func, insert, select
from sqlalchemy.exc import IntegrityError

from app import reference
from app.db import engine, identifiers, reporters, reports
from app.normalize import IDENTIFIER_TYPES, InvalidIdentifier, normalize
from app.privacy import hash_value
from app.timeutil import now_utc, parse_ts

# How far into the future a report time may be (phone clocks drift a little).
FUTURE_TOLERANCE = timedelta(minutes=10)
# Reports older than this are rejected as "invalid time".
MAX_AGE = timedelta(days=365)
# Longest note we keep (notes are only used for copy-paste detection).
MAX_NOTE_CHARS = 2000


class ReportError(ValueError):
    """A report we must reject. The message becomes {"error": "..."} with status 400."""


def validate_report(body) -> dict:
    """Check one incoming report and return a cleaned-up copy.

    In: the parsed JSON body (should be a dict).
    Out: dict with normalized identifier, UTC times, hashed reporter/IP, canonical channel etc.
    Raises ReportError for anything [PRD §A.2] says is a 400: bad identifier, unknown area code,
    bad time. Unknown channel / scam_type are NOT errors; they become "Something else" / "other".
    """
    # 1) The body must be a JSON object.
    if not isinstance(body, dict):
        raise ReportError("body must be a JSON object")

    # 2) Identifier: known type + a value our normalizer accepts.
    id_type = body.get("identifier_type")
    if id_type not in IDENTIFIER_TYPES:
        raise ReportError("identifier_type must be one of phone, upi, url, sender_id")
    try:
        id_value = normalize(id_type, body.get("identifier_value"))
    except InvalidIdentifier:
        # Don't echo the value back: error text could end up in someone's logs.
        raise ReportError("invalid identifier_value") from None

    # 3) Area: must be one of our pincodes. Locality/city come from OUR data, not the body,
    #    so nobody can slip extra location detail into the database.
    area = reference.get_area(body.get("pincode"))
    if area is None:
        raise ReportError("unknown pincode")

    # 4) Times: occurred_at required and sensible; reported_at optional but not before it.
    now = now_utc()
    try:
        occurred = parse_ts(body.get("occurred_at"))
    except (ValueError, TypeError):
        raise ReportError("invalid occurred_at") from None
    if occurred > now + FUTURE_TOLERANCE:
        raise ReportError("occurred_at is in the future")
    if occurred < now - MAX_AGE:
        raise ReportError("occurred_at is too old")
    reported = None
    if body.get("reported_at") not in (None, ""):
        try:
            reported = parse_ts(body.get("reported_at"))
        except (ValueError, TypeError):
            raise ReportError("invalid reported_at") from None
        if reported < occurred - FUTURE_TOLERANCE:
            raise ReportError("reported_at is before occurred_at")
        if reported > now + FUTURE_TOLERANCE:
            raise ReportError("reported_at is in the future")

    # 5) Reporter identity comes from the body ([PRD §A.0] rule 2), and we keep only hashes.
    reporter_id, ip_prefix = body.get("reporter_id"), body.get("ip_prefix")
    if not isinstance(reporter_id, str) or not reporter_id.strip():
        raise ReportError("reporter_id is required")
    if not isinstance(ip_prefix, str) or not ip_prefix.strip():
        raise ReportError("ip_prefix is required")

    # 6) Optional extras, cleaned rather than rejected.
    note = body.get("note")
    note = note.strip()[:MAX_NOTE_CHARS] if isinstance(note, str) else None
    try:
        amount = max(0.0, float(body.get("amount_lost_inr") or 0))
    except (TypeError, ValueError):
        amount = 0.0
    report_id = body.get("report_id")
    if not isinstance(report_id, str) or not report_id.strip():
        report_id = "rep_" + uuid.uuid4().hex[:12]

    return {
        "report_id": report_id.strip()[:128],
        "identifier_type": id_type,
        "identifier_value": id_value,
        "occurred_at": occurred,
        "reported_at": reported,
        "reporter_hash": hash_value(reporter_id),
        "ip_hash": hash_value(ip_prefix),
        "channel": reference.canonical_channel(body.get("channel")),
        "scam_type": reference.canonical_scam_type(body.get("scam_type")),
        "pincode": area["pincode"],
        "locality": area["locality"],
        "city": area["city"],
        "note": note or None,
        "has_screenshot": bool(body.get("has_screenshot")),
        "amount_lost_inr": amount,
    }


def _get_or_create_identifier(conn, id_type: str, value: str) -> int:
    """Return the identifiers.id for (type, value), creating the row if it's new.

    Two reports for a new number can arrive at the same moment. Both may try to insert, and the
    database's unique rule lets only one win. The loser catches the error and reads the winner's row.
    """
    query = select(identifiers.c.id).where(identifiers.c.type == id_type, identifiers.c.value == value)
    row = conn.execute(query).first()
    if row:
        return row.id
    try:
        with conn.begin_nested():  # savepoint: a failed insert doesn't undo the whole request
            result = conn.execute(insert(identifiers).values(
                type=id_type, value=value, challenged=False, created_at=now_utc()))
            return result.inserted_primary_key[0]
    except IntegrityError:
        return conn.execute(query).scalar_one()


def save_report(clean: dict) -> dict:
    """Store a validated report.

    In: output of validate_report(). Out: {"report_id", "case_id", "merged"} for the 201 reply.
    `merged` is true when this identifier already had at least one report.
    If the same report_id arrives twice (a client retrying), we don't store it again; we just
    return the original answer, so retries can't inflate counts.
    """
    with engine.begin() as conn:  # one transaction: all of this happens, or none of it
        # 1) Same report_id seen before? Return the earlier result instead of double-counting.
        existing = conn.execute(
            select(reports.c.identifier_id).where(reports.c.report_id == clean["report_id"])
        ).first()
        if existing:
            return {"report_id": clean["report_id"], "case_id": f"case_{existing.identifier_id}",
                    "merged": True}

        # 2) Find or create the identifier row. Its id is the case_id.
        ident_id = _get_or_create_identifier(conn, clean["identifier_type"], clean["identifier_value"])

        # 3) Was there already a report about it? That's what "merged" means.
        before = conn.execute(
            select(func.count()).select_from(reports).where(reports.c.identifier_id == ident_id)
        ).scalar_one()

        # 4) Remember the (hashed) reporter for reputation later (Step 4).
        if conn.execute(select(reporters.c.reporter_hash)
                        .where(reporters.c.reporter_hash == clean["reporter_hash"])).first() is None:
            try:
                with conn.begin_nested():
                    conn.execute(insert(reporters).values(
                        reporter_hash=clean["reporter_hash"], first_seen=now_utc(), reputation=0.6))
            except IntegrityError:
                pass  # another request created it at the same moment; that's fine

        # 5) Store the report itself.
        try:
            with conn.begin_nested():
                conn.execute(insert(reports).values(
                    report_id=clean["report_id"], identifier_id=ident_id,
                    occurred_at=clean["occurred_at"], reported_at=clean["reported_at"],
                    received_at=now_utc(), reporter_hash=clean["reporter_hash"],
                    ip_hash=clean["ip_hash"], channel=clean["channel"], scam_type=clean["scam_type"],
                    pincode=clean["pincode"], locality=clean["locality"], city=clean["city"],
                    note=clean["note"], has_screenshot=clean["has_screenshot"],
                    amount_lost_inr=clean["amount_lost_inr"],
                ))
        except IntegrityError:
            # The same report_id was inserted by a parallel retry a moment ago.
            pass

    return {"report_id": clean["report_id"], "case_id": f"case_{ident_id}", "merged": before > 0}
