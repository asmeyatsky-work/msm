"""Retrain via the existing ml-pipeline-train Cloud Run Job. Layer:
infrastructure. Implements application.Trainer.

The drift agent runs on a request-scoped Cloud Run service; training is heavy and
long-running, so RETRAIN does NOT train in-process — it fires the existing
ml-pipeline-train Job (the canonical training path) with the agent's window as a
container-arg override, and returns immediately. The returned ModelVersion is a
sentinel ("job-triggered") since registration completes asynchronously in the
Job. §4: Workload Identity; the run-job call is the audited side effect.
"""
from __future__ import annotations

import structlog
from google.cloud import run_v2

from msm_ml.application import TrainModelResult
from msm_ml.domain import ModelVersion

_log = structlog.get_logger()


class CloudRunJobTrainModel:
    def __init__(self, project: str, region: str, job_name: str, *,
                 dataset: str, staging_bucket: str) -> None:
        self._client = run_v2.JobsClient()
        self._job_path = f"projects/{project}/locations/{region}/jobs/{job_name}"
        self._project = project
        self._dataset = dataset
        self._staging_bucket = staging_bucket

    def execute(self, model_id: str, window_start_ms: int, window_end_ms: int) -> TrainModelResult:
        args = [
            "train", "--model-id", model_id,
            "--start-ms", str(window_start_ms), "--end-ms", str(window_end_ms),
            "--project", self._project, "--dataset", self._dataset,
            "--staging-bucket", self._staging_bucket,
        ]
        request = run_v2.RunJobRequest(
            name=self._job_path,
            overrides=run_v2.RunJobRequest.Overrides(
                container_overrides=[
                    run_v2.RunJobRequest.Overrides.ContainerOverride(args=args)
                ],
            ),
        )
        self._client.run_job(request=request)  # fire-and-forget; Job registers async
        _log.info("retrain_job_triggered", job=self._job_path, model_id=model_id,
                  start_ms=window_start_ms, end_ms=window_end_ms)
        return TrainModelResult(
            model_version=ModelVersion(model_id, "job-triggered", window_end_ms),
            n_rows=0,
        )
