from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT / "src"))

from supportops_api.main import create_app  # noqa: E402
from supportops_api.models import Ticket, TicketSummary  # noqa: E402
from supportops_api.settings import Settings  # noqa: E402


class FakeRepository:
    def __init__(self) -> None:
        self.ticket = Ticket(
            ticket_id="SUP-000001",
            created_at=datetime(2026, 1, 5, 8, 0, tzinfo=UTC),
            channel="portal",
            language="en",
            customer_tier="enterprise",
            product="VPN",
            subject="VPN access failure",
            body="Unable to connect to VPN.",
            category="access",
            priority="P1",
            escalated=True,
            resolution_time_minutes=60,
            agent_response="Reset the access policy.",
            satisfaction_score=5,
        )
        self.fail_ping = False

    def ping(self) -> None:
        if self.fail_ping:
            raise RuntimeError("database unavailable")

    def list_tickets(self, **kwargs):
        matches = [self.ticket]
        if kwargs.get("priority") not in (None, self.ticket.priority):
            matches = []
        return matches, len(matches)

    def get_ticket(self, ticket_id: str):
        return self.ticket if ticket_id == self.ticket.ticket_id else None

    def summary(self) -> TicketSummary:
        return TicketSummary(
            total=1,
            escalated=1,
            average_resolution_time_minutes=60.0,
            average_satisfaction_score=5.0,
            by_priority={"P1": 1},
            by_category={"access": 1},
        )


def client_and_repo() -> tuple[TestClient, FakeRepository]:
    repository = FakeRepository()
    app = create_app(
        settings=Settings(database_password="test"),
        repository=repository,
    )
    return TestClient(app), repository


def test_health_and_readiness() -> None:
    client, _ = client_and_repo()
    with client:
        health = client.get("/healthz")
        readiness = client.get("/readyz")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert readiness.status_code == 200
    assert readiness.json() == {"status": "ready", "database": "reachable"}


def test_readiness_failure_returns_503() -> None:
    client, repository = client_and_repo()
    repository.fail_ping = True
    with client:
        response = client.get("/readyz")
    assert response.status_code == 503
    assert response.json()["detail"] == "Database is not reachable"


def test_list_filter_detail_and_summary() -> None:
    client, _ = client_and_repo()
    with client:
        listing = client.get("/api/v1/tickets?priority=P1&limit=10")
        missing = client.get("/api/v1/tickets/SUP-999999")
        summary = client.get("/api/v1/summary")
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["ticket_id"] == "SUP-000001"
    assert missing.status_code == 404
    assert summary.status_code == 200
    assert summary.json()["by_priority"] == {"P1": 1}


def test_invalid_query_is_rejected() -> None:
    client, _ = client_and_repo()
    with client:
        response = client.get("/api/v1/tickets?priority=P9&limit=0")
    assert response.status_code == 422
