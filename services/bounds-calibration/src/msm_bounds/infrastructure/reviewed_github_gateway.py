"""ReviewedPullRequestGateway adapter. Layer: infrastructure. Implements
application.ReviewedPullRequestGateway.

Same mechanics as GitHubPullRequestGateway (edit the runtime-config JSON on a
fresh branch, open a PR) but the PR title/body are the agent-authored title and
rationale. The bounds *numbers* still come from the deterministic ProposedBounds
passed in — the agent never supplies them (ADR 0005 guardrail).
"""
from __future__ import annotations
import json
import time
from github import Github, Auth

from msm_bounds.domain import ProposedBounds
from msm_bounds.application.ports import ReviewedPullRequestGateway


class ReviewedGitHubPullRequestGateway(ReviewedPullRequestGateway):
    def __init__(self, token: str, repo_full_name: str, config_path: str, base_branch: str = "main") -> None:
        self._gh = Github(auth=Auth.Token(token))
        self._repo = self._gh.get_repo(repo_full_name)
        self._config_path = config_path
        self._base = base_branch

    def open_reviewed_pr(
        self, proposed: ProposedBounds, current_min: float, current_max: float,
        title: str, rationale: str,
    ) -> str:
        branch = f"auto/bounds-{int(time.time())}"
        base_ref = self._repo.get_git_ref(f"heads/{self._base}")
        self._repo.create_git_ref(ref=f"refs/heads/{branch}", sha=base_ref.object.sha)

        existing = self._repo.get_contents(self._config_path, ref=branch)
        current = json.loads(existing.decoded_content.decode("utf-8"))
        current["bounds_min"] = proposed.min_rpc
        current["bounds_max"] = proposed.max_rpc
        new_content = json.dumps(current, indent=2) + "\n"

        self._repo.update_file(
            path=self._config_path,
            message=f"auto: calibrate bounds to [{proposed.min_rpc}, {proposed.max_rpc}]",
            content=new_content,
            sha=existing.sha,
            branch=branch,
        )
        body = (
            f"{rationale}\n\n"
            f"---\n"
            f"Current: min={current_min}, max={current_max}\n"
            f"Proposed: min={proposed.min_rpc}, max={proposed.max_rpc}\n"
            f"Policy basis: {proposed.reason}\n\n"
            f"_Numbers are deterministic (`propose_bounds`); narrative authored by "
            f"the bounds calibration agent. Merge to roll out._"
        )
        pr = self._repo.create_pull(title=title, body=body, base=self._base, head=branch)
        return pr.html_url
