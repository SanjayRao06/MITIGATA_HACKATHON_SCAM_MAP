"""Shared pytest setup.

- Makes `import app` work when pytest is run from the `server/` folder.
- Points the app at a throwaway SQLite file BEFORE the app is imported, so tests never touch
  `dev.db` or the live Neon database.
"""

import os
import sys
import tempfile
from pathlib import Path

_tmp_db = Path(tempfile.gettempdir()) / "scam_map_test.db"
if _tmp_db.exists():
    _tmp_db.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_db.as_posix()}"
os.environ["HASH_SECRET"] = "test-secret"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
