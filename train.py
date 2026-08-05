from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

import mlflow
import mlflow.sklearn
import pandas as pd
from mlflow.models import infer_signature
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import FeatureUnion, Pipeline

DEFAULT_DATASET = Path("datasets/releases/sample/tickets.csv")
DEFAULT_EXPERIMENT = "supportops-ticket-priority"
DEFAULT_REGISTERED_MODEL = "supportops-priority-classifier"


@dataclass(frozen=True)
class TrainingResult:
    run_id: str
    experiment_name: str
    registered_model_name: str
    model_version: str | None
    accuracy: float
    macro_f1: float
    train_rows: int
    test_rows: int


def load_dataset(path: Path) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(f"Dataset does not exist: {path}")

    frame = pd.read_csv(path)
    required = {"subject", "body", "product", "category", "priority"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Dataset is missing required columns: {', '.join(missing)}")
    if frame.empty:
        raise ValueError("Dataset is empty")
    if frame["priority"].nunique() < 2:
        raise ValueError("Training requires at least two priority classes")

    frame = frame.copy()
    for column in ("subject", "body", "product", "category"):
        frame[column] = frame[column].fillna("").astype(str)
    frame["text"] = (
        frame["subject"]
        + " "
        + frame["body"]
        + " product="
        + frame["product"]
        + " category="
        + frame["category"]
    )
    return frame


def build_pipeline(random_state: int = 42) -> Pipeline:
    text_features = FeatureUnion(
        transformer_list=[
            (
                "word_tfidf",
                TfidfVectorizer(
                    ngram_range=(1, 2),
                    min_df=1,
                    max_features=5000,
                    strip_accents="unicode",
                    lowercase=True,
                ),
            ),
            (
                "character_tfidf",
                TfidfVectorizer(
                    analyzer="char_wb",
                    ngram_range=(3, 5),
                    min_df=1,
                    max_features=5000,
                    lowercase=True,
                ),
            ),
        ]
    )
    return Pipeline(
        steps=[
            ("features", text_features),
            (
                "classifier",
                LogisticRegression(
                    max_iter=1000,
                    class_weight="balanced",
                    random_state=random_state,
                ),
            ),
        ]
    )


def train_model(
    *,
    dataset_path: Path,
    experiment_name: str,
    registered_model_name: str,
    test_size: float = 0.2,
    random_state: int = 42,
    register_model: bool = True,
) -> TrainingResult:
    frame = load_dataset(dataset_path)
    x_train, x_test, y_train, y_test = train_test_split(
        frame["text"],
        frame["priority"],
        test_size=test_size,
        random_state=random_state,
        stratify=frame["priority"],
    )

    pipeline = build_pipeline(random_state=random_state)
    mlflow.set_experiment(experiment_name)

    with mlflow.start_run() as run:
        pipeline.fit(x_train, y_train)
        predictions = pipeline.predict(x_test)

        accuracy = float(accuracy_score(y_test, predictions))
        macro_f1 = float(f1_score(y_test, predictions, average="macro"))
        report = classification_report(
            y_test,
            predictions,
            output_dict=True,
            zero_division=0,
        )

        mlflow.log_params(
            {
                "dataset_path": str(dataset_path),
                "dataset_rows": len(frame),
                "test_size": test_size,
                "random_state": random_state,
                "classifier": "LogisticRegression",
                "feature_family": "word_and_character_tfidf",
            }
        )
        mlflow.log_metrics(
            {
                "accuracy": accuracy,
                "macro_f1": macro_f1,
                "train_rows": len(x_train),
                "test_rows": len(x_test),
            }
        )

        report_path = Path(".local/training/classification-report.json")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        mlflow.log_artifact(str(report_path), artifact_path="evaluation")

        signature = infer_signature(x_train.to_frame(name="text"), predictions)
        input_example = x_train.head(3).to_frame(name="text")
        model_info = mlflow.sklearn.log_model(
            sk_model=pipeline,
            artifact_path="model",
            signature=signature,
            input_example=input_example,
            registered_model_name=registered_model_name if register_model else None,
        )

        model_version: str | None = None
        if register_model:
            client = mlflow.MlflowClient()
            versions = client.search_model_versions(f"run_id = '{run.info.run_id}'")
            matching = [
                version
                for version in versions
                if version.name == registered_model_name
            ]
            if matching:
                model_version = max(matching, key=lambda item: int(item.version)).version

        mlflow.set_tag("supportops.component", "priority-classifier")
        mlflow.set_tag("supportops.dataset", dataset_path.name)
        mlflow.set_tag("supportops.model_uri", model_info.model_uri)

        return TrainingResult(
            run_id=run.info.run_id,
            experiment_name=experiment_name,
            registered_model_name=registered_model_name,
            model_version=model_version,
            accuracy=accuracy,
            macro_f1=macro_f1,
            train_rows=len(x_train),
            test_rows=len(x_test),
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the SupportOps priority classifier")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--experiment", default=DEFAULT_EXPERIMENT)
    parser.add_argument("--registered-model", default=DEFAULT_REGISTERED_MODEL)
    parser.add_argument("--tracking-uri", default=os.getenv("MLFLOW_TRACKING_URI"))
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--no-register", action="store_true")
    parser.add_argument("--output", type=Path, default=Path(".local/training/result.json"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.tracking_uri:
        mlflow.set_tracking_uri(args.tracking_uri)

    result = train_model(
        dataset_path=args.dataset,
        experiment_name=args.experiment,
        registered_model_name=args.registered_model,
        test_size=args.test_size,
        random_state=args.random_state,
        register_model=not args.no_register,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(asdict(result), indent=2), encoding="utf-8")
    print(json.dumps(asdict(result), indent=2))


if __name__ == "__main__":
    main()
