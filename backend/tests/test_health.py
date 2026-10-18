from fastapi.testclient import TestClient
from unittest.mock import patch
from sqlalchemy.exc import OperationalError


def test_health_check_success(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"


def test_health_check_database_failure(client: TestClient):
    with patch("sqlalchemy.orm.Session.execute", side_effect=OperationalError("Connection failed", {}, None)):
        response = client.get("/health")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["database"] == "disconnected"
