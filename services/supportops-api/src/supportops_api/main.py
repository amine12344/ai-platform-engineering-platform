from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, cast

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .models import HealthResponse, ReadinessResponse, Ticket, TicketList, TicketSummary
from .repository import PostgresTicketRepository, TicketRepository
from .settings import Settings, get_settings
from .model_client import (
    CategoryModelClient,
    HttpCategoryModelClient,
    ModelServiceUnavailableError,
)
from .models import (
    CategoryPredictionRequest,
    CategoryPredictionResponse,
    HealthResponse,
    ReadinessResponse,
    Ticket,
    TicketList,
    TicketSummary,
)

LOGGER = logging.getLogger("supportops_api")


async def get_repository(request: Request) -> TicketRepository:
    repository = getattr(request.app.state, "repository", None)
    if repository is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ticket repository is unavailable",
        )
    return cast(TicketRepository, repository)


def get_model_client(request: Request) -> CategoryModelClient:
    client = getattr(request.app.state, "model_client", None)
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model service client is unavailable",
        )
    return client

def create_app(
    *,
    settings: Settings | None = None,
    repository: TicketRepository | None = None,
    model_client: CategoryModelClient | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logging.basicConfig(level=resolved_settings.log_level)
        created_repository = None
        if repository is None:
            created_repository = PostgresTicketRepository(
                resolved_settings.database_dsn,
                min_size=resolved_settings.database_pool_min_size,
                max_size=resolved_settings.database_pool_max_size,
            )
            app.state.repository = created_repository
            if model_client is None:
                created_model_client = HttpCategoryModelClient(
                    resolved_settings.model_service_url,
                    resolved_settings.model_service_timeout_seconds,
                )
                app.state.model_client = created_model_client
            else:
                app.state.model_client = model_client
        else:
            app.state.repository = repository
        LOGGER.info("service_started environment=%s", resolved_settings.environment)
        try:
            yield
        finally:
            if created_repository is not None:
                created_repository.close()
            LOGGER.info("service_stopped")
            if created_model_client is not None:
                created_model_client.close()
            LOGGER.info("model_client_stopped")

    app = FastAPI(
        title="SupportOps API",
        description="Read-only API for the versioned SupportOps ticket dataset.",
        version=__version__,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[],
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["Accept", "Content-Type"],
    )

    @app.get("/healthz", response_model=HealthResponse, tags=["operations"])
    async def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            service=resolved_settings.service_name,
            version=__version__,
        )

    @app.get("/readyz", response_model=ReadinessResponse, tags=["operations"])
    async def readiness(
        repo: Annotated[TicketRepository, Depends(get_repository)],
    ) -> ReadinessResponse:
        try:
            repo.ping()
        except Exception as exc:
            LOGGER.exception("database_readiness_failed")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database is not reachable",
            ) from exc
        return ReadinessResponse(status="ready", database="reachable")

    @app.get("/api/v1/tickets", response_model=TicketList, tags=["tickets"])
    async def list_tickets(
        repo: Annotated[TicketRepository, Depends(get_repository)],
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        offset: Annotated[int, Query(ge=0)] = 0,
        priority: Annotated[str | None, Query(pattern="^P[1-4]$")] = None,
        category: str | None = None,
        escalated: bool | None = None,
        language: Annotated[str | None, Query(min_length=2, max_length=8)] = None,
        search: Annotated[str | None, Query(min_length=2, max_length=100)] = None,
    ) -> TicketList:
        items, total = repo.list_tickets(
            limit=limit,
            offset=offset,
            priority=priority,
            category=category,
            escalated=escalated,
            language=language,
            search=search,
        )
        return TicketList(items=items, total=total, limit=limit, offset=offset)

    @app.get("/api/v1/tickets/{ticket_id}", response_model=Ticket, tags=["tickets"])
    async def get_ticket(
        ticket_id: str,
        repo: Annotated[TicketRepository, Depends(get_repository)],
    ) -> Ticket:
        ticket = repo.get_ticket(ticket_id)
        if ticket is None:
            raise HTTPException(status_code=404, detail="Ticket not found")
        return ticket

    @app.get("/api/v1/summary", response_model=TicketSummary, tags=["analytics"])
    async def summary(
        repo: Annotated[TicketRepository, Depends(get_repository)],
    ) -> TicketSummary:
        return repo.summary()

    @app.post(
    "/api/v1/predictions/category",
    response_model=CategoryPredictionResponse,
    tags=["predictions"],
)
def predict_category(
    payload: CategoryPredictionRequest,
    client: Annotated[CategoryModelClient, Depends(get_model_client)],
) -> CategoryPredictionResponse:
    try:
        return client.predict(payload)
    except ModelServiceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        LOGGER.exception("category_prediction_failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Model service returned an invalid response",
        ) from exc

    return app


app = create_app()
