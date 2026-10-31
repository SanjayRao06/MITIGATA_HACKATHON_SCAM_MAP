"""POST /challenges logic: a business disputes a number ([PRD §A.7], bonus feature).

Example: Fresh Bakes says "+91 80 4100 2233 is our real shop number". After a dispute, /lookup
shows `"challenged": true` and the number can never be KNOWN_SCAM while it is under review.

Design choices (explain in the README):
- A dispute never deletes reports and never clears a number automatically. It only softens the
  label to "under review", so a scammer who disputes their own number still shows as reported.
- We do NOT lower the reputation of people who reported a disputed number: anyone can file a
  dispute (there is no approval step), so doing that would let a scammer punish honest reporters.
- The claimant's name, email and proof are stored for a human reviewer only. They are never
  logged and never returned by any endpoint (privacy, docs/04).
"""

import re

from sqlalchemy import insert, update

from app.db import challenges, engine, identifiers
from app.normalize import IDENTIFIER_TYPES, InvalidIdentifier, normalize
from app.reports import _get_or_create_identifier
from app.timeutil import now_utc

MAX_NAME_CHARS = 200
MAX_PROOF_CHARS = 2000
# A simple, forgiving email check: something@something.something, no spaces.
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ChallengeError(ValueError):
    """A dispute we must reject. The message becomes {"error": "..."} with status 400."""


def validate_challenge(body) -> dict:
    """Check a dispute and return a cleaned copy.

    In: the parsed JSON body. Out: dict with normalized identifier + trimmed claimant fields.
    Raises ChallengeError for a bad identifier, missing business name or invalid email.
    """
    # 1) Must be a JSON object.
    if not isinstance(body, dict):
        raise ChallengeError("body must be a JSON object")

    # 2) Identifier: same normalizer as reports and lookups, so any format of the number works.
    id_type = body.get("identifier_type")
    id_type = id_type.strip().lower() if isinstance(id_type, str) else id_type
    if id_type not in IDENTIFIER_TYPES:
        raise ChallengeError("identifier_type must be one of phone, upi, url, sender_id")
    try:
        value = normalize(id_type, body.get("identifier_value"))
    except InvalidIdentifier:
        raise ChallengeError("invalid identifier_value") from None

    # 3) Who is disputing: a business name and a contact email are required.
    name = body.get("claimant_name")
    if not isinstance(name, str) or not name.strip():
        raise ChallengeError("claimant_name is required")
    email = body.get("contact_email")
    if not isinstance(email, str) or not EMAIL_RE.match(email.strip()):
        raise ChallengeError("contact_email must be a valid email address")
    proof = body.get("proof_note")
    proof = proof.strip()[:MAX_PROOF_CHARS] if isinstance(proof, str) else None

    return {"identifier_type": id_type, "identifier_value": value,
            "claimant_name": name.strip()[:MAX_NAME_CHARS], "contact_email": email.strip()[:256],
            "proof_note": proof or None}


def save_challenge(clean: dict) -> dict:
    """Store a dispute and mark the identifier as under review.

    In: output of validate_challenge(). Out: {"challenge_id", "status"} for the 201 reply.
    Works even if nobody has reported the number yet (the case is created).
    """
    with engine.begin() as conn:
        # 1) Find or create the case for this identifier.
        ident_id = _get_or_create_identifier(conn, clean["identifier_type"], clean["identifier_value"])

        # 2) Save the dispute for a human reviewer.
        result = conn.execute(insert(challenges).values(
            identifier_id=ident_id, claimant_name=clean["claimant_name"],
            contact_email=clean["contact_email"], proof_note=clean["proof_note"],
            status="under_review", created_at=now_utc()))
        challenge_pk = result.inserted_primary_key[0]

        # 3) Flag the identifier: /lookup will show challenged=true and never KNOWN_SCAM.
        conn.execute(update(identifiers).where(identifiers.c.id == ident_id).values(challenged=True))

    return {"challenge_id": f"chal_{challenge_pk}", "status": "under_review"}
