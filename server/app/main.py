"""The FastAPI app: this is where every route is wired up.

Run it with `uvicorn app.main:app --reload --no-access-log` from the `server/` folder.
Right now it only has `/health`; the other endpoints from docs/01-api-contract.md are added
step by step (see docs/08-implementation-plan.md).
"""

from fastapi import FastAPI

from app import reference
from app.privacy import safe_logging_middleware, setup_logging

# 1) Logging first, so even startup problems are logged safely.
setup_logging()

# 2) Load reference data (areas, verified list, scam types) once. If a JSON file is missing
#    or broken we want the server to fail loudly at startup, not on the first request.
reference.load()

# 3) Build the app and attach our privacy-safe request logger.
app = FastAPI(title="Community Scam Map", version="0.1.0")
app.middleware("http")(safe_logging_middleware)


@app.get("/health")
def health() -> dict:
    """Alive check for judges, uptime monitors and the deploy platform.

    In: nothing. Out: `{"ok": true}` with status 200.
    Why: docs/01 says it must always work, even when the licence has expired.
    """
    return {"ok": True}
