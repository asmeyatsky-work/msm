"""DistributionHistory adapters. Layer: infrastructure. Implements
application.DistributionHistory. §4: Workload Identity, query timeout, no PII.

`BigQueryDistributionHistory` reads daily-bucketed prediction percentiles from
`rpc_predictions` (model path only), mirroring `bigquery_source.py`, so the agent
can tell a sustained shift from a single-bucket spike. `InMemoryDistributionHistory`
is the in-memory/test adapter (§3.2).
"""
from __future__ import annotations
from typing import Sequence

import structlog
from google.cloud import bigquery

from msm_bounds.application.ports import DistributionHistory
from msm_bounds.domain import PercentileSample

_log = structlog.get_logger()


class InMemoryDistributionHistory(DistributionHistory):
    def __init__(self, samples: Sequence[PercentileSample]) -> None:
        self._samples = tuple(samples)

    def recent_samples(self, lookback_hours: int, buckets: int) -> Sequence[PercentileSample]:
        return self._samples[:buckets]


class BigQueryDistributionHistory(DistributionHistory):
    def __init__(self, project: str, dataset: str, *, query_timeout_s: float = 30.0) -> None:
        self._client = bigquery.Client(project=project)
        self._project = project
        self._dataset = dataset
        self._query_timeout_s = query_timeout_s

    def recent_samples(self, lookback_hours: int, buckets: int) -> Sequence[PercentileSample]:
        sql = f"""
        SELECT
          APPROX_QUANTILES(predicted_rpc, 100)[OFFSET(1)]  AS p1,
          APPROX_QUANTILES(predicted_rpc, 100)[OFFSET(99)] AS p99,
          COUNT(*) AS n
        FROM `{self._project}.{self._dataset}.rpc_predictions`
        WHERE source = 'MODEL'
          AND predicted_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @h HOUR)
        GROUP BY DATE(predicted_at)
        ORDER BY DATE(predicted_at) DESC
        LIMIT @buckets
        """
        try:
            job = self._client.query(
                sql,
                job_config=bigquery.QueryJobConfig(query_parameters=[
                    bigquery.ScalarQueryParameter("h", "INT64", lookback_hours),
                    bigquery.ScalarQueryParameter("buckets", "INT64", buckets),
                ]),
                timeout=self._query_timeout_s,  # §3.2
            )
            return [
                PercentileSample(p1=float(row["p1"] or 0.0), p99=float(row["p99"] or 0.0),
                                 n=int(row["n"] or 0))
                for row in job.result(timeout=self._query_timeout_s)
            ]
        except Exception as e:  # noqa: BLE001 — degrade to current-sample-only reasoning
            _log.warning("distribution_history_query_failed", error=str(e))
            return ()
