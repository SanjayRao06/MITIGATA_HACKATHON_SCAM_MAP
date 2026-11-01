"""Try the "Why this result?" feature in one command, with no server and no Neon.

Builds a throwaway database in a temp folder, loads 5 situations (Wi-Fi farm, real scam, one
person x3, verified helpline, unreported number), looks each one up and prints the verdict and the
reasons in plain English, exactly as the website's panel shows them.

Usage (from the repo root):
    server\\.venv\\Scripts\\python tools\\try_why.py
"""

import json
import os
import re
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 1) A private temp database, set BEFORE the server code is imported (never dev.db, never Neon).
os.environ["DATABASE_URL"] = "sqlite:///" + (Path(tempfile.mkdtemp()) / "try_why.db").as_posix()
os.environ.setdefault("HASH_SECRET", "try-why")
sys.path.insert(0, str(ROOT / "server"))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))
NOTES = [
    "man in police uniform said my aadhaar was used for a drug parcel and I must pay",
    "caller said cbi case is filed against me and asked me to transfer money to clear it",
    "got a whatsapp video call with a fake police station behind him very convincing",
    "he knew my full name and address and said my bank account would be frozen tonight",
]


def ts(hours_ago: float) -> str:
    return (datetime.now(IST) - timedelta(hours=hours_ago)).isoformat(timespec="seconds")


def english_texts() -> dict:
    """The panel's English sentences, read from the website's own i18n.js (so this matches the UI)."""
    js = (ROOT / "server" / "web" / "i18n.js").read_text(encoding="utf-8")
    en = js[: js.index("\n  hi: {")]
    return {m[0]: m[1].replace('\\"', '"') for m in re.findall(r'\bwhy_(\w+): "((?:[^"\\]|\\.)*)"', en)}


def main() -> int:
    with TestClient(app) as c:
        # 2) Licence (the real long one) and an empty database.
        lic = json.loads((ROOT / "licenses" / "long.json").read_text(encoding="utf-8"))
        assert c.post("/license", json=lic).status_code == 200, "licences/long.json not accepted"
        c.post("/admin/reset")

        base = {"channel": "Phone call", "scam_type": "digital-arrest", "identifier_type": "phone",
                "pincode": "560102", "locality": "HSR Layout", "city": "Bengaluru"}
        # A) Wi-Fi farm: 22 accounts on one connection, copy-paste note.
        for i in range(22):
            c.post("/reports", json={**base, "occurred_at": ts(1 + i * 0.02), "reporter_id": f"farm{i}",
                                     "ip_prefix": "49.36.12", "identifier_value": "9811122233",
                                     "note": "fake number do not trust"})
        # B) Real scam: 4 different people, networks and words.
        for i in range(4):
            c.post("/reports", json={**base, "occurred_at": ts(2 + i * 5), "reporter_id": f"real{i}",
                                     "ip_prefix": f"10.{i}.0", "identifier_value": "9876543210",
                                     "note": NOTES[i]})
        # C) One person reporting the same number 3 times.
        for i in range(3):
            c.post("/reports", json={**base, "occurred_at": ts(1 + i * 0.1), "reporter_id": "spammer",
                                     "ip_prefix": "11.0.0", "identifier_value": "9822233344"})

        # 3) Look each one up and print the panel's sentences.
        text = english_texts()
        cases = [("9811122233", "22 accounts on one Wi-Fi", "SUSPICIOUS"),
                 ("9876543210", "4 real, different people", "KNOWN_SCAM"),
                 ("9822233344", "1 person reporting 3 times", "SUSPICIOUS"),
                 ("1930", "national helpline (verified list)", "VERIFIED_BUSINESS"),
                 ("9000000001", "nobody reported it", "NO_REPORTS")]
        ok = True
        for value, story, expected in cases:
            body = c.get("/lookup", params={"type": "phone", "value": value}).json()
            good = body["verdict"] == expected and body.get("why")
            ok &= bool(good)
            print(f"\n{'PASS' if good else 'FAIL'}  {value}  ({story})  ->  {body['verdict']}")
            for n, w in enumerate(body.get("why", []), 1):
                sentence = text.get(w["code"], w["code"])
                for k, v in w.items():
                    sentence = sentence.replace("{" + k + "}", str(v))
                print(f"   {n}. {sentence}")
        print("\nALL PASS" if ok else "\nSOMETHING FAILED")
        return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
