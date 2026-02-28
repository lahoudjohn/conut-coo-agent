from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"


def test_tool_schema() -> None:
    response = client.get("/tools/schema")
    assert response.status_code == 200
    body = response.json()
    assert "tools" in body
    assert len(body["tools"]) == 5


def test_forecast_endpoint_smoke() -> None:
    response = client.post("/tools/forecast_demand", json={"branch": "demo-branch", "horizon_days": 3})
    assert response.status_code == 200
    body = response.json()
    assert body["tool_name"] == "forecast_demand"
    assert "result" in body
