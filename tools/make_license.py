"""Make a signed licence file ([PRD §6] step 2), using the private key from tools/keygen.py.

The licence says who may use the server and until when. Its signature covers every field, so
editing the date (or anything else) makes the server reject it.

Usage (from the repo root; `licenses/` is git-ignored):
    server\\.venv\\Scripts\\python tools\\make_license.py --licensee "Demo Bank" --minutes 5 --out licenses\\short.json
    server\\.venv\\Scripts\\python tools\\make_license.py --licensee "Demo Bank" --days 365 --out licenses\\long.json
    server\\.venv\\Scripts\\python tools\\make_license.py --licensee "Demo Bank" --expires-at 2026-11-15T10:05:00+05:30

DEMO GOTCHA: expires_at is an absolute time. Make the 5-minute licence at demo time, not before.
"""

import argparse
import base64
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from nacl.signing import SigningKey

IST = timezone(timedelta(hours=5, minutes=30))
DEFAULT_KEY = Path(__file__).resolve().parents[1] / "private.key"


def canonical_bytes(lic: dict) -> bytes:
    """Bytes to sign: every field except the signature, keys sorted, no spaces.

    MUST stay identical to canonical_bytes() in server/app/license.py (a test checks this).
    """
    unsigned = {k: v for k, v in lic.items() if k != "signature"}
    return json.dumps(unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def make_licence(licensee: str, expires_at: datetime, signing_key: SigningKey) -> dict:
    """In: licensee name, expiry time, private key. Out: the licence dict with its signature."""
    now = datetime.now(IST)
    lic = {
        "licensee": licensee,
        "expires_at": expires_at.astimezone(IST).isoformat(timespec="seconds"),
        "issued_at": now.isoformat(timespec="seconds"),
    }
    lic["signature"] = base64.b64encode(signing_key.sign(canonical_bytes(lic)).signature).decode()
    return lic


def load_key(path: Path) -> SigningKey:
    """Read the base64 private key written by keygen.py."""
    return SigningKey(base64.b64decode(path.read_text(encoding="ascii").strip()))


def main(argv=None) -> int:
    """Command line: work out the expiry, sign, print or save the licence."""
    parser = argparse.ArgumentParser(description="Make a signed licence file.")
    parser.add_argument("--licensee", required=True, help='who may use the server, e.g. "Demo Bank"')
    when = parser.add_mutually_exclusive_group(required=True)
    when.add_argument("--minutes", type=float, help="valid for this many minutes from now")
    when.add_argument("--days", type=float, help="valid for this many days from now")
    when.add_argument("--expires-at", help="exact expiry, e.g. 2026-11-15T10:05:00+05:30")
    parser.add_argument("--key", type=Path, default=DEFAULT_KEY, help="private key file")
    parser.add_argument("--out", type=Path, help="write to this file (default: print it)")
    args = parser.parse_args(argv)

    # 1) The expiry: relative to now, or an exact time (no offset given = India time).
    if args.expires_at:
        expires = datetime.fromisoformat(args.expires_at)
        expires = expires if expires.tzinfo else expires.replace(tzinfo=IST)
    else:
        expires = datetime.now(IST) + timedelta(minutes=args.minutes or 0, days=args.days or 0)

    # 2) Sign it with the private key.
    if not args.key.exists():
        print(f"No private key at {args.key}. Run tools/keygen.py first (or pass --key).")
        return 1
    lic = make_licence(args.licensee, expires, load_key(args.key))

    # 3) Save or print.
    text = json.dumps(lic, indent=2, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
        print(f"Wrote {args.out}: {lic['licensee']}, expires {lic['expires_at']}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
