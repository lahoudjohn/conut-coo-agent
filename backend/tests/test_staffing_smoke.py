from fastapi.testclient import TestClient

from app.main import app
from app.objectives.objective4_staffing.service import estimate_shift_staffing
from app.schemas.staffing import StaffingRequest


client = TestClient(app)


def test_estimate_staffing_function_smoke() -> None:
    response = estimate_shift_staffing(
        StaffingRequest(
            branch="Conut Jnah",
            target_period="2025-12",
            shift_name="evening",
        )
    )
    assert response.recommended_staff >= 1
    assert response.required_labor_hours > 0
    assert response.productivity_sales_per_labor_hour > 0
    assert "evidence" in response.model_dump()


def test_estimate_staffing_endpoint_smoke() -> None:
    response = client.post(
        "/tools/estimate_staffing",
        json={
            "branch": "Conut Jnah",
            "target_period": "2025-12",
            "shift_name": "evening",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["recommended_staff"] >= 1
    assert "evidence" in body
    assert "assumptions" in body
    assert "data_coverage" in body


def test_estimate_staffing_missing_branch() -> None:
    response = client.post(
        "/tools/estimate_staffing",
        json={
            "branch": "Unknown Branch",
            "target_period": "2025-12",
            "shift_name": "morning",
        },
    )
    assert response.status_code == 404
    body = response.json()
    assert "not found" in body["detail"].lower()


def test_understaffed_branches_endpoint_smoke() -> None:
    response = client.post(
        "/tools/understaffed_branches",
        json={
            "target_period": "2025-12",
            "shift_name": "evening",
            "top_n": 3,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["shift_name"] == "evening"
    assert len(body["branches_ranked"]) >= 1


def test_average_shift_length_endpoint_smoke() -> None:
    response = client.post(
        "/tools/average_shift_length",
        json={
            "shift_name": "evening",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["average_shift_length_hours"] > 0
    assert len(body["branch_stats"]) >= 1
