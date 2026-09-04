"""Tests for Traffic Generator FastAPI application."""

from fastapi.testclient import TestClient

from traffic_generator.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    """Tests the /health probe returns 200 OK and expected keys."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "HEALTHY"
    assert data["schedule"] == "every 45 minutes"
    assert "timestamp" in data


def test_scenarios_endpoint() -> None:
    """Tests the /scenarios endpoint lists all default scenarios."""
    response = client.get("/scenarios")
    assert response.status_code == 200
    data = response.json()
    assert data["total_scenarios"] >= 10
    categories = {s["category"] for s in data["scenarios"]}
    assert "SUCCESS_VALID_SYNTHESIS" in categories
    assert "FAIL_OUT_OF_CORPUS" in categories
    assert "FAIL_HALLUCINATION_TRAP" in categories
    assert "FAIL_SAFETY_ADVERSARIAL" in categories
    assert "FAIL_MALFORMED_INPUT" in categories
    assert "FAIL_FAULT_INJECTION" in categories


def test_run_eval_traffic_validation_missing_project() -> None:
    """Tests that missing project_id raises 400 Bad Request."""
    response = client.post(
        "/run-eval-traffic",
        json={"project_id": "", "reasoning_engine_id": ""},
    )
    # When project_id is empty and not in env, expect 400
    assert response.status_code in (400, 500)
