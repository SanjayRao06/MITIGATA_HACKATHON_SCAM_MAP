"""Privacy helpers: hashing, masking and safe request logging (docs/04-privacy.md).

- hash_value(): reporter ids and IP prefixes are stored only as HMAC hashes. We can still tell
  "same reporter / same network" apart, but a database dump reveals nothing about who reported.
- mask(): hides an identifier ("98XXXXX210") until at least 3 different people have reported it,
  so one angry person can't publicly label someone ([PRD §5] rule 2).
- Logging: uvicorn's built-in access log prints client IPs and full URLs (which can contain an
  identifier), so we switch it off and log only method, path, status and latency.
"""

import hashlib
import hmac
import logging
import os
import time

from fastapi import Request
from fastapi.responses import JSONResponse

# Our own logger. Everything we log goes through this name so it is easy to audit.
log = logging.getLogger("scam_map")

# Secret key for hashing. On Render it comes from the HASH_SECRET env var. The fallback is only
# for laptop development and tests; it never protects real data.
_HASH_SECRET = (os.environ.get("HASH_SECRET") or "dev-only-not-secret").encode()


def hash_value(value: str) -> str:
    """One-way hash a reporter id or IP prefix.

    In: raw text, e.g. "r_7c2d91aa". Out: 64-char hex string.
    HMAC with a server secret (not plain SHA-256), so nobody can rebuild the mapping by
    hashing guesses without the secret. The same input always gives the same output, which is
    how we still count "same person" and "same Wi-Fi".
    """
    return hmac.new(_HASH_SECRET, value.strip().encode(), hashlib.sha256).hexdigest()


def mask(identifier_type: str, value: str) -> str:
    """Hide most of a normalized identifier.

    In: type + normalized value. Out: masked text (formats from [PRD §A.3] / docs/04):
      +919876543210 -> 98XXXXX210 | 18001600 -> 18XXX600 | ravi12@okaxis -> r***@okaxis
      https://sbi-kyc.in/pay -> sbi***.in/... | HDFCBK -> HD****
    """
    # 1) Phones: mobile/landline show first 2 + XXXXX + last 3 of the 10-digit body.
    if identifier_type == "phone":
        digits = value[3:] if value.startswith("+91") else value
        if len(digits) >= 8:
            return digits[:2] + "X" * (len(digits) - 5) + digits[-3:]
        return digits[:2] + "X" * (len(digits) - 2)      # short codes like 1098 -> 10XX

    # 2) UPI: first letter of the name + *** + the bank handle.
    if identifier_type == "upi":
        name, _, handle = value.partition("@")
        return name[:1] + "***@" + handle

    # 3) Links: first 3 letters of the host + *** + the ending (.in, .com) + "/...".
    if identifier_type == "url":
        host = value.split("://", 1)[-1].split("/", 1)[0]
        labels = host.split(".")
        first = labels[0]
        keep = min(3, max(1, len(first) - 1))            # never reveal a whole short name
        return first[:keep] + "***." + labels[-1] + "/..."

    # 4) SMS sender: first 2 letters + ****.
    if identifier_type == "sender_id":
        return value[:2] + "****"

    return "****"


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

    # 4) Tell the caller how long WE took (standard Server-Timing header, only a number).
    #    Why: from a laptop, the network to Render hides our own time; this shows it separately.
    response.headers["Server-Timing"] = f"app;dur={ms:.1f}"
    return response
