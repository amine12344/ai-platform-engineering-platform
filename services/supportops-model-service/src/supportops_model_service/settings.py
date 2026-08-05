from __future__ import annotations

import os
from functools import lru_cache

from pydantic import BaseModel, Field


class Settings(BaseModel):
    service_name: str = "supportops-model-service"
    environment: str = "development"
    log_level: str = "INFO"
    mlflow_tracking_uri: str = "http://localhost:5000"
    model_name: str = "supportops-category-classifier"
    model_alias: str = "champion"
    model_load_timeout_seconds: int = Field(default=120, ge=5, le=600)
    prediction_max_characters: int = Field(default=5000, ge=100, le=50000)
    model_service_url: str = "http://localhost:8081"
    model_service_timeout_seconds: float = 10.0

    @property
    def model_uri(self) -> str:
        return f"models:/{self.model_name}@{self.model_alias}"

    @classmethod
    def from_environment(cls) -> Settings:
        prefix = "SUPPORTOPS_MODEL_"
        return cls(
            service_name=os.getenv(f"{prefix}SERVICE_NAME", "supportops-model-service"),
            environment=os.getenv(f"{prefix}ENVIRONMENT", "development"),
            log_level=os.getenv(f"{prefix}LOG_LEVEL", "INFO"),
            mlflow_tracking_uri=os.getenv(
                f"{prefix}MLFLOW_TRACKING_URI",
                "http://localhost:5000",
            ),
            model_name=os.getenv(
                f"{prefix}NAME",
                "supportops-category-classifier",
            ),
            model_alias=os.getenv(f"{prefix}ALIAS", "champion"),
            model_load_timeout_seconds=int(
                os.getenv(f"{prefix}LOAD_TIMEOUT_SECONDS", "120")
            ),
            model_service_url=os.getenv(
                f"{prefix}MODEL_SERVICE_URL",
                "http://localhost:8081",
            ),
            model_service_timeout_seconds=float(
                os.getenv(f"{prefix}MODEL_SERVICE_TIMEOUT_SECONDS", "10")
            ),
            prediction_max_characters=int(
                os.getenv(f"{prefix}PREDICTION_MAX_CHARACTERS", "5000")
            ),
        )


@lru_cache
def get_settings() -> Settings:
    return Settings.from_environment()