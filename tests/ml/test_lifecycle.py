from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from lifecycle import find_latest_version, promote_if_qualified


class LifecycleTests(unittest.TestCase):
    def test_find_latest_version_uses_highest_numeric_version(self) -> None:
        client = MagicMock()
        client.search_model_versions.return_value = [
            SimpleNamespace(version="2"),
            SimpleNamespace(version="10"),
            SimpleNamespace(version="3"),
        ]
        self.assertEqual(find_latest_version(client, "model"), "10")

    def test_promotion_sets_alias_when_metric_passes(self) -> None:
        client = MagicMock()
        client.get_model_version.return_value = SimpleNamespace(run_id="run-1")
        client.get_run.return_value = SimpleNamespace(
            data=SimpleNamespace(metrics={"macro_f1": 0.81})
        )

        with patch("lifecycle.mlflow.MlflowClient", return_value=client):
            decision = promote_if_qualified(
                model_name="supportops-priority-classifier",
                version="4",
                alias="candidate",
                metric_name="macro_f1",
                threshold=0.70,
            )

        self.assertTrue(decision.promoted)
        client.set_registered_model_alias.assert_called_once_with(
            "supportops-priority-classifier", "candidate", "4"
        )

    def test_promotion_rejects_version_below_threshold(self) -> None:
        client = MagicMock()
        client.get_model_version.return_value = SimpleNamespace(run_id="run-2")
        client.get_run.return_value = SimpleNamespace(
            data=SimpleNamespace(metrics={"macro_f1": 0.40})
        )

        with patch("lifecycle.mlflow.MlflowClient", return_value=client):
            decision = promote_if_qualified(
                model_name="supportops-priority-classifier",
                version="5",
                alias="candidate",
                metric_name="macro_f1",
                threshold=0.70,
            )

        self.assertFalse(decision.promoted)
        client.set_registered_model_alias.assert_not_called()


if __name__ == "__main__":
    unittest.main()
