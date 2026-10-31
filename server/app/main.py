"""The FastAPI app: this is where every route is wired up.

Run it with `uvicorn app.main:app --reload --no-access-log` from the `server/` folder.
Endpoints so far (contract in docs/01, source of truth [PRD §A]):
  GET /health, POST /reports, GET /lookup, POST /admin/reset
  GET /debug/explain (only when the EXPLAIN_ENABLED env var is "1"; shows the trust rules' working)
Later steps add /map, /alerts, /challenges and /license (see docs/08-implementation-plan.md).
"""

import asyncio
import contextlib
import os

from fastapi import Body, FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import delete

from app import db, reference
from app.lookup import explain, lookup
from app.normalize import IDENTIFIER_TYPES, InvalidIdentifier, normalize
from app.privacy import log, safe_logging_middleware, setup_logging
from app.reports import RateLimited, ReportError, save_report, validate_report

# 1) Logging first, so even startup problems are logged safely.
setup_logging()

# 2) Load reference data (areas, verified list, scam types) once. If a JSON file is missing
#    or broken we want the server to fail loudly at startup, not on the first request.
reference.load()

# 3) Create any missing database tables.
db.init_db()

# Neon's free database falls asleep after ~5 idle minutes, and waking it takes up to a second,
# which would blow our 0.5 s lookup budget. A tiny query every 4 minutes keeps it awake.
KEEPALIVE_SECONDS = 240


async def _keep_db_awake() -> None:
    """Background loop: ping the database every few minutes (Postgres only)."""
    while True:
        await asyncio.sleep(KEEPALIVE_SECONDS)
        try:
            await run_in_threadpool(db.ping)
        except Exception as exc:  # noqa: BLE001 - never let the keep-alive crash the server
            log.warning("db keepalive failed: %s", type(exc).__name__)


@contextlib.asynccontextmanager
async def lifespan(_app: FastAPI):
    """Start the keep-alive task when the server starts; stop it when the server stops."""
    task = asyncio.create_task(_keep_db_awake()) if db.is_postgres() else None
    yield
    if task:
        task.cancel()


# 4) Build the app and attach our privacy-safe request logger.
app = FastAPI(title="Community Scam Map", version="0.2.0", lifespan=lifespan)
app.middleware("http")(safe_logging_middleware)


@app.exception_handler(RequestValidationError)
async def validation_error_to_400(_request: Request, _exc: RequestValidationError):
    """FastAPI's default for bad input is 422, but the PRD wants 400 {"error": ...}."""
    return JSONResponse(status_code=400, content={"error": "invalid request"})


def bad_request(message: str) -> JSONResponse:
    """Shortcut for a 400 reply in the PRD's shape."""
    return JSONResponse(status_code=400, content={"error": message})


@app.get("/health")
def health() -> dict:
    """Alive check for judges, uptime monitors and the deploy platform.

    In: nothing. Out: `{"ok": true}` with status 200.
    Why: docs/01 says it must always work, even when the licence has expired.
    """
    return {"ok": True}


# Example shown (and editable) in the /docs page, copied from [PRD §A.2].
REPORT_EXAMPLE = {
    "report_id": "rep_000123",
    "occurred_at": "2026-10-31T14:00:00+05:30",
    "reported_at": "2026-10-31T14:10:00+05:30",
    "reporter_id": "r_7c2d91aa",
    "ip_prefix": "103.21.58",
    "channel": "Phone call",
    "scam_type": "digital-arrest",
    "identifier_type": "phone",
    "identifier_value": "+91 98765 43210",
    "pincode": "560102",
    "locality": "HSR Layout",
    "city": "Bengaluru",
    "note": "Video call from a man in police uniform...",
    "has_screenshot": False,
    "amount_lost_inr": 0,
}


@app.post("/reports", status_code=201)
async def post_report(body: dict = Body(..., openapi_examples={
        "report": {"summary": "A phone scam report", "value": REPORT_EXAMPLE}})):
    """Receive one scam report ([PRD §A.2]).

    In: report JSON. Out: 201 {report_id, case_id, merged}, or 400 {"error"} for junk.
    `body: dict` tells FastAPI (and the /docs page) to expect a JSON object. Broken JSON or a
    non-object becomes a 400 via validation_error_to_400. All field checks happen in validate_report().
    """
    # 1) Validate (normalizer, pincode, times, reporter fields).
    try:
        clean = validate_report(body)
    except ReportError as exc:
        return bad_request(str(exc))

    # 2) Save it. The database work runs in a worker thread so the server stays responsive.
    #    Too many reports from one reporter in a short time -> 429 (allowed, [PRD §A.0] rule 4).
    try:
        return await run_in_threadpool(save_report, clean)
    except RateLimited:
        return JSONResponse(status_code=429, content={"error": "RATE_LIMITED"})


@app.get("/lookup")
def get_lookup(type: str | None = None, value: str | None = None):  # noqa: A002 - name from the PRD
    """Check an identifier ([PRD §A.3]), e.g. /lookup?type=phone&value=%2B91%2098765%2043210.

    Out: 200 with a verdict (never 404, even for unknown numbers), or 400 for impossible values.
    """
    # 1) Both query parameters are required and the type must be one of the four.
    #    Ignore capitals/spaces ("Phone", " phone") - being strict here only loses real lookups.
    type = (type or "").strip().lower()
    if type not in IDENTIFIER_TYPES:
        return bad_request("type must be one of phone, upi, url, sender_id")
    if not value:
        return bad_request("value is required")

    # 2) Same normalizer as /reports, so every way of typing a number gives the same answer.
    try:
        normalized = normalize(type, value)
    except InvalidIdentifier:
        return bad_request("invalid value")

    return lookup(type, normalized)


# The explain endpoint is for demos and debugging. It only shows counts and scores (no ids, no
# notes), but it is still switched off unless EXPLAIN_ENABLED=1 is set on the server.
EXPLAIN_ENABLED = os.environ.get("EXPLAIN_ENABLED") == "1"


@app.get("/debug/explain", include_in_schema=EXPLAIN_ENABLED)
def debug_explain(type: str | None = None, value: str | None = None):  # noqa: A002
    """Why did /lookup give this verdict? Shows each trust layer's effect for one identifier."""
    if not EXPLAIN_ENABLED:
        return JSONResponse(status_code=404, content={"error": "not found"})
    type = (type or "").strip().lower()
    if type not in IDENTIFIER_TYPES or not value:
        return bad_request("type and value are required")
    try:
        normalized = normalize(type, value)
    except InvalidIdentifier:
        return bad_request("invalid value")
    return explain(type, normalized)


@app.post("/admin/reset")
def admin_reset():
    """Delete all reports so the judges can start clean ([PRD §A.6]).

    Also clears identifiers, reporter reputation and challenges, which are all derived from
    reports. Keeps the licence and clock guard (the licence demo must survive a reset).
    """
    with db.engine.begin() as conn:
        deleted = conn.execute(delete(db.reports)).rowcount
        conn.execute(delete(db.challenges))
        conn.execute(delete(db.identifiers))
        conn.execute(delete(db.reporters))
    return {"ok": True, "deleted_reports": deleted}


def _openapi_with_real_status_codes():
    """Build the /docs description with the status codes we really send.

    FastAPI auto-lists "422 Validation Error" for every endpoint that takes input, but our
    validation_error_to_400 handler means we never send 422 - the PRD wants 400 {"error": ...}.
    So we swap every 422 entry for a 400 one, so the docs page doesn't mislead anyone (judges included).
    """
    if app.openapi_schema:
        return app.openapi_schema
    from fastapi.openapi.utils import get_openapi
    schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
    error_400 = {
        "description": "Invalid input, e.g. junk identifier, unknown pincode, bad time",
        "content": {"application/json": {"example": {"error": "invalid identifier_value"}}},
    }
    for methods in schema.get("paths", {}).values():
        for op in methods.values():
            responses = op.get("responses", {})
            if responses.pop("422", None) is not None:
                responses["400"] = error_400
    # POST /reports can also answer 429 when one reporter sends too many ([PRD §A.0] rule 4).
    reports_op = schema.get("paths", {}).get("/reports", {}).get("post")
    if reports_op:
        reports_op["responses"]["429"] = {
            "description": "Too many reports from this reporter in a short time (not stored)",
            "content": {"application/json": {"example": {"error": "RATE_LIMITED"}}},
        }
    schema.get("components", {}).get("schemas", {}).pop("HTTPValidationError", None)
    schema.get("components", {}).get("schemas", {}).pop("ValidationError", None)
    app.openapi_schema = schema
    return schema


app.openapi = _openapi_with_real_status_codes
