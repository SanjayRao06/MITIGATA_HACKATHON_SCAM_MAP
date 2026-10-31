"""GET /lookup logic: what do we know about one identifier?

Answers with exactly one verdict ([PRD §A.3]): VERIFIED_BUSINESS, NO_REPORTS, KNOWN_SCAM or
SUSPICIOUS. Each lookup re-reads the identifier's reports and runs the trust rules (trust.py), which
is always correct even when many reports arrive at once, and takes a few milliseconds.

`distinct_reporters` is the number of independent, trusted people AFTER the trust rules: one
person x6 = 1, 22 accounts on one Wi-Fi = 1, a copy-paste wave = 0-1. It also decides masking.
"""

from collections import Counter

from sqlalchemy import select

from app import reference, trust
from app.assessment import assess_identifier
from app.db import engine, identifiers
from app.privacy import mask
from app.timeutil import to_ist_str

# How many recent reports to list as evidence (date, channel, type, area only).
MAX_EVIDENCE = 20


def message_for(verdict: str, people: int, belongs_to: str | None, challenged: bool) -> str:
    """Careful, human wording for the app ([PRD §5] rule 3: say "reported", never accuse)."""
    if verdict == "VERIFIED_BUSINESS":
        return f"Verified business: {belongs_to}" if belongs_to else "Verified business"
    if verdict == "NO_REPORTS":
        return "No reports yet"
    if verdict == "KNOWN_SCAM":
        return f"Reported by {people} people - be careful"
    if challenged:
        return "A business has disputed these reports - under review"
    return "Some reports, not confirmed" if people > 1 else "Reported, not confirmed"


def _find(conn, id_type: str, value: str):
    """The identifiers row for (type, value), or None if nobody reported it."""
    return conn.execute(select(identifiers).where(
        identifiers.c.type == id_type, identifiers.c.value == value)).first()


def lookup(id_type: str, value: str) -> dict:
    """Build the /lookup reply for an already-normalized identifier.

    In: type + normalized value. Out: the JSON dict from [PRD §A.3] plus a friendly `message`.
    """
    # 1) Load the identifier and judge its reports with the trust rules.
    verified = reference.get_verified(id_type, value)
    with engine.connect() as conn:
        ident = _find(conn, id_type, value)
        rows, result = assess_identifier(conn, ident.id if ident else None, verified is not None)
    challenged = bool(ident.challenged) if ident is not None else False

    # 2) People = independent trusted sources. If there are reports but none are trusted
    #    (e.g. a fake wave), we still say "1" so the reply never claims nobody reported it.
    people = result["trusted_sources"] or (1 if rows else 0)

    # 3) Verdict, in priority order (docs/03 "Verdict"): verified list always wins, then no
    #    reports, then KNOWN_SCAM only if the trust rules allow it and nobody disputed it.
    if verified:
        verdict = "VERIFIED_BUSINESS"
    elif not rows:
        verdict = "NO_REPORTS"
    elif result["known_scam_allowed"] and not challenged:
        verdict = "KNOWN_SCAM"
    else:
        verdict = "SUSPICIOUS"

    # 4) Show the full value only for verified businesses or 3+ independent trusted people.
    #    A disputed number stays hidden while it is under review: if the business is right, we
    #    must not have its real number on screen next to "reported" (privacy first, docs/04).
    enough_people = result["trusted_sources"] >= trust.KNOWN_SCAM_MIN_SOURCES
    show_full = verified is not None or (enough_people and not challenged)
    display_value = value if show_full else mask(id_type, value)

    # 5) Most common scam type, and evidence WITHOUT who/IP/note (privacy rule).
    top_type = Counter(r["scam_type"] for r in rows).most_common(1)[0][0] if rows else None
    evidence = [
        {"occurred_at": to_ist_str(r["occurred_at"]), "channel": r["channel"],
         "scam_type": r["scam_type"], "pincode": r["pincode"]}
        for r in rows[:MAX_EVIDENCE]
    ]

    return {
        "verdict": verdict,
        "report_count": len(rows),
        "distinct_reporters": people,
        "first_seen": to_ist_str(rows[-1]["occurred_at"]) if rows else None,
        "last_seen": to_ist_str(rows[0]["occurred_at"]) if rows else None,
        "scam_type": top_type,
        "display_value": display_value,
        "evidence": evidence,
        "challenged": challenged,
        # extra fields (allowed by the PRD): friendly text for the app
        "message": message_for(verdict, people, verified["belongs_to"] if verified else None, challenged),
        "masked": not show_full,
    }


def explain(id_type: str, value: str) -> dict:
    """The trust rules' working for one identifier: counts and scores only, no ids or notes."""
    verified = reference.get_verified(id_type, value)
    with engine.connect() as conn:
        ident = _find(conn, id_type, value)
        _rows, result = assess_identifier(conn, ident.id if ident else None, verified is not None)
    return {"type": id_type, "verified": verified is not None,
            "challenged": bool(ident.challenged) if ident else False,
            "known_scam_allowed": result["known_scam_allowed"], **result["explain"]}
