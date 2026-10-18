"""Publication authorization using recorded GitHub response shapes, without network."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "image_publish_gate", Path(__file__).parents[1] / "scripts/image_publish_gate.py"
)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
SHA = "a" * 40


class API:
    repository = "owner/dosho"

    def __init__(self):
        self.permission = "write"
        self.user_type = "User"
        self.pr = {
            "state": "open",
            "draft": False,
            "mergeable": True,
            "mergeable_state": "clean",
            "base": {"ref": "main", "repo": {"full_name": self.repository}},
            "head": {"sha": SHA, "ref": "feature", "repo": {"full_name": self.repository}},
        }
        self.decision = "APPROVED"
        self.run = {
            "event": "workflow_dispatch",
            "head_sha": SHA,
            "actor": {"login": "human"},
            "check_suite_id": 99,
            "workflow_id": 99,
        }
        self.ci = {
            "id": 1,
            "run_attempt": 1,
            "workflow_id": 1,
            "path": ".github/workflows/ci.yml",
            "event": "pull_request",
            "head_sha": SHA,
            "pull_requests": [{"number": 93}],
            "status": "completed",
            "conclusion": "success",
        }
        self.runs = [self.ci]
        self.jobs = [
            {"id": i, "name": name, "status": "completed", "conclusion": "success"}
            for i, name in enumerate(["test (3.11)", "test (3.12)", "docs"])
        ]
        self.checks = [
            {
                "id": 1,
                "name": "external",
                "app": {"id": 1},
                "head_sha": SHA,
                "check_suite": {"id": 1},
                "status": "completed",
                "conclusion": "success",
            }
        ]
        self.statuses = [{"id": 1, "context": "external", "state": "success"}]
        self.reads = 0
        self.move_head = False

    def request(self, path):
        assert path == "/users/human"
        return {"type": self.user_type}

    def get(self, path):
        if path == "collaborators/human/permission":
            return {"permission": self.permission}
        if path == "pulls/93":
            self.reads += 1
            result = copy.deepcopy(self.pr)
            if self.move_head and self.reads > 1:
                result["head"]["sha"] = "b" * 40
            return result
        assert path == "actions/runs/10"
        return self.run

    def review(self, number):
        assert number == 93
        return {"headRefOid": SHA, "reviewDecision": self.decision}

    def pages(self, path, key=None):
        if path == f"actions/runs?head_sha={SHA}":
            return self.runs
        if path == "actions/runs/1/attempts/1/jobs":
            return self.jobs
        if path == f"commits/{SHA}/check-runs?filter=all":
            return self.checks
        assert path == f"commits/{SHA}/statuses"
        return self.statuses


def validate(api, **kwargs):
    return gate.validate(
        api, number=93, sha=SHA, actor="human", ref="refs/heads/feature", run_id=10, **kwargs
    )


def test_approved_head():
    validate(API())


@pytest.mark.parametrize("decision", ["REVIEW_REQUIRED", "CHANGES_REQUESTED", None, "UNKNOWN"])
def test_missing_or_negative_reviews(decision):
    api = API()
    api.decision = decision
    with pytest.raises(gate.GateError):
        validate(api)


@pytest.mark.parametrize(
    "permission,decision,allowed",
    [
        ("write", "REVIEW_REQUIRED", False),
        ("admin", "REVIEW_REQUIRED", True),
        ("admin", "CHANGES_REQUESTED", False),
        ("admin", None, False),
    ],
)
def test_admin_override_only_incomplete_approval_requirements(permission, decision, allowed):
    # reviewDecision remains REVIEW_REQUIRED with partial approval or unmet code-owner/count rules.
    api = API()
    api.permission, api.decision = permission, decision
    if allowed:
        validate(api, override=True)
    else:
        with pytest.raises(gate.GateError):
            validate(api, override=True)


@pytest.mark.parametrize(
    "field,value",
    [
        ("state", "closed"),
        ("draft", True),
        ("mergeable", False),
        ("mergeable", None),
        ("mergeable_state", "dirty"),
    ],
)
def test_invalid_pr(field, value):
    api = API()
    api.pr[field] = value
    with pytest.raises(gate.GateError):
        validate(api)


@pytest.mark.parametrize("change", ["fork", "base", "head", "ref", "actor", "bot", "read", "drift"])
def test_identity_and_drift(change):
    api = API()
    if change == "fork":
        api.pr["head"]["repo"]["full_name"] = "fork/dosho"
    elif change == "base":
        api.pr["base"]["ref"] = "other"
    elif change == "head":
        api.pr["head"]["sha"] = "b" * 40
    elif change == "ref":
        api.pr["head"]["ref"] = "other"
    elif change == "actor":
        api.run["actor"]["login"] = "other"
    elif change == "bot":
        api.user_type = "Bot"
    elif change == "read":
        api.permission = "read"
    else:
        api.move_head = True
    with pytest.raises(gate.GateError):
        validate(api)


@pytest.mark.parametrize(
    "kind",
    [
        "missing-ci",
        "ci-pending",
        "ci-failure",
        "ci-other-pr",
        "missing-job",
        "job-failure",
        "new-check-failure",
        "check-pending",
        "check-neutral",
        "status-failure",
        "status-pending",
    ],
)
def test_checks_cannot_be_overridden(kind):
    api = API()
    api.permission, api.decision = "admin", "REVIEW_REQUIRED"
    if kind == "missing-ci":
        api.runs = []
    elif kind == "ci-pending":
        api.ci["status"] = "in_progress"
    elif kind == "ci-failure":
        api.ci["conclusion"] = "failure"
    elif kind == "ci-other-pr":
        api.ci["pull_requests"] = [{"number": 94}]
    elif kind == "missing-job":
        api.jobs.pop()
    elif kind == "job-failure":
        api.jobs[-1]["conclusion"] = "failure"
    elif kind == "new-check-failure":
        api.checks.append({**api.checks[0], "id": 2, "conclusion": "failure"})
    elif kind == "check-pending":
        api.checks[0]["status"] = "queued"
    elif kind == "check-neutral":
        api.checks[0]["conclusion"] = "neutral"
    elif kind == "status-failure":
        api.statuses.append({**api.statuses[0], "id": 2, "state": "failure"})
    else:
        api.statuses[0]["state"] = "pending"
    with pytest.raises(gate.GateError):
        validate(api, override=True)


def test_current_publisher_suite_excluded():
    api = API()
    api.checks.append(
        {
            **api.checks[0],
            "id": 2,
            "name": "discover",
            "check_suite": {"id": 99},
            "status": "in_progress",
        }
    )
    validate(api)


def test_api_failure_fails_closed():
    api = API()

    def fail(number):
        raise OSError("API unavailable")

    api.review = fail
    with pytest.raises(OSError):
        validate(api)


@pytest.mark.parametrize("state", ["queued", "in_progress", "waiting", "unknown"])
def test_workflow_pending_before_checks_exist(state):
    api = API()
    api.runs.append({**api.ci, "id": 2, "workflow_id": 2, "path": "other.yml", "status": state})
    with pytest.raises(gate.GateError):
        validate(api)


def test_latest_workflow_failure_blocks_older_success():
    api = API()
    api.runs.append({**api.ci, "id": 2, "conclusion": "failure"})
    with pytest.raises(gate.GateError):
        validate(api)


def test_paginated_checks_include_late_failure():
    api = gate.GitHub("owner/dosho", "unused")
    called = []

    def get(path):
        called.append(path)
        return {
            "check_runs": [{"id": i} for i in range(100)]
            if path.endswith("&page=1")
            else [{"id": 101}]
        }

    api.get = get
    checks = api.pages("commits/sha/check-runs?filter=all", "check_runs")
    assert len(checks) == 101
    assert called[-1].endswith("per_page=100&page=2")


def test_workflow_gates_before_login_and_pins_checkouts():
    import yaml

    root = Path(__file__).parents[1]
    workflow = yaml.safe_load((root / ".github/workflows/images.yml").read_text())
    # PyYAML reads YAML 1.1's `on` as a boolean.
    assert set(workflow[True]) == {"workflow_dispatch"}
    assert set(workflow[True]["workflow_dispatch"]["inputs"]) == {
        "pr_number",
        "head_sha",
        "override_unreviewed",
    }
    assert workflow["concurrency"]["cancel-in-progress"] is False
    assert "packages" not in workflow["permissions"]
    for name, job in workflow["jobs"].items():
        steps = job["steps"]
        assert steps[0]["with"]["ref"] == "${{ inputs.head_sha }}"
        assert steps[1]["run"] == "python3 scripts/image_publish_gate.py"
        login = [i for i, step in enumerate(steps) if "docker/login-action" in step.get("uses", "")]
        if name == "discover":
            assert not login
        else:
            assert login[0] > 1
            assert job["permissions"]["packages"] == "write"


def test_failed_prior_publisher_does_not_block_retry():
    api = API()
    api.runs.append(
        {
            **api.ci,
            "id": 2,
            "workflow_id": 99,
            "check_suite_id": 98,
            "path": ".github/workflows/images.yml",
            "event": "workflow_dispatch",
            "status": "completed",
            "conclusion": "failure",
        }
    )
    api.checks.append(
        {
            **api.checks[0],
            "id": 2,
            "name": "discover",
            "check_suite": {"id": 98},
            "conclusion": "failure",
        }
    )
    validate(api)
