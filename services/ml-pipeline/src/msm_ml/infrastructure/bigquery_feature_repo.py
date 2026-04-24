"""BigQuery-backed FeatureRepo (PRD §2.2). §3.1: no business logic here — I/O only."""
from __future__ import annotations
from typing import Sequence

from google.cloud import bigquery

from msm_ml.domain import FeatureVector
from msm_ml.application.ports import FeatureRepo


# Training view; produced by Dataform (PRD §2.2) and kept stable as a contract.
_TRAINING_VIEW = "rpc_training_rows"


class BigQueryFeatureRepo(FeatureRepo):
    def __init__(self, project: str, dataset: str, *, query_timeout_s: float = 60.0) -> None:
        # §4: auth via Workload Identity; no keys in code/env.
        self._client = bigquery.Client(project=project)
        self._project = project
        self._dataset = dataset
        self._query_timeout_s = query_timeout_s

    def load_training_frame(self, start_ms: int, end_ms: int) -> Sequence[tuple[FeatureVector, float]]:
        sql = f"""
        SELECT
          click_id, device, geo, hour_of_day, cerberus_score,
          rpc_7d, rpc_14d, rpc_30d, is_payday_week, auction_pressure,
          visits_prev_30d, target_revenue
        FROM `{self._project}.{self._dataset}.{_TRAINING_VIEW}`
        WHERE click_ts_ms BETWEEN @start_ms AND @end_ms
        """
        job = self._client.query(
            sql,
            job_config=bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("start_ms", "INT64", start_ms),
                    bigquery.ScalarQueryParameter("end_ms", "INT64", end_ms),
                ],
            ),
            timeout=self._query_timeout_s,  # §3.2: explicit timeout
        )
        out: list[tuple[FeatureVector, float]] = []
        for row in job.result(timeout=self._query_timeout_s):
            fv = FeatureVector(
                click_id=row["click_id"],
                device=row["device"],
                geo=row["geo"],
                hour_of_day=int(row["hour_of_day"]),
                cerberus_score=float(row["cerberus_score"]),
                rpc_7d=float(row["rpc_7d"]),
                rpc_14d=float(row["rpc_14d"]),
                rpc_30d=float(row["rpc_30d"]),
                is_payday_week=bool(row["is_payday_week"]),
                auction_pressure=float(row["auction_pressure"]),
                visits_prev_30d=int(row["visits_prev_30d"]),
            )
            out.append((fv, float(row["target_revenue"])))
        return out
