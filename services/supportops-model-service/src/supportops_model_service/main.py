from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status

from . import __version__
from .model_runtime import ModelRuntime, ModelUnavailableError
from .models import (
    HealthResponse,
    ModelMetadata,
    PredictionRequest,
    PredictionResponse,
    ReadinessResponse,
    ReloadResponse,
)
from .settings import Settings, get_settings

LOGGER = logging.getLogger("supportops_model_service")


def get_runtime(request: Request) -> ModelRuntime:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model runtime is unavailable",
        )
    return runtime


def create_app(
    *,
    settings: Settings | None = None,
    runtime: ModelRuntime | None = None,
    load_on_startup: bool = True,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    resolved_runtime = runtime or ModelRuntime(resolved_settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logging.basicConfig(level=resolved_settings.log_level)
        app.state.runtime = resolved_runtime
        if load_on_startup:
            try:
                resolved_runtime.load()
            except Exception:
                LOGGER.exception("initial_model_load_failed")
        yield

    app = FastAPI(
        title="SupportOps Model Service",
        description="Serves the promoted SupportOps category classifier.",
        version=__version__,
        lifespan=lifespan,
    )

    @app.get("/healthz", response_model=HealthResponse, tags=["operations"])
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            service=resolved_settings.service_name,
            version=__version__,
        )

    @app.get("/readyz", response_model=ReadinessResponse, tags=["operations"])
    def readiness(request: Request) -> ReadinessResponse:
        metadata = get_runtime(request).metadata
        if metadata is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No promoted model is loaded",
            )
        return ReadinessResponse(
            status="ready",
            model_name=metadata.name,
            model_alias=metadata.alias,
            model_version=metadata.version,
        )

    @app.get("/model", response_model=ModelMetadata, tags=["model"])
    def model_metadata(request: Request) -> ModelMetadata:
        metadata = get_runtime(request).metadata
        if metadata is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No promoted model is loaded",
            )
        return metadata

    @app.post("/predict", response_model=PredictionResponse, tags=["prediction"])
    def predict(payload: PredictionRequest, request: Request) -> PredictionResponse:
        combined_text = payload.combined_text
        if len(combined_text) > resolved_settings.prediction_max_characters:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Combined prediction text exceeds "
                    f"{resolved_settings.prediction_max_characters} characters"
                ),
            )
        runtime_instance = get_runtime(request)
        metadata = runtime_instance.metadata
        if metadata is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No promoted model is loaded",
            )
        try:
            prediction = runtime_instance.predict(combined_text)
        except ModelUnavailableError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc
        except Exception as exc:
            LOGGER.exception("prediction_failed")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Model prediction failed",
            ) from exc
        return PredictionResponse(
            predicted_category=prediction.category,
            confidence=prediction.confidence,
            model_name=metadata.name,
            model_alias=metadata.alias,
            model_version=metadata.version,
        )

    @app.post("/reload", response_model=ReloadResponse, tags=["operations"])
    def reload_model(request: Request) -> ReloadResponse:
        try:
            metadata = get_runtime(request).load()
        except Exception as exc:
            LOGGER.exception("model_reload_failed")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Promoted model could not be loaded",
            ) from exc
        return ReloadResponse(status="reloaded", model=metadata)

    return app


app = create_app()
