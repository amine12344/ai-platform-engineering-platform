from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Any, Protocol

import mlflow
import pandas as pd
from mlflow import MlflowClient

from .models import ModelMetadata
from .settings import Settings

LOGGER = logging.getLogger("supportops_model_service.runtime")


class PredictableModel(Protocol):
    def predict(self, data: Any) -> Any: ...


@dataclass(frozen=True)
class Prediction:
    category: str
    confidence: float | None


class ModelUnavailableError(RuntimeError):
    """Raised when no serving model is loaded."""


class ModelRuntime:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._lock = threading.RLock()
        self._model: PredictableModel | None = None
        self._metadata: ModelMetadata | None = None

    @property
    def metadata(self) -> ModelMetadata | None:
        with self._lock:
            return self._metadata

    def load(self) -> ModelMetadata:
        LOGGER.info(
            "loading_model uri=%s tracking_uri=%s",
            self._settings.model_uri,
            self._settings.mlflow_tracking_uri,
        )
        mlflow.set_tracking_uri(self._settings.mlflow_tracking_uri)
        client = MlflowClient()
        version = client.get_model_version_by_alias(
            self._settings.model_name,
            self._settings.model_alias,
        )
        model = mlflow.pyfunc.load_model(self._settings.model_uri)
        metadata = ModelMetadata(
            name=version.name,
            alias=self._settings.model_alias,
            version=str(version.version),
            run_id=version.run_id,
            source=version.source,
            status=str(version.status),
        )
        with self._lock:
            self._model = model
            self._metadata = metadata
        LOGGER.info(
            "model_loaded name=%s alias=%s version=%s",
            metadata.name,
            metadata.alias,
            metadata.version,
        )
        return metadata

    def predict(self, text: str) -> Prediction:
        with self._lock:
            model = self._model
        if model is None:
            raise ModelUnavailableError("No model is currently loaded")

        frame = pd.DataFrame({"text": [text]})
        raw = model.predict(frame)
        if len(raw) != 1:
            raise RuntimeError("Model returned an unexpected prediction count")

        item = raw[0]
        if isinstance(item, dict):
            category = str(
                item.get("predicted_category")
                or item.get("prediction")
                or item.get("label")
            )
            confidence_value = item.get("confidence")
            confidence = (
                float(confidence_value) if confidence_value is not None else None
            )
            return Prediction(category=category, confidence=confidence)

        return Prediction(category=str(item), confidence=None)
