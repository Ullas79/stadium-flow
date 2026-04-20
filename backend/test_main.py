"""
Tests for the CrowdSync FastAPI backend.

Run with:
    pytest test_main.py -v --cov=. --cov-report=term-missing
"""
import asyncio
import time

import pytest
from fastapi.testclient import TestClient

import utils
from main import app, state, _metrics

client = TestClient(app)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_state():
    """Reset in-memory cache and metrics before every test for full isolation."""
    state.cached_status = None
    state.last_update_time = 0.0
    _metrics["request_count"] = 0
    _metrics["ai_call_count"] = 0
    _metrics["cache_hit_count"] = 0
    _metrics["cache_miss_count"] = 0
    utils.reset_rate_limits()
    yield


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

def test_health_check():
    """Liveness probe should always return 200."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# GET /metrics
# ---------------------------------------------------------------------------

def test_metrics_endpoint_shape():
    """/metrics must return a JSON object with all required fields."""
    response = client.get("/metrics")
    assert response.status_code == 200
    body = response.json()
    for field in ("request_count", "ai_call_count", "cache_hit_count",
                  "cache_miss_count", "cache_age_seconds", "cache_ttl_seconds"):
        assert field in body, f"Missing field: {field}"


def test_metrics_cache_ttl_value():
    """cache_ttl_seconds should match the constant defined in main."""
    from main import CACHE_TTL
    body = client.get("/metrics").json()
    assert body["cache_ttl_seconds"] == CACHE_TTL


# ---------------------------------------------------------------------------
# Security headers
# ---------------------------------------------------------------------------

def test_security_headers_present():
    """Every response must carry the hardened security header set."""
    response = client.get("/health")
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert "max-age=31536000" in response.headers.get("Strict-Transport-Security", "")
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


def test_csp_header_present():
    """Content-Security-Policy header must be set."""
    response = client.get("/health")
    csp = response.headers.get("Content-Security-Policy", "")
    assert "default-src" in csp


# ---------------------------------------------------------------------------
# GET /api/stadium/status
# ---------------------------------------------------------------------------

def test_get_stadium_status_shape():
    """First call must return fresh data with the correct shape."""
    response = client.get("/api/stadium/status")
    assert response.status_code == 200
    body = response.json()
    assert "data" in body
    assert "cached" in body
    assert body["cached"] is False
    data = body["data"]
    assert "gates" in data and len(data["gates"]) == 4
    assert "transport" in data and len(data["transport"]) == 3


def test_gate_fields():
    """Each gate must expose 'id', 'status', and 'density' fields."""
    body = client.get("/api/stadium/status").json()
    for gate in body["data"]["gates"]:
        assert "id" in gate
        assert gate["status"] in {"Red", "Yellow", "Green"}
        assert 10 <= gate["density"] <= 100


def test_transport_fields():
    """Each transport entry must have 'mode' and a 'wait_time' ending in 'm'."""
    body = client.get("/api/stadium/status").json()
    for transport in body["data"]["transport"]:
        assert "mode" in transport
        assert "wait_time" in transport
        assert transport["wait_time"].endswith("m")


def test_stadium_status_caching():
    """Second immediate request must be served from cache with identical data."""
    first = client.get("/api/stadium/status").json()
    second = client.get("/api/stadium/status").json()
    assert second["cached"] is True
    assert second["data"] == first["data"]


def test_density_status_correlation():
    """Gate status must be consistent with its density value across all 4 gates."""
    body = client.get("/api/stadium/status").json()
    for gate in body["data"]["gates"]:
        d = gate["density"]
        s = gate["status"]
        if d >= 70:
            assert s == "Red", f"{gate['id']}: density {d} should be Red, got {s}"
        elif d >= 40:
            assert s == "Yellow", f"{gate['id']}: density {d} should be Yellow, got {s}"
        else:
            assert s == "Green", f"{gate['id']}: density {d} should be Green, got {s}"


@pytest.mark.parametrize("density,expected_status", [
    (10, "Green"),
    (39, "Green"),
    (40, "Yellow"),
    (69, "Yellow"),
    (70, "Red"),
    (100, "Red"),
])
def test_gate_status_boundary_conditions(density, expected_status):
    """Parametrized: boundary density values must map to the correct status."""
    from utils import _gate as _gate_fn
    import unittest.mock as mock
    with mock.patch("random.randint", return_value=density):
        gate = _gate_fn("Gate X")
    assert gate["status"] == expected_status, (
        f"density={density} → expected {expected_status}, got {gate['status']}"
    )


# ---------------------------------------------------------------------------
# POST /api/chat
# ---------------------------------------------------------------------------

def test_chat_empty_message():
    """Whitespace-only message must be rejected with HTTP 400."""
    response = client.post("/api/chat", json={"message": "   "})
    assert response.status_code == 400


def test_chat_exceeds_max_length():
    """Messages longer than MAX_MESSAGE_LENGTH must be rejected with HTTP 422."""
    response = client.post("/api/chat", json={"message": "x" * 501})
    assert response.status_code == 422


def test_chat_fallback_response_shape(monkeypatch):
    """Without an active client, the endpoint must still return a valid ChatResponse (200)."""
    monkeypatch.setattr("main._gemini_client", None)
    response = client.post("/api/chat", json={"message": "Where is Gate A?"})
    assert response.status_code == 200
    assert "reply" in response.json()


def test_chat_sanitizes_html_tags():
    """Chat endpoint must strip HTML tags and not crash."""
    response = client.post("/api/chat", json={"message": "<script>alert(1)</script>"})
    assert response.status_code in {400, 200}


def test_chat_preserves_slash_in_message():
    """sanitize_input must NOT strip valid punctuation like slashes."""
    from utils import sanitize_input
    cleaned = sanitize_input("Gate B/C exit?")
    assert "/" in cleaned, "sanitize_input stripped a valid slash character"


def test_chat_truly_empty_string():
    """An empty string must be rejected by Pydantic validation (min_length=1)."""
    response = client.post("/api/chat", json={"message": ""})
    assert response.status_code == 422


def test_chat_missing_field():
    """Omitting the 'message' field must return 422."""
    response = client.post("/api/chat", json={})
    assert response.status_code == 422


def test_chat_valid_response_structure(monkeypatch):
    """A valid message with no active client must return a JSON body with a 'reply' string."""
    monkeypatch.setattr("main._gemini_client", None)
    response = client.post("/api/chat", json={"message": "Where is Gate B?"})
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body.get("reply"), str)
    assert len(body["reply"]) > 0


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

def test_rate_limit_allows_10_requests(monkeypatch):
    """10 chat requests from the same IP must all succeed (200)."""
    monkeypatch.setattr("main._gemini_client", None)
    for i in range(10):
        res = client.post("/api/chat", json={"message": f"test message {i}"})
        assert res.status_code == 200, f"Request {i+1} should succeed, got {res.status_code}"


def test_rate_limit_blocks_11th_request(monkeypatch):
    """The 11th request within the window must be rejected with HTTP 429."""
    monkeypatch.setattr("main._gemini_client", None)
    for i in range(10):
        client.post("/api/chat", json={"message": f"test message {i}"})
    res = client.post("/api/chat", json={"message": "this should be blocked"})
    assert res.status_code == 429, f"Expected 429, got {res.status_code}"


def test_rate_limit_reset_allows_requests_again(monkeypatch):
    """After rate-limit reset, requests must succeed again."""
    monkeypatch.setattr("main._gemini_client", None)
    for i in range(10):
        client.post("/api/chat", json={"message": f"test message {i}"})
    utils.reset_rate_limits()
    res = client.post("/api/chat", json={"message": "after reset"})
    assert res.status_code == 200


# ---------------------------------------------------------------------------
# utils.py unit tests
# ---------------------------------------------------------------------------

def test_generate_simulated_status_structure():
    """generate_simulated_status must return a dict with gates, transport, announcement."""
    from utils import generate_simulated_status
    result = generate_simulated_status()
    assert "gates" in result
    assert "transport" in result
    assert "announcement" in result
    assert len(result["gates"]) == 4
    assert len(result["transport"]) == 3


@pytest.mark.asyncio
async def test_is_rate_limited_async():
    """is_rate_limited must return False for a fresh IP and True after limit exceeded."""
    utils.reset_rate_limits()
    for _ in range(10):
        limited = await utils.is_rate_limited("192.0.2.1")
    assert not limited  # 10th request is still within limit
    limited_11th = await utils.is_rate_limited("192.0.2.1")
    assert limited_11th  # 11th must be rate-limited


@pytest.mark.asyncio
async def test_is_rate_limited_different_ips():
    """Different IPs must have independent rate-limit counters."""
    utils.reset_rate_limits()
    for _ in range(10):
        await utils.is_rate_limited("10.0.0.1")
    # 10.0.0.1 is now at limit; 10.0.0.2 must still be allowed
    limited_other = await utils.is_rate_limited("10.0.0.2")
    assert not limited_other
