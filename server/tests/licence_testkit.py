"""Licence helpers for tests: a throwaway signing key and a one-call "valid licence" installer.

The real private key never exists in tests. Instead each test run makes its own key pair, tells the
server to trust its public half (`license.use_public_key`), and signs test licences with it.
"""

import base64
from datetime import datetime, timedelta, timezone

from nacl.signing import SigningKey

IST = timezone(timedelta(hours=5, minutes=30))
TEST_KEY = SigningKey.generate()


def sign(lic: dict, key: SigningKey = TEST_KEY) -> dict:
    """Return a copy of `lic` with a signature over all its other fields (same rule as the server)."""
    from app.license import canonical_bytes
    unsigned = {k: v for k, v in lic.items() if k != "signature"}
    return {**unsigned, "signature": base64.b64encode(key.sign(canonical_bytes(unsigned)).signature).decode()}


def make(minutes: float = 60 * 24 * 365, licensee: str = "Test Bank", key: SigningKey = TEST_KEY) -> dict:
    """A signed licence that expires `minutes` from now (default: a year)."""
    expires = (datetime.now(IST) + timedelta(minutes=minutes)).isoformat(timespec="seconds")
    return sign({"licensee": licensee, "expires_at": expires}, key)


def install_valid_licence() -> None:
    """Make the server trust the test key and hold a long, valid licence (used by conftest)."""
    from app import db, license
    license.use_public_key(base64.b64encode(bytes(TEST_KEY.verify_key)).decode())
    # Forget any clock-guard state an earlier test left behind (in memory and in the DB).
    with db.engine.begin() as conn:
        conn.execute(db.clock_guard.delete())
    license.state.last_seen = None
    license.state.next_sync = 0.0
    license.install(make())
