"""GET /lookup logic: what do we know about one identifier?

Answers with exactly one verdict ([PRD §A.3]): VERIFIED_BUSINESS, NO_REPORTS, KNOWN_SCAM or
SUSPICIOUS. We count reports live from the reports table each time, which is always correct even
when many reports arrive at once, and takes a few milliseconds thanks to the index.

STEP 2 NOTE: the counting here is deliberately naive (one vote per distinct hashed reporter_id).
That means 22 fake accounts CAN still make a number KNOWN_SCAM. Step 4 replaces
`count_people()` with the trust engine (docs/03). Nothing else in this file needs to change.
"""

from collections import Counter

from sqlalchemy import select

from app import reference
from app.db import engine, identifiers, reports
from app.privacy import mask
from app.timeutil import to_ist_str

# How many different people must report an identifier before we (a) call it KNOWN_SCAM and
# (b) show it unmasked. Both are "3" in the PRD (§5 rule 2).
KNOWN_SCAM_MIN_PEOPLE = 3
SHOW_UNMASKED_MIN_PEOPLE = 3
# How many recent reports to list as evidence (date, channel, type, area only).
MAX_EVIDENCE = 20


def count_people(rows) -> int:
    """How many different people reported this? (Step 2: distinct hashed reporter ids.)"""
    return len({r.reporter_hash for r in rows})


def message_for(verdict: str, people: int, belongs_to: str | None) -> str:
    """Careful, human wording for the app ([PRD §5] rule 3: say "reported", never accuse)."""
    if verdict == "VERIFIED_BUSINESS":
        return f"Verified business: {belongs_to}" if belongs_to else "Verified business"
    if verdict == "NO_REPORTS":
        return "No reports yet"
    if verdict == "KNOWN_SCAM":
        return f"Reported by {people} people - be careful"
    return "Some reports, not confirmed" if people > 1 else "Reported by 1 person, not confirmed"


def lookup(id_type: str, value: str) -> dict:
    """Build the /lookup reply for an already-normalized identifier.

    In: type + normalized value. Out: the JSON dict from [PRD §A.3] plus a friendly `message`.
    """
    # 1) Load the identifier row and all its reports (two indexed queries).
    with engine.connect() as conn:
        ident = conn.execute(select(identifiers).where(
            identifiers.c.type == id_type, identifiers.c.value == value)).first()
        rows = []
        if ident is not None:
            rows = conn.execute(select(
                reports.c.reporter_hash, reports.c.occurred_at, reports.c.channel,
                reports.c.scam_type, reports.c.pincode,
            ).where(reports.c.identifier_id == ident.id)
             .order_by(reports.c.occurred_at.desc())).all()

    # 2) Basic numbers.
    people = count_people(rows)
    challenged = bool(ident.challenged) if ident is not None else False
    verified = reference.get_verified(id_type, value)

    # 3) Verdict, in priority order (docs/03 "Verdict"):
    #    the verified list always wins, then no reports, then enough people (and not disputed).
    if verified:
        verdict = "VERIFIED_BUSINESS"
    elif not rows:
        verdict = "NO_REPORTS"
    elif people >= KNOWN_SCAM_MIN_PEOPLE and not challenged:
        verdict = "KNOWN_SCAM"
    else:
        verdict = "SUSPICIOUS"

    # 4) What the app may show: full value only for verified businesses or 3+ people.
    show_full = verified is not None or people >= SHOW_UNMASKED_MIN_PEOPLE
    display_value = value if show_full else mask(id_type, value)

    # 5) Most common scam type, and evidence WITHOUT who/IP/note (privacy rule).
    top_type = Counter(r.scam_type for r in rows).most_common(1)[0][0] if rows else None
    evidence = [
        {"occurred_at": to_ist_str(r.occurred_at), "channel": r.channel,
         "scam_type": r.scam_type, "pincode": r.pincode}
        for r in rows[:MAX_EVIDENCE]
    ]

    return {
        "verdict": verdict,
        "report_count": len(rows),
        "distinct_reporters": people,
        "first_seen": to_ist_str(rows[-1].occurred_at) if rows else None,
        "last_seen": to_ist_str(rows[0].occurred_at) if rows else None,
        "scam_type": top_type,
        "display_value": display_value,
        "evidence": evidence,
        "challenged": challenged,
        # extra fields (allowed by the PRD): friendly text for the app
        "message": message_for(verdict, people, verified["belongs_to"] if verified else None),
        "masked": not show_full,
    }
