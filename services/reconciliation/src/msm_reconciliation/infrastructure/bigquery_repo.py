"""BigQuery-backed ReconciliationRepo — reads predictions_vs_revenue view."""
from __future__ import annotations
from typing import Sequence

from google.cloud import bigquery

from msm_reconciliation.domain import ReconciliationRow, PredictionSource
from msm_reconciliation.application.ports import ReconciliationRepo


class BigQueryReconciliationRepo(ReconciliationRepo):
    def __init__(self, project: str, dataset: str, *, query_timeout_s: float = 10.0) -> None:
        self._client = bigquery.Client(project=project)
        self._project = project
        self._dataset = dataset
        self._query_timeout_s = query_timeout_s

    def fetch_window(self, start_ms: int, end_ms: int) -> Sequence[ReconciliationRow]:
        sql = f"""
        SELECT click_id, predicted_rpc, realized_rpc, source, window_ends_at_ms
        FROM `{self._project}.{self._dataset}.predictions_vs_revenue`
        WHERE window_ends_at_ms BETWEEN @start_ms AND @end_ms
        """
        job = self._client.query(
            sql,
            job_config=bigquery.QueryJobConfig(query_parameters=[
                bigquery.ScalarQueryParameter("start_ms", "INT64", start_ms),
                bigquery.ScalarQueryParameter("end_ms", "INT64", end_ms),
            ]),
            timeout=self._query_timeout_s,  # §3.2
        )
        return [
            ReconciliationRow(
                click_id=row["click_id"],
                predicted_rpc=float(row["predicted_rpc"]),
                realized_rpc=float(row["realized_rpc"]),
                source=PredictionSource(row["source"]),
                window_ends_at_ms=int(row["window_ends_at_ms"]),
            )
            for row in job.result(timeout=self._query_timeout_s)
        ]
