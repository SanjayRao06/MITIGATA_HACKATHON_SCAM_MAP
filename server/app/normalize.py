"""Turn the many ways people type an identifier into ONE stored key.

"+91 98765 43210", "09876543210" and "98765-43210" are the same phone, so they must become
the same key ("+919876543210") or our report counts would be split. These are pure functions
(no database, no network), so they are easy to test.
Anything we can't make sense of raises `InvalidIdentifier`, which the API turns into a 400.
"""

import re
from urllib.parse import urlsplit

# The four identifier types the API accepts.
IDENTIFIER_TYPES = ("phone", "upi", "url", "sender_id")


class InvalidIdentifier(ValueError):
    """Raised when a value can't be normalized. The API maps this to HTTP 400."""


def normalize(identifier_type: str, raw) -> str:
    """Normalize one identifier.

    In: the type ("phone" | "upi" | "url" | "sender_id") and the raw text the user typed.
    Out: the canonical string we store and look up.
    Raises InvalidIdentifier for an unknown type, a non-string, or a value that fails the rules.
    """
    # 1) Basic shape checks shared by every type.
    if identifier_type not in _NORMALIZERS:
        raise InvalidIdentifier(f"unknown identifier_type: {identifier_type!r}")
    if not isinstance(raw, str) or not raw.strip():
        raise InvalidIdentifier("empty value")

    # 2) Hand off to the type-specific rule.
    return _NORMALIZERS[identifier_type](raw)


# ---------------------------------------------------------------- phone
def normalize_phone(raw: str) -> str:
    """Normalize an Indian phone number.

    In: e.g. "+91 98765 43210", "080 2553 0190", "1800 1600", "1930".
    Out: "+91" + 10 digits for normal numbers, or the bare digits for helplines / toll-free.
    Why the junk checks: fake reports often use "9999999999" or "1234567890"; those are
    never real subscriber numbers, so we reject them instead of letting them pile up.
    """
    # 1) Keep only digits, but remember whether the user typed a leading "+".
    text = raw.strip()
    had_plus = text.startswith("+")
    digits = re.sub(r"\D", "", text)
    if not digits:
        raise InvalidIdentifier("phone has no digits")
    n = len(digits)

    # 2) Short helplines like 1930, 1909, 112: 3-4 digits starting with 1. Stored as-is,
    #    but junk like "123", "1234" or "1111" is still rejected (no real helpline looks like that).
    if not had_plus and 3 <= n <= 4 and digits.startswith("1"):
        if _is_junk_digits(digits):
            raise InvalidIdentifier("short number looks like junk")
        return digits

    # 3) Toll-free 1800 / 1860 numbers (8-13 digits). Stored as bare digits, no +91.
    if not had_plus and digits[:4] in ("1800", "1860") and 8 <= n <= 13:
        return digits

    # 4) Find the 10-digit national body.
    if n == 12 and digits.startswith("91"):
        body = digits[2:]                    # 91XXXXXXXXXX -> drop country code
    elif n == 13 and digits.startswith("910"):
        body = digits[3:]                    # "+91 0 98765 43210" -> people often keep the 0 too
    elif had_plus:
        # A "+" means a country code follows. We only accept +91 (India); anything else
        # (e.g. +1 ..., +44 ...) is outside what this app tracks.
        raise InvalidIdentifier("only +91 numbers are supported")
    elif n == 11 and digits.startswith("0"):
        body = digits[1:]                    # 0XXXXXXXXXX -> drop trunk prefix
    elif n == 10:
        body = digits
    else:
        raise InvalidIdentifier("phone has the wrong number of digits")

    # 5) Indian numbers start with 6-9 (mobile) or 2-8 (landline with STD code) -> 2-9.
    if body[0] not in "23456789":
        raise InvalidIdentifier("phone must start with 2-9")

    # 6) Reject obvious junk: all the same digit, or a straight rising run like 2345678901.
    if _is_junk_digits(body):
        raise InvalidIdentifier("phone looks like junk (repeated digit or sequence)")

    return "+91" + body


def _is_junk_digits(digits: str) -> bool:
    """True if the digits are one repeated digit ("9999999999") or a rising run ("1234", "2345678901").

    Falling runs ("9876543210") are NOT junk: real numbers can look like that.
    """
    if len(set(digits)) == 1:
        return True
    return all((int(b) - int(a)) % 10 == 1 for a, b in zip(digits, digits[1:]))


# ---------------------------------------------------------------- upi
_UPI_RE = re.compile(r"^[a-z0-9._-]{2,256}@[a-z][a-z0-9]{1,63}$")


def normalize_upi(raw: str) -> str:
    """Normalize a UPI ID like "Ravi12@OKAXIS" -> "ravi12@okaxis".

    In: raw text. Out: lowercase ID with all whitespace removed.
    UPI IDs are case-insensitive, so lowercasing makes the same ID match every time.
    """
    # 1) Lowercase and remove every whitespace character (people paste " name @bank ").
    value = re.sub(r"\s+", "", raw).lower()

    # 2) Must look like name@handle.
    if not _UPI_RE.match(value):
        raise InvalidIdentifier("not a valid UPI ID")
    return value


# ---------------------------------------------------------------- url
# One DNS label: letters/digits/hyphens, not starting or ending with a hyphen.
_LABEL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


def normalize_url(raw: str) -> str:
    """Normalize a link to "https://" + host + path.

    In: e.g. "http://www.sbi-kyc.in/pay?utm=sms". Out: "https://sbi-kyc.in/pay".
    Why drop query/fragment: scammers add tracking junk (?utm=...) to make each SMS unique;
    the page that matters is host + path. We NEVER remove characters from the host itself -
    "sbi-kyc.in" and "sbikyc.in" are different sites.
    """
    # 1) Trim. If there is no scheme, assume https:// so urlsplit finds the host.
    text = raw.strip()
    if re.search(r"\s", text):
        raise InvalidIdentifier("url contains spaces")
    if "://" not in text:
        text = "https://" + text

    # 2) Parse. Only web links count.
    try:
        parts = urlsplit(text)
        host = parts.hostname or ""          # hostname is already lowercased, port/user removed
    except ValueError as exc:
        raise InvalidIdentifier("url could not be parsed") from exc
    if parts.scheme.lower() not in ("http", "https"):
        raise InvalidIdentifier("only http/https links are supported")

    # 3) Clean the host: strip trailing dot, leading "www.", convert non-ASCII to punycode
    #    (so a lookalike like "sbі.in" with a Cyrillic "і" gets its own distinct key).
    host = host.rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    try:
        host = host.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise InvalidIdentifier("url host has invalid characters") from exc

    # 4) Host must have a dot and every label must be valid.
    labels = host.split(".")
    if len(labels) < 2 or not all(_LABEL_RE.match(label) for label in labels):
        raise InvalidIdentifier("url host is not a valid domain")

    # 5) Force https, drop query + fragment, drop trailing "/" from the path.
    path = parts.path.rstrip("/")
    return "https://" + host + path


# ---------------------------------------------------------------- sender_id
def normalize_sender(raw: str) -> str:
    """Normalize an SMS sender header like "AD-HDFCBK" -> "HDFCBK".

    In: raw text. Out: exactly 6 uppercase letters/digits.
    Why: Indian SMS headers have a 2-letter operator/circle prefix ("VM-", "AD-") that changes
    by network. The real brand part is the last 6 characters, so we keep only that.
    """
    # 1) Optional: strip a trailing type suffix like "-S", "-P", "-T", "-G" (service/promo/...).
    #    Only when separated by "-" or a space, so a header that simply ends in S/P/T/G is kept.
    text = re.sub(r"[-\s][SPTGsptg]$", "", raw.strip())

    # 2) Uppercase and keep only letters/digits (removes "-").
    value = re.sub(r"[^A-Z0-9]", "", text.upper())

    # 3) 8 chars with 2 leading letters = operator prefix + 6-char header -> keep last 6.
    if len(value) == 8 and value[:2].isalpha():
        value = value[2:]

    # 4) Must now be exactly 6 characters.
    if len(value) != 6:
        raise InvalidIdentifier("sender_id must be 6 letters/digits")
    return value


_NORMALIZERS = {
    "phone": normalize_phone,
    "upi": normalize_upi,
    "url": normalize_url,
    "sender_id": normalize_sender,
}
