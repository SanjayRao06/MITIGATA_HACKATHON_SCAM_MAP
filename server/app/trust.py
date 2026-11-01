"""Trust rules: decide how much each report should count.

The idea in one line: don't count REPORTS, count INDEPENDENT HUMANS. A fake wave is one source
wearing many masks; a real scam wave is many unrelated people writing in their own words.

How one identifier's reports are judged (assess() below):
  L1 Same person      - all reports from one reporter_id are one "person".
  L2 Same network     - people on the same ip_prefix reporting within 24 h merge into one source
                        (22 accounts on one Wi-Fi = 1).
  L3 Copy-paste notes - people whose notes are (nearly) identical merge into one source.
                        Each person's note also changes their weight: personal story x1.2,
                        empty x1.0, short generic ("scam") x0.9, copy-pasted x0.8.
  L4 Coordination     - for 3+ people we score 6 warning signs (burst, all new accounts, few
                        networks, one area, empty/duplicate notes, nobody lost money). Score >= 0.6
                        means "looks organised": brand-new accounts count x0.2 and KNOWN_SCAM is blocked.
                        Exception: if >= 80% of people wrote their own unique words from their own
                        networks, it is a real wave of independent voices, not an organised one.
  L5 Reputation       - new reporter 0.6; a track record on other numbers raises it to 0.8 / 1.0;
                        someone who reported a verified business drops to 0.3.
Then: a source is TRUSTED if its weight >= 0.5. KNOWN_SCAM needs >= 3 trusted sources from >= 3
different networks, no coordination, and no open dispute. `distinct_reporters` = trusted sources.

Everything here is a pure function of the report data (no database), so it is easy to test and
explain. All numbers are named constants at the top, tuned with tools/scenarios.py.
"""

import re
from datetime import timedelta

# ---------------------------------------------------------------- tunable constants
TRUSTED_WEIGHT = 0.5            # a source counts as an independent person at or above this weight
KNOWN_SCAM_MIN_SOURCES = 3      # trusted sources needed for KNOWN_SCAM (and to unmask)
KNOWN_SCAM_MIN_NETWORKS = 3     # ...from at least this many different ip_prefixes

NETWORK_MERGE_WINDOW = timedelta(hours=24)   # L2: same ip_prefix within this window = one source
NOTE_SIMILAR = 0.8                           # L3: Jaccard similarity at/above this = copy-paste
PERSONAL_NOTE_WORDS = 8                      # a note this long (and unique) is a personal story
GENERIC_NOTE_WORDS = 3                       # a note this short is generic ("scam", "fraud number")
NOTE_MULT = {"personal": 1.2, "empty": 1.0, "generic": 0.9, "copy": 0.8}

COORD_MIN_PEOPLE = 3            # L4 only makes sense with at least this many people
COORD_THRESHOLD = 0.6           # score at/above this = coordinated wave
COORD_PENALTY = 0.2             # brand-new accounts in a coordinated wave count this much
BURST_WINDOW = timedelta(hours=2)
# A wave is NOT organised when this share (or more) of its people wrote their own unique words AND
# came from different networks: that is exactly how the brief describes a real campaign (
# "many different, unrelated people writing in their own words"). Without this, a real wave that
# hits ONE neighbourhood within an hour (all new accounts, nobody lost money yet) looked organised.
INDEPENDENT_VOICES = 0.8

REP_NEW = 0.6                   # L5: first-time reporter
REP_SOME_HISTORY = 0.8          # 2+ other numbers reported earlier
REP_ESTABLISHED = 1.0           # 5+ other numbers reported earlier
REP_FLAGGED = 0.3               # reported a verified business / disputed number before
HISTORY_SOME, HISTORY_ESTABLISHED = 2, 5


# ---------------------------------------------------------------- notes (L3)
def note_words(note) -> list[str]:
    """Lowercase words of a note with punctuation and digits removed ("Lost 5000!!" -> ["lost"])."""
    if not note:
        return []
    return re.findall(r"[^\W\d_]+", note.lower())


def note_similarity(a: list[str], b: list[str]) -> float:
    """How alike two notes are, 0..1 (Jaccard on 3-word chunks; on words for very short notes).

    Copy-paste gives 1.0; two people describing the same scam in their own words stay low.
    """
    if not a or not b:
        return 0.0
    if len(a) < 3 or len(b) < 3:                  # too short for 3-word chunks: compare word sets
        sa, sb = set(a), set(b)
    else:
        sa = {tuple(a[i:i + 3]) for i in range(len(a) - 2)}
        sb = {tuple(b[i:i + 3]) for i in range(len(b) - 2)}
    return len(sa & sb) / len(sa | sb)


def note_kind(words: list[str], is_copy: bool) -> str:
    """Classify one person's note: 'copy', 'empty', 'generic' or 'personal'."""
    if is_copy:
        return "copy"
    if not words:
        return "empty"
    if len(words) <= GENERIC_NOTE_WORDS:
        return "generic"
    return "personal" if len(words) >= PERSONAL_NOTE_WORDS else "generic"


# ---------------------------------------------------------------- reputation (L5)
def reputation(history_count: int, flagged: bool) -> float:
    """Base weight of one reporter. In: how many OTHER numbers they reported earlier, flagged?"""
    if flagged:
        return REP_FLAGGED
    if history_count >= HISTORY_ESTABLISHED:
        return REP_ESTABLISHED
    if history_count >= HISTORY_SOME:
        return REP_SOME_HISTORY
    return REP_NEW


# ---------------------------------------------------------------- small union-find for merging
class _Groups:
    """Keeps track of which people have been merged into one source (union-find)."""

    def __init__(self, keys):
        self.parent = {k: k for k in keys}

    def find(self, k):
        while self.parent[k] != k:
            self.parent[k] = self.parent[self.parent[k]]
            k = self.parent[k]
        return k

    def join(self, a, b):
        self.parent[self.find(a)] = self.find(b)


def report_time(r):
    """When a report was made: reported_at if given, else occurred_at (both naive UTC)."""
    return r["reported_at"] or r["occurred_at"]


# ---------------------------------------------------------------- coordination (L4)
def coordination(people: dict, reports: list) -> tuple[float, dict]:
    """Score 0..1 for "this looks like an organised wave", plus the 6 signals behind it.

    In: people = {reporter_hash: person dict}, reports = all reports on this identifier.
    Real waves score low because their networks, areas and wording are varied.
    """
    n = len(people)
    if n < COORD_MIN_PEOPLE:
        return 0.0, {}

    # 1) burst: the biggest share of reports inside any 2-hour window.
    times = sorted(report_time(r) for r in reports)
    best, j = 0, 0
    for i, t in enumerate(times):
        while times[j] < t - BURST_WINDOW:
            j += 1
        best = max(best, i - j + 1)
    signals = {"burst": best / len(times)}

    # 2) newness: share of people with no earlier reports on other numbers.
    signals["newness"] = sum(1 for p in people.values() if p["history"] == 0) / n
    # 3) and 4) few networks / one area compared with the number of people.
    signals["low_net_diversity"] = 1 - len({r["ip_hash"] for r in reports}) / n
    signals["low_area_diversity"] = 1 - len({r["pincode"] for r in reports}) / n
    # 5) share of people whose note is empty, generic or copy-pasted.
    signals["low_text_diversity"] = sum(1 for p in people.values() if p["note_kind"] != "personal") / n
    # 6) share of reports where nobody lost money and nobody attached a screenshot.
    signals["no_loss"] = sum(1 for r in reports
                             if not r["amount_lost_inr"] and not r["has_screenshot"]) / len(reports)

    signals = {k: round(max(0.0, v), 3) for k, v in signals.items()}
    return round(sum(signals.values()) / len(signals), 3), signals


# ---------------------------------------------------------------- the main entry point
def assess(reports: list, history: dict, flagged: set, verified: bool) -> dict:
    """Judge all reports about ONE identifier.

    In:
      reports  - dicts with id, reporter_hash, ip_hash, occurred_at, reported_at, note, pincode,
                 amount_lost_inr, has_screenshot (one per stored report)
      history  - {reporter_hash: number of OTHER identifiers they reported earlier}
      flagged  - reporter hashes that reported a verified/disputed number before
      verified - True if this identifier is on the verified list (its reports are never trusted)
    Out: dict with trusted_sources, distinct_networks, coordination score + signals, the ids of
    the reports that count as trusted (one per trusted source, used by map/alerts), whether
    KNOWN_SCAM is allowed, and an `explain` summary with counts only (no ids, no notes).
    """
    if not reports:
        return {"trusted_sources": 0, "distinct_networks": 0, "coordination": 0.0, "signals": {},
                "trusted_report_ids": [], "known_scam_allowed": False, "explain": {"reports": 0}}

    # ---- L1: one "person" per reporter_hash -------------------------------------------------
    people = {}
    for r in reports:
        p = people.setdefault(r["reporter_hash"], {"reports": [], "history": history.get(r["reporter_hash"], 0),
                                                   "flagged": r["reporter_hash"] in flagged})
        p["reports"].append(r)
    for h, p in people.items():
        p["reports"].sort(key=report_time)
        longest = max((r["note"] or "" for r in p["reports"]), key=len)   # their most detailed note
        p["words"] = note_words(longest)

    keys = list(people)
    groups = _Groups(keys)

    # ---- L2: same network on the same number within 24 h -> one source ----------------------
    merged_by_network = 0
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            if groups.find(a) == groups.find(b):
                continue
            if any(ra["ip_hash"] == rb["ip_hash"]
                   and abs(report_time(ra) - report_time(rb)) <= NETWORK_MERGE_WINDOW
                   for ra in people[a]["reports"] for rb in people[b]["reports"]):
                groups.join(a, b)
                merged_by_network += 1

    # ---- L3: copy-paste notes -> one source; note kind for each person ----------------------
    copied = set()
    merged_by_note = 0
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            if note_similarity(people[a]["words"], people[b]["words"]) >= NOTE_SIMILAR:
                copied.update((a, b))
                if groups.find(a) != groups.find(b):
                    groups.join(a, b)
                    merged_by_note += 1
    for h, p in people.items():
        p["note_kind"] = note_kind(p["words"], h in copied)

    # ---- L4: is the whole set an organised wave? --------------------------------------------
    coord, signals = coordination(people, reports)
    # Real waves are many unrelated people in their own words: if (nearly) everyone wrote a
    # personal, non-copied note from their own network, burst + one area alone don't make it fake.
    independent_voices = bool(signals) and (
        1 - signals["low_text_diversity"] >= INDEPENDENT_VOICES
        and 1 - signals["low_net_diversity"] >= INDEPENDENT_VOICES)
    coordinated = coord >= COORD_THRESHOLD and not independent_voices

    # ---- L5 + weights: one weight per merged source -----------------------------------------
    sources = {}
    for h in keys:
        sources.setdefault(groups.find(h), []).append(h)

    trusted_ids, trusted_nets, weights = [], set(), []
    for members in sources.values():
        rep = max(reputation(people[h]["history"], people[h]["flagged"]) for h in members)
        mult = max(NOTE_MULT[people[h]["note_kind"]] for h in members)
        weight = rep * mult
        all_new = all(people[h]["history"] == 0 for h in members)
        if coordinated and all_new:
            weight *= COORD_PENALTY
        weights.append(round(weight, 3))
        if weight >= TRUSTED_WEIGHT and not verified:
            # One representative report per trusted source: its earliest one. So a trusted person
            # who reported 3 times still adds only 1 to map counts and alerts.
            first = min((r for h in members for r in people[h]["reports"]), key=report_time)
            trusted_ids.append(first["id"])
            trusted_nets.update(r["ip_hash"] for h in members for r in people[h]["reports"])

    trusted_sources = len(trusted_ids)
    allowed = (trusted_sources >= KNOWN_SCAM_MIN_SOURCES and len(trusted_nets) >= KNOWN_SCAM_MIN_NETWORKS
               and not coordinated and not verified)

    return {
        "trusted_sources": trusted_sources,
        "distinct_networks": len(trusted_nets),
        "coordination": coord,
        "signals": signals,
        "trusted_report_ids": trusted_ids,
        "known_scam_allowed": allowed,
        "explain": {
            "reports": len(reports),
            "people (distinct reporter ids)": len(people),
            "merged_by_same_network": merged_by_network,
            "merged_by_copy_paste_notes": merged_by_note,
            "independent_sources": len(sources),
            "source_weights": sorted(weights, reverse=True),
            "coordination_score": coord,
            "coordination_signals": signals,
            "independent_voices": independent_voices,
            "coordinated": coordinated,
            "trusted_sources": trusted_sources,
            "trusted_networks": len(trusted_nets),
            "effective_weight": round(sum(weights), 2),
        },
    }


# ---------------------------------------------------------------- rate limit (429)
RATE_LIMITS = [(timedelta(hours=1), 3), (timedelta(hours=24), 20)]   # (window, max reports in it)


def over_rate_limit(new_time, other_times: list) -> bool:
    """Would one more report at `new_time` put this reporter over a limit?

    In: the new report's time and the times of this reporter's stored reports.
    Times are the REPORTS' OWN times, not arrival time: the test tool replays weeks of reports in
    seconds, so arrival time would wrongly block real people.
    "More than 3 in any 60 minutes" is checked by sliding a window across every position that
    contains the new report.
    """
    for window, limit in RATE_LIMITS:
        nearby = sorted([t for t in other_times if abs(t - new_time) <= window] + [new_time])
        j = 0
        for i, t in enumerate(nearby):
            while nearby[j] < t - window:
                j += 1
            if i - j + 1 > limit and nearby[j] <= new_time <= t:
                return True
    return False
