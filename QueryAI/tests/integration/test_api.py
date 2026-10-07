"""
QueryAI — API Integration Tests.
Tests FastAPI endpoints using TestClient:
  - GET /health
  - GET /api/v1/system/status
  - POST /api/v1/query/validate
  - GET /api/v1/schema
  - GET /api/v1/history
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database.connection import init_app_db

# Initialize database tables for testing
init_app_db()

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == "QueryAI"


def test_system_status_endpoint():
    response = client.get("/api/v1/system/status")
    assert response.status_code == 200
    data = response.json()
    assert "app_db" in data
    assert "business_db" in data
    assert "ollama" in data
    assert "chromadb" in data


def test_query_validate_valid():
    payload = {"sql": "SELECT id, name FROM customers LIMIT 10"}
    response = client.post("/api/v1/query/validate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["is_valid"] is True
    assert data["error"] is None


def test_query_validate_invalid_drop():
    payload = {"sql": "DROP TABLE customers"}
    response = client.post("/api/v1/query/validate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["is_valid"] is False
    assert "forbidden keyword" in data["error"].lower()


def test_get_schema_endpoint():
    response = client.get("/api/v1/schema")
    assert response.status_code == 200
    data = response.json()
    assert "tables" in data


def test_get_history_endpoint():
    response = client.get("/api/v1/history")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
