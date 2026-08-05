from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from datasets.generate_supportops import FIELDS, write_dataset
from datasets.verify_supportops import validate_dataset

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads(
    (ROOT / "datasets/releases/sample/manifest.json").read_text(
        encoding="utf-8"
    )
)


class DatasetTests(unittest.TestCase):
    def test_generator_matches_release_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "tickets.csv"
            checksum = write_dataset(
                output=output,
                seed=MANIFEST["seed"],
                count=MANIFEST["rows"],
            )
            self.assertEqual(MANIFEST["sha256"], checksum)
            evidence = validate_dataset(
                output,
                expected_rows=MANIFEST["rows"],
                expected_sha256=MANIFEST["sha256"],
            )
            self.assertEqual(MANIFEST["rows"], evidence["rows"])
            self.assertEqual(MANIFEST["fields"], evidence["schema_fields"])

    def test_validator_rejects_duplicate_ticket_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "tickets.csv"
            write_dataset(output=output, seed=123, count=2)
            with output.open(newline="", encoding="utf-8") as file:
                rows = list(csv.DictReader(file))
            rows[1]["ticket_id"] = rows[0]["ticket_id"]
            with output.open("w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=FIELDS)
                writer.writeheader()
                writer.writerows(rows)
            with self.assertRaisesRegex(ValueError, "duplicates"):
                validate_dataset(output, expected_rows=2)

    def test_validator_rejects_invalid_priority(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "tickets.csv"
            write_dataset(output=output, seed=123, count=1)
            with output.open(newline="", encoding="utf-8") as file:
                rows = list(csv.DictReader(file))
            rows[0]["priority"] = "URGENT"
            with output.open("w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=FIELDS)
                writer.writeheader()
                writer.writerows(rows)
            with self.assertRaisesRegex(ValueError, "invalid priority"):
                validate_dataset(output, expected_rows=1)


if __name__ == "__main__":
    unittest.main()
