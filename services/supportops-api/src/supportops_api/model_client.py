from __future__ import annotations

from typing import Protocol

import httpx

from .models import CategoryPredictionRequest, CategoryPredictionResponse


class ModelServiceUnavailableError(RuntimeError):
    pass


class CategoryModelClient(Protocol):
    def predict(self, payload: CategoryPredictionRequest) -> CategoryPredictionResponse: ...


class HttpCategoryModelClient:
    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(timeout_seconds),
        )

    def close(self) -> None:
        self._client.close()

    def predict(self, payload: CategoryPredictionRequest) -> CategoryPredictionResponse:
        try:
            response = self._client.post("/predict", json=payload.model_dump())
            response.raise_for_status()
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise ModelServiceUnavailableError(
                "Model service is unreachable"
            ) from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 503:
                raise ModelServiceUnavailableError(
                    "Promoted model is unavailable"
                ) from exc
            raise
        return CategoryPredictionResponse.model_validate(response.json())
