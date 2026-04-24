"""Cloud Run Job entry point. Scheduled via Cloud Scheduler → Workflows."""
from __future__ import annotations
import os
import sys
from msm_bounds.application import Calibrate
from msm_bounds.infrastructure.bigquery_source import BigQueryPercentileSource
from msm_bounds.infrastructure.github_gateway import GitHubPullRequestGateway


def main() -> None:
    lookback = int(os.environ.get("LOOKBACK_HOURS", "168"))  # 7d default
    current_min = float(os.environ["CURRENT_MIN"])
    current_max = float(os.environ["CURRENT_MAX"])

    source = BigQueryPercentileSource(os.environ["GCP_PROJECT"], os.environ["BQ_DATASET"])
    gateway = GitHubPullRequestGateway(
        token=os.environ["GITHUB_TOKEN"],     # §4: from Secret Manager
        repo_full_name=os.environ["GITHUB_REPO"],
        config_path=os.environ.get("CONFIG_PATH", "infra/runtime_config.json"),
    )
    result = Calibrate(source, gateway).execute(lookback, current_min, current_max)
    print(f"reason={result.reason} pr={result.pr_url}", file=sys.stdout)


if __name__ == "__main__":
    main()
