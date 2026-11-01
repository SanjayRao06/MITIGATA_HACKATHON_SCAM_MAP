"""Step 1 tests: reference data loads and the helpers behave as docs/02 describes."""

from app import reference
from app.normalize import normalize

reference.load()


# The brief's 25 areas ([PRD Appendix B]). We add 3 more localities per other city for the demo map,
# but these 25 must always be there, unchanged.
PRD_PINCODES = ("560102 560038 560034 560066 560076 560011 560037 560103 560100 560078 560003 560010 560024 "
                "560064 560070 400050 110016 500081 600020 411014 700091 380015 302017 226010 682030").split()


def test_areas_loaded():
    assert len(reference.AREAS) == 55
    assert all(reference.get_area(p) is not None for p in PRD_PINCODES)
    assert reference.get_area("400050")["locality"] == "Bandra West"   # a brief area keeps its name
    assert reference.get_area("560038")["locality"] == "Indiranagar"
    assert reference.get_area(560038) is not None      # int pincode also works
    assert reference.get_area("999999") is None


def test_verified_list_matches_any_typed_form():
    # load() already raises on a mismatch; here we check that differently-typed forms hit the list.
    for raw in ["1800 1600", "1800-1600", "18001600"]:
        assert reference.get_verified("phone", normalize("phone", raw))["belongs_to"].startswith("HDFC")
    assert reference.get_verified("sender_id", normalize("sender_id", "VM-HDFCBK")) is not None
    assert reference.get_verified("upi", normalize("upi", "FreshBakes@OKAXIS")) is not None
    assert reference.get_verified("url", normalize("url", "https://www.cybercrime.gov.in/")) is not None
    assert reference.get_verified("phone", normalize("phone", "080 4100 2233")) is not None
    assert reference.get_verified("phone", "+919876543210") is None


def test_unknown_channel_and_scam_type_fall_back():
    assert reference.canonical_channel("Phone call") == "Phone call"
    assert reference.canonical_channel("  sms or whatsapp ") == "SMS or WhatsApp"
    assert reference.canonical_channel("Carrier pigeon") == "Something else"
    assert reference.canonical_channel(None) == "Something else"
    assert reference.canonical_scam_type("digital-arrest") == "digital-arrest"
    assert reference.canonical_scam_type("alien-invasion") == "other"
    assert reference.canonical_scam_type(None) == "other"
