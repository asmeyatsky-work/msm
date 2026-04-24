"""CLI for the ml-pipeline. Wires adapters into use cases."""
from __future__ import annotations
import argparse
from msm_ml.application import TrainModel
from msm_ml.infrastructure.bigquery_feature_repo import BigQueryFeatureRepo
from msm_ml.infrastructure.xgboost_trainer import XGBoostTrainer
from msm_ml.infrastructure.vertex_registry import VertexModelRegistry


def main() -> None:
    parser = argparse.ArgumentParser(prog="msm-ml")
    sub = parser.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("train")
    t.add_argument("--model-id", required=True)
    t.add_argument("--start-ms", type=int, required=True)
    t.add_argument("--end-ms", type=int, required=True)
    t.add_argument("--project", required=True)
    t.add_argument("--dataset", required=True)
    t.add_argument("--region", default="us-central1")
    t.add_argument("--staging-bucket", required=True, help="gs://... bucket for model artifacts")

    args = parser.parse_args()

    if args.cmd == "train":
        use_case = TrainModel(
            features=BigQueryFeatureRepo(args.project, args.dataset),
            trainer=XGBoostTrainer(),
            registry=VertexModelRegistry(args.project, args.region, args.staging_bucket),
        )
        result = use_case.execute(args.model_id, args.start_ms, args.end_ms)
        print(result.model_version.qualified(), result.n_rows)


if __name__ == "__main__":
    main()
