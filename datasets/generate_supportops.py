#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import hashlib
import random
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path

FIELDS = [
    "ticket_id",
    "created_at",
    "channel",
    "language",
    "customer_tier",
    "product",
    "subject",
    "body",
    "category",
    "priority",
    "escalated",
    "resolution_time_minutes",
    "agent_response",
    "satisfaction_score",
]

CATEGORY_PRODUCTS = {
    "access": ("Identity Portal", "VPN"),
    "hardware": ("Laptop", "Monitor", "Peripheral"),
    "network": ("Corporate WiFi", "VPN", "DNS"),
    "software": ("CRM", "Finance Suite", "Developer Tools"),
    "collaboration": ("Email", "Calendar", "Video Conferencing"),
}

PRIORITIES = ("P1", "P2", "P3", "P4")
CHANNELS = ("portal", "email", "chat", "phone")
LANGUAGES = ("en", "fr", "es", "de")
CUSTOMER_TIERS = ("standard", "premium", "enterprise")


def generate_rows(seed: int, count: int) -> Iterator[dict[str, str | int]]:
    rng = random.Random(seed)
    base_time = datetime(2026, 1, 5, 8, 0, tzinfo=timezone.utc)

    for index in range(1, count + 1):
        category = rng.choice(tuple(CATEGORY_PRODUCTS))
        product = rng.choice(CATEGORY_PRODUCTS[category])

        priority = rng.choices(
            PRIORITIES,
            weights=(2, 13, 55, 30),
            k=1,
        )[0]

        escalated = priority == "P1" or (
            priority == "P2" and rng.random() < 0.35
        )

        resolution_limit = {
            "P1": 120,
            "P2": 360,
            "P3": 1440,
            "P4": 2880,
        }[priority]

        created_at = base_time + timedelta(
            minutes=(index - 1) * 47 + rng.randint(0, 30)
        )

        yield {
            "ticket_id": f"SUP-{index:06d}",
            "created_at": created_at.isoformat().replace("+00:00", "Z"),
            "channel": rng.choice(CHANNELS),
            "language": rng.choices(
                LANGUAGES,
                weights=(70, 12, 10, 8),
                k=1,
            )[0],
            "customer_tier": rng.choice(CUSTOMER_TIERS),
            "product": product,
            "subject": f"{product} {category} support request",
            "body": (
                f"User reports a {category} issue affecting "
                f"{product} during normal work."
            ),
            "category": category,
            "priority": priority,
            "escalated": str(escalated).lower(),
            "resolution_time_minutes": rng.randint(8, resolution_limit),
            "agent_response": (
                f"SupportOps diagnosed and resolved the {product} request."
            ),
            "satisfaction_score": rng.randint(1, 5),
        }


def write_dataset(output: Path, seed: int, count: int) -> str:
    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=FIELDS,
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(generate_rows(seed, count))

    return hashlib.sha256(output.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate deterministic SupportOps tickets"
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=20260713,
    )

    parser.add_argument(
        "--rows",
        type=int,
        default=250,
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("datasets/releases/sample/tickets.csv"),
    )

    args = parser.parse_args()

    checksum = write_dataset(
        output=args.output,
        seed=args.seed,
        count=args.rows,
    )

    print(
        f"generated={args.output} "
        f"rows={args.rows} "
        f"seed={args.seed} "
        f"sha256={checksum}"
    )


if __name__ == "__main__":
    main()