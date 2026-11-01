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


# Licence: every endpoint except /health and /license needs a valid licence, so every test
# starts with a long, valid one signed by a throwaway test key (see tests/licence_testkit.py).
import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _valid_licence():
    """Install a valid test licence before each test (tests that expire it get a fresh one next time)."""
    from tests.licence_testkit import install_valid_licence
    install_valid_licence()
