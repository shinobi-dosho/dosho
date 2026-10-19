"""Fail closed before publishing images from an explicitly approved PR head."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request


class GateError(RuntimeError):
    """Publication is not authorized."""


def require(condition, message):
    if not condition:
        raise GateError(message)


class GitHub:
    def __init__(self, repository, token):
        self.repository = repository
        self.token = token

    def request(self, path, data=None):
        url = "https://api.github.com" + path
        request = urllib.request.Request(
            url,
            data=json.dumps(data).encode() if data is not None else None,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)

    def get(self, path):
        return self.request(f"/repos/{self.repository}/{path}")

    def pages(self, path, key=None):
        result = []
        for page in range(1, 1001):
            separator = "&" if "?" in path else "?"
            payload = self.get(f"{path}{separator}per_page=100&page={page}")
            items = payload[key] if key else payload
            require(isinstance(items, list), "Invalid paginated API response")
            result.extend(items)
            if len(items) < 100:
                return result
        raise GateError("Pagination limit reached")

    def review(self, number):
        owner, name = self.repository.split("/")
        payload = self.request(
            "/graphql",
            {
                "query": """query($owner:String!, $name:String!, $number:Int!) {
              repository(owner:$owner, name:$name) {
                pullRequest(number:$number) { headRefOid reviewDecision }
              }
            }""",
                "variables": {"owner": owner, "name": name, "number": number},
            },
        )
        require(not payload.get("errors"), "Review API returned errors")
        return payload["data"]["repository"]["pullRequest"]


def latest(items, key):
    """API numeric IDs order creations; an older green result cannot hide a rerun."""
    selected = {}
    for item in items:
        identity = key(item)
        if identity not in selected or item["id"] > selected[identity]["id"]:
            selected[identity] = item
    return selected.values()


def validate(api, *, number, sha, actor, ref, run_id, dispatch_sha, override=False):
    require(re.fullmatch(r"[0-9a-f]{40}", sha), "Expected a full lowercase 40-character head SHA")
    require(number > 0, "Expected a positive PR number")
    user = api.request(f"/users/{urllib.parse.quote(actor, safe='')}")
    require(user["type"] == "User", "Dispatcher must be a human")
    permission = api.get(f"collaborators/{urllib.parse.quote(actor, safe='')}/permission")[
        "permission"
    ]
    require(
        permission in {"write", "maintain", "admin"}, "Dispatcher needs repository write permission"
    )
    if override:
        require(permission == "admin", "Only an administrator may override missing approvals")

    def pull():
        pr = api.get(f"pulls/{number}")
        require(
            pr["state"] == "open" and pr["draft"] is False, "PR must be open and ready for review"
        )
        require(pr["base"]["ref"] == "main", "PR must target main")
        require(pr["base"]["repo"]["full_name"] == api.repository, "Unexpected base repository")
        require(pr["head"]["repo"]["full_name"] == api.repository, "Fork PRs cannot publish")
        require(pr["head"]["sha"] == sha, "PR head changed")
        require(ref == "refs/heads/main", "Dispatch must use protected main")
        require(pr["mergeable"] is True, "PR mergeability is unknown or conflicted")
        require(
            pr["mergeable_state"] in {"clean", "blocked", "unstable", "has_hooks", "behind"},
            "PR is not mergeable",
        )
        return pr

    pull()
    run = api.get(f"actions/runs/{run_id}")
    require(
        run["event"] == "workflow_dispatch" and run["head_sha"] == dispatch_sha,
        "Dispatch run must use trusted main SHA",
    )
    require(run["actor"]["login"] == actor, "Unexpected dispatch actor")
    review = api.review(number)
    require(review["headRefOid"] == sha, "Review head changed")
    decision = review["reviewDecision"]
    require(
        decision == "APPROVED" or (override and decision == "REVIEW_REQUIRED"),
        "Approvals missing or changes requested",
    )

    runs = api.pages(f"actions/runs?head_sha={sha}", "workflow_runs")
    # Workflow runs can be queued before their check runs exist.
    publisher_suites = {run["check_suite_id"]}
    publisher_suites.update(
        r["check_suite_id"] for r in runs if r["workflow_id"] == run["workflow_id"]
    )
    other_runs = [r for r in runs if r["workflow_id"] != run["workflow_id"]]
    for other in latest(other_runs, lambda r: (r["workflow_id"], r["event"])):
        require(
            other["status"] == "completed" and other["conclusion"] == "success",
            f"Workflow {other['path']} must succeed",
        )
    ci = [
        r
        for r in runs
        if r["path"] == ".github/workflows/ci.yml"
        and r["event"] == "pull_request"
        and r["head_sha"] == sha
        and any(p["number"] == number for p in r["pull_requests"])
    ]
    require(ci, "No CI workflow run for this PR and exact head")
    ci_run = max(ci, key=lambda r: (r["id"], r["run_attempt"]))
    require(
        ci_run["status"] == "completed" and ci_run["conclusion"] == "success",
        "Latest CI run must succeed",
    )
    jobs = api.pages(f"actions/runs/{ci_run['id']}/jobs?filter=all", "jobs")
    by_name = {j["name"]: j for j in latest(jobs, lambda j: j["name"])}
    for name in ("test (3.11)", "test (3.12)", "docs"):
        require(
            name in by_name
            and by_name[name]["status"] == "completed"
            and by_name[name]["conclusion"] == "success",
            f"CI job {name} must succeed",
        )

    checks = api.pages(f"commits/{sha}/check-runs?filter=all", "check_runs")
    others = [c for c in checks if c["check_suite"]["id"] not in publisher_suites]
    for check in latest(others, lambda c: (c["app"]["id"], c["name"])):
        require(check["head_sha"] == sha, "Unexpected check head")
        require(
            check["status"] == "completed" and check["conclusion"] == "success",
            f"Check {check['name']} must succeed",
        )
    statuses = api.pages(f"commits/{sha}/statuses")
    for status in latest(statuses, lambda s: s["context"]):
        require(status["state"] == "success", f"Status {status['context']} must succeed")
    # Catch movement while the paginated check and review requests were running.
    pull()


def main():
    try:
        api = GitHub(os.environ["GITHUB_REPOSITORY"], os.environ["GH_TOKEN"])
        for root, expected in (
            (".", os.environ["GITHUB_SHA"]),
            (os.environ["CANDIDATE_ROOT"], os.environ["HEAD_SHA"]),
        ):
            actual = subprocess.check_output(
                ["git", "-C", root, "rev-parse", "HEAD"], text=True
            ).strip()
            require(actual == expected, "Checkout SHA does not match selected source")
        validate(
            api,
            number=int(os.environ["PR_NUMBER"]),
            sha=os.environ["HEAD_SHA"],
            actor=os.environ["GITHUB_TRIGGERING_ACTOR"],
            ref=os.environ["GITHUB_REF"],
            run_id=int(os.environ["GITHUB_RUN_ID"]),
            dispatch_sha=os.environ["GITHUB_SHA"],
            override=os.environ["OVERRIDE_UNREVIEWED"] == "true",
        )
    except Exception as exc:  # The gate must fail closed on malformed data and API failures too.
        sys.exit(f"Image publication blocked: {exc}")
    sys.stdout.write("Image publication gate passed.\n")


if __name__ == "__main__":
    main()
