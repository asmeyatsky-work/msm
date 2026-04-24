"""GitHub PR gateway. Opens a PR editing a JSON file that the runtime-config
secret mirror watches, so approved merges roll out without redeploy."""
from __future__ import annotations
import json
import time
from github import Github, Auth
from msm_bounds.domain import ProposedBounds
from msm_bounds.application.ports import PullRequestGateway


class GitHubPullRequestGateway(PullRequestGateway):
    def __init__(self, token: str, repo_full_name: str, config_path: str, base_branch: str = "main") -> None:
        self._gh = Github(auth=Auth.Token(token))
        self._repo = self._gh.get_repo(repo_full_name)
        self._config_path = config_path
        self._base = base_branch

    def open_bounds_pr(self, proposed: ProposedBounds, current_min: float, current_max: float) -> str:
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
        pr = self._repo.create_pull(
            title=f"auto: recalibrate RPC bounds",
            body=(
                f"Auto-calibration run.\n\n"
                f"Current: min={current_min}, max={current_max}\n"
                f"Proposed: min={proposed.min_rpc}, max={proposed.max_rpc}\n\n"
                f"Reason: {proposed.reason}\n\n"
                f"Merge to roll out — scoring-api will pick up the new bounds on its next refresh."
            ),
            base=self._base,
            head=branch,
        )
        return pr.html_url
