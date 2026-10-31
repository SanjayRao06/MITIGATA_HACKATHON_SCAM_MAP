"""Database: table definitions and the connection ("engine").

Same code for both places we run:
- Laptop: SQLite file `server/dev.db` (default, nothing to install).
- Render: Neon Postgres, from the DATABASE_URL environment variable.
We deliberately do NOT read DATABASE_URL from `.env.local` on the laptop. Otherwise local tests,
or a local /admin/reset, would wipe the live database the judges use.

Privacy (docs/04): no table has a column for reporter name, phone, raw reporter_id, raw IP or
lat/lng. Reporter id and IP prefix are stored only as HMAC hashes (see privacy.py).
"""

import os

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, MetaData, String, Table, Text,
    UniqueConstraint, create_engine, inspect, text,
)

metadata = MetaData()

# One row per distinct identifier (phone / UPI / link / sender). Its id is the "case_id".
identifiers = Table(
    "identifiers", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("type", String(16), nullable=False),          # phone | upi | url | sender_id
    Column("value", String(512), nullable=False),        # normalized form, e.g. +919876543210
    Column("challenged", Boolean, nullable=False, default=False),  # set by POST /challenges (Step 7)
    Column("created_at", DateTime, nullable=False),
    UniqueConstraint("type", "value", name="uq_identifier"),
)

# One row per report. Only area-level location (pincode/locality/city), never coordinates.
reports = Table(
    "reports", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("report_id", String(128), nullable=False, unique=True),  # the client's id (idempotency)
    Column("identifier_id", Integer, ForeignKey("identifiers.id"), nullable=False),
    Column("occurred_at", DateTime, nullable=False),     # naive UTC
    Column("reported_at", DateTime, nullable=True),      # naive UTC
    Column("received_at", DateTime, nullable=False),     # server clock when we stored it
    Column("reporter_hash", String(64), nullable=False), # HMAC(reporter_id), never the raw id
    Column("ip_hash", String(64), nullable=False),       # HMAC(ip_prefix), never the raw prefix
    Column("channel", String(64), nullable=False),
    Column("scam_type", String(64), nullable=False),
    Column("pincode", String(6), nullable=False),
    Column("locality", String(128), nullable=False),
    Column("city", String(64), nullable=False),
    Column("note", Text, nullable=True),                 # for similarity checks only; never returned
    Column("has_screenshot", Boolean, nullable=False, default=False),
    Column("amount_lost_inr", Float, nullable=False, default=0),
    # Set by the trust engine: True for ONE report per independent, trusted source. /map and
    # /alerts count only these, so fake waves never show up on the map or fire alerts.
    Column("trusted", Boolean, nullable=False, default=False),
    # The reporter's own words when they picked "Something else" as the channel or scam type
    # (e.g. "Telegram", "fake rent deposit"). Kept for reviewers only; never returned or logged.
    Column("channel_other", String(60), nullable=True),
    Column("scam_type_other", String(60), nullable=True),
)
Index("ix_reports_identifier", reports.c.identifier_id)
Index("ix_reports_reporter", reports.c.reporter_hash)
Index("ix_reports_area_time", reports.c.pincode, reports.c.occurred_at)

# One row per (hashed) reporter. Reputation is used by the trust engine in Step 4.
reporters = Table(
    "reporters", metadata,
    Column("reporter_hash", String(64), primary_key=True),
    Column("first_seen", DateTime, nullable=False),
    Column("reputation", Float, nullable=False, default=0.6),
)

# Business disputes (POST /challenges, Step 7). Claimant details are never logged or shown.
challenges = Table(
    "challenges", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("identifier_id", Integer, ForeignKey("identifiers.id"), nullable=False),
    Column("claimant_name", String(256)),
    Column("contact_email", String(256)),
    Column("proof_note", Text),
    Column("status", String(32), nullable=False, default="under_review"),
    Column("created_at", DateTime, nullable=False),
)

# Licence (Step 5): one row holding the current licence JSON. Survives restarts; never reset.
license_table = Table(
    "license", metadata,
    Column("id", Integer, primary_key=True),
    Column("body", Text, nullable=False),
    Column("updated_at", DateTime, nullable=False),
)

# Clock guard (Step 5): the latest time the server has seen, to catch clocks set backwards.
clock_guard = Table(
    "clock_guard", metadata,
    Column("id", Integer, primary_key=True),
    Column("last_seen_utc", DateTime, nullable=False),
)


def database_url() -> str:
    """Pick the database address.

    In: env var DATABASE_URL (set on Render), else the local SQLite file.
    Out: a URL SQLAlchemy understands. Neon/Render give "postgres://" or "postgresql://", but
    SQLAlchemy needs to be told which driver to use, so we rewrite them to "postgresql+psycopg://".
    """
    url = os.environ.get("DATABASE_URL", "").strip().strip('"') or "sqlite:///./dev.db"
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def make_engine():
    """Create the connection pool.

    SQLite: allow use from FastAPI's worker threads.
    Postgres: `pool_pre_ping` checks a pooled connection is still alive before using it. Neon closes
    idle connections, and without this the first request after a quiet spell would error.
    """
    url = database_url()
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False})
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5, pool_recycle=300)


engine = make_engine()


def init_db() -> None:
    """Create any missing tables and columns (safe to run on every start; data is untouched).

    `create_all` only creates whole tables, so a column added later (like reports.trusted)
    must be added by hand to databases that already exist, e.g. our live Neon database.
    """
    metadata.create_all(engine)
    with engine.begin() as conn:
        existing = {c["name"] for c in inspect(conn).get_columns("reports")}
        if "trusted" not in existing:
            conn.execute(text("ALTER TABLE reports ADD COLUMN trusted BOOLEAN NOT NULL DEFAULT FALSE"))
        for column in ("channel_other", "scam_type_other"):
            if column not in existing:
                conn.execute(text(f"ALTER TABLE reports ADD COLUMN {column} VARCHAR(60)"))


def is_postgres() -> bool:
    """True when running against Postgres (i.e. on Render with Neon)."""
    return engine.dialect.name == "postgresql"


def ping() -> None:
    """Run a trivial query. Used to keep Neon's free database awake (it sleeps after ~5 min)."""
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
