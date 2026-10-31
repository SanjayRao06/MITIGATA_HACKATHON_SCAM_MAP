"""Glue between the database and the trust rules.

trust.py is pure logic (no database). This file fetches what it needs for ONE identifier:
its reports, each reporter's history on other numbers (for reputation), and which reporters
are flagged (they reported a verified business before). It then runs trust.assess() and can
write back the `trusted` flag that /map and /alerts use.
"""

from datetime import timedelta

from sqlalchemy import select, update

from app import trust
from app.db import reporters, reports

# A report on another number only counts as "history" if it came at least this long before the
# reporter's first report on this number, so a fake farm can't create its own history in one burst.
HISTORY_GAP = timedelta(hours=24)


def load_reports(conn, identifier_id: int) -> list[dict]:
    """All reports for one identifier, as plain dicts with the fields trust.assess() needs."""
    rows = conn.execute(select(
        reports.c.id, reports.c.reporter_hash, reports.c.ip_hash, reports.c.occurred_at,
        reports.c.reported_at, reports.c.note, reports.c.pincode, reports.c.amount_lost_inr,
        reports.c.has_screenshot, reports.c.channel, reports.c.scam_type,
    ).where(reports.c.identifier_id == identifier_id).order_by(reports.c.occurred_at.desc())).all()
    return [dict(r._mapping) for r in rows]


def load_context(conn, identifier_id: int, rows: list[dict]) -> tuple[dict, set]:
    """Reputation inputs for the reporters of one identifier.

    Out: (history, flagged) where history = {reporter_hash: number of OTHER identifiers they
    reported well before this one} and flagged = reporter hashes with a lowered reputation.
    """
    hashes = list({r["reporter_hash"] for r in rows})
    if not hashes:
        return {}, set()

    # 1) When did each reporter first report THIS identifier?
    first_here = {}
    for r in rows:
        t = trust.report_time(r)
        h = r["reporter_hash"]
        first_here[h] = min(first_here.get(h, t), t)

    # 2) Their earliest report on every OTHER identifier; count those well before (1).
    others = conn.execute(select(reports.c.reporter_hash, reports.c.identifier_id, reports.c.occurred_at)
                          .where(reports.c.reporter_hash.in_(hashes),
                                 reports.c.identifier_id != identifier_id)).all()
    earliest = {}
    for h, ident, t in others:
        key = (h, ident)
        earliest[key] = min(earliest.get(key, t), t)
    history = {h: 0 for h in hashes}
    for (h, _ident), t in earliest.items():
        if t <= first_here[h] - HISTORY_GAP:
            history[h] += 1

    # 3) Reporters whose stored reputation was lowered (reported a verified/disputed number).
    flagged = {h for (h,) in conn.execute(select(reporters.c.reporter_hash).where(
        reporters.c.reporter_hash.in_(hashes), reporters.c.reputation <= trust.REP_FLAGGED)).all()}
    return history, flagged


def assess_identifier(conn, identifier_id: int | None, verified: bool) -> tuple[list[dict], dict]:
    """Load one identifier's reports and judge them. Out: (rows, trust result)."""
    if identifier_id is None:
        return [], trust.assess([], {}, set(), verified)
    rows = load_reports(conn, identifier_id)
    history, flagged = load_context(conn, identifier_id, rows)
    return rows, trust.assess(rows, history, flagged, verified)


def refresh_trusted_flags(conn, identifier_id: int, verified: bool) -> dict:
    """Re-judge an identifier after a new report and store which reports count as trusted.

    Called inside the same transaction as the insert, so map/alerts always see current flags.
    """
    rows, result = assess_identifier(conn, identifier_id, verified)
    trusted_ids = set(result["trusted_report_ids"])
    conn.execute(update(reports).where(reports.c.identifier_id == identifier_id).values(trusted=False))
    if trusted_ids:
        conn.execute(update(reports).where(reports.c.id.in_(trusted_ids)).values(trusted=True))
    return result


def refresh_all_trusted_flags() -> int:
    """Re-judge every identifier and store fresh `trusted` flags. Returns how many were checked.

    Run once at server start. Reports stored before the `trusted` column existed, or before a
    rule was tuned, then get the right flags, so /map and /alerts are correct after any deploy.
    """
    from app import reference
    from app.db import engine, identifiers

    with engine.begin() as conn:
        idents = conn.execute(select(identifiers.c.id, identifiers.c.type, identifiers.c.value)).all()
        for ident in idents:
            verified = reference.get_verified(ident.type, ident.value) is not None
            refresh_trusted_flags(conn, ident.id, verified)
    return len(idents)
