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
# Reuse the existing endpoint to avoid spinning up a second billable endpoint
# (memory: "no spend-increasing scale-up"). New model is added with 100%
# traffic; old deployedModels are undeployed after the new one is live.
ENDPOINT_ID = "4471390533746425856"

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
    # Schema: PRD V2 (Credit Cards) §7.1. Feature order MUST match
    # services/ml-pipeline/.../xgboost_trainer.py _FEATURE_ORDER and the
    # serving payload in services/scoring-api/.../vertex_endpoint.rs.
    df = bq.query(f"""
        SELECT
          hour_of_day, affinity_score, rpc_14d, rpc_60d,
          CAST(prior_applicant AS INT64) AS prior_applicant,
          auction_pressure, visits_prev_30d,
          CAST(phoebe_calculator_used AS INT64) AS phoebe_calculator_used,
          phoebe_guides_read, phoebe_cards_compared, phoebe_session_engagement_s,
          target_revenue
        FROM `{PROJECT}.{DATASET}.rpc_training_rows`
    """).to_dataframe()
    print(f"   n={len(df)}  mean(target)={df['target_revenue'].mean():.3f}")

    # MUST match services/scoring-api/.../vertex_endpoint.rs payload order
    # AND ops/explanation_metadata.json index_feature_mapping.
    feature_cols = [
        "hour_of_day", "affinity_score", "rpc_14d", "rpc_60d",
        "prior_applicant", "auction_pressure", "visits_prev_30d",
        "phoebe_calculator_used", "phoebe_guides_read",
        "phoebe_cards_compared", "phoebe_session_engagement_s",
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
        # Use the booster API directly: XGBRegressor.save_model() pulls in the
        # sklearn estimator wrapper, which broke between xgboost 1.7 (pinned to
        # match the Vertex serving container) and sklearn>=1.5. The Vertex
        # xgboost-cpu container only needs the booster artifact.
        model.get_booster().save_model(str(path))
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

    # ---------- 5. Deploy new version to the EXISTING endpoint ----------
    step(f"5/6 deploy to existing endpoint {ENDPOINT_ID} (slowest step; ~8 min)")
    endpoint = aiplatform.Endpoint(
        endpoint_name=f"projects/{PROJECT}/locations/{REGION}/endpoints/{ENDPOINT_ID}"
    )
    pre_deployed = list(endpoint.list_models())
    print(f"   existing deployedModels: {[d.id for d in pre_deployed]}")
    endpoint.deploy(
        model=registered,
        deployed_model_display_name=f"{MODEL_ID}-deploy-{int(time.time())}",
        machine_type="e2-standard-2",
        min_replica_count=1,
        max_replica_count=1,
        traffic_percentage=100,  # SDK rebalances traffic to 100% new
    )
    # Undeploy the previous deployedModels after the new one is serving 100%
    # so we don't keep paying for two replicas.
    for old in pre_deployed:
        print(f"   undeploying old deployedModel id={old.id}")
        endpoint.undeploy(deployed_model_id=old.id)
    print(f"   endpoint resource = {endpoint.resource_name}")

    # ---------- 6. Secret URL is unchanged (same endpoint) ----------
    step("6/6 verify secret URL still points at this endpoint")
    expected = (
        f"https://{REGION}-aiplatform.googleapis.com/v1/"
        f"projects/{PROJECT}/locations/{REGION}/endpoints/{ENDPOINT_ID}:predict"
    )
    sm = secretmanager.SecretManagerServiceClient()
    current = sm.access_secret_version(
        request={"name": f"projects/{PROJECT}/secrets/{SECRET}/versions/latest"}
    ).payload.data.decode("utf-8").strip()
    if current != expected:
        print(f"   secret drift — updating to {expected}")
        sm.add_secret_version(request={
            "parent": f"projects/{PROJECT}/secrets/{SECRET}",
            "payload": {"data": expected.encode("utf-8")},
        })
    else:
        print(f"   secret OK ({expected})")

    print("\n✓ done. scoring-api reads the endpoint URL at boot, so no restart")
    print("  is needed if the secret didn't change. If it did, force a new revision:")
    print(f"   gcloud run services update scoring-api-staging "
          f"--project={PROJECT} --region={REGION} --update-labels=deploy=$(date +%s)")


if __name__ == "__main__":
    main()
