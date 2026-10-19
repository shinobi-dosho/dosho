"""Tests for the `dosho images` build CLI (no docker required)."""

import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from dosho import cli, images as _images


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
    assert "ghcr.io/shinobi-dosho/simms:3.0.2-multiarch1-d0.1.0" in result.output
    # simms builds FROM the shared base-astro image (base: resolved to a full ref)
    assert "FROM ghcr.io/shinobi-dosho/base-astro:noble-kern10-d0.1.0" in result.output
    assert "--break-system-packages" in result.output and "simms==3.0.2" in result.output
    assert "RUN simms --help" in result.output


def test_base_image_configures_kern_ppa_without_a_base_ref():
    result = CliRunner().invoke(cli.main, ["images", "build", "BASE_ASTRO", "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "ghcr.io/shinobi-dosho/base-astro:noble-kern10-d0.1.0" in result.output
    assert "FROM ubuntu:24.04" in result.output
    assert "ppa.launchpadcontent.net/kernsuite/kern-10" in result.output


def test_build_package_override_changes_installed_spec_but_not_tag():
    result = CliRunner().invoke(
        cli.main, ["images", "build", "SIMMS", "--dry-run", "--package", "simms==3.0b2"]
    )
    assert result.exit_code == 0, result.output
    assert "simms==3.0b2" in result.output
    # tag still from manifest version
    assert "ghcr.io/shinobi-dosho/simms:3.0.2-multiarch1-d0.1.0" in result.output


def test_registry_override_changes_tag():
    result = CliRunner().invoke(
        cli.main, ["images", "build", "SIMMS", "--dry-run", "--registry", "quay.io/dosho"]
    )
    assert result.exit_code == 0, result.output
    assert "quay.io/dosho/simms:3.0.2-multiarch1-d0.1.0" in result.output


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


def _plan(*changed):
    args = ["images", "build-plan"]
    for c in changed:
        args += ["--changed", c]
    result = CliRunner().invoke(cli.main, args)
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def test_build_plan_changed_selects_only_the_changed_leaf_tool():
    plan = _plan("src/dosho/cargo/wsclean/Dockerfile")
    assert plan == {"bases": [], "tools": ["WSCLEAN"]}


def test_build_plan_changed_shared_pip_dockerfile_selects_all_pip_tools():
    plan = _plan("src/dosho/cargo/pip/Dockerfile")
    # Every image using the shared template is selected, including new entries.
    expected = {
        key
        for key, entry in _images.manifest["images"].items()
        if entry.get("build", {}).get("dockerfile") == "pip/Dockerfile"
    }
    assert plan == {"bases": [], "tools": sorted(expected)}


def test_build_plan_changed_numpy2_converter_rebuilds_its_users():
    plan = _plan("src/dosho/cargo/numpy2-casacore/Dockerfile")
    expected = {
        key
        for key, entry in _images.manifest["images"].items()
        if entry.get("build", {}).get("dockerfile") == "numpy2-casacore/Dockerfile"
    }
    assert "QUARTICAL" in expected
    assert plan == {"bases": [], "tools": sorted(expected)}


def test_build_plan_changed_base_rebuilds_base_and_all_dependents():
    plan = _plan("src/dosho/cargo/base-astro/Dockerfile")
    assert plan["bases"] == ["BASE_ASTRO"]
    # base-DAG invalidation: everything built FROM base-astro comes along
    assert "SIMMS" in plan["tools"] and "QUARTICAL" in plan["tools"]
    assert {"WSCLEAN", "AOFLAGGER", "SOFIA2"} <= set(plan["tools"])
    # an image outside this base dependency chain is not pulled in
    assert "CASA6" not in plan["tools"]


def test_ddfacet_multiarch_build_precedes_killms():
    assert _plan("src/dosho/cargo/ddfacet/Dockerfile") == {
        "bases": ["DDFACET"],
        "tools": ["KILLMS"],
    }
    assert _plan("src/dosho/cargo/killms/Dockerfile") == {"bases": [], "tools": ["KILLMS"]}
    for key in ("DDFACET", "KILLMS"):
        assert _images.manifest["images"][key]["build"]["platforms"] == [
            "linux/amd64",
            "linux/arm64",
        ]


def test_build_plan_changed_context_file_selects_its_image():
    # a non-Dockerfile file in an image's build context still selects it
    plan = _plan("src/dosho/cargo/casa6/casasiteconfig.py")
    assert plan == {"bases": [], "tools": ["CASA6"]}


def test_build_plan_changed_manifest_rebuilds_everything():
    plan = _plan("src/dosho/images.yaml")
    full = _plan()
    assert plan == full


def _plan_missing_only(monkeypatch, exists, *changed):
    monkeypatch.setattr(cli, "_image_exists", exists)
    monkeypatch.setattr(cli, "_image_has_platforms", lambda tag, platforms: True)
    args = ["images", "build-plan", "--missing-only"]
    for c in changed:
        args += ["--changed", c]
    result = CliRunner().invoke(cli.main, args)
    assert result.exit_code == 0, result.output

    # The plan JSON is always the final echo (to stdout); any "excluded from
    # plan" notice is echoed to stderr beforehand. Across Click versions
    # result.output is the merged stderr+stdout stream, so the last line is the
    # JSON and the whole string still carries the notice for assertions.
    plan = json.loads(result.output.strip().splitlines()[-1])

    return plan, result


def test_build_plan_missing_only_empty_when_all_tags_present(monkeypatch):
    plan, result = _plan_missing_only(monkeypatch, lambda tag: True)
    assert plan == {"bases": [], "tools": []}
    assert "excluded from plan" in result.output


def test_build_plan_missing_only_full_when_registry_empty(monkeypatch):
    plan, _ = _plan_missing_only(monkeypatch, lambda tag: False)
    assert plan == json.loads(CliRunner().invoke(cli.main, ["images", "build-plan"]).output)


def test_build_plan_missing_only_selects_just_the_absent_tag(monkeypatch):
    plan, _ = _plan_missing_only(monkeypatch, lambda tag: "/simms:" not in tag)
    assert plan == {"bases": [], "tools": ["SIMMS"]}


def test_build_plan_missing_only_after_manifest_change(monkeypatch):
    # the smart trigger: a manifest edit makes everything a candidate, but only
    # tags that moved (or were never published) actually build
    plan, _ = _plan_missing_only(
        monkeypatch, lambda tag: "/cubical:" not in tag, "src/dosho/images.yaml"
    )
    assert plan == {"bases": [], "tools": ["CUBICAL"]}
    # a bundle_version bump moves every tag -> all missing -> full rebuild
    plan, _ = _plan_missing_only(monkeypatch, lambda tag: False, "src/dosho/images.yaml")
    assert plan == json.loads(CliRunner().invoke(cli.main, ["images", "build-plan"]).output)


def test_build_plan_changed_unrelated_file_selects_nothing():
    plan = _plan("README.md")
    assert plan == {"bases": [], "tools": []}


def test_build_plan_changed_workflow_alone_builds_nothing():
    # a CI-workflow change orchestrates builds but can't change image contents
    plan = _plan(".github/workflows/images.yml")
    assert plan == {"bases": [], "tools": []}


def test_push_skips_already_published_tag(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_image_exists", lambda tag: True)
    monkeypatch.setattr(cli, "_run", lambda *a, **k: calls.append(a))
    result = CliRunner().invoke(cli.main, ["images", "push", "CASA6"])
    assert result.exit_code == 0, result.output
    assert "already published" in result.output
    assert calls == []  # no docker push


def test_push_force_overwrites(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_image_exists", lambda tag: True)
    monkeypatch.setattr(cli, "_run", lambda argv, **k: calls.append(argv))
    result = CliRunner().invoke(cli.main, ["images", "push", "CASA6", "--force"])
    assert result.exit_code == 0, result.output
    assert any(a[:2] == ["docker", "push"] for a in calls)


def test_verify_ok_when_present(monkeypatch):
    monkeypatch.setattr(cli, "_image_exists", lambda tag: True)
    monkeypatch.setattr(cli, "_image_has_platforms", lambda tag, platforms: True)
    result = CliRunner().invoke(cli.main, ["images", "verify"])
    assert result.exit_code == 0, result.output
    assert (
        "ok" in result.output
        and "ghcr.io/shinobi-dosho/simms:3.0.2-multiarch1-d0.1.0" in result.output
    )


def test_verify_fails_when_missing(monkeypatch):
    monkeypatch.setattr(cli, "_image_exists", lambda tag: False)
    result = CliRunner().invoke(cli.main, ["images", "verify"])
    assert result.exit_code != 0
    assert "MISSING" in result.output


def test_image_has_platforms_reads_manifest_architectures(monkeypatch):
    manifest = {
        "manifests": [
            {"platform": {"os": "linux", "architecture": "amd64"}},
            {"platform": {"os": "linux", "architecture": "arm64"}},
        ]
    }
    monkeypatch.setattr(
        cli.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=json.dumps(manifest)),
    )
    tag = "ghcr.io/shinobi-dosho/casa-tasks:6.7.0.31-d0.1.0"
    assert cli._image_has_platforms(tag, ["linux/amd64", "linux/arm64"])
    assert not cli._image_has_platforms(tag, ["linux/ppc64le"])


def test_casa_tasks_push_uses_buildx_for_both_platforms(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_image_exists", lambda tag: False)
    monkeypatch.setattr(cli, "_image_has_platforms", lambda tag, platforms: True)
    monkeypatch.setattr(cli, "_run", lambda argv, **kwargs: calls.append((argv, kwargs)))
    result = CliRunner().invoke(cli.main, ["images", "build", "CASA_TASKS", "--push"])
    assert result.exit_code == 0, result.output
    assert len(calls) == 1
    argv, kwargs = calls[0]
    assert argv[:5] == ["docker", "buildx", "build", "--platform", "linux/amd64,linux/arm64"]
    assert "--push" in argv
    assert b"RUN python3 -c 'from casatasks import listobs" in kwargs["input"]


def test_large_multiarch_push_stages_each_platform_before_manifest(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_image_exists", lambda tag: False)
    monkeypatch.setattr(cli, "_image_has_platforms", lambda tag, platforms: True)
    monkeypatch.setattr(cli, "_run", lambda argv, **kwargs: calls.append(argv))
    result = CliRunner().invoke(
        cli.main,
        [
            "images",
            "build",
            "DDFACET",
            "--push",
            "--sequential-platforms",
            "--prune-between-platforms",
        ],
    )
    assert result.exit_code == 0, result.output
    tag = "ghcr.io/shinobi-dosho/ddfacet:1.0.0.0-multiarch-d0.1.0"
    assert calls[0][:5] == ["docker", "buildx", "build", "--platform", "linux/amd64"]
    assert calls[0][calls[0].index("-t") + 1] == f"{tag}-amd64"
    assert calls[1] == ["docker", "buildx", "prune", "--all", "--force"]
    assert calls[2][:5] == ["docker", "buildx", "build", "--platform", "linux/arm64"]
    assert calls[2][calls[2].index("-t") + 1] == f"{tag}-arm64"
    assert calls[3] == [
        "docker",
        "buildx",
        "imagetools",
        "create",
        "-t",
        tag,
        f"{tag}-amd64",
        f"{tag}-arm64",
    ]


def test_failed_second_platform_cannot_publish_manifest(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_image_exists", lambda tag: False)

    def run(argv, **kwargs):
        calls.append(argv)
        if "linux/arm64" in argv:
            raise RuntimeError("ARM build failed")

    monkeypatch.setattr(cli, "_run", run)
    result = CliRunner().invoke(
        cli.main, ["images", "build", "DDFACET", "--push", "--sequential-platforms"]
    )
    assert result.exit_code != 0
    assert not any(argv[:4] == ["docker", "buildx", "imagetools", "create"] for argv in calls)


def test_ddfacet_render_preinstalls_arm64_numcodecs_without_x86_flags():
    result = CliRunner().invoke(cli.main, ["images", "build", "DDFACET", "--dry-run"])
    assert result.exit_code == 0, result.output
    assert 'if [ "$(dpkg --print-architecture)" = "arm64" ]' in result.output
    assert 'CFLAGS="-O2" DISABLE_NUMCODECS_SSE2=1 DISABLE_NUMCODECS_AVX2=1' in result.output
    assert "numcodecs==0.15.1" in result.output


def test_killms_tag_suffix_does_not_change_upstream_package_version():
    result = CliRunner().invoke(cli.main, ["images", "build", "KILLMS", "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "killms:3.3.0-multiarch-d0.1.0" in result.output
    assert "pip install --use-pep517 killms==3.3.0" in result.output
    assert "killms==3.3.0-multiarch" not in result.output


def test_casa_tasks_single_arch_push_is_rejected(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_run", lambda argv, **kwargs: calls.append(argv))
    result = CliRunner().invoke(cli.main, ["images", "push", "CASA_TASKS"])
    assert result.exit_code != 0
    assert "declares multiple platforms" in result.output
    assert not calls


def test_existing_casa_tasks_tag_without_arm64_is_not_overwritten(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_image_exists", lambda tag: True)
    monkeypatch.setattr(cli, "_image_has_platforms", lambda tag, platforms: False)
    monkeypatch.setattr(cli, "_run", lambda argv, **kwargs: calls.append(argv))
    result = CliRunner().invoke(cli.main, ["images", "build", "CASA_TASKS", "--push"])
    assert result.exit_code != 0
    assert "exists without all declared platforms" in result.output
    assert not calls


def test_verify_requires_casa_tasks_arm64(monkeypatch):
    monkeypatch.setattr(cli, "_image_exists", lambda tag: True)
    monkeypatch.setattr(cli, "_image_has_platforms", lambda tag, platforms: False)
    result = CliRunner().invoke(cli.main, ["images", "verify", "CASA_TASKS"])
    assert result.exit_code != 0
    assert "MISSING" in result.output


# -- dev images --


def test_dev_build_installs_from_the_branch_and_tags_dev():
    result = CliRunner().invoke(cli.main, ["images", "build", "SIMMS", "--dev", "--dry-run"])
    assert result.exit_code == 0, result.output
    # mutable pointer tag, deliberately outside the {version}-{bundle} scheme
    assert "# tag: ghcr.io/shinobi-dosho/simms:dev" in result.output
    assert "git+https://github.com/shinobi-dosho/simms@main" in result.output
    assert "simms==3.0.2" not in result.output  # the release spec is replaced
    # ...on the same base, from the same `build:` block
    assert "FROM ghcr.io/shinobi-dosho/base-astro:noble-kern10-d0.1.0" in result.output


def test_dev_build_injects_the_framework_dev_pin():
    # a tool built from its own `main` is written against shinobi `main`, but
    # `pip install` would resolve the plain dependency from PyPI (a tool's
    # [tool.uv.sources] git pin is uv-only, stripped from published metadata)
    pin = _images.manifest["metadata"]["dev_deps"]
    # a commit, not a branch: `:dev` is a mutable tag, so what a given dev
    # image installed is otherwise unknowable after the fact and a rebuild
    # picks up whatever shinobi landed meanwhile
    assert re.fullmatch(
        r"git\+https://github\.com/shinobi-dosho/stimela-ninja@[0-9a-f]{40}", pin
    ), pin
    result = CliRunner().invoke(cli.main, ["images", "build", "SIMMS", "--dev", "--dry-run"])
    assert pin in result.output
    # ...on the same pip line as the tool, so the resolver prefers both URLs
    # over the PyPI fallback instead of installing it and stepping on it
    install = next(ln for ln in result.output.splitlines() if ln.startswith("RUN pip install"))
    assert "simms@main" in install and pin in install


def test_ddfacet_dev_build_keeps_the_release_extras():
    # DDFacet's dev image exists for a fix that only lives on `master` (joint
    # imaging of multiple MSs), and its spec is a PEP 508 direct URL rather
    # than a bare `git+` one precisely so the release's extras survive the swap
    # -- losing them would silently drop the beam/kMS/dft backends.
    extras = (
        "[testing-requirements,fits-beam-support,kms-support,alternate-data-backends,dft-support]"
    )
    result = CliRunner().invoke(cli.main, ["images", "build", "DDFACET", "--dev", "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "# tag: ghcr.io/shinobi-dosho/ddfacet:dev" in result.output
    assert f"DDFacet{extras} @ git+https://github.com/saopicc/DDFacet@master" in result.output
    assert f"DDFacet{extras}==1.0.0.0" not in result.output  # the release pin is replaced

    release = CliRunner().invoke(cli.main, ["images", "build", "DDFACET", "--dry-run"])
    install = next(
        ln for ln in release.output.splitlines() if 'pip install --use-pep517 "DDFacet[' in ln
    )
    assert f"DDFacet{extras}==1.0.0.0" in install
    assert "@master" not in install


def test_msutils_dev_build_keeps_the_release_extras_as_one_shell_word():
    # msutils' dev image tracks `main` for work not yet released.
    # Its spec is the same PEP 508 direct-URL form as DDFacet's, so it has a
    # space in it -- and unlike DDFacet's dedicated Dockerfile the shared pip
    # template used to interpolate it bare, which pip reads as three separate
    # requirements ("msutils[all]", "@", the URL) and installs no extras.
    result = CliRunner().invoke(cli.main, ["images", "build", "MSUTILS", "--dev", "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "# tag: ghcr.io/shinobi-dosho/msutils:dev" in result.output
    install = next(ln for ln in result.output.splitlines() if ln.startswith("RUN pip install"))
    assert '"msutils[all] @ git+https://github.com/shinobi-dosho/msutils@main"' in install
    assert "msutils[all]==3.1.0" not in install  # the release pin is replaced


def test_rm_tools_builds_finufft_for_baseline_arm64():
    result = CliRunner().invoke(cli.main, ["images", "build", "RM_TOOLS", "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "dpkg --print-architecture" in result.output
    assert "-Ccmake.define.FINUFFT_ARCH_FLAGS=-march=armv8-a" in result.output
    assert "-march=native" not in result.output


def test_quartical_dev_build_installs_the_fix_branch_with_build_isolation():
    # The fix for a two-term, two-direction solve lives only on v0.2.8-dev.
    # Both variants use the NumPy 2 casacore converter and retain build isolation.
    result = CliRunner().invoke(cli.main, ["images", "build", "QUARTICAL", "--dev", "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "# tag: ghcr.io/shinobi-dosho/quartical:dev" in result.output
    install = next(ln for ln in result.output.splitlines() if ln.startswith("RUN pip install"))
    assert '"git+https://github.com/ratt-ru/QuartiCal@v0.2.8-dev"' in install
    assert "quartical==0.2.5" not in install
    assert "--no-build-isolation" not in install

    release = CliRunner().invoke(cli.main, ["images", "build", "QUARTICAL", "--dry-run"])
    install = next(ln for ln in release.output.splitlines() if ln.startswith("RUN pip install"))
    assert '"quartical==0.2.5"' in install
    assert "--no-build-isolation" not in install


def test_install_quotes_the_package_but_not_the_extra_deps():
    # extra_deps is a list of specs (SHADEMS: three of them), so quoting it
    # whole would hand pip one unresolvable requirement.
    result = CliRunner().invoke(cli.main, ["images", "build", "SHADEMS", "--dry-run"])
    install = next(ln for ln in result.output.splitlines() if ln.startswith("RUN pip install"))
    assert install.endswith('"shadems==0.5.4" pyarrow pandas "dask<2025.1"')


def test_release_build_is_untouched_by_the_dev_block():
    result = CliRunner().invoke(cli.main, ["images", "build", "SIMMS", "--dry-run"])
    assert "ghcr.io/shinobi-dosho/simms:3.0.2-multiarch1-d0.1.0" in result.output
    assert "simms==3.0.2" in result.output
    assert "@main" not in result.output


def test_dev_build_requires_a_dev_block():
    key = next(k for k, e in _images.manifest["images"].items() if "build" in e and "dev" not in e)
    result = CliRunner().invoke(cli.main, ["images", "build", key, "--dev", "--dry-run"])
    assert result.exit_code != 0
    assert "no `dev:` block" in result.output


def test_dev_keys_are_a_subset_of_build_keys():
    dev = json.loads(CliRunner().invoke(cli.main, ["images", "build-keys", "--dev"]).output)
    all_keys = json.loads(CliRunner().invoke(cli.main, ["images", "build-keys"]).output)
    assert dev and set(dev) <= set(all_keys)
    assert all("dev" in _images.manifest["images"][k] for k in dev)


def test_dev_multiarch_push_reports_the_exact_buildx_index_digest(monkeypatch):
    calls = []
    digest = "sha256:" + "a" * 64

    def run(argv, **kwargs):
        calls.append(argv)
        if "--metadata-file" in argv:
            path = Path(argv[argv.index("--metadata-file") + 1])
            path.write_text(json.dumps({"containerimage.descriptor": {"digest": digest}}))

    monkeypatch.setattr(cli, "_image_has_platforms", lambda tag, platforms: True)
    monkeypatch.setattr(cli, "_run", run)
    result = CliRunner().invoke(cli.main, ["images", "build", "SIMMS", "--dev", "--push"])
    assert result.exit_code == 0, result.output
    assert len(calls) == 1
    assert calls[0][:5] == ["docker", "buildx", "build", "--metadata-file", calls[0][4]]
    assert "--push" in calls[0]
    assert f"pin this digest, not the tag: ghcr.io/shinobi-dosho/simms@{digest}" in result.output


def test_dev_sequential_multiarch_push_reports_manifest_creation_digest(monkeypatch):
    calls = []
    digest = "sha256:" + "b" * 64

    def run(argv, **kwargs):
        calls.append(argv)
        if "--metadata-file" in argv:
            path = Path(argv[argv.index("--metadata-file") + 1])
            path.write_text(json.dumps({"containerimage.descriptor": {"digest": digest}}))

    monkeypatch.setattr(cli, "_image_has_platforms", lambda tag, platforms: True)
    monkeypatch.setattr(cli, "_run", run)
    result = CliRunner().invoke(
        cli.main, ["images", "build", "DDFACET", "--dev", "--push", "--sequential-platforms"]
    )
    assert result.exit_code == 0, result.output
    assert len(calls) == 3
    assert calls[-1][:5] == ["docker", "buildx", "imagetools", "create", "--metadata-file"]
    assert all("--metadata-file" not in argv for argv in calls[:-1])
    assert f"pin this digest, not the tag: ghcr.io/shinobi-dosho/ddfacet@{digest}" in result.output


def test_dev_multiarch_push_fails_if_buildx_omits_digest(monkeypatch):
    def run(argv, **kwargs):
        if "--metadata-file" in argv:
            path = Path(argv[argv.index("--metadata-file") + 1])
            path.write_text("{}")

    monkeypatch.setattr(cli, "_run", run)
    result = CliRunner().invoke(cli.main, ["images", "build", "SIMMS", "--dev", "--push"])
    assert result.exit_code != 0
    assert "Buildx did not report a digest" in result.output


def test_dev_single_platform_push_is_rejected_for_multiarch_image(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_run", lambda argv, **k: calls.append(argv))
    result = CliRunner().invoke(cli.main, ["images", "push", "SIMMS", "--dev"])
    assert result.exit_code != 0, result.output
    assert calls == []


def test_dev_images_never_enter_the_release_build_plan():
    # dev tags are mutable and must not be reachable from the automated
    # release path, or a dev push could overwrite a published release tag
    plan = json.loads(CliRunner().invoke(cli.main, ["images", "build-plan"]).output)
    assert "SIMMS" in plan["tools"]  # the release image, at its release tag
    result = CliRunner().invoke(cli.main, ["images", "build", "SIMMS", "--dry-run"])
    assert ":dev" not in result.output


def test_all_remaining_build_images_declare_both_platforms():
    expected = ["linux/amd64", "linux/arm64"]
    for key, entry in _images.manifest["images"].items():
        if "build" in entry and key != "CASA6":
            assert entry["build"]["platforms"] == expected, key
    assert "platforms" not in _images.manifest["images"]["CASA6"]["build"]
    assert "ref" in _images.manifest["images"]["SIMMS_CLASSIC"]


def test_aimfast_astlib_constraint_is_quoted():
    result = CliRunner().invoke(cli.main, ["images", "build", "AIMFAST", "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "RUN pip install --break-system-packages -U 'astLib>=0.13.2'" in result.output


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
