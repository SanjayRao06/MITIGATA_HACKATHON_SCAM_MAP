"""Privacy helpers: safe request logging (more helpers arrive in later steps).

Our hard rule is "nothing personal in logs". Uvicorn's built-in access log prints the
client IP and the full URL (which can contain an identifier in the query string), so we
switch it off and log only method, path, status and how long the request took.
Masking and hashing helpers will be added here in Step 2 (see docs/04-privacy.md).
"""

import logging
import time

from fastapi import Request
from fastapi.responses import JSONResponse

# Our own logger. Everything we log goes through this name so it is easy to audit.
log = logging.getLogger("scam_map")


def setup_logging() -> None:
    """Configure logging once at startup.

    In: nothing. Out: nothing.
    Why: turn off uvicorn's access log (it prints IPs and query strings) and give our own
    logger a simple one-line format. Safe to call more than once.
    """
    # 1) Silence uvicorn's access logger completely - it would leak IPs and query strings.
    access = logging.getLogger("uvicorn.access")
    access.disabled = True
    access.handlers.clear()
    access.propagate = False

    # 2) Give our logger one plain handler (only if it doesn't have one already).
    if not log.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(handler)
    log.setLevel(logging.INFO)
    log.propagate = False


async def safe_logging_middleware(request: Request, call_next):
    """Log one line per request with no personal data.

    In: the incoming request and FastAPI's `call_next` (runs the real endpoint).
    Out: the endpoint's response (or a plain 500 if the endpoint crashed).
    What is logged: method, path WITHOUT the query string, status code, latency in ms.
    What is never logged: bodies, query strings, identifiers, IPs, headers.
    """
    # 1) Start the stopwatch. `url.path` excludes "?value=..." so identifiers never reach the log.
    start = time.perf_counter()
    method, path = request.method, request.url.path

    # 2) Run the endpoint. If it crashes, log only the error TYPE and path - not the payload
    #    or the exception message (a message could echo user input).
    try:
        response = await call_next(request)
    except Exception as exc:  # noqa: BLE001 - we really do want to catch everything here
        ms = (time.perf_counter() - start) * 1000
        log.error("%s %s 500 %.1fms error=%s", method, path, ms, type(exc).__name__)
        return JSONResponse(status_code=500, content={"error": "INTERNAL_ERROR"})

    # 3) Log the normal one-liner.
    ms = (time.perf_counter() - start) * 1000
    log.info("%s %s %d %.1fms", method, path, response.status_code, ms)
    return response
