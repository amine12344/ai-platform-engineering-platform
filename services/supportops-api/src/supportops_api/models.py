from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Priority = Literal["P1", "P2", "P3", "P4"]


class Ticket(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticket_id: str
    created_at: datetime
    channel: str
    language: str
    customer_tier: str
    product: str
    subject: str
    body: str
    category: str
    priority: Priority
    escalated: bool
    resolution_time_minutes: int = Field(gt=0)
    agent_response: str
    satisfaction_score: int = Field(ge=1, le=5)


class TicketList(BaseModel):
    items: list[Ticket]
    total: int
    limit: int
    offset: int


class TicketSummary(BaseModel):
    total: int
    escalated: int
    average_resolution_time_minutes: float
    average_satisfaction_score: float
    by_priority: dict[str, int]
    by_category: dict[str, int]


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    version: str


class ReadinessResponse(BaseModel):
    status: Literal["ready"]
    database: Literal["reachable"]
