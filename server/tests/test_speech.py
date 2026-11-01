"""Tests for GET /speak: Hindi/English "Read aloud" audio for devices with no Hindi voice.

The real voice service is replaced by a fake, so these tests never touch the internet.
"""

import pytest
from fastapi.testclient import TestClient

from app import speech
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def fake_voice(monkeypatch):
    """Swap the voice service for a counter that returns fake MP3 bytes; empty the cache."""
    calls = []

    def fake(text, lang):
        calls.append((text, lang))
        return b"ID3-fake-mp3-" + lang.encode()

    monkeypatch.setattr(speech, "synthesize", fake)
    speech._cache.clear()
    return calls


def test_hindi_text_gives_mp3(fake_voice):
    r = client.get("/speak", params={"lang": "hi", "text": "संदिग्ध। फ़ोन काटें और 1930 पर कॉल करें।"})
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg"
    assert r.content == b"ID3-fake-mp3-hi"
    assert fake_voice == [("संदिग्ध। फ़ोन काटें और 1930 पर कॉल करें।", "hi")]


def test_same_text_is_served_from_memory_the_second_time(fake_voice):
    for _ in range(3):
        assert client.get("/speak", params={"lang": "hi", "text": "सुरक्षित रहें।"}).status_code == 200
    assert len(fake_voice) == 1   # made once, then cached


@pytest.mark.parametrize("params", [
    {"lang": "fr", "text": "Bonjour"},                     # unknown language
    {"lang": "hi", "text": ""},                            # nothing to say
    {"lang": "hi", "text": "अ" * 601},                     # too long
    {"lang": "en", "text": "Call 9876543210 now"},         # a phone number must never be spoken
    {"lang": "en", "text": "account 12345678"},
])
def test_bad_requests_are_400_and_never_reach_the_voice_service(params, fake_voice):
    assert client.get("/speak", params=params).status_code == 400
    assert fake_voice == []


def test_helpline_1930_and_small_counts_are_allowed():
    assert client.get("/speak", params={"lang": "en", "text": "Reported by 7 people. Call 1930."}).status_code == 200


def test_voice_service_down_is_503_not_a_crash(monkeypatch):
    def broken(text, lang):
        raise ConnectionError("offline")
    monkeypatch.setattr(speech, "synthesize", broken)
    r = client.get("/speak", params={"lang": "hi", "text": "सुरक्षित रहें।"})
    assert r.status_code == 503 and r.json() == {"error": "SPEECH_UNAVAILABLE"}


def test_speak_is_locked_when_the_licence_has_expired(monkeypatch):
    from app import license as licence
    monkeypatch.setattr(licence.state, "licence", None)
    monkeypatch.setattr(licence.state, "next_sync", float("inf"))   # don't reload it from the DB
    assert client.get("/speak", params={"lang": "hi", "text": "सुरक्षित रहें।"}).status_code == 403
