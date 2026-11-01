"""P1 tests: each trust layer on its own, plus whole attack / real-scam patterns.

These call trust.py directly (no server, no database), so each rule can be checked in isolation.
The most important tests are the "must NOT be blocked" ones: real scams that look a bit like an
attack (a fast real wave, colleagues on one office Wi-Fi) must still become KNOWN_SCAM.
"""

from datetime import datetime, timedelta

from app import trust

NOW = datetime(2026, 10, 31, 12, 0, 0)
_counter = iter(range(1, 100000))

OWN_WORDS = [
    "man in police uniform said my aadhaar was used for a drug parcel and I must pay",
    "mujhe bola arrest warrant nikla hai skype pe aao abhi warna police aayegi",
    "they kept my father on video for three hours and told him not to tell family",
    "caller said cbi case is filed against me and asked me to transfer money to clear it",
    "a lady said she was from customs and the parcel had passports and drugs inside",
    "got a whatsapp video call with a fake police station behind him very convincing",
    "he knew my full name and address and said my bank account would be frozen tonight",
    "said the case would be closed only if I paid a security deposit through upi",
]


def rep(reporter, ip, hours_ago, note="", pin="560102", lost=0, shot=False):
    """One report dict in the shape trust.assess() expects."""
    t = NOW - timedelta(hours=hours_ago)
    return {"id": next(_counter), "reporter_hash": reporter, "ip_hash": ip, "occurred_at": t,
            "reported_at": t + timedelta(minutes=10), "note": note, "pincode": pin,
            "amount_lost_inr": lost, "has_screenshot": shot}


def judge(reports, history=None, flagged=None, verified=False):
    """Run the trust rules with no reporter history unless given."""
    return trust.assess(reports, history or {}, flagged or set(), verified)


# ---------------------------------------------------------------- L3 notes
def test_copy_paste_is_similar_own_words_are_not():
    a = trust.note_words("This bakery is cheating customers, fake number, do not call!!")
    b = trust.note_words("this bakery is cheating customers fake number do not call")
    c = trust.note_words(OWN_WORDS[0])
    d = trust.note_words(OWN_WORDS[3])
    assert trust.note_similarity(a, b) == 1.0
    assert trust.note_similarity(c, d) < 0.3


def test_note_kinds():
    assert trust.note_kind([], False) == "empty"
    assert trust.note_kind(["scam"], False) == "generic"
    assert trust.note_kind(trust.note_words(OWN_WORDS[0]), False) == "personal"
    assert trust.note_kind(trust.note_words(OWN_WORDS[0]), True) == "copy"


# ---------------------------------------------------------------- L5 reputation
def test_reputation_levels():
    assert trust.reputation(0, False) == 0.6
    assert trust.reputation(2, False) == 0.8
    assert trust.reputation(5, False) == 1.0
    assert trust.reputation(9, True) == 0.3      # flagged always wins


# ---------------------------------------------------------------- rate limit
def test_rate_limit_fourth_in_an_hour_is_blocked():
    times = [NOW - timedelta(minutes=m) for m in (50, 35, 20)]
    assert trust.over_rate_limit(NOW, times) is True
    assert trust.over_rate_limit(NOW, times[:2]) is False


def test_rate_limit_spread_out_is_fine():
    # 4 reports spread over 4 hours: never more than 3 in any hour.
    times = [NOW - timedelta(hours=h) for h in (1.5, 3, 4.5)]
    assert trust.over_rate_limit(NOW, times) is False


def test_rate_limit_ignores_arrival_order():
    # A report from the past, arriving after newer ones (the test tool replays out of order).
    later = [NOW + timedelta(minutes=m) for m in (5, 15, 25)]
    assert trust.over_rate_limit(NOW, later) is True


def test_rate_limit_daily_cap():
    times = [NOW - timedelta(hours=h) for h in range(1, 21)]   # 20 in the last day, 1 per hour
    assert trust.over_rate_limit(NOW, times) is True


# ---------------------------------------------------------------- attacks (must be stopped)
def test_same_person_many_times_is_one_source():
    reports = [rep("spammer", "ip1", 1 - i * 0.1, note="scam call fraud") for i in range(6)]
    result = judge(reports)
    assert result["trusted_sources"] <= 1
    assert result["known_scam_allowed"] is False


def test_wifi_farm_22_accounts_is_one_source():
    reports = [rep(f"fake{i}", "same_wifi", 1.5 - i * 0.06, note=["", "scam", "fraud number"][i % 3])
               for i in range(22)]
    result = judge(reports)
    assert result["trusted_sources"] <= 1
    assert result["explain"]["independent_sources"] == 1
    assert result["known_scam_allowed"] is False


def test_bakery_bomb_40_friends_is_coordinated():
    copy = "This bakery is cheating customers, fake number, do not call or pay them!!"
    notes = [copy, copy, copy, "", "", "scam", "fraud"]
    reports = [rep(f"friend{i}", f"home{i % 25}", 2 - i * 0.05, note=notes[i % 7], pin="560038")
               for i in range(40)]
    result = judge(reports)
    assert result["coordination"] >= trust.COORD_THRESHOLD
    assert result["known_scam_allowed"] is False
    assert result["trusted_sources"] < trust.KNOWN_SCAM_MIN_SOURCES   # stays masked


def test_verified_number_reports_are_never_trusted():
    reports = [rep(f"p{i}", f"net{i}", 10 + i * 5, note=OWN_WORDS[i]) for i in range(5)]
    result = judge(reports, verified=True)
    assert result["trusted_sources"] == 0
    assert result["known_scam_allowed"] is False


def test_flagged_reporters_count_less():
    reports = [rep(f"p{i}", f"net{i}", 10 + i * 5, note=OWN_WORDS[i]) for i in range(3)]
    result = judge(reports, flagged={"p0", "p1", "p2"})
    assert result["trusted_sources"] == 0


# ---------------------------------------------------------------- real scams (must NOT be stopped)
def test_real_campaign_8_people_is_known_scam():
    reports = [rep(f"real{i}", f"net{i % 6}", 70 - i * 8.5, note=OWN_WORDS[i],
                   pin=["560102", "560034", "560076", "560011"][i % 4],
                   lost=[0, 15000][i % 2], shot=(i % 3 == 0)) for i in range(8)]
    result = judge(reports)
    assert result["known_scam_allowed"] is True
    assert result["trusted_sources"] >= 3


def test_fast_real_wave_within_two_hours_still_known_scam():
    # A real campaign can also arrive in a burst ([PRD §4] "Caution"): all new people, all within
    # 2 hours, but different networks, areas and words, and some lost money.
    pins = ["560102", "560034", "560076", "560011", "560078", "560003"]
    reports = [rep(f"real{i}", f"net{i}", 2 - i * 0.3, note=OWN_WORDS[i], pin=pins[i],
                   lost=[0, 5000][i % 2]) for i in range(6)]
    result = judge(reports)
    assert result["coordination"] < trust.COORD_THRESHOLD
    assert result["known_scam_allowed"] is True


def test_real_wave_in_one_area_within_an_hour_still_known_scam():
    # [PRD §4] "Caution": a scam call blast can hit ONE neighbourhood in one hour. Everyone is new
    # and nobody lost money yet, but they are on different networks and wrote their own words,
    # so this is independent voices, not an organised wave.
    reports = [rep(f"neighbour{i}", f"net{i}", 1 - i * 0.1, note=OWN_WORDS[i], pin="560102")
               for i in range(8)]
    result = judge(reports)
    assert result["coordination"] >= trust.COORD_THRESHOLD      # the raw score alone would block it
    assert result["explain"]["independent_voices"] is True
    assert result["explain"]["coordinated"] is False
    assert result["known_scam_allowed"] is True


def test_bomb_with_a_few_personal_notes_is_still_coordinated():
    # 40 friends where only some write their own words: not enough independent voices.
    copy = "This bakery is cheating customers, fake number, do not call or pay them!!"
    reports = [rep(f"friend{i}", f"home{i}", 2 - i * 0.04,
                   note=OWN_WORDS[i % 8] if i % 4 == 0 else copy, pin="560038") for i in range(40)]
    result = judge(reports)
    assert result["explain"]["independent_voices"] is False
    assert result["known_scam_allowed"] is False


def test_colleagues_on_one_office_wifi_plus_others_still_known_scam():
    # Two colleagues share the office network (merged into one source), plus 3 people elsewhere.
    reports = [rep("colleague1", "office", 5, note=OWN_WORDS[0]),
               rep("colleague2", "office", 4, note=OWN_WORDS[1])]
    reports += [rep(f"other{i}", f"home{i}", 20 + i * 10, note=OWN_WORDS[i + 2],
                    pin=["560034", "560076", "560011"][i]) for i in range(3)]
    result = judge(reports)
    assert result["explain"]["merged_by_same_network"] == 1
    assert result["trusted_sources"] == 4
    assert result["known_scam_allowed"] is True


def test_two_real_people_is_not_enough():
    reports = [rep("a", "n1", 10, note=OWN_WORDS[0]), rep("b", "n2", 30, note=OWN_WORDS[1], pin="560034")]
    result = judge(reports)
    assert result["trusted_sources"] == 2
    assert result["known_scam_allowed"] is False


def test_established_reporters_are_not_penalised_by_coordination():
    # Same coordinated-looking pattern, but these people have a track record on other numbers:
    # the penalty only hits brand-new accounts.
    copy = "scam number do not pick up"
    reports = [rep(f"vet{i}", f"home{i}", 1 - i * 0.1, note=copy, pin="560038") for i in range(5)]
    history = {f"vet{i}": 3 for i in range(5)}
    result = judge(reports, history=history)
    assert result["explain"]["coordinated"] is True
    assert result["trusted_sources"] >= 1          # copy-paste still merges them into one source
    assert result["known_scam_allowed"] is False   # ...and coordination still blocks KNOWN_SCAM


# ---------------------------------------------------------------- explain output is safe
def test_explain_has_counts_only():
    reports = [rep(f"secret_reporter_{i}", f"secret_ip_{i}", 5 + i, note="my neighbour Sunil") for i in range(3)]
    text = str(judge(reports)["explain"])
    for leak in ["secret_reporter", "secret_ip", "Sunil"]:
        assert leak not in text
