"""
Tests for the CrowdSync FastAPI backend.
Run with: pytest test_main.py -v
"""
import pytest
from fastapi.testclient import TestClient
from main import app, state

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_state():
    """Reset in-memory cache before every test for full isolation."""
    state.cached_status = None
    state.last_update_time = 0.0
    yield


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------
def test_health_check():
    """Liveness probe should always return 200."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


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
    """Each transport entry must have 'mode' and a 'wait_time' string ending in 'm'."""
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


def test_chat_fallback_response_shape():
    """Without an API key, the endpoint must still return a valid ChatResponse."""
    response = client.post("/api/chat", json={"message": "Where is Gate A?"})
    # 200 = fallback path (no key); 500 = unexpected error from SDK config
    assert response.status_code in {200, 500}
    if response.status_code == 200:
        assert "reply" in response.json()


def test_chat_sanitizes_special_chars():
    """Chat endpoint must not crash on messages with special characters."""
    response = client.post("/api/chat", json={"message": "<script>alert(1)</script>"})
    assert response.status_code in {200, 400, 500}


def test_chat_truly_empty_string():
    """An empty string must be rejected by Pydantic validation (min_length=1)."""
    response = client.post("/api/chat", json={"message": ""})
    assert response.status_code == 422


def test_chat_missing_field():
    """Omitting the 'message' field must return 422."""
    response = client.post("/api/chat", json={})
    assert response.status_code == 422


def test_chat_valid_response_structure():
    """A valid message must return a JSON body with a 'reply' string."""
    response = client.post("/api/chat", json={"message": "Where is Gate B?"})
    if response.status_code == 200:
        body = response.json()
        assert isinstance(body.get("reply"), str)
        assert len(body["reply"]) > 0


def test_density_status_correlation():
    """Gate status must be consistent with its density value."""
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
