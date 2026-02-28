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


def test_combo_endpoint_smoke() -> None:
    response = client.post(
        "/tools/recommend_combos",
        json={
            "mode": "with_item",
            "branch": "Conut - Tyre",
            "anchor_item": "CLASSIC CHIMNEY",
            "include_categories": ["sweet", "beverage"],
            "exclude_items": ["DELIVERY CHARGE"],
            "top_n": 3,
            "min_support": 0.02,
            "min_confidence": 0.2,
            "min_lift": 1.0,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["tool_name"] == "recommend_combos"
    assert "top_rules" in body["result"]
    assert "recommended_combos" in body["result"]
    assert "query_context" in body["result"]
