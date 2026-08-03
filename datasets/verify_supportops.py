#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

try:
    from .generate_supportops import (
        CATEGORY_PRODUCTS,
        CHANNELS,
        CUSTOMER_TIERS,
        FIELDS,
        LANGUAGES,
        PRIORITIES,
    )
except ImportError:  # Support direct execution as a script.
    from generate_supportops import (
        CATEGORY_PRODUCTS,
        CHANNELS,
        CUSTOMER_TIERS,
        FIELDS,
        LANGUAGES,
        PRIORITIES,
    )


def validate_dataset(
    path: Path,
    expected_rows: int,
    expected_sha256: str | None = None,
) -> dict[str, int | str]:
    if not path.is_file():
        raise ValueError(f"dataset does not exist: {path}")

    digest = hashlib.sha256(path.read_bytes()).hexdigest()

    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError(
            f"content hash differs from release manifest: {digest}"
        )

    with path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        if reader.fieldnames != FIELDS:
            raise ValueError(
                f"schema differs from canonical fields: {reader.fieldnames}"
            )

        records = list(reader)

    if len(records) != expected_rows:
        raise ValueError(
            f"expected {expected_rows} rows; observed {len(records)}"
        )

    identifiers = [record["ticket_id"] for record in records]

    if len(identifiers) != len(set(identifiers)):
        raise ValueError("ticket_id contains duplicates")

    for line_number, record in enumerate(records, start=2):
        try:
            datetime.fromisoformat(
                record["created_at"].replace("Z", "+00:00")
            )
            satisfaction_score = int(record["satisfaction_score"])
            resolution_minutes = int(
                record["resolution_time_minutes"]
            )
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"row {line_number} contains an invalid typed value: {error}"
            ) from error

        if record["priority"] not in PRIORITIES:
            raise ValueError(
                f"row {line_number} has an invalid priority"
            )

        if record["category"] not in CATEGORY_PRODUCTS:
            raise ValueError(
                f"row {line_number} has an invalid category"
            )

        valid_products = CATEGORY_PRODUCTS[record["category"]]

        if record["product"] not in valid_products:
            raise ValueError(
                f"row {line_number} has an invalid category/product pair"
            )

        if record["channel"] not in CHANNELS:
            raise ValueError(
                f"row {line_number} has an invalid channel"
            )

        if record["language"] not in LANGUAGES:
            raise ValueError(
                f"row {line_number} has an invalid language"
            )

        if record["customer_tier"] not in CUSTOMER_TIERS:
            raise ValueError(
                f"row {line_number} has an invalid customer tier"
            )

        if record["escalated"] not in {"true", "false"}:
            raise ValueError(
                f"row {line_number} has an invalid escalated value"
            )

        if resolution_minutes <= 0:
            raise ValueError(
                f"row {line_number} has an invalid resolution time"
            )

        if not 1 <= satisfaction_score <= 5:
            raise ValueError(
                f"row {line_number} has an invalid satisfaction score"
            )

        if not record["subject"].strip():
            raise ValueError(
                f"row {line_number} is missing a subject"
            )

        if not record["body"].strip():
            raise ValueError(
                f"row {line_number} is missing a body"
            )

    return {
        "schema_fields": len(FIELDS),
        "rows": len(records),
        "unique_ticket_ids": len(set(identifiers)),
        "sha256": digest,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate a SupportOps dataset"
    )

    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=Path(
            "datasets/releases/sample/tickets.csv"
        ),
    )

    parser.add_argument(
        "--rows",
        type=int,
        default=250,
    )

    args = parser.parse_args()

    manifest_path = (
        Path(__file__).parent
        / "releases"
        / "sample"
        / "manifest.json"
    )

    manifest = json.loads(
        manifest_path.read_text(encoding="utf-8")
    )

    expected_sha256 = None

    if args.rows == manifest["rows"]:
        expected_sha256 = manifest["sha256"]

    try:
        evidence = validate_dataset(
            path=args.path,
            expected_rows=args.rows,
            expected_sha256=expected_sha256,
        )
    except ValueError as error:
        print(f"FAIL  {error}", file=sys.stderr)
        raise SystemExit(1) from error

    print(
        "PASS  "
        f"schema={evidence['schema_fields']} fields "
        f"rows={evidence['rows']} "
        f"unique_ticket_ids={evidence['unique_ticket_ids']} "
        f"sha256={evidence['sha256']}"
    )


if __name__ == "__main__":
    main()
