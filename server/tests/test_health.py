"""Tests: /health works and the request log contains nothing personal."""

import logging

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok():
    """GET /health -> 200 {"ok": true} exactly as the API spec says."""
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_log_line_has_no_query_string_or_ip(caplog):
    """Our log line must show method/path/status/ms but never the query string or client IP."""
    # 1) Our logger doesn't propagate to root (on purpose); attach caplog's handler directly.
    logger = logging.getLogger("scam_map")
    logger.addHandler(caplog.handler)
    try:
        client.get("/health?value=+919876543210")
    finally:
        logger.removeHandler(caplog.handler)

    # 2) Check what was written.
    text = caplog.text
    assert "GET /health 200" in text
    assert "9876543210" not in text
    assert "testclient" not in text  # TestClient's fake client host


def test_uvicorn_access_log_disabled():
    """Uvicorn's own access log prints IPs, so setup_logging() must switch it off."""
    assert logging.getLogger("uvicorn.access").disabled is True


def test_unknown_path_is_404():
    """Sanity: routes we haven't built yet return 404, not a crash."""
    assert client.get("/nope").status_code == 404
