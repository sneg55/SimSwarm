import pytest


async def test_health_returns_ok(client):
    response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


async def test_health_includes_database_status(client):
    response = await client.get("/api/health")
    data = response.json()
    assert data["database"] == "connected"
