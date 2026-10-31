"""Put a licence straight into the LIVE database, BEFORE pushing the licence code ([PRD §6]).

Why: the moment Render deploys the licence code, every request is locked until a licence exists.
If the licence row is already in the database, the new server reads it on its very first request,
so the live site is never locked and nothing has to be uploaded after the deploy.
It only writes the single `license` row (id=1). No other table is touched.

Usage (from the repo root, run ONCE before `git push`):
    server\\.venv\\Scripts\\python tools\\preload_live_licence.py               # uses licenses\\long.json
    server\\.venv\\Scripts\\python tools\\preload_live_licence.py licenses\\other.json
Reads DATABASE_URL from `.env.local` (the Neon address) just for this run.
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def neon_url() -> str:
    """The DATABASE_URL line from .env.local (the server itself never reads that file)."""
    for line in (ROOT / ".env.local").read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("No DATABASE_URL in .env.local")


def main(argv=None) -> int:
    """Verify the licence with the server's own code, then save it in the live database."""
    argv = sys.argv[1:] if argv is None else argv
    file = Path(argv[0]) if argv else ROOT / "licenses" / "long.json"

    # 1) Point the server code at Neon (must happen before `app.db` is imported).
    os.environ["DATABASE_URL"] = neon_url()
    sys.path.insert(0, str(ROOT / "server"))
    from app import db, license as licence  # noqa: E402

    # 2) Make sure the licence tables exist (creates only missing ones; data untouched), then install.
    db.metadata.create_all(db.engine, tables=[db.license_table, db.clock_guard])
    try:
        result = licence.install(json.loads(file.read_text(encoding="utf-8")))
    except licence.LicenceError as exc:
        print(f"Refused: {exc.code}. Nothing was written.")
        return 1
    print(f"Live database ({db.engine.url.host}) now holds: {result['licensee']} until "
          f"{result['expires_at']} ({result['status']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
