import pytest
from rest_framework.test import APIClient


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
def test_health_returns_200_and_ok(api_client):
    res = api_client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data.get("status") == "ok"
    assert data.get("database") == "ok"
    backup = (data.get("services") or {}).get("backup") or {}
    assert backup.get("status") in ("not_configured", "unknown", "ok", "stale")
    assert "last_run" in backup or backup.get("status") == "not_configured"


