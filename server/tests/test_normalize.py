"""Step 1 tests: every example from docs/02-normalization.md, plus a few edge cases."""

import pytest

from app.normalize import InvalidIdentifier, normalize


def ok(kind, raw, expected):
    """Helper: assert raw normalizes to expected."""
    assert normalize(kind, raw) == expected


def bad(kind, raw):
    """Helper: assert raw is rejected (the API turns this into a 400)."""
    with pytest.raises(InvalidIdentifier):
        normalize(kind, raw)


# ---------------------------------------------------------------- phone
@pytest.mark.parametrize("raw", ["+91 98765 43210", "09876543210", "98765-43210", "919876543210",
                                 "+91-98765-43210", "(+91) 9876543210", " 9876543210 ",
                                 "+91 0 98765 43210"])
def test_phone_mobile_formats_all_match(raw):
    ok("phone", raw, "+919876543210")


@pytest.mark.parametrize("raw,expected", [
    ("+91 80 4100 2233", "+918041002233"),
    ("080 2553 0190", "+918025530190"),
    ("1800 1600", "18001600"),
    ("1860 419 5555", "18604195555"),
    ("1930", "1930"),
    ("1909", "1909"),
    ("112", "112"),
    ("1800-266-2666", "18002662666"),
])
def test_phone_landline_tollfree_helpline(raw, expected):
    ok("phone", raw, expected)


@pytest.mark.parametrize("raw", [
    "12345", "test", "", "   ",
    "9999999999",          # one repeated digit
    "1234567890",          # straight sequence (also starts with 1)
    "0123456789",          # straight sequence
    "2345678901",          # rising run that wraps 9 -> 0
    "+91 1234567891",      # body starts with 1
    "0987654321",          # 10 digits starting with 0
    "+1 415 555 0100",     # non-Indian country code
    "98765432101234",      # too long
    "123", "1234", "1111", # junk short codes (look like helplines but aren't)
])
def test_phone_invalid(raw):
    bad("phone", raw)


def test_phone_descending_digits_are_allowed():
    # 9876543210 is the docs' own example, so only *rising* runs count as junk.
    ok("phone", "9876543210", "+919876543210")


# ---------------------------------------------------------------- upi
@pytest.mark.parametrize("raw,expected", [
    ("Ravi12@OKAXIS", "ravi12@okaxis"),
    (" freshbakes @okaxis ", "freshbakes@okaxis"),
    ("refund.help-1_x@ybl", "refund.help-1_x@ybl"),
])
def test_upi_valid(raw, expected):
    ok("upi", raw, expected)


@pytest.mark.parametrize("raw", ["ravi", "@okaxis", "ravi@", "r@okaxis", "ravi@1bank", "ravi@ok@axis", ""])
def test_upi_invalid(raw):
    bad("upi", raw)


# ---------------------------------------------------------------- url
@pytest.mark.parametrize("raw,expected", [
    ("http://www.sbi-kyc.in/pay?utm=sms", "https://sbi-kyc.in/pay"),
    ("https://cybercrime.gov.in/", "https://cybercrime.gov.in"),
    ("sbi-kyc.in/pay", "https://sbi-kyc.in/pay"),
    ("HTTPS://WWW.SBI-KYC.IN/Pay/#top", "https://sbi-kyc.in/Pay"),
    ("https://sbi-kyc.in:8443/pay", "https://sbi-kyc.in/pay"),
    ("https://sbi.co.in@evil-site.in/login", "https://evil-site.in/login"),  # real host is after @
])
def test_url_valid(raw, expected):
    ok("url", raw, expected)


def test_url_keeps_hyphen_in_host():
    # Never remove characters from the host: these are two different sites.
    assert normalize("url", "sbi-kyc.in") != normalize("url", "sbikyc.in")


@pytest.mark.parametrize("raw", ["notaurl", "http://", "ftp://files.example.in", "https://-bad-.in",
                                 "https://exa mple.in", "https://.in", ""])
def test_url_invalid(raw):
    bad("url", raw)


# ---------------------------------------------------------------- sender_id
@pytest.mark.parametrize("raw,expected", [
    ("HDFCBK", "HDFCBK"),
    ("VMHDFCBK", "HDFCBK"),
    ("AD-HDFCBK", "HDFCBK"),
    ("vm-hdfcbk", "HDFCBK"),
    ("AD-HDFCBK-S", "HDFCBK"),
    ("JD-ICICIB-T", "ICICIB"),
])
def test_sender_valid(raw, expected):
    ok("sender_id", raw, expected)


@pytest.mark.parametrize("raw", ["HDFC", "HDFCBANK1", "AD-HDF", "", "!!!!!!"])
def test_sender_invalid(raw):
    bad("sender_id", raw)


# ---------------------------------------------------------------- general
def test_unknown_type_rejected():
    bad("email", "a@b.com")


def test_non_string_rejected():
    bad("phone", None)
    bad("phone", 9876543210)
