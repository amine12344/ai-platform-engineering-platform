from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol, cast

from .models import Ticket, TicketSummary


class TicketRepository(Protocol):
    def ping(self) -> None: ...

    def list_tickets(
        self,
        *,
        limit: int,
        offset: int,
        priority: str | None,
        category: str | None,
        escalated: bool | None,
        language: str | None,
        search: str | None,
    ) -> tuple[list[Ticket], int]: ...

    def get_ticket(self, ticket_id: str) -> Ticket | None: ...

    def summary(self) -> TicketSummary: ...


class PostgresTicketRepository:
    def __init__(self, dsn: str, min_size: int = 1, max_size: int = 5) -> None:
        try:
            from psycopg.rows import dict_row
            from psycopg_pool import ConnectionPool
        except ImportError as exc:  # pragma: no cover - deployment dependency check
            raise RuntimeError(
                "PostgreSQL dependencies are missing; install requirements.txt"
            ) from exc

        self._dict_row = dict_row
        self._pool = ConnectionPool(
            conninfo=dsn,
            min_size=min_size,
            max_size=max_size,
            open=False,
            kwargs={"row_factory": dict_row},
        )
        self._pool.open(wait=True)

    def close(self) -> None:
        self._pool.close()

    def ping(self) -> None:
        with self._pool.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()

    @staticmethod
    def _ticket(row: Mapping[str, Any]) -> Ticket:
        return Ticket.model_validate(dict(row))

    def list_tickets(
        self,
        *,
        limit: int,
        offset: int,
        priority: str | None,
        category: str | None,
        escalated: bool | None,
        language: str | None,
        search: str | None,
    ) -> tuple[list[Ticket], int]:
        predicates: list[str] = []
        parameters: list[Any] = []

        for column, value in (
            ("priority", priority),
            ("category", category),
            ("language", language),
        ):
            if value is not None:
                predicates.append(f"{column} = %s")
                parameters.append(value)

        if escalated is not None:
            predicates.append("escalated = %s")
            parameters.append(escalated)

        if search:
            predicates.append(
                "to_tsvector('simple', subject || ' ' || body || ' ' || product) "
                "@@ plainto_tsquery('simple', %s)"
            )
            parameters.append(search)

        where = f"WHERE {' AND '.join(predicates)}" if predicates else ""

        count_sql = f"SELECT COUNT(*) AS total FROM helpdesk.tickets {where}"
        data_sql = f"""
            SELECT *
            FROM helpdesk.tickets
            {where}
            ORDER BY created_at DESC, ticket_id
            LIMIT %s OFFSET %s
        """

        with self._pool.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(count_sql, parameters)
                count_row = cast(Mapping[str, Any], cursor.fetchone())
                total = int(count_row["total"])
                cursor.execute(data_sql, [*parameters, limit, offset])
                rows = cast(list[Mapping[str, Any]], cursor.fetchall())
                tickets = [self._ticket(row) for row in rows]
        return tickets, total

    def get_ticket(self, ticket_id: str) -> Ticket | None:
        with self._pool.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM helpdesk.tickets WHERE ticket_id = %s",
                    (ticket_id,),
                )
                row = cast(Mapping[str, Any] | None, cursor.fetchone())
        return self._ticket(row) if row else None

    def summary(self) -> TicketSummary:
        with self._pool.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                      COUNT(*) AS total,
                      COUNT(*) FILTER (WHERE escalated) AS escalated,
                      ROUND(AVG(resolution_time_minutes)::numeric, 2) AS avg_resolution,
                      ROUND(AVG(satisfaction_score)::numeric, 2) AS avg_satisfaction
                    FROM helpdesk.tickets
                    """
                )
                totals = cast(Mapping[str, Any], cursor.fetchone())
                cursor.execute(
                    """
                    SELECT priority, COUNT(*) AS count
                    FROM helpdesk.tickets
                    GROUP BY priority
                    ORDER BY priority
                    """
                )
                priority_rows = cast(list[Mapping[str, Any]], cursor.fetchall())
                by_priority = {
                    row["priority"]: int(row["count"]) for row in priority_rows
                }
                cursor.execute(
                    """
                    SELECT category, COUNT(*) AS count
                    FROM helpdesk.tickets
                    GROUP BY category
                    ORDER BY category
                    """
                )
                category_rows = cast(list[Mapping[str, Any]], cursor.fetchall())
                by_category = {
                    row["category"]: int(row["count"]) for row in category_rows
                }

        return TicketSummary(
            total=int(totals["total"]),
            escalated=int(totals["escalated"]),
            average_resolution_time_minutes=float(totals["avg_resolution"] or 0),
            average_satisfaction_score=float(totals["avg_satisfaction"] or 0),
            by_priority=by_priority,
            by_category=by_category,
        )
