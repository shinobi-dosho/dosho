"""Tests for the `dosho images` build CLI (no docker required)."""

import pytest
from click.testing import CliRunner

from dosho import cli


def _candidate_source(tmp_path):
    import yaml

    root = tmp_path / "candidate"
    cargo = root / "src/dosho/cargo/tool"
    cargo.mkdir(parents=True)
    (cargo / "Dockerfile").write_text("FROM ubuntu:24.04\nRUN echo candidate\n")
    manifest = {
        "metadata": {"registry": "ghcr.io/shinobi-dosho", "bundle_version": "d1"},
        "images": {
            "TOOL": {"name": "tool", "build": {"version": "1", "dockerfile": "tool/Dockerfile"}}
        },
    }
    path = root / "src/dosho/images.yaml"
    path.write_text(yaml.safe_dump(manifest))
    return root, path, manifest


def test_candidate_source_uses_data_and_ignores_deployment_overrides(tmp_path, monkeypatch):
    root, _, _ = _candidate_source(tmp_path)
    (root / "src/dosho/__init__.py").write_text("raise RuntimeError('never import candidate')")
    monkeypatch.setenv("DOSHO_IMAGES", str(root / "missing.yaml"))
    monkeypatch.setenv("DOSHO_IMAGE_TOOL", "evil.invalid/tool:latest")
    result = CliRunner().invoke(
        cli.main, ["images", "--source-root", str(root), "build", "TOOL", "--dry-run"]
    )
    assert result.exit_code == 0, result.output
    assert "ghcr.io/shinobi-dosho/tool:1-d1" in result.output
    assert "RUN echo candidate" in result.output


def test_candidate_source_rejects_registry_override(tmp_path):
    root, _, _ = _candidate_source(tmp_path)
    result = CliRunner().invoke(
        cli.main,
        [
            "images",
            "--source-root",
            str(root),
            "build",
            "TOOL",
            "--registry",
            "evil.invalid",
            "--dry-run",
        ],
    )
    assert result.exit_code != 0
    assert "cannot be overridden" in result.output


@pytest.mark.parametrize("unsafe", ["registry", "name", "tag", "dockerfile", "symlink"])
def test_candidate_source_rejects_escaping_paths_and_namespaces(tmp_path, unsafe):
    import yaml

    root, path, manifest = _candidate_source(tmp_path)
    if unsafe == "registry":
        manifest["metadata"]["registry"] = "evil.invalid"
    elif unsafe == "name":
        manifest["images"]["TOOL"]["name"] = "../escape"
    elif unsafe == "tag":
        manifest["images"]["TOOL"]["build"]["version"] = "bad/tag"
    elif unsafe == "dockerfile":
        manifest["images"]["TOOL"]["build"]["dockerfile"] = str(path)
    else:
        (root / "src/dosho/cargo/tool/outside").symlink_to(tmp_path)
    path.write_text(yaml.safe_dump(manifest))
    result = CliRunner().invoke(cli.main, ["images", "--source-root", str(root), "build-plan"])
    assert result.exit_code != 0


@pytest.mark.parametrize(
    "command",
    [
        ["docker", "push", "tag"],
        ["docker", "buildx", "build", "--push", "context"],
        ["docker", "buildx", "imagetools", "create", "tag"],
    ],
)
def test_publication_hook_runs_before_each_registry_write(monkeypatch, command):
    calls = []
    monkeypatch.setattr(cli.subprocess, "run", lambda argv, **kwargs: calls.append(argv))
    with cli.images.make_context("images", ["--pre-publish", "python3 /trusted/gate.py"]) as ctx:
        ctx.obj = cli.PublicationSource(pre_publish=("python3", "/trusted/gate.py"))
        cli._run(command)
        cli._run(command)
    assert calls == [["python3", "/trusted/gate.py"], command] * 2


def test_publication_hook_failure_prevents_registry_write(monkeypatch):
    import subprocess

    calls = []

    def fail(argv, **kwargs):
        calls.append(argv)
        raise subprocess.CalledProcessError(1, argv)

    monkeypatch.setattr(cli.subprocess, "run", fail)
    with cli.images.make_context("images", ["list"]) as ctx:
        ctx.obj = cli.PublicationSource(pre_publish=("gate",))
        with pytest.raises(subprocess.CalledProcessError):
            cli._run(["docker", "push", "tag"])
    assert calls == [["gate"]]


def test_candidate_source_list_reports_candidate_reference(tmp_path):
    root, _, _ = _candidate_source(tmp_path)
    result = CliRunner().invoke(cli.main, ["images", "--source-root", str(root), "list"])
    assert result.exit_code == 0, result.output
    assert "ghcr.io/shinobi-dosho/tool:1-d1" in result.output


@pytest.mark.parametrize("multi", [False, True])
def test_candidate_cli_revalidates_staged_and_final_publications(tmp_path, monkeypatch, multi):
    import yaml

    root, path, manifest = _candidate_source(tmp_path)
    if multi:
        manifest["images"]["TOOL"]["build"]["platforms"] = ["linux/amd64", "linux/arm64"]
        path.write_text(yaml.safe_dump(manifest))
    calls = []
    monkeypatch.setattr(cli, "_image_exists", lambda tag: False)
    monkeypatch.setattr(cli, "_image_has_platforms", lambda tag, platforms: True)
    monkeypatch.setattr(cli.subprocess, "run", lambda argv, **kwargs: calls.append(argv))
    args = [
        "images",
        "--source-root",
        str(root),
        "--pre-publish",
        "python3 /trusted/gate.py",
        "build",
        "TOOL",
        "--push",
    ]
    if multi:
        args.append("--sequential-platforms")
    result = CliRunner().invoke(cli.main, args)
    assert result.exit_code == 0, result.output
    writes = [i for i, argv in enumerate(calls) if cli._registry_write(argv)]
    assert len(writes) == (3 if multi else 1)
    assert all(calls[i - 1] == ["python3", "/trusted/gate.py"] for i in writes)
