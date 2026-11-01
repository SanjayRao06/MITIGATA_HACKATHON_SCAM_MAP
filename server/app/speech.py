"""Hindi (and English) speech for the website's "Read aloud" button, for devices with no Hindi voice.

The website first uses the phone's own text-to-speech. Many phones and laptops have no Hindi voice
installed, so then it asks us: GET /speak?lang=hi&text=... returns an MP3 made with Microsoft's
free neural voices (Swara for Hindi, Neerja for English) via the `edge-tts` package.

Privacy and safety:
- The website only ever sends text that's already on screen (verdict, headline, safety advice),
  never the identifier. We refuse any text with 5+ digits in a row, so a phone number, UPI handle
  digits or account number can't be spoken through us even by a hand-made request.
- The text is never logged (the request logger drops query strings) and never stored on disk.
- Results are cached in memory: the same few sentences repeat, so after the first play it's instant
  and we rarely call Microsoft at all.
- Like every other endpoint, this is locked when the licence expires.
"""

import re
import threading
from collections import OrderedDict

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, Response

from app.privacy import log

VOICES = {"hi": "hi-IN-SwaraNeural", "en": "en-IN-NeerjaNeural"}
MAX_CHARS = 600                      # a full result card is ~250-400 characters
LONG_NUMBER = re.compile(r"\d{5,}")  # never speak phone numbers / ids (1930 and counts are fine)
CACHE_SIZE = 200                     # recent MP3s kept in memory (each ~50-100 KB)

_cache: "OrderedDict[tuple[str, str], bytes]" = OrderedDict()
_lock = threading.Lock()

router = APIRouter()


def synthesize(text: str, lang: str) -> bytes:
    """Turn text into MP3 bytes with the neural voice for `lang`. Raises on any failure.

    Kept as one small function so tests can replace it (tests never call the internet).
    """
    import asyncio

    import edge_tts   # imported here: the server still starts if the package is missing

    async def run() -> bytes:
        audio = b""
        async for chunk in edge_tts.Communicate(text, VOICES[lang], rate="-5%").stream():
            if chunk["type"] == "audio":
                audio += chunk["data"]
        return audio

    audio = asyncio.run(run())   # we're in a worker thread, so a fresh event loop is fine
    if not audio:
        raise RuntimeError("no audio returned")
    return audio


def speech_for(text: str, lang: str) -> bytes:
    """MP3 for (text, lang), from the cache or freshly made (then cached)."""
    key = (lang, text)
    with _lock:
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]
    audio = synthesize(text, lang)
    with _lock:
        _cache[key] = audio
        while len(_cache) > CACHE_SIZE:
            _cache.popitem(last=False)
    return audio


@router.get("/speak", include_in_schema=False)
async def speak(lang: str = "", text: str = ""):
    """Read-aloud audio for the website. In: lang (hi | en) and the text. Out: audio/mpeg.

    400 for a bad language, empty/too-long text, or text containing a long number.
    503 if the voice service can't be reached (the website then shows a short message).
    """
    # 1) Check the request.
    lang, text = lang.strip().lower(), " ".join(text.split())
    if lang not in VOICES or not text or len(text) > MAX_CHARS or LONG_NUMBER.search(text):
        return JSONResponse(status_code=400, content={"error": "invalid speech request"})

    # 2) Make (or reuse) the audio, off the main thread.
    try:
        audio = await run_in_threadpool(speech_for, text, lang)
    except Exception as exc:  # noqa: BLE001 - a voice-service hiccup must never break the site
        log.warning("speech unavailable: %s", type(exc).__name__)
        return JSONResponse(status_code=503, content={"error": "SPEECH_UNAVAILABLE"})

    # 3) Browsers may keep it for a day: the same text always gives the same audio.
    return Response(content=audio, media_type="audio/mpeg", headers={"Cache-Control": "public, max-age=86400"})
