"""Upload a licence file to a server, show the server's current licence, or prove tampering fails ([PRD §6] demo).

Usage (from the repo root):
    python tools\\upload_license.py licenses\\long.json            # upload to the local server
    python tools\\upload_license.py licenses\\long.json --live     # upload to the live Render server
    python tools\\upload_license.py --show --live                  # just show the live licence
    python tools\\upload_license.py licenses\\long.json --tamper-test --live
        # edits the expiry in memory (+70 years), uploads it, and checks the server says
        # 400 INVALID_SIGNATURE and still holds the old licence. Prints PASS or FAIL.
Standard library only, so it runs with any Python 3.
"""

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

LIVE_URL = "https://mitigata-hackathon-scam-map.onrender.com"


def call(method: str, url: str, body: bytes | None = None):
    """Send one request. Out: (status code, parsed JSON reply)."""
    req = urllib.request.Request(url, data=body, method=method, headers={"content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:   # 90 s: a sleeping free server wakes slowly
            return resp.status, json.loads(resp.read() or b"null")
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read() or b"null")


def tamper_test(url: str, file: Path) -> int:
    """Upload a copy of FILE with its expiry pushed 70 years later; the server must refuse it.

    Why: this is the judges' "what stops someone editing the date?" question, in one command.
    PASS = 400 INVALID_SIGNATURE and the licence the server holds is unchanged.
    """
    # 1) What the server holds before, and a forged copy of the file (only the year changed).
    _, before = call("GET", url)
    lic = json.loads(file.read_text(encoding="utf-8"))
    year = lic["expires_at"][:4]
    lic["expires_at"] = str(int(year) + 70) + lic["expires_at"][4:]
    print(f"Uploading a forged licence: expires_at changed to {lic['expires_at']}")

    # 2) Upload it and check the server said no and kept its licence.
    status, reply = call("POST", url, json.dumps(lic).encode("utf-8"))
    _, after = call("GET", url)
    print(f"HTTP {status} {json.dumps(reply)}")
    ok = (status == 400 and (reply or {}).get("error") == "INVALID_SIGNATURE"
          and (before or {}).get("expires_at") == (after or {}).get("expires_at"))
    print(f"Server still holds: {after.get('licensee')} until {after.get('expires_at')} ({after.get('status')})")
    print("PASS: forged licence rejected, current licence kept" if ok else "FAIL")
    return 0 if ok else 1


def main(argv=None) -> int:
    """Upload FILE to BASE/license (or GET it with --show, or forge it with --tamper-test)."""
    parser = argparse.ArgumentParser(description="Upload or show the server licence.")
    parser.add_argument("file", nargs="?", type=Path, help="licence JSON made by make_license.py")
    parser.add_argument("--base", default="http://127.0.0.1:8000", help="server address")
    parser.add_argument("--live", action="store_true", help=f"use the live server ({LIVE_URL})")
    parser.add_argument("--show", action="store_true", help="only show the current licence")
    parser.add_argument("--tamper-test", action="store_true", help="upload an edited copy of FILE; expect 400")
    args = parser.parse_args(argv)
    base = LIVE_URL if args.live else args.base
    url = base.rstrip("/").replace("://localhost", "://127.0.0.1", 1) + "/license"

    # 1) Tamper test, show only, or upload the file.
    if args.tamper_test:
        if args.file is None:
            parser.error("--tamper-test needs a licence file, e.g. licenses\\long.json")
        return tamper_test(url, args.file)
    if args.show or args.file is None:
        status, reply = call("GET", url)
    else:
        status, reply = call("POST", url, args.file.read_bytes())

    # 2) Print the answer plainly.
    print(f"HTTP {status}")
    print(json.dumps(reply, indent=2, ensure_ascii=False))
    return 0 if status == 200 else 1


if __name__ == "__main__":
    sys.exit(main())
