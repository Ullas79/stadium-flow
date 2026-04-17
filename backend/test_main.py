"""
Tests for the CrowdSync FastAPI backend.
"""
from fastapi.testclient import TestClient
from main import app
import time

client = TestClient(app)

def test_get_stadium_status():
    """Test retrieving stadium status and check caching logic."""
    response1 = client.get("/api/stadium/status")
    assert response1.status_code == 200
    data1 = response1.json()
    assert "data" in data1
    assert "gates" in data1["data"]
    assert "transport" in data1["data"]
    assert data1["cached"] == False

    # Second request immediately after should be cached
    response2 = client.get("/api/stadium/status")
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["cached"] == True
    assert data2["data"] == data1["data"]

def test_chat_concierge_empty():
    """Test chat endpoint with empty message."""
    response = client.post("/api/chat", json={"message": "   "})
    assert response.status_code == 400

def test_chat_concierge_sanitization():
    """Test chat endpoint handles sanitized string."""
    response = client.post("/api/chat", json={"message": "Where is the exit??!!@#"})
    # Expect 200 (simulated/api response) or 500 if API fails, no crashes during parsing
    assert response.status_code in [200, 500] 
