"""The `/build-images` gate and workflow, using recorded GitHub response shapes."""

from __future__ import annotations

import copy
import importlib.util
import io
import os
import subprocess
import urllib.error
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location(
    "image_publish_gate", ROOT / "scripts/image_publish_gate.py"
)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
SHA = "a" * 40
COMMENTED = "2026-11-24T10:00:00Z"


class API:
    repository = "owner/dosho"

    def __init__(self):
        self.role = "maintain"
        self.collaborator = True
        self.pr = {
            "number": 93,
            "state": "open",
            "changed_files": 2,
            "base": {"ref": "main", "repo": {"full_name": self.repository}},
            "head": {"sha": SHA, "repo": {"full_name": self.repository}},
        }
        self.files = [
            {"filename": "src/dosho/images.yaml"},
            {"filename": "src/dosho/cargo/tool/Dockerfile"},
        ]
        self.jobs = [{"name": name, "conclusion": "success"} for name in gate.CI_JOBS]
        self.ci = {
            "id": 1,
            "path": ".github/workflows/ci.yml",
            "head_sha": SHA,
            "pull_requests": [{"number": 93}],
            "created_at": "2026-11-24T09:59:00Z",
            "status": "completed",
            "conclusion": "success",
            "html_url": "https://example.invalid/run/1",
        }
        self.runs = [self.ci]
        self.pr_reads = 0
        self.on_pr_read = None  # callback(read_number) to change state mid-wait

    def get(self, path):
        if path == "collaborators/human/permission":
            if not self.collaborator:
                raise urllib.error.HTTPError(path, 404, "Not Found", {}, io.BytesIO())
            return {"permission": "write", "role_name": self.role}
        assert path == "pulls/93"
        self.pr_reads += 1
        if self.on_pr_read:
            self.on_pr_read(self.pr_reads)
        return copy.deepcopy(self.pr)

    def pages(self, path, key=None):
        if path == "pulls/93/files":
            assert key is None
            return copy.deepcopy(self.files)
        if path == "actions/runs/1/jobs":
            assert key == "jobs"
            return copy.deepcopy(self.jobs)
        assert path == f"actions/runs?head_sha={SHA}&event=pull_request"
        assert key == "workflow_runs"
        return copy.deepcopy(self.runs)


def run_gate(api, body="/build-images", **kwargs):
    kwargs.setdefault("sleep", lambda seconds: None)
    return gate.gate(api, number=93, body=body, author="human", created_at=COMMENTED, **kwargs)


def test_maintainer_with_green_ci_gets_the_head():
    assert run_gate(API()) == SHA


@pytest.mark.parametrize("role", ["admin", "maintain"])
def test_admin_and_maintain_may_build(role):
    api = API()
    api.role = role
    assert run_gate(api) == SHA


@pytest.mark.parametrize("role", ["write", "triage", "read", None, "custom-role"])
def test_other_roles_are_refused(role):
    # `permission` reports maintain as "write"; only role_name distinguishes them.
    api = API()
    api.role = role
    with pytest.raises(gate.GateError, match="admin or maintain"):
        run_gate(api)


def test_non_collaborator_is_refused():
    api = API()
    api.collaborator = False
    with pytest.raises(gate.GateError, match="admin or maintain"):
        run_gate(api)


@pytest.mark.parametrize(
    "body,ok",
    [
        ("/build-images", True),
        ("/build-images  \nplease", True),
        # The workflow's startsWith() never starts a run for these, so the
        # gate must not claim to accept them either.
        ("  /build-images", False),
        ("\n/build-images", False),
        ("/build-images now", False),
        ("/build-imagesx", False),
        ("/Build-Images", False),
        ("please /build-images", False),
        ("", False),
    ],
)
def test_command_must_be_the_whole_first_line(body, ok):
    assert gate.is_command(body) is ok


def test_not_a_command_is_refused_before_any_api_call():
    with pytest.raises(gate.GateError, match="first line"):
        run_gate(object(), body="/build-images now")


def test_closed_or_merged_pr_is_refused():
    api = API()
    api.pr["state"] = "closed"
    with pytest.raises(gate.GateError, match="automatically on main"):
        run_gate(api)


@pytest.mark.parametrize("repo", [{"full_name": "fork/dosho"}, None])
def test_fork_pr_is_refused(repo):
    api = API()
    api.pr["head"]["repo"] = repo
    with pytest.raises(gate.GateError, match="fork"):
        run_gate(api)


@pytest.mark.parametrize(
    "base",
    [
        {"ref": "feature", "repo": {"full_name": "owner/dosho"}},
        {"ref": "main", "repo": {"full_name": "other/dosho"}},
    ],
)
def test_pr_not_targeting_main_is_refused(base):
    api = API()
    api.pr["base"] = base
    with pytest.raises(gate.GateError, match="targeting main"):
        run_gate(api)


@pytest.mark.parametrize(
    "change",
    [
        {"filename": ".github/workflows/ci.yml"},
        {"filename": ".github/scripts/install-pair.sh"},
        {"filename": "elsewhere.sh", "previous_filename": ".github/scripts/install-pair.sh"},
    ],
)
def test_pr_changing_ci_is_refused(change):
    # A pull_request CI run uses the PR's own workflows: such a PR could pass
    # its own CI trivially.
    api = API()
    api.files.append(change)
    api.pr["changed_files"] += 1
    with pytest.raises(gate.GateError, match="must merge"):
        run_gate(api)


def test_incomplete_file_list_is_refused():
    api = API()
    api.pr["changed_files"] = 3001  # the files API stops at 3000
    with pytest.raises(gate.GateError, match="every file"):
        run_gate(api)


@pytest.mark.parametrize("name", gate.CI_JOBS)
@pytest.mark.parametrize("problem", ["missing", "skipped"])
def test_every_ci_job_must_run_and_pass(name, problem):
    api = API()
    if problem == "missing":
        api.jobs = [j for j in api.jobs if j["name"] != name]
    else:
        next(j for j in api.jobs if j["name"] == name)["conclusion"] = "skipped"
    with pytest.raises(gate.GateError, match="did not run and pass"):
        run_gate(api)


def test_failed_ci_is_refused():
    api = API()
    api.ci["conclusion"] = "failure"
    with pytest.raises(gate.GateError, match="CI did not pass"):
        run_gate(api)


def test_latest_ci_run_decides():
    api = API()
    api.runs.append({**api.ci, "id": 2, "conclusion": "failure"})
    with pytest.raises(gate.GateError, match="CI did not pass"):
        run_gate(api)


def test_ci_run_for_another_pr_or_workflow_does_not_count():
    api = API()
    api.ci["pull_requests"] = [{"number": 94}]
    api.runs.append({**api.ci, "id": 2, "path": ".github/workflows/other.yml"})
    with pytest.raises(gate.GateError, match="Timed out"):
        run_gate(api, timeout=0)


def test_waits_for_pending_ci_then_builds():
    api = API()
    api.ci["status"] = "in_progress"
    sleeps = []

    def sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 2:
            api.runs[0]["status"] = "completed"

    assert run_gate(api, sleep=sleep, interval=7) == SHA
    assert sleeps == [7, 7]


def test_waits_for_ci_that_has_not_started():
    api = API()
    pending, api.runs = api.runs, []

    def sleep(seconds):
        api.runs = pending

    assert run_gate(api, sleep=sleep) == SHA


def test_pending_ci_times_out():
    api = API()
    api.ci["status"] = "queued"
    now = iter(range(0, 10_000, 30))
    with pytest.raises(gate.GateError, match="Timed out"):
        run_gate(api, timeout=60, clock=lambda: next(now))


def test_push_after_the_command_is_refused():
    # A CI run created after the comment means the head may not be the one
    # the maintainer looked at -- even if that SHA was pushed back again.
    api = API()
    api.ci["created_at"] = "2026-11-24T10:00:01Z"
    with pytest.raises(gate.GateError, match="changed after the command"):
        run_gate(api)


def test_head_moving_while_waiting_is_refused():
    api = API()
    api.ci["status"] = "in_progress"

    def move(read):
        if read > 1:
            api.pr["head"]["sha"] = "b" * 40

    api.on_pr_read = move
    with pytest.raises(gate.GateError, match="head changed"):
        run_gate(api)


def test_api_failure_fails_closed():
    api = API()

    def fail(path, key=None):
        raise OSError("API unavailable")

    api.pages = fail
    with pytest.raises(OSError):
        run_gate(api)


def test_pagination_reads_every_page():
    api = gate.GitHub("owner/dosho", "unused")
    called = []

    def get(path):
        called.append(path)
        return {"workflow_runs": [{}] * (100 if path.endswith("&page=1") else 1)}

    api.get = get
    assert len(api.pages("actions/runs?head_sha=x", "workflow_runs")) == 101
    assert called[-1].endswith("per_page=100&page=2")


def _main(monkeypatch, tmp_path, api):
    output = tmp_path / "output"
    monkeypatch.setattr(gate, "GitHub", lambda repository, token: api)
    monkeypatch.setattr(gate.time, "sleep", lambda seconds: None)
    for key, value in {
        "GITHUB_OUTPUT": str(output),
        "GITHUB_REPOSITORY": "owner/dosho",
        "GH_TOKEN": "unused",
        "PR_NUMBER": "93",
        "COMMENT_BODY": "/build-images",
        "COMMENT_AUTHOR": "human",
        "COMMENT_CREATED_AT": COMMENTED,
    }.items():
        monkeypatch.setenv(key, value)
    return output


def test_main_writes_the_sha(monkeypatch, tmp_path):
    output = _main(monkeypatch, tmp_path, API())
    gate.main()
    assert output.read_text() == f"sha={SHA}\n"


def test_main_writes_a_one_line_reason_and_fails(monkeypatch, tmp_path):
    api = API()
    api.role = "write"
    output = _main(monkeypatch, tmp_path, api)
    with pytest.raises(SystemExit) as exc:
        gate.main()
    assert exc.value.code != 0
    lines = output.read_text().splitlines()
    assert len(lines) == 1 and lines[0].startswith("error=") and "admin or maintain" in lines[0]


def _workflow():
    return yaml.safe_load((ROOT / ".github/workflows/images.yml").read_text())


def test_workflow_triggers_and_least_privilege():
    workflow = _workflow()
    # PyYAML reads YAML 1.1's `on` as a boolean.
    on = workflow[True]
    assert on["issue_comment"] == {"types": ["created"]}
    assert on["push"]["branches"] == ["main"]
    assert "workflow_dispatch" in on
    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["concurrency"]["cancel-in-progress"] is False
    for name, job in workflow["jobs"].items():
        permissions = job.get("permissions", {})
        login = any("docker/login-action" in s.get("uses", "") for s in job["steps"])
        assert login == name.startswith("build-")
        assert ("packages" in permissions) == login
        assert not ({"packages", "issues"} <= set(permissions))


def test_workflow_never_interpolates_event_data_into_scripts():
    for job in _workflow()["jobs"].values():
        for step in job["steps"]:
            assert "${{" not in step.get("run", "")


def test_builds_run_mains_cli_on_the_gated_source():
    jobs = _workflow()["jobs"]
    assert "scripts/image_publish_gate.py" in jobs["request"]["steps"][-1]["run"]
    assert jobs["request"]["steps"][0]["with"]["ref"] == "${{ github.sha }}"
    assert (
        jobs["discover"]["steps"][1]["with"]["ref"]
        == "${{ needs.request.outputs.sha || github.sha }}"
    )
    for name in ("discover", "build-base", "build-tools"):
        steps = jobs[name]["steps"]
        assert steps[0]["with"] == {
            "ref": "${{ github.sha }}",
            "path": "trusted",
            "persist-credentials": False,
        }
        assert steps[1]["with"]["path"] == "candidate"
        assert steps[1]["with"]["persist-credentials"] is False
        assert jobs[name]["defaults"]["run"]["working-directory"] == "trusted"
        assert "--source-root ../candidate" in steps[-1]["run"]
    for name in ("build-base", "build-tools"):
        assert jobs[name]["steps"][1]["with"]["ref"] == "${{ needs.discover.outputs.source }}"
    # A non-comment trigger may only build from main.
    assert "github.ref == 'refs/heads/main'" in jobs["discover"]["if"]


def test_skipped_request_does_not_skip_builds_on_main():
    # On push/dispatch `request` is skipped; a build job whose `if:` lacks a
    # status function inherits that skip through discover.
    for name in ("discover", "build-base", "build-tools"):
        condition = _workflow()["jobs"][name]["if"]
        assert "!cancelled()" in condition or "always()" in condition, name


def test_only_trusted_commenters_join_a_pr_queue():
    # Joining a queue replaces the run already waiting there, so an outside
    # comment must not land in a PR's queue.
    group = _workflow()["concurrency"]["group"]
    assert "github.event.comment.author_association" in group
    assert '"OWNER", "MEMBER", "COLLABORATOR"' in group


def test_reply_names_the_pinned_head_when_planning_fails():
    env = _workflow()["jobs"]["report"]["env"]
    assert env["SOURCE"] == "${{ needs.discover.outputs.source || needs.request.outputs.sha }}"


def _shell(script, env):
    # Replace uv/gh with argument recorders: run the real workflow shell without
    # Docker or the network.
    stubs = 'uv() { printf "%s\\n" "$@"; }\ngh() { printf "%s\\n" "$@"; }\n'
    return subprocess.run(
        ["bash", "-c", stubs + script],
        env={**os.environ, **env},
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()


@pytest.mark.parametrize(
    "job,image,sequential",
    [
        ("build-base", "BASE_ASTRO", True),
        ("build-tools", "WSCLEAN", True),
        ("build-tools", "CASA6", False),
    ],
)
def test_build_flags(job, image, sequential):
    argv = _shell(_workflow()["jobs"][job]["steps"][-1]["run"], {"IMAGE": image})
    assert image in argv and "--push" in argv
    assert ("--sequential-platforms" in argv) is sequential


@pytest.mark.parametrize(
    "env,expected",
    [
        (
            {"REQUEST": "failure", "ERROR": "`x` needs the admin role"},
            "refused: `x` needs the admin role",
        ),
        ({"REQUEST": "cancelled", "ERROR": ""}, "refused: the request did not complete"),
        ({"REQUEST": "success", "RESULTS": "success failure skipped"}, "failed"),
        ({"REQUEST": "success", "RESULTS": "success success cancelled"}, "failed"),
        (
            {
                "REQUEST": "success",
                "RESULTS": "success skipped skipped",
                "BASES": "[]",
                "TOOLS": "[]",
            },
            "nothing to build",
        ),
        (
            {
                "REQUEST": "success",
                "RESULTS": "success skipped success",
                "BASES": "[]",
                "TOOLS": '["WSCLEAN"]',
            },
            'tools ["WSCLEAN"]',
        ),
    ],
)
def test_reply(env, expected):
    script = _workflow()["jobs"]["report"]["steps"][0]["run"]
    env = {
        "GITHUB_SERVER_URL": "https://github.com",
        "GITHUB_REPOSITORY": "owner/dosho",
        "GITHUB_RUN_ID": "1",
        "PR_NUMBER": "93",
        "SOURCE": SHA,
        "RESULTS": "skipped skipped skipped",
        "BASES": "",
        "TOOLS": "",
        **env,
    }
    argv = _shell(script, env)
    assert argv[:2] == ["api", "repos/owner/dosho/issues/93/comments"]
    assert expected in argv[-1]
