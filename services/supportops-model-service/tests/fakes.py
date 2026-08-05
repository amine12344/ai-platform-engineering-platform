from __future__ import annotations

from supportops_model_service.model_runtime import Prediction
from supportops_model_service.models import ModelMetadata


class FakeRuntime:
    def __init__(self, *, loaded: bool = True, fail_prediction: bool = False) -> None:
        self._metadata = (
            ModelMetadata(
                name="supportops-category-classifier",
                alias="champion",
                version="7",
                run_id="run-123",
                source="s3://supportops-models/model",
                status="READY",
            )
            if loaded
            else None
        )
        self.fail_prediction = fail_prediction

    @property
    def metadata(self) -> ModelMetadata | None:
        return self._metadata

    def load(self) -> ModelMetadata:
        self._metadata = ModelMetadata(
            name="supportops-category-classifier",
            alias="champion",
            version="8",
            run_id="run-456",
            source="s3://supportops-models/model-v8",
            status="READY",
        )
        return self._metadata

    def predict(self, text: str) -> Prediction:
        if self.fail_prediction:
            raise RuntimeError("synthetic prediction failure")
        assert text
        return Prediction(category="network", confidence=0.91)
