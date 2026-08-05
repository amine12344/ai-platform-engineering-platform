from __future__ import annotations

from fastapi.testclient import TestClient

from supportops_model_service.main import create_app
from supportops_model_service.settings import Settings

from .fakes import FakeRuntime


def make_client(runtime: FakeRuntime, max_characters: int = 5000) -> TestClient:
    settings = Settings(prediction_max_characters=max_characters)
    app = create_app(
        settings=settings,
        runtime=runtime,  # type: ignore[arg-type]
        load_on_startup=False,
    )
    return TestClient(app)


def test_health_is_process_health() -> None:
    with make_client(FakeRuntime(loaded=False)) as client:
        response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readiness_requires_loaded_model() -> None:
    with make_client(FakeRuntime(loaded=False)) as client:
        response = client.get("/readyz")
    assert response.status_code == 503
    assert response.json()["detail"] == "No promoted model is loaded"


def test_prediction_returns_model_provenance() -> None:
    with make_client(FakeRuntime()) as client:
        response = client.post(
            "/predict",
            json={
                "subject": "VPN disconnected",
                "body": "The company VPN drops every five minutes.",
                "product": "SecureConnect",
            },
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["predicted_category"] == "network"
    assert payload["confidence"] == 0.91
    assert payload["model_alias"] == "champion"
    assert payload["model_version"] == "7"


def test_blank_input_is_rejected() -> None:
    with make_client(FakeRuntime()) as client:
        response = client.post(
            "/predict",
            json={"subject": "   ", "body": "content"},
        )
    assert response.status_code == 422


def test_combined_length_limit_is_enforced() -> None:
    with make_client(FakeRuntime(), max_characters=100) as client:
        response = client.post(
            "/predict",
            json={"subject": "a" * 50, "body": "b" * 60},
        )
    assert response.status_code == 422


def test_prediction_failure_is_hidden_from_client() -> None:
    with make_client(FakeRuntime(fail_prediction=True)) as client:
        response = client.post(
            "/predict",
            json={"subject": "Printer error", "body": "Printer is offline"},
        )
    assert response.status_code == 500
    assert response.json()["detail"] == "Model prediction failed"


def test_reload_replaces_model_metadata() -> None:
    runtime = FakeRuntime(loaded=False)
    with make_client(runtime) as client:
        response = client.post("/reload")
    assert response.status_code == 200
    assert response.json()["model"]["version"] == "8"
