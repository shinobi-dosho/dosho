"""Authorize a ``/build-images`` PR comment and wait for CI on the PR head.

Run by ``.github/workflows/images.yml`` from ``main``'s copy of this file, so a
PR cannot change the rules it is judged by. It fails closed: any API error,
malformed response or unexpected state refuses the build.

On success it writes ``sha=<head>`` to ``$GITHUB_OUTPUT``; on refusal it
writes ``error=<reason>`` there (for the reply comment) and exits non-zero.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

COMMAND = "/build-images"
ROLES = {"admin", "maintain"}  # org owners report as "admin"
CI_PATH = ".github/workflows/ci.yml"
# CI's own jobs must have run, so a PR cannot pass by renaming or dropping them.
CI_JOBS = ("core (3.11)", "core (3.12)", "test (3.11)", "test (3.12)", "docs")
# A pull_request CI run uses the PR's own workflows and the scripts they call,
# so a PR that changes them could make its own CI pass trivially.
PROTECTED = ".github/"
TIMEOUT = 3600
INTERVAL = 30


class GateError(RuntimeError):
    """The build is not authorized; the message is shown to the commenter."""


def require(condition, message):
    if not condition:
        raise GateError(message)


class GitHub:
    def __init__(self, repository, token):
        self.repository = repository
        self.token = token

    def get(self, path):
        request = urllib.request.Request(
            f"https://api.github.com/repos/{self.repository}/{path}",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)

    def pages(self, path, key=None):
        result = []
        for page in range(1, 101):
            separator = "&" if "?" in path else "?"
            payload = self.get(f"{path}{separator}per_page=100&page={page}")
            items = payload[key] if key else payload
            require(isinstance(items, list), "Invalid paginated API response")
            result.extend(items)
            if len(items) < 100:
                return result
        raise GateError("Pagination limit reached")


def is_command(body):
    # Must start the comment: the workflow only starts for bodies that do.
    lines = (body or "").splitlines()
    return bool(lines) and lines[0].rstrip() == COMMAND


def timestamp(value):
    return datetime.fromisoformat(value)


def authorize(api, login):
    denied = f"`{login}` needs the admin or maintain role on this repository to build images"
    try:
        payload = api.get(f"collaborators/{urllib.parse.quote(login, safe='')}/permission")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:  # not a collaborator at all
            raise GateError(denied) from exc
        raise
    # `permission` folds maintain into write; `role_name` keeps them apart.
    require(payload.get("role_name") in ROLES, denied)


def pull(api, number):
    pr = api.get(f"pulls/{number}")
    require(
        pr["state"] == "open",
        "This PR is not open. Merged image changes build automatically on main",
    )
    require(
        pr["base"]["ref"] == "main" and pr["base"]["repo"]["full_name"] == api.repository,
        "Images can only be built from PRs targeting main",
    )
    head_repo = pr["head"]["repo"] or {}
    require(head_repo.get("full_name") == api.repository, "Images cannot be built from fork PRs")
    return pr


def require_ci_untouched(api, pr):
    files = api.pages(f"pulls/{pr['number']}/files")
    # The files API stops at 3000; an incomplete list cannot prove anything.
    require(len(files) == pr["changed_files"], "Could not list every file this PR changes")
    for f in files:
        for name in (f["filename"], f.get("previous_filename") or ""):
            require(
                not name.startswith(PROTECTED),
                f"This PR changes `{name}`. Changes under `{PROTECTED}` must merge "
                "before images can be built from a PR",
            )


def ci_state(api, number, sha, requested_at):
    """``"success"`` or ``"pending"`` for the latest CI run of this PR head."""
    runs = api.pages(f"actions/runs?head_sha={sha}&event=pull_request", "workflow_runs")
    ci = [
        r
        for r in runs
        if r["path"] == CI_PATH
        and r["head_sha"] == sha
        and any(p["number"] == number for p in r["pull_requests"])
    ]
    if not ci:
        return "pending"
    run = max(ci, key=lambda r: r["id"])
    # A push makes a new run (a rerun keeps its run and created_at). A latest run
    # newer than the command means the head may not be what the maintainer saw.
    require(
        timestamp(run["created_at"]) <= requested_at,
        "The PR changed after the command (or its CI had not started yet). Comment again",
    )
    if run["status"] != "completed":
        return "pending"
    require(run["conclusion"] == "success", f"CI did not pass: {run['html_url']}")
    jobs = {j["name"]: j for j in api.pages(f"actions/runs/{run['id']}/jobs", "jobs")}
    for name in CI_JOBS:
        require(
            name in jobs and jobs[name]["conclusion"] == "success",
            f"CI job `{name}` did not run and pass: {run['html_url']}",
        )
    return "success"


def wait_for_ci(
    api,
    number,
    requested_at,
    *,
    timeout=TIMEOUT,
    interval=INTERVAL,
    sleep=time.sleep,
    clock=time.monotonic,
):
    """Pin the PR head, wait until its CI passes, and return the pinned SHA."""
    pr = pull(api, number)
    sha = pr["head"]["sha"]
    require_ci_untouched(api, pr)  # the head re-check below covers this listing too
    deadline = clock() + timeout
    while True:
        state = ci_state(api, number, sha, requested_at)
        require(
            pull(api, number)["head"]["sha"] == sha,
            "The PR head changed while waiting for CI. Comment again",
        )
        if state == "success":
            return sha
        require(clock() < deadline, f"Timed out after {timeout // 60} minutes waiting for CI")
        sleep(interval)


def gate(api, *, number, body, author, created_at, timeout=TIMEOUT, **wait):
    require(is_command(body), f"Expected `{COMMAND}` on the first line")
    authorize(api, author)
    return wait_for_ci(api, number, timestamp(created_at), timeout=timeout, **wait)


def main():
    output = os.environ["GITHUB_OUTPUT"]
    try:
        sha = gate(
            GitHub(os.environ["GITHUB_REPOSITORY"], os.environ["GH_TOKEN"]),
            number=int(os.environ["PR_NUMBER"]),
            body=os.environ["COMMENT_BODY"],
            author=os.environ["COMMENT_AUTHOR"],
            created_at=os.environ["COMMENT_CREATED_AT"],
            timeout=int(os.environ.get("CI_TIMEOUT", TIMEOUT)),
        )
    except Exception as exc:  # fail closed on API errors and malformed data too
        reason = str(exc) if isinstance(exc, GateError) else f"gate error: {exc}"
        reason = " ".join(reason.split())
        with open(output, "a") as f:
            f.write(f"error={reason}\n")
        sys.exit(f"Image build refused: {reason}")
    with open(output, "a") as f:
        f.write(f"sha={sha}\n")
    sys.stdout.write(f"Building images from {sha}.\n")


if __name__ == "__main__":
    main()
