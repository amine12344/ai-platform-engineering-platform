from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from train import build_pipeline, load_dataset


class TrainingTests(unittest.TestCase):
    def test_load_dataset_builds_text_column(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tickets.csv"
            pd.DataFrame(
                [
                    {
                        "subject": "VPN issue",
                        "body": "Cannot connect",
                        "product": "VPN",
                        "category": "access",
                        "priority": "P1",
                    },
                    {
                        "subject": "Printer request",
                        "body": "Need paper",
                        "product": "Printer",
                        "category": "hardware",
                        "priority": "P4",
                    },
                ]
            ).to_csv(path, index=False)

            frame = load_dataset(path)

        self.assertIn("text", frame.columns)
        self.assertIn("VPN issue", frame.iloc[0]["text"])
        self.assertIn("product=VPN", frame.iloc[0]["text"])

    def test_load_dataset_rejects_missing_columns(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tickets.csv"
            pd.DataFrame([{"subject": "Only one field"}]).to_csv(path, index=False)
            with self.assertRaisesRegex(ValueError, "missing required columns"):
                load_dataset(path)

    def test_pipeline_can_fit_and_predict(self) -> None:
        x = pd.Series(
            [
                "urgent VPN outage",
                "critical authentication failure",
                "minor printer request",
                "general documentation question",
                "urgent database outage",
                "routine software installation",
                "major network incident",
                "low priority account question",
            ]
        )
        y = pd.Series(["P1", "P1", "P4", "P4", "P1", "P4", "P1", "P4"])
        model = build_pipeline()
        model.fit(x, y)
        predictions = model.predict(pd.Series(["urgent VPN failure"]))
        self.assertEqual(len(predictions), 1)
        self.assertIn(predictions[0], {"P1", "P4"})


if __name__ == "__main__":
    unittest.main()
