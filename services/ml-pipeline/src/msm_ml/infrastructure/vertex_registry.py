"""Vertex AI Model Registry adapter — uploads via google-cloud-aiplatform."""
from __future__ import annotations
import time
import tempfile
from pathlib import Path

from google.cloud import aiplatform
from google.cloud import storage

from msm_ml.domain import ModelVersion
from msm_ml.application.ports import ModelRegistry


class VertexModelRegistry(ModelRegistry):
    """Registers a serialized XGBoost booster as a Vertex AI Model.

    Flow: stage artifact in GCS → aiplatform.Model.upload → return ModelVersion.
    §4: Workload Identity only — no key files. §3.1: no business logic.
    """

    def __init__(self, project: str, region: str, staging_bucket: str) -> None:
        aiplatform.init(project=project, location=region, staging_bucket=staging_bucket)
        self._storage = storage.Client(project=project)
        self._bucket_name = staging_bucket.removeprefix("gs://")
        self._latest: dict[str, ModelVersion] = {}
        self._region = region

    def register(self, artifact: bytes, model_id: str) -> ModelVersion:
        ts = int(time.time())
        blob_path = f"models/{model_id}/{ts}/model.xgb"
        bucket = self._storage.bucket(self._bucket_name)
        blob = bucket.blob(blob_path)
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "model.xgb"
            p.write_bytes(artifact)
            blob.upload_from_filename(str(p))
        uploaded = aiplatform.Model.upload(
            display_name=model_id,
            artifact_uri=f"gs://{self._bucket_name}/models/{model_id}/{ts}",
            serving_container_image_uri=(
                f"{self._region}-docker.pkg.dev/vertex-ai/prediction/xgboost-cpu.1-7:latest"
            ),
        )
        version = uploaded.version_id or f"v{ts}"
        mv = ModelVersion(model_id=model_id, version=version, trained_at_epoch_ms=ts * 1000)
        self._latest[model_id] = mv
        return mv

    def latest(self, model_id: str) -> ModelVersion | None:
        return self._latest.get(model_id)
