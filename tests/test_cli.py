"""Tests for the `dosho images` build CLI (no docker required)."""

import json

from click.testing import CliRunner

from dosho import cli
from dosho import images as _images


def _a_ref_only_key() -> str:
    """A manifest key that uses `ref:` (external image), for ref-only assertions.

    Derived from the manifest rather than hardcoded so onboarding a tool
    (flipping its entry ref:->build:) doesn't break these tests.
    """
    for key, entry in _images.manifest["images"].items():
        if "ref" in entry:
            return key
    raise AssertionError("manifest has no ref: entry to test against")


def test_images_list_shows_build_and_ref_kinds():
    result = CliRunner().invoke(cli.main, ["images", "list"])
    assert result.exit_code == 0, result.output
    assert "SIMMS" in result.output and "[build]" in result.output
    assert _a_ref_only_key() in result.output and "[ref  ]" in result.output


def test_build_dry_run_renders_dockerfile_and_tag():
    result = CliRunner().invoke(cli.main, ["images", "build", "SIMMS", "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "ghcr.io/shinobi-dosho/simms:3.0b3-d0.1.0" in result.output
    # simms builds FROM the shared base-astro image (base: resolved to a full ref)
    assert "FROM ghcr.io/shinobi-dosho/base-astro:kern10-d0.1.0" in result.output
    assert "--break-system-packages" in result.output and "simms==3.0b3" in result.output


def test_base_image_builds_from_kern_without_a_base_ref():
    result = CliRunner().invoke(cli.main, ["images", "build", "BASE_ASTRO", "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "ghcr.io/shinobi-dosho/base-astro:kern10-d0.1.0" in result.output
    assert "FROM kernsuite/base:10" in result.output


def test_build_package_override_changes_installed_spec_but_not_tag():
    result = CliRunner().invoke(
        cli.main, ["images", "build", "SIMMS", "--dry-run", "--package", "simms==3.0b2"]
    )
    assert result.exit_code == 0, result.output
    assert "simms==3.0b2" in result.output
    # tag still from manifest version
    assert "ghcr.io/shinobi-dosho/simms:3.0b3-d0.1.0" in result.output


def test_registry_override_changes_tag():
    result = CliRunner().invoke(
        cli.main, ["images", "build", "SIMMS", "--dry-run", "--registry", "quay.io/dosho"]
    )
    assert result.exit_code == 0, result.output
    assert "quay.io/dosho/simms:3.0b3-d0.1.0" in result.output


def test_build_refuses_a_ref_only_image():
    result = CliRunner().invoke(cli.main, ["images", "build", _a_ref_only_key()])
    assert result.exit_code != 0
    assert "does not build" in result.output


def test_build_unknown_image_errors():
    result = CliRunner().invoke(cli.main, ["images", "build", "NOPE"])
    assert result.exit_code != 0
    assert "no image" in result.output


def test_build_keys_emits_json_list_of_build_images():
    result = CliRunner().invoke(cli.main, ["images", "build-keys"])
    assert result.exit_code == 0, result.output
    keys = json.loads(result.output)
    assert "SIMMS" in keys
    # ref: entries are external images, never in the build set
    ref_only = {k for k, e in _images.manifest["images"].items() if "ref" in e}
    assert ref_only and not (ref_only & set(keys))


def test_build_plan_orders_bases_before_tools():
    result = CliRunner().invoke(cli.main, ["images", "build-plan"])
    assert result.exit_code == 0, result.output
    plan = json.loads(result.output)
    assert "BASE_ASTRO" in plan["bases"]
    assert "SIMMS" in plan["tools"] and "BASE_ASTRO" not in plan["tools"]


def test_push_skips_already_published_tag(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_image_exists", lambda tag: True)
    monkeypatch.setattr(cli, "_run", lambda *a, **k: calls.append(a))
    result = CliRunner().invoke(cli.main, ["images", "push", "SIMMS"])
    assert result.exit_code == 0, result.output
    assert "already published" in result.output
    assert calls == []  # no docker push


def test_push_force_overwrites(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_image_exists", lambda tag: True)
    monkeypatch.setattr(cli, "_run", lambda argv, **k: calls.append(argv))
    result = CliRunner().invoke(cli.main, ["images", "push", "SIMMS", "--force"])
    assert result.exit_code == 0, result.output
    assert any(a[:2] == ["docker", "push"] for a in calls)


def test_verify_ok_when_present(monkeypatch):
    monkeypatch.setattr(cli, "_image_exists", lambda tag: True)
    result = CliRunner().invoke(cli.main, ["images", "verify"])
    assert result.exit_code == 0, result.output
    assert "ok" in result.output and "ghcr.io/shinobi-dosho/simms:3.0b3-d0.1.0" in result.output


def test_verify_fails_when_missing(monkeypatch):
    monkeypatch.setattr(cli, "_image_exists", lambda tag: False)
    result = CliRunner().invoke(cli.main, ["images", "verify"])
    assert result.exit_code != 0
    assert "MISSING" in result.output
