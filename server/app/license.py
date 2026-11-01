"""Licence: the server only works while it holds a valid, signed, unexpired licence.

How it works (wax-seal idea): we sign `{licensee, expires_at}` on our laptop with a PRIVATE
key that never leaves it. The server has only the matching PUBLIC key (below), which can check a
seal but never make one. Change one character of the date and the check fails.

- Every request except /health and /license passes through `license_middleware`. No valid licence
  -> 403 {"error": "LICENSE_EXPIRED"}. The check is an in-memory comparison (microseconds).
- POST /license swaps in a new licence immediately: no restart. It's also saved in the database,
  so restarts and redeploys keep it. Expiry only LOCKS the server; no data is ever deleted.
- Clock guard (bonus): we remember the latest time we've seen. If the clock ever jumps
  back more than 2 minutes (someone setting it back a year to stretch the licence), we lock.
"""

import base64
import json
import os
import threading
import time
from datetime import datetime, timedelta

from fastapi import APIRouter, Body, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey
from sqlalchemy import select

from app import db, timeutil
from app.privacy import log

# The public half of our signing key (made by tools/keygen.py). Safe to publish: it can only CHECK
# signatures. The private half is `private.key` on Sanjay's laptop, never in git.
PUBLIC_KEY_B64 = "zwy/FoUOhkbVHOWcCyhIgQDVPEFpsmvGn8+iURCawak="

# Paths that keep working without a licence: the alive check, and the licence
# endpoints themselves (otherwise an expired server could never be renewed).
# The website's page ("/") and its files ("/static/...") also stay open, but they hold no data: they
# are what draws the "Licence expired" screen. Every data request the page makes still gets the 403.
OPEN_PATHS = {"/health", "/license", "/", "/favicon.ico"}
OPEN_PREFIXES = ("/static/",)

# Clock jumps backwards bigger than this count as tampering. Small drifts (NTP corrections) are fine.
CLOCK_TOLERANCE = timedelta(minutes=2)
# How often (seconds) each server process re-reads the licence + clock guard from the database and
# saves the latest time it has seen. Picks up a licence uploaded to another worker, within a minute.
SYNC_SECONDS = 30

# Error codes in replies.
EXPIRED = {"error": "LICENSE_EXPIRED"}


def clock() -> datetime:
    """The server clock as naive UTC. One function, so tests can pretend the clock moved."""
    return timeutil.now_utc()


# ----------------------------------------------------------------------------- signature check
class LicenceError(ValueError):
    """An uploaded licence we refuse. `code` becomes the {"error": ...} text (400)."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


_verify_key = VerifyKey(base64.b64decode(PUBLIC_KEY_B64))


def use_public_key(public_key_b64: str) -> None:
    """Swap the public key. ONLY for tests, which sign licences with their own throwaway key."""
    global _verify_key
    _verify_key = VerifyKey(base64.b64decode(public_key_b64))


def canonical_bytes(lic: dict) -> bytes:
    """The exact bytes that get signed: every field except the signature, keys sorted, no spaces.

    Signing all fields (not just licensee + expires_at) means nobody can add or change any field
    of a signed licence. tools/make_license.py uses this same rule.
    """
    unsigned = {k: v for k, v in lic.items() if k != "signature"}
    return json.dumps(unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def verify(lic) -> dict:
    """Check a licence and return a clean copy with `expires_utc` (naive UTC) added.

    In: the licence JSON (dict). Raises LicenceError("INVALID_LICENSE") if fields are missing or
    malformed, LicenceError("INVALID_SIGNATURE") if the seal doesn't match (e.g. edited date).
    """
    # 1) Shape: licensee, expires_at and signature must be present and sensible.
    if not isinstance(lic, dict):
        raise LicenceError("INVALID_LICENSE")
    licensee, expires_at, signature = lic.get("licensee"), lic.get("expires_at"), lic.get("signature")
    if not (isinstance(licensee, str) and licensee.strip() and len(licensee) <= 200):
        raise LicenceError("INVALID_LICENSE")
    if not isinstance(signature, str):
        raise LicenceError("INVALID_SIGNATURE")
    try:
        expires_utc = timeutil.parse_ts(expires_at)
    except (ValueError, TypeError):
        raise LicenceError("INVALID_LICENSE") from None

    # 2) Seal: the signature must match these exact bytes under our public key.
    try:
        _verify_key.verify(canonical_bytes(lic), base64.b64decode(signature, validate=True))
    except (BadSignatureError, ValueError):
        raise LicenceError("INVALID_SIGNATURE") from None

    return {**lic, "expires_utc": expires_utc}


# ----------------------------------------------------------------------------- state (in memory)
class _State:
    """What this server process knows right now. Reads are lock-free; changes take the lock."""

    def __init__(self):
        self.licence: dict | None = None        # verified licence (with expires_utc), or None
        self.raw_body: str | None = None        # the JSON text as stored in the DB
        self.last_seen: datetime | None = None  # latest server time ever seen (clock guard)
        self.next_sync = 0.0                    # time.monotonic() of the next DB sync (0 = now)
        self.lock = threading.Lock()


state = _State()


def status_now(now: datetime | None = None) -> dict:
    """Work out the licence status. Pure in-memory; called on every request.

    Out: {"status": VALID | EXPIRED | MISSING | CLOCK_TAMPERED, "valid": bool, ...licence info}.
    Also moves the clock-guard high-water mark forward.
    """
    now = now or clock()
    lic = state.licence

    # 1) Clock guard: time going backwards past the tolerance means someone set the clock back.
    if state.last_seen is not None and now < state.last_seen - CLOCK_TOLERANCE:
        status = "CLOCK_TAMPERED"
    else:
        if state.last_seen is None or now > state.last_seen:
            state.last_seen = now
        # 2) No licence, or past its expiry -> locked. Otherwise valid.
        if lic is None:
            status = "MISSING"
        elif now >= lic["expires_utc"]:
            status = "EXPIRED"
        else:
            status = "VALID"

    seconds_left = max(0, int((lic["expires_utc"] - now).total_seconds())) if lic else 0
    return {
        "licensee": lic["licensee"] if lic else None,
        "expires_at": lic["expires_at"] if lic else None,
        "valid": status == "VALID",
        "status": status,
        "seconds_left": seconds_left if status == "VALID" else 0,
        "server_time": timeutil.to_ist_str(now),
    }


# ----------------------------------------------------------------------------- database sync
def _adopt(raw_body: str) -> None:
    """Make a stored licence (JSON text) the current one, if its signature still checks out."""
    try:
        lic = verify(json.loads(raw_body))
    except (LicenceError, ValueError):
        log.warning("stored licence failed verification; server stays locked")
        lic = None
    state.licence, state.raw_body = lic, raw_body


def sync_with_db() -> None:
    """Re-read the licence and clock guard from the database, and save the latest time seen.

    Runs at most every SYNC_SECONDS per process (in a worker thread). Why:
    - restarts/redeploys: the licence survives because it's in the DB, not just memory;
    - several server processes: a licence uploaded to one is picked up by the others;
    - clock guard: the "latest time seen" survives restarts, so a restart can't hide a rollback.
    If the DB has no licence yet, the optional LICENSE_JSON env var is installed (first deploy).
    """
    now = clock()
    with state.lock, db.engine.begin() as conn:
        # 1) Licence row: adopt it if it differs from what we hold.
        row = conn.execute(select(db.license_table.c.body).where(db.license_table.c.id == 1)).first()
        if row is not None and row.body != state.raw_body:
            _adopt(row.body)
        elif row is None and os.environ.get("LICENSE_JSON", "").strip():
            try:
                body = os.environ["LICENSE_JSON"].strip()
                verify(json.loads(body))
                conn.execute(db.license_table.insert().values(id=1, body=body, updated_at=now))
                _adopt(body)
            except (LicenceError, ValueError):
                log.warning("LICENSE_JSON env var is not a valid licence; ignored")

        # 2) Clock guard: combine the DB's latest time with ours; save it unless the clock went back.
        guard = conn.execute(select(db.clock_guard.c.last_seen_utc).where(db.clock_guard.c.id == 1)).first()
        if guard is not None and (state.last_seen is None or guard.last_seen_utc > state.last_seen):
            state.last_seen = guard.last_seen_utc
        if state.last_seen is None or now >= state.last_seen - CLOCK_TOLERANCE:
            latest = max(now, state.last_seen or now)
            state.last_seen = latest
            if guard is None:
                conn.execute(db.clock_guard.insert().values(id=1, last_seen_utc=latest))
            elif latest > guard.last_seen_utc:
                conn.execute(db.clock_guard.update().where(db.clock_guard.c.id == 1)
                             .values(last_seen_utc=latest))

    state.next_sync = time.monotonic() + SYNC_SECONDS  # monotonic: immune to wall-clock changes


def install(lic: dict) -> dict:
    """Verify and switch to a new licence right now (memory + DB). Returns the new status.

    Raises LicenceError for a bad signature/shape, or LICENSE_ALREADY_EXPIRED: we refuse a licence
    that is already over, so a stale file uploaded by mistake can't lock a working server.
    """
    # 1) Check it. An expired-but-genuine file is refused, and the current licence stays.
    clean = verify(lic)
    now = clock()
    if now >= clean["expires_utc"]:
        raise LicenceError("LICENSE_ALREADY_EXPIRED")

    # 2) Save it (one row, id=1) and swap it in memory. Nothing else in the DB is touched.
    body = json.dumps({k: v for k, v in lic.items()}, ensure_ascii=False)
    with state.lock, db.engine.begin() as conn:
        updated = conn.execute(db.license_table.update().where(db.license_table.c.id == 1)
                               .values(body=body, updated_at=now)).rowcount
        if not updated:
            conn.execute(db.license_table.insert().values(id=1, body=body, updated_at=now))
        state.licence, state.raw_body = clean, body
    return status_now()


# ----------------------------------------------------------------------------- middleware + routes
async def license_middleware(request: Request, call_next):
    """Runs on EVERY request: lock everything except /health and /license.

    Browser pre-flight checks (OPTIONS) also pass, so a website on another address can still read
    the 403 reply and show the "Licence expired" screen.
    """
    # 1) Open paths (health, licence, the website's own files) and pre-flight requests pass.
    path = request.url.path
    if path in OPEN_PATHS or path.startswith(OPEN_PREFIXES) or request.method == "OPTIONS":
        return await call_next(request)

    # 2) Refresh from the DB now and then (in a worker thread so the server never stalls).
    if time.monotonic() >= state.next_sync:
        try:
            await run_in_threadpool(sync_with_db)
        except Exception as exc:  # noqa: BLE001 - a DB hiccup must not take the server down
            log.warning("licence sync failed: %s", type(exc).__name__)
            state.next_sync = time.monotonic() + 5

    # 3) The actual check: in memory, microseconds.
    if not status_now()["valid"]:
        return JSONResponse(status_code=403, content=EXPIRED)
    return await call_next(request)


router = APIRouter()

# Example shown in the /docs page.
LICENSE_EXAMPLE = {"licensee": "Demo Bank", "expires_at": "2026-11-15T10:05:00+05:30",
                   "signature": "<base64 signature made by tools/make_license.py>"}


@router.get("/license")
async def get_license():
    """Who the server is licensed to, until when, and whether it's working.

    Out: {licensee, expires_at, valid, status, seconds_left, server_time}. Always 200, even when expired.
    """
    try:
        await run_in_threadpool(sync_with_db)
    except Exception as exc:  # noqa: BLE001
        log.warning("licence sync failed: %s", type(exc).__name__)
    return status_now()


@router.post("/license")
async def post_license(body: dict = Body(..., openapi_examples={
        "licence": {"summary": "A signed licence file", "value": LICENSE_EXAMPLE}})):
    """Upload a new licence; it takes effect immediately, no restart.

    No password needed: only we can make a valid signature, so the signature IS the authentication.
    Out: 200 with the GET /license body, or 400 {"error": INVALID_SIGNATURE | INVALID_LICENSE |
    LICENSE_ALREADY_EXPIRED}, in which case the current licence stays in place.
    """
    try:
        return await run_in_threadpool(install, body)
    except LicenceError as exc:
        return JSONResponse(status_code=400, content={"error": exc.code})
