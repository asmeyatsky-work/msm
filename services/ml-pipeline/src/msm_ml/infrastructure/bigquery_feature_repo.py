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
          click_id, vertical_id, device, geo, hour_of_day,
          product_type, card_product_id, query_intent,
          affinity_score, prior_applicant, income_band_bucket,
          auction_pressure, rpc_14d, rpc_60d,
          visits_prev_30d,
          phoebe_calculator_used, phoebe_guides_read,
          phoebe_cards_compared, phoebe_session_engagement_s,
          target_revenue
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
            band = row["income_band_bucket"]
            fv = FeatureVector(
                click_id=row["click_id"],
                vertical_id=row["vertical_id"],
                device=row["device"],
                geo=row["geo"],
                hour_of_day=int(row["hour_of_day"]),
                product_type=row["product_type"],
                card_product_id=row["card_product_id"],
                query_intent=row["query_intent"],
                affinity_score=float(row["affinity_score"]),
                prior_applicant=bool(row["prior_applicant"]),
                income_band_bucket=band if band else None,
                auction_pressure=float(row["auction_pressure"]),
                rpc_14d=float(row["rpc_14d"]),
                rpc_60d=float(row["rpc_60d"]),
                visits_prev_30d=int(row["visits_prev_30d"]),
                phoebe_calculator_used=bool(row.get("phoebe_calculator_used") or False),
                phoebe_guides_read=int(row.get("phoebe_guides_read") or 0),
                phoebe_cards_compared=int(row.get("phoebe_cards_compared") or 0),
                phoebe_session_engagement_s=float(row.get("phoebe_session_engagement_s") or 0.0),
            )
            out.append((fv, float(row["target_revenue"])))
        return out
