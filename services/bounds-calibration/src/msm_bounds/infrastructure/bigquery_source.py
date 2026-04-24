"""BigQuery-backed PercentileSource. Reads from rpc_predictions — model path only."""
from __future__ import annotations
from google.cloud import bigquery
from msm_bounds.domain import PercentileSample
from msm_bounds.application.ports import PercentileSource


class BigQueryPercentileSource(PercentileSource):
    def __init__(self, project: str, dataset: str, *, query_timeout_s: float = 30.0) -> None:
        self._client = bigquery.Client(project=project)
        self._project = project
        self._dataset = dataset
        self._query_timeout_s = query_timeout_s

    def sample(self, lookback_hours: int) -> PercentileSample:
        sql = f"""
        WITH filtered AS (
          SELECT predicted_rpc
          FROM `{self._project}.{self._dataset}.rpc_predictions`
          WHERE source = 'MODEL'
            AND predicted_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @h HOUR)
        )
        SELECT
          APPROX_QUANTILES(predicted_rpc, 100)[OFFSET(1)]  AS p1,
          APPROX_QUANTILES(predicted_rpc, 100)[OFFSET(99)] AS p99,
          COUNT(*) AS n
        FROM filtered
        """
        job = self._client.query(
            sql,
            job_config=bigquery.QueryJobConfig(query_parameters=[
                bigquery.ScalarQueryParameter("h", "INT64", lookback_hours),
            ]),
            timeout=self._query_timeout_s,  # §3.2
        )
        row = next(iter(job.result(timeout=self._query_timeout_s)))
        return PercentileSample(
            p1=float(row["p1"] or 0.0),
            p99=float(row["p99"] or 0.0),
            n=int(row["n"] or 0),
        )
