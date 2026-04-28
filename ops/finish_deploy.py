"""Resume step 5 of deploy_real_model.py after the client-side LRO polling
timed out. The model upload succeeded server-side; we just need to deploy
the new model onto the existing endpoint, shift traffic, and undeploy the
old version to keep replica cost flat.

Run via the same .venv-deploy-model venv as deploy_real_model.py.
"""
from __future__ import annotations

PROJECT  = "msm-rpc"
REGION   = "europe-west2"

NEW_MODEL_ID  = "6679238469622956032"
ENDPOINT_ID   = "4471390533746425856"


def main() -> None:
    from google.cloud import aiplatform
    aiplatform.init(project=PROJECT, location=REGION)

    model    = aiplatform.Model(model_name=f"projects/{PROJECT}/locations/{REGION}/models/{NEW_MODEL_ID}")
    endpoint = aiplatform.Endpoint(endpoint_name=f"projects/{PROJECT}/locations/{REGION}/endpoints/{ENDPOINT_ID}")

    existing = list(endpoint.list_models())
    print(f"existing deployed models on endpoint: {[(d.id, d.display_name) for d in existing]}")

    print("deploying new model (sync, may take ~10 min)...")
    endpoint.deploy(
        model=model,
        deployed_model_display_name="rpc-estimator-deploy-v2",
        machine_type="e2-standard-2",
        min_replica_count=1,
        max_replica_count=1,
        traffic_percentage=100,
    )
    print("deploy complete; current traffic split:", endpoint.traffic_split)

    for d in existing:
        print(f"undeploying old deployed_model_id={d.id} ({d.display_name})")
        endpoint.undeploy(deployed_model_id=d.id)

    print("done. endpoint:", endpoint.resource_name)


if __name__ == "__main__":
    main()
