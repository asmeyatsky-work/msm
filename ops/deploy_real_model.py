"""One-shot: train XGBoost on synthetic BQ data → upload to Vertex AI Model
Registry → deploy to an Online Endpoint → update vertex-endpoint-url secret.

Assumes ADC is authenticated to msm-rpc with quota project set. Takes about
10-15 minutes end-to-end (endpoint deploy is the slow part).

Usage:
    python3 ops/deploy_real_model.py
"""
from __future__ import annotations
import io
import os
import subprocess
import tempfile
import time
from pathlib import Path

PROJECT  = "msm-rpc"
REGION   = "europe-west2"
DATASET  = "rpc_estimator_staging"
BUCKET   = "msm-rpc-rpc-artifacts-staging"
SECRET   = "vertex-endpoint-url-staging"
MODEL_ID = "rpc-estimator"

# Vertex AI prebuilt XGBoost serving container in europe-west2.
SERVING_IMAGE = "europe-docker.pkg.dev/vertex-ai/prediction/xgboost-cpu.1-7:latest"


def step(msg: str) -> None:
    print(f"\n=== {msg} ===", flush=True)


def main() -> None:
    import pandas as pd
    import numpy as np
    import xgboost as xgb
    from google.cloud import bigquery, storage, aiplatform
    from google.cloud import secretmanager

    # ---------- 1. Pull training frame from BQ ----------
    step("1/6 fetch training frame from BQ")
    bq = bigquery.Client(project=PROJECT)
    df = bq.query(f"""
        SELECT
          hour_of_day, cerberus_score, rpc_7d, rpc_14d, rpc_30d,
          CAST(is_payday_week AS INT64) AS is_payday_week,
          auction_pressure, visits_prev_30d, target_revenue
        FROM `{PROJECT}.{DATASET}.rpc_training_rows`
    """).to_dataframe()
    print(f"   n={len(df)}  mean(target)={df['target_revenue'].mean():.3f}")

    feature_cols = [
        "hour_of_day", "cerberus_score", "rpc_7d", "rpc_14d", "rpc_30d",
        "is_payday_week", "auction_pressure", "visits_prev_30d",
    ]
    X = df[feature_cols].to_numpy(dtype=np.float32)
    y = df["target_revenue"].to_numpy(dtype=np.float32)

    # ---------- 2. Train XGBoost ----------
    step("2/6 train XGBoost")
    model = xgb.XGBRegressor(
        max_depth=6, n_estimators=400, learning_rate=0.05,
        objective="reg:squarederror", tree_method="hist",
    )
    model.fit(X, y)
    pred = model.predict(X[:5])
    print(f"   sample predictions: {pred.tolist()}")

    # ---------- 3. Save model artifact to GCS ----------
    step("3/6 upload model artifact to GCS")
    with tempfile.TemporaryDirectory() as tmp:
        # Vertex AI's xgboost-cpu.1-7 expects a file named `model.bst` under
        # the artifact_uri directory.
        path = Path(tmp) / "model.bst"
        model.save_model(str(path))
        blob_path = f"models/{MODEL_ID}/{int(time.time())}"
        gcs = storage.Client(project=PROJECT).bucket(BUCKET)
        gcs.blob(f"{blob_path}/model.bst").upload_from_filename(str(path))
        artifact_uri = f"gs://{BUCKET}/{blob_path}"
        print(f"   artifact_uri = {artifact_uri}")

    # ---------- 4. Register model in Vertex AI ----------
    # ADR 0002: explanationSpec is required so /v1/explain returns real
    # attributions. Sampled-shapley with paths=10 is the standard tradeoff.
    step("4/6 register model in Vertex AI (with explanationSpec)")
    aiplatform.init(project=PROJECT, location=REGION, staging_bucket=f"gs://{BUCKET}")
    import json as _json
    metadata_path = Path(__file__).parent / "explanation_metadata.json"
    explain_meta = _json.loads(metadata_path.read_text())
    explanation_spec = aiplatform.explain.ExplanationSpec(
        parameters=aiplatform.explain.ExplanationParameters(
            sampled_shapley_attribution=aiplatform.explain.SampledShapleyAttribution(path_count=10),
        ),
        metadata=aiplatform.explain.ExplanationMetadata(
            inputs={
                k: aiplatform.explain.ExplanationMetadata.InputMetadata(
                    encoding=v.get("encoding", "IDENTITY"),
                    modality=v.get("modality"),
                    index_feature_mapping=v.get("index_feature_mapping"),
                )
                for k, v in explain_meta["inputs"].items()
            },
            outputs={
                k: aiplatform.explain.ExplanationMetadata.OutputMetadata()
                for k in explain_meta["outputs"]
            },
        ),
    )
    registered = aiplatform.Model.upload(
        display_name=MODEL_ID,
        artifact_uri=artifact_uri,
        serving_container_image_uri=SERVING_IMAGE,
        explanation_parameters=explanation_spec.parameters,
        explanation_metadata=explanation_spec.metadata,
    )
    registered.wait()
    print(f"   model resource = {registered.resource_name}")

    # ---------- 5. Create endpoint + deploy model ----------
    step("5/6 deploy to endpoint (slowest step; ~8 min)")
    endpoint = aiplatform.Endpoint.create(display_name=f"{MODEL_ID}-endpoint")
    endpoint.deploy(
        model=registered,
        deployed_model_display_name=f"{MODEL_ID}-deploy",
        machine_type="e2-standard-2",
        min_replica_count=1,
        max_replica_count=1,
        traffic_percentage=100,
    )
    print(f"   endpoint resource = {endpoint.resource_name}")
    predict_url = (
        f"https://{REGION}-aiplatform.googleapis.com/v1/{endpoint.resource_name}:predict"
    )
    print(f"   predict_url = {predict_url}")

    # ---------- 6. Update Secret Manager ----------
    step("6/6 update vertex-endpoint-url secret")
    sm = secretmanager.SecretManagerServiceClient()
    parent = f"projects/{PROJECT}/secrets/{SECRET}"
    version = sm.add_secret_version(
        request={"parent": parent, "payload": {"data": predict_url.encode("utf-8")}},
    )
    print(f"   new secret version: {version.name}")

    print("\n✓ done. Restart scoring-api to pick up the new URL:")
    print(f"   gcloud run services update scoring-api-staging "
          f"--project={PROJECT} --region={REGION} --update-labels=deploy=$(date +%s)")


if __name__ == "__main__":
    main()
