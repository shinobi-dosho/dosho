"""Tests for the `dosho images` build CLI (no docker required)."""

from click.testing import CliRunner

from dosho import cli


def test_images_list_shows_build_and_ref_kinds():
    result = CliRunner().invoke(cli.main, ["images", "list"])
    assert result.exit_code == 0, result.output
    assert "SIMMS" in result.output and "[build]" in result.output
    assert "WSCLEAN" in result.output and "[ref  ]" in result.output


def test_build_dry_run_renders_dockerfile_and_tag():
    result = CliRunner().invoke(cli.main, ["images", "build", "SIMMS", "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "ghcr.io/shinobi-dosho/simms:3.0b3-d0.1.0" in result.output
    assert "FROM kernsuite/base:10" in result.output
    assert "pip install --break-system-packages simms==3.0b3" in result.output


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
    result = CliRunner().invoke(cli.main, ["images", "build", "WSCLEAN"])
    assert result.exit_code != 0
    assert "does not build" in result.output


def test_build_unknown_image_errors():
    result = CliRunner().invoke(cli.main, ["images", "build", "NOPE"])
    assert result.exit_code != 0
    assert "no image" in result.output
