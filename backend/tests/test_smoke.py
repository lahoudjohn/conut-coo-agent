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
    assert "primary_objective_tools" in body
    tool_names = {tool["name"] for tool in body["tools"]}
    assert len(body["tools"]) >= 7
    assert len(body["primary_objective_tools"]) == 5
    assert "estimate_staffing" in tool_names
    assert "understaffed_branches" in tool_names
    assert "average_shift_length" in tool_names


def test_openclaw_manifest() -> None:
    response = client.get("/tools/openclaw_manifest")
    assert response.status_code == 200
    body = response.json()
    assert body["plugin_id"] == "conut-coo-agent"
    assert body["tool_count"] == 5
    openclaw_names = {tool["openclaw_name"] for tool in body["tools"]}
    assert "conut_combo_optimization" in openclaw_names
    assert "conut_shift_staffing" in openclaw_names


def test_tool_activity_feed_records_calls() -> None:
    call_response = client.post(
        "/tools/recommend_combos",
        headers={"X-Conut-Caller": "openclaw", "X-Conut-Agent-Tool": "conut_combo_optimization"},
        json={"top_n": 1},
    )
    assert call_response.status_code == 200

    response = client.get("/tools/activity?limit=5")
    assert response.status_code == 200
    body = response.json()
    assert "events" in body
    assert len(body["events"]) >= 1
    latest_event = body["events"][0]
    assert latest_event["tool_name"] == "recommend_combos"
    assert latest_event["source"] == "openclaw"
    assert "raw_output" in latest_event


def test_forecast_endpoint_smoke() -> None:
    response = client.post("/tools/forecast_demand", json={"branch": "Conut Jnah", "horizon_days": 3})
    assert response.status_code == 200
    body = response.json()
    assert body["tool_name"] == "forecast_demand"
    assert "result" in body
    assert body["result"]["model"] == "3-period weighted moving average"
    assert body["key_evidence_metrics"]["history_months_used"] >= 3


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


def test_growth_endpoint_smoke() -> None:
    response = client.post(
        "/tools/growth_strategy",
        json={"focus_categories": ["coffee", "milkshake"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["tool_name"] == "growth_strategy"
    assert "category_metrics" in body["result"]
    assert body["result"].get("placeholder") is not True
