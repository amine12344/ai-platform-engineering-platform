from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

import mlflow

DEFAULT_MODEL = "supportops-priority-classifier"


@dataclass(frozen=True)
class PromotionDecision:
    model_name: str
    version: str
    alias: str
    metric_name: str
    metric_value: float
    threshold: float
    promoted: bool
    reason: str


def find_latest_version(client: mlflow.MlflowClient, model_name: str) -> str:
    versions = client.search_model_versions(f"name = '{model_name}'")
    if not versions:
        raise ValueError(f"No registered versions found for model: {model_name}")
    return max(versions, key=lambda item: int(item.version)).version


def promote_if_qualified(
    *,
    model_name: str,
    version: str | None,
    alias: str,
    metric_name: str,
    threshold: float,
) -> PromotionDecision:
    client = mlflow.MlflowClient()
    resolved_version = version or find_latest_version(client, model_name)
    model_version = client.get_model_version(model_name, resolved_version)
    run = client.get_run(model_version.run_id)

    if metric_name not in run.data.metrics:
        raise ValueError(
            f"Run {model_version.run_id} does not contain metric {metric_name}"
        )

    metric_value = float(run.data.metrics[metric_name])
    promoted = metric_value >= threshold
    if promoted:
        client.set_registered_model_alias(model_name, alias, resolved_version)
        reason = (
            f"{metric_name}={metric_value:.4f} met threshold={threshold:.4f}"
        )
    else:
        reason = (
            f"{metric_name}={metric_value:.4f} was below threshold={threshold:.4f}"
        )

    client.set_model_version_tag(
        model_name,
        resolved_version,
        "supportops.promotion_result",
        "promoted" if promoted else "rejected",
    )
    client.set_model_version_tag(
        model_name,
        resolved_version,
        "supportops.promotion_reason",
        reason,
    )

    return PromotionDecision(
        model_name=model_name,
        version=resolved_version,
        alias=alias,
        metric_name=metric_name,
        metric_value=metric_value,
        threshold=threshold,
        promoted=promoted,
        reason=reason,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Promote a qualified MLflow model")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--version")
    parser.add_argument("--alias", default="candidate")
    parser.add_argument("--metric", default="macro_f1")
    parser.add_argument("--threshold", type=float, default=0.50)
    parser.add_argument("--tracking-uri", default=os.getenv("MLFLOW_TRACKING_URI"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".local/training/promotion.json"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.tracking_uri:
        mlflow.set_tracking_uri(args.tracking_uri)

    decision = promote_if_qualified(
        model_name=args.model,
        version=args.version,
        alias=args.alias,
        metric_name=args.metric,
        threshold=args.threshold,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(asdict(decision), indent=2), encoding="utf-8")
    print(json.dumps(asdict(decision), indent=2))

    if not decision.promoted:
        raise SystemExit(3)


if __name__ == "__main__":
    main()
