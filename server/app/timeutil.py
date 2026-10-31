"""Time helpers: one place that decides how we read, store and print times.

Rules (CLAUDE.md hard rule 6): we store every time as UTC without a timezone label
(SQLite can't keep one), compare against the server clock, and print times in India time
(+05:30) like "2026-10-27T18:21:04+05:30", which is the format the judges' test tool uses.
"""

from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))


def now_utc() -> datetime:
    """The server clock as a naive UTC datetime (same shape as what we store in the DB)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def parse_ts(value) -> datetime:
    """Parse an ISO-8601 time string into naive UTC.

    In: e.g. "2026-10-27T18:21:04+05:30" or "...Z". Out: naive UTC datetime.
    A time with no offset is assumed to be India time, since all our users and the test tool are
    in India. Rejecting it would throw away a real report over a formatting detail.
    Raises ValueError if it isn't a time at all.
    """
    # 1) Must be a non-empty string.
    if not isinstance(value, str) or not value.strip():
        raise ValueError("time missing")

    # 2) Parse it (Python 3.11 understands "+05:30" and "Z").
    dt = datetime.fromisoformat(value.strip())

    # 3) No offset given -> assume IST. Then convert to UTC and drop the label for storage.
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=IST)
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def to_ist_str(dt: datetime | None) -> str | None:
    """Turn a stored naive-UTC datetime into "YYYY-MM-DDTHH:MM:SS+05:30" (or None)."""
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc).astimezone(IST).isoformat(timespec="seconds")
