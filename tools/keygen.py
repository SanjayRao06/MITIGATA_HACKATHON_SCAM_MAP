"""Make our licence signing key pair (run ONCE, on the laptop that will sign licences).

Writes the PRIVATE key to `private.key` (git-ignored: it must never be committed or shared) and
prints the PUBLIC key, which goes into `server/app/license.py` as PUBLIC_KEY_B64.
Whoever has private.key can make licences, so keep a backup somewhere safe (e.g. a password manager).

Usage (from the repo root):
    server\\.venv\\Scripts\\python tools\\keygen.py            # refuses to overwrite an existing key
    server\\.venv\\Scripts\\python tools\\keygen.py --force    # replace it (old licences stop working!)
"""

import argparse
import base64
import sys
from pathlib import Path

from nacl.signing import SigningKey

DEFAULT_KEY = Path(__file__).resolve().parents[1] / "private.key"


def main(argv=None) -> int:
    """Generate an Ed25519 key pair; save the private seed, print the public key."""
    parser = argparse.ArgumentParser(description="Generate the licence signing key pair.")
    parser.add_argument("--out", type=Path, default=DEFAULT_KEY, help="where to write the private key")
    parser.add_argument("--force", action="store_true", help="overwrite an existing private key")
    args = parser.parse_args(argv)

    # 1) Never silently replace a key: every licence signed with the old one would stop working.
    if args.out.exists() and not args.force:
        print(f"{args.out} already exists. Use --force to replace it (old licences will stop working).")
        return 1

    # 2) A random 32-byte seed is the whole private key. Save it as base64 text.
    key = SigningKey.generate()
    args.out.write_text(base64.b64encode(bytes(key)).decode() + "\n", encoding="ascii")

    # 3) The public key is derived from it; it can only CHECK signatures, so it's safe in the code.
    public_b64 = base64.b64encode(bytes(key.verify_key)).decode()
    print(f"Private key written to {args.out} (git-ignored - never commit or share it).")
    print("Paste this into server/app/license.py:")
    print(f'PUBLIC_KEY_B64 = "{public_b64}"')
    return 0


if __name__ == "__main__":
    sys.exit(main())
