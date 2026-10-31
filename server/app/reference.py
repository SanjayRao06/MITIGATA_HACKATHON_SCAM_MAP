"""Reference data from the brief's appendix, loaded once from `app/data/*.json`.

- areas.json: the 25 pincodes we accept, with locality, city and a centre lat/lng for the map.
- verified.json: known-good business/helpline identifiers. This is the ONLY identifier list
  allowed in our code (CLAUDE.md hard rule 2) - lookups of these say VERIFIED_BUSINESS.
- scam_types.json: allowed channels and scam types. Unknown values are not rejected;
  they are stored as "Something else" / "other" (docs/02).
"""

import json
from pathlib import Path

from app.normalize import IDENTIFIER_TYPES, normalize

DATA_DIR = Path(__file__).parent / "data"

# Filled by load(). Module-level so every other module can just `from app import reference`.
AREAS: dict[str, dict] = {}                     # pincode -> {pincode, locality, city, lat, lng}
VERIFIED: dict[tuple[str, str], dict] = {}      # (type, normalized) -> entry
CHANNELS: list[str] = []
SCAM_TYPES: dict[str, str] = {}                 # slug -> description
FALLBACK_CHANNEL = "Something else"
FALLBACK_SCAM_TYPE = "other"


def _read(name: str):
    """Read one JSON file from the data folder. In: file name. Out: parsed JSON."""
    with open(DATA_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def load() -> None:
    """Load (or reload) all reference data into the module-level dicts.

    In: nothing (reads app/data/*.json). Out: nothing.
    Raises if a file is missing or a verified entry doesn't normalize to its stated value -
    we'd rather crash at startup than silently fail to recognise a verified business.
    """
    global FALLBACK_CHANNEL, FALLBACK_SCAM_TYPE

    # 1) Areas, keyed by pincode for O(1) validation.
    AREAS.clear()
    for area in _read("areas.json"):
        AREAS[str(area["pincode"])] = area

    # 2) Verified list. We re-run our own normalizer on each "raw" value and check it gives
    #    the stated "normalized" value, so the list and the normalizer can never drift apart.
    VERIFIED.clear()
    for entry in _read("verified.json"):
        kind = entry["type"]
        if kind not in IDENTIFIER_TYPES:
            raise ValueError(f"verified.json: unknown type {kind!r}")
        key = normalize(kind, entry["raw"])
        if key != entry["normalized"]:
            raise ValueError(
                f"verified.json: {entry['raw']!r} normalizes to {key!r}, "
                f"file says {entry['normalized']!r}"
            )
        VERIFIED[(kind, key)] = entry

    # 3) Channels and scam types.
    types = _read("scam_types.json")
    CHANNELS[:] = list(types["channels"])
    SCAM_TYPES.clear()
    SCAM_TYPES.update(types["scam_types"])
    FALLBACK_SCAM_TYPE = types.get("unknown_scam_type_maps_to", "other")
    FALLBACK_CHANNEL = "Something else" if "Something else" in CHANNELS else CHANNELS[-1]


def get_area(pincode) -> dict | None:
    """Look up an area. In: pincode (str or int). Out: the area dict, or None if not one of ours."""
    return AREAS.get(str(pincode).strip()) if pincode is not None else None


def get_verified(identifier_type: str, normalized: str) -> dict | None:
    """Is this (already normalized) identifier on the verified list? Out: entry or None."""
    return VERIFIED.get((identifier_type, normalized))


def canonical_channel(channel) -> str:
    """Map a channel to a known one. Unknown/missing -> "Something else" (never rejected).

    Matching ignores case and surrounding spaces, so "sms or whatsapp" still counts.
    """
    if isinstance(channel, str):
        wanted = channel.strip().lower()
        for known in CHANNELS:
            if known.lower() == wanted:
                return known
    return FALLBACK_CHANNEL


def canonical_scam_type(scam_type) -> str:
    """Map a scam type slug to a known one. Unknown/missing -> "other" (never rejected)."""
    if isinstance(scam_type, str):
        slug = scam_type.strip().lower()
        if slug in SCAM_TYPES:
            return slug
    return FALLBACK_SCAM_TYPE
