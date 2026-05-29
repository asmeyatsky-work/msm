"""DistributionHistory adapters. Layer: infrastructure. Implements
application.DistributionHistory. §4: Workload Identity, query timeout, no PII.

`InMemoryDistributionHistory` is the in-memory/test adapter (§3.2).
`BigQueryDistributionHistory` reads bucketed percentiles from rpc_predictions —
scaffolded; the bucketed query is a TODO. Returns [] on failure so the agent
degrades to current-sample-only reasoning rather than blocking.
"""
from __future__ import annotations
from typing import Sequence

import structlog

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
        self._project = project
        self._dataset = dataset
        self._query_timeout_s = query_timeout_s

    def recent_samples(self, lookback_hours: int, buckets: int) -> Sequence[PercentileSample]:
        # TODO(agentic-ops): APPROX_QUANTILES grouped by TIMESTAMP_BUCKET over the
        # lookback window (mirror bigquery_source.py), bounded by query_timeout_s.
        _log.warning("distribution_history_stub", lookback_hours=lookback_hours,
                     buckets=buckets, note="returning no history — not yet wired")
        return ()
