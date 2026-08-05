from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    version: str


class ReadinessResponse(BaseModel):
    status: Literal["ready"]
    model_name: str
    model_alias: str
    model_version: str


class ModelMetadata(BaseModel):
    name: str
    alias: str
    version: str
    run_id: str
    source: str
    status: str


class PredictionRequest(BaseModel):
    subject: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1, max_length=5000)
    product: str | None = Field(default=None, max_length=200)

    @field_validator("subject", "body")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("value must contain non-whitespace characters")
        return stripped

    @property
    def combined_text(self) -> str:
        parts = [self.subject, self.body]
        if self.product:
            parts.append(self.product.strip())
        return " ".join(part for part in parts if part)


class PredictionResponse(BaseModel):
    predicted_category: str
    confidence: float | None = Field(default=None, ge=0, le=1)
    model_name: str
    model_alias: str
    model_version: str


class ReloadResponse(BaseModel):
    status: Literal["reloaded"]
    model: ModelMetadata


class ErrorResponse(BaseModel):
    detail: str
    context: dict[str, Any] | None = None

class CategoryPredictionRequest(BaseModel):
    subject: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1, max_length=5000)
    product: str | None = Field(default=None, max_length=200)


class CategoryPredictionResponse(BaseModel):
    predicted_category: str
    confidence: float | None = Field(default=None, ge=0, le=1)
    model_name: str
    model_alias: str
    model_version: str