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


# Standalone catalogue commands inspect definitions without adapting or running them.
def test_cabs_list_is_sorted_real_inventory():
    from dosho.registry import list_cabs

    result = CliRunner().invoke(cli.main, ["list"])
    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == sorted(list_cabs())


@pytest.mark.parametrize(
    "args", [["--help"], ["list", "--help"], ["show", "--help"], ["validate", "--help"]]
)
def test_cabs_help_is_discoverable(args):
    result = CliRunner().invoke(cli.main, args)
    assert result.exit_code == 0
    assert "Usage:" in result.output


@pytest.mark.parametrize(
    "name,expected",
    [
        (
            "wsclean",
            [
                "List[MSv2]",
                "ProductFamily[FITSImage]",
                _images.WSCLEAN,
                "requires stimela-ninja to validate",
                "dataset_accesses",
            ],
        ),
        ("listobs", ["Inputs:", "Outputs:", "vis:", "listfile:"]),
        ("bdsf-catalog", ["Inputs:", "Outputs:"]),
    ],
)
def test_cabs_show_real_schemas(name, expected):
    result = CliRunner().invoke(cli.main, ["show", name])
    assert result.exit_code == 0, result.output
    for text in expected:
        assert text in result.output
    assert "--ms" not in result.output


def test_cabs_unknown_checked_before_optional_dependency(monkeypatch):
    def fail():
        raise AssertionError("dependency loaded for unknown name")

    monkeypatch.setattr(cli, "_inspection_dependency", fail)
    result = CliRunner().invoke(cli.main, ["show", "unknown-tool"])
    assert result.exit_code == 1
    assert "unknown cab" in result.output


def test_cabs_show_reads_python_signature_without_calling_body(monkeypatch):
    from typing import Literal

    from dosho import pystep, registry

    @pystep(image="example:1", info="A schema only.")
    def sample(
        ctx,
        flag: bool = False,
        count: int = 0,
        text: str = "",
        mode: Literal["a", "b"] | None = None,
    ) -> None:
        raise AssertionError("must never run body")

    monkeypatch.setattr(registry, "list_cabs", lambda: ["sample"])
    monkeypatch.setattr(registry, "get", lambda name: sample)
    result = CliRunner().invoke(cli.main, ["show", "sample"])
    assert result.exit_code == 0, result.output
    for text in [
        "default=False",
        "default=0",
        "default=''",
        "default=None",
        "Choices: ['a', 'b']",
        "A schema only.",
        "example:1",
    ]:
        assert text in result.output


def _check_cabs(tmp_path, text):
    path = tmp_path / "cabs.yaml"
    path.write_text(text)
    return CliRunner().invoke(cli.main, ["validate", str(path)])


def test_cabs_validate_all_definitions_and_falsey_defaults(tmp_path):
    result = _check_cabs(
        tmp_path,
        """
cabs:
  first:
    command: echo
    inputs:
      flag: {dtype: bool, default: false}
      count: {dtype: int, default: 0}
      text: {dtype: str, default: ''}
      required: {dtype: int, required: true}
  second:
    command: other
    flavour: {kind: binary}
""",
    )
    assert result.exit_code == 0, result.output
    assert "Static definition checks passed: first, second" in result.output
    assert "Actual data and execution qualification" in result.output


@pytest.mark.parametrize(
    "fragment,expected",
    [
        ("command: ''", "nonempty string"),
        ("command: [echo]", "command"),
        ("inputs: {}", "no 'command'"),
        ("command: echo\n  dynamic_schema: evil.make", "dynamic_schema"),
        ("command: echo\n  flavour: python", "only binary"),
        ("command: echo\n  cache: 7", "cache"),
        ("command: echo\n  policies: {prefix: []}", "prefix"),
        ("command: echo\n  inputs: []", ""),
        ("command: echo\n  inputs: {n: {dtype: int, default: wrong}}", "inputs.n"),
        ("command: echo\n  inputs: {n: {dtype: 'List[str]', default: wrong}}", "inputs.n"),
        ("command: echo\n  inputs: {n: {dtype: int, choices: [1, 2], default: 3}}", "inputs.n"),
        ("command: echo\n  inputs: {n: {dtype: str, nullable: false}}", "null"),
        ("command: echo\n  inputs: {n: {dtype: str, min_length: 3, default: ab}}", "inputs.n"),
        (
            "command: echo\n  inputs: {n: {dtype: str, string_pattern: '^a', default: b}}",
            "inputs.n",
        ),
        ("command: echo\n  inputs: {ms: {dtype: MSv2, min_length: -1}}", "min_length"),
        ("command: echo\n  outputs: {n: {dtype: File, writable: false}}", "writable"),
    ],
)
def test_cabs_validate_rejects_bad_definitions(tmp_path, fragment, expected):
    result = _check_cabs(tmp_path, "bad:\n  " + fragment + "\n")
    assert result.exit_code == 1, result.output
    assert "cabs.yaml" in result.output and "bad" in result.output
    assert expected in result.output
    assert "Static definition checks passed" not in result.output


def test_cabs_validate_checks_native_field_alongside_deferred_framework(tmp_path):
    result = _check_cabs(
        tmp_path,
        """
strict:
  command: tool
  inputs:
    ms: {dtype: 'List[MSv2]', required: true}
    count: {dtype: int, default: wrong}
""",
    )
    assert result.exit_code == 1
    assert "inputs.count" in result.output
    assert "Static definition checks passed" not in result.output


@pytest.mark.parametrize(
    "text",
    [
        "",
        "{}",
        "[]",
        "- tool",
        "cabs: []",
        "cabs: null",
        "bad: null",
        "bad: [echo]",
        "bad: {command: [}",
    ],
)
def test_cabs_validate_bad_document_shapes(tmp_path, text):
    result = _check_cabs(tmp_path, text)
    assert result.exit_code == 1, result.output
    assert "Error:" in result.output


def test_cabs_validate_fails_when_later_cab_is_bad(tmp_path):
    result = _check_cabs(tmp_path, "good: {command: echo}\nbad: {command: ''}\n")
    assert result.exit_code == 1
    assert "bad" in result.output
    assert "checks passed" not in result.output


def test_cabs_validate_relative_composition(tmp_path):
    (tmp_path / "base.yaml").write_text("base: {command: echo, inputs: {n: {dtype: int}}}\n")
    result = _check_cabs(tmp_path, "_include: base.yaml\ncabs:\n  sample:\n    _use: base\n")
    assert result.exit_code == 0, result.output
    assert "checks passed: sample" in result.output


@pytest.mark.parametrize(
    "text,expected",
    [
        ("_include: missing.yaml", "missing.yaml"),
        ("_include: cabs.yaml", "cycle"),
        ("cabs:\n  a: {_use: cabs.b}\n  b: {_use: cabs.a}", "cycle"),
        ("_include: (not_a_real_package)bad.yaml", "no filesystem root"),
    ],
)
def test_cabs_validate_composition_errors(tmp_path, text, expected):
    result = _check_cabs(tmp_path, text)
    assert result.exit_code == 1
    assert expected in result.output


def test_cabs_validate_file_paths(tmp_path):
    for path in [tmp_path, tmp_path / "missing.yaml"]:
        result = CliRunner().invoke(cli.main, ["validate", str(path)])
        assert result.exit_code == 2


def test_cabs_validate_bundled_documents_report_exact_deferrals():
    from dosho import registry
    from dosho.validation.compiler import _check_static, load_file

    root = Path(registry.__file__).parent / "documents"
    for path in root.glob("*.yaml"):
        definitions = load_file(path, **registry.loader_options())
        for definition in definitions.values():
            _check_static(definition)
    result = CliRunner().invoke(cli.main, ["validate", str(root / "wsclean.yaml")])
    assert result.exit_code == 0, result.output
    assert "wsclean.inputs.ms (List[MSv2]): requires stimela-ninja to validate" in result.output
    assert (
        "wsclean.outputs.image (ProductFamily[FITSImage]): requires stimela-ninja to validate"
        in result.output
    )
    assert (
        "dataset_accesses (framework access declaration): requires stimela-ninja to validate"
        in result.output
    )


def test_cabs_does_not_offer_execution():
    for args in [
        ["cab", "wsclean", "--help"],
        ["cabs", "wsclean"],
        ["cabs", "run"],
        ["cabs", "list"],
        ["cabs", "show", "wsclean"],
    ]:
        result = CliRunner().invoke(cli.main, args)
        assert result.exit_code == 2
        assert "Error:" in result.output


def _blocked_cli(args, blocked):
    import subprocess
    import sys

    program = """
import importlib.abc
import sys
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in BLOCKED:
            raise ModuleNotFoundError(f'blocked {fullname}', name=fullname.split('.')[0])
sys.meta_path.insert(0, Block())
from dosho.cli import main
main(ARGS, standalone_mode=True)
"""
    return subprocess.run(
        [
            sys.executable,
            "-c",
            "BLOCKED=" + repr(blocked) + "\nARGS=" + repr(args) + "\n" + program,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    "args",
    [
        ["--help"],
        ["validate", "--help"],
        ["list"],
        ["show", "wsclean", "--help"],
        ["images", "list"],
    ],
)
def test_cabs_base_commands_without_pydantic_or_shinobi(args):
    result = _blocked_cli(args, ["pydantic", "shinobi"])
    assert result.returncode == 0, result.stderr
    assert result.stdout


@pytest.mark.parametrize("args", [["show", "wsclean"], ["show", "listobs"]])
def test_cabs_schema_commands_need_validation_extra(args):
    result = _blocked_cli(args, ["pydantic", "shinobi"])
    assert result.returncode == 1
    assert 'pip install "dosho[validation]"' in result.stderr
    assert "Traceback" not in result.stderr


def test_cabs_validate_needs_validation_extra(tmp_path):
    path = tmp_path / "cab.yaml"
    path.write_text("sample: {command: echo}")
    result = _blocked_cli(["validate", str(path)], ["pydantic", "shinobi"])
    assert result.returncode == 1
    assert 'pip install "dosho[validation]"' in result.stderr


@pytest.mark.parametrize("name", ["wsclean", "listobs", "bdsf-catalog"])
def test_cabs_schema_never_imports_framework_or_tool_packages(name):
    result = _blocked_cli(["show", name], ["shinobi", "casatasks", "bdsf", "casacore"])
    assert result.returncode == 0, result.stderr
    assert "Inputs:" in result.stdout and "Outputs:" in result.stdout


def test_cabs_validate_never_imports_dynamic_hook_or_framework(tmp_path):
    path = tmp_path / "cab.yaml"
    path.write_text("sample: {command: tool, inputs: {ms: {dtype: MSv2}}}")
    blocked = ["shinobi", "evil", "casatasks", "bdsf"]
    result = _blocked_cli(["validate", str(path)], blocked)
    assert result.returncode == 0, result.stderr
    assert "requires stimela-ninja to validate" in result.stdout
    path.write_text("sample: {command: tool, dynamic_schema: evil.make}")
    result = _blocked_cli(["validate", str(path)], blocked)
    assert result.returncode == 1
    assert "dynamic_schema" in result.stderr
    assert "blocked" not in result.stderr


def test_cabs_unrelated_import_error_is_not_mislabelled(monkeypatch):
    from dosho import registry

    def fail(name):
        raise ModuleNotFoundError("unrelated dependency missing", name="unrelated")

    monkeypatch.setattr(registry, "get", fail)
    result = CliRunner().invoke(cli.main, ["show", "wsclean"])
    assert isinstance(result.exception, ModuleNotFoundError)
    assert result.exception.name == "unrelated"
    assert "dosho[validation]" not in result.output


def test_cabs_show_finite_literal_choices():
    from typing import Literal

    from dosho._inspection import _literal_choices

    assert _literal_choices(Literal["a"] | Literal["b"] | None) == ["a", "b"]
    assert _literal_choices(list[Literal["a", "b"]] | None) == ["a", "b"]
    assert _literal_choices(str | Literal["a"]) is None


def test_cabs_validate_json_and_explicit_dosho_root(tmp_path):
    result = _check_cabs(tmp_path, '{"cabs": {"sample": {"command": "tool"}}}')
    assert result.exit_code == 0, result.output


def test_cabs_validate_explicit_dosho_root(tmp_path):
    result = _check_cabs(tmp_path, '_include: "(dosho)documents/wsclean.yaml"')
    assert result.exit_code == 0, result.output
    assert "requires stimela-ninja to validate" in result.output


def test_validate_strict_native_only_succeeds(tmp_path):
    path = tmp_path / "native.yaml"
    path.write_text("sample: {command: tool, inputs: {count: {dtype: int, default: 0}}}")
    result = CliRunner().invoke(cli.main, ["validate", str(path), "--strict"])
    assert result.exit_code == 0, result.output
    assert "Static definition checks passed: sample" in result.output


def test_validate_strict_reports_all_framework_deferrals(tmp_path):
    path = tmp_path / "framework.yaml"
    path.write_text("""
first:
  command: tool
  inputs:
    ms: {dtype: MSv2}
  outputs:
    image:
      dtype: ProductFamily[FITSImage]
      family: {}
  dataset_accesses: []
second:
  command: other
  inputs:
    fits: {dtype: FITSImage}
""")
    result = CliRunner().invoke(cli.main, ["validate", str(path), "--strict"])
    assert result.exit_code == 1
    for label in (
        "first.inputs.ms",
        "first.outputs.image",
        "first.outputs.image.family",
        "first.dataset_accesses",
        "second.inputs.fits",
    ):
        assert label in result.output
    assert result.output.count("requires stimela-ninja to validate") == 5
    assert "Strict validation failed" in result.output
    # Even strict mode never loads framework/tool packages.
    blocked = _blocked_cli(["validate", str(path), "--strict"], ["shinobi", "casatasks", "bdsf"])
    assert blocked.returncode == 1
    assert "second.inputs.fits" in blocked.stdout
    assert "blocked" not in blocked.stderr


def test_validate_strict_rejects_static_error(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("sample: {command: tool, inputs: {n: {dtype: int, default: wrong}}}")
    result = CliRunner().invoke(cli.main, ["validate", str(path), "--strict"])
    assert result.exit_code == 1
    assert "inputs.n" in result.output
    assert "checks passed" not in result.output


@pytest.mark.parametrize(
    "args", [["--strict"], ["list", "--strict"], ["show", "wsclean", "--strict"]]
)
def test_strict_is_only_available_for_validate(args):
    result = CliRunner().invoke(cli.main, args)
    assert result.exit_code == 2
    assert "No such option" in result.output and "--strict" in result.output


@pytest.mark.parametrize(
    "fragment,expected",
    [
        ("harvest: files", "harvest"),
        ("scratch: path", "scratch"),
        ("inputs: {n: {dtype: int, policies: []}}", "policies"),
        ("inputs: {ms: {dtype: MSv2, policies: wrong}}", "policies"),
        ("inputs: []", "inputs"),
        ("inputs: false", "inputs"),
        ("inputs: 0", "inputs"),
        ("outputs: []", "outputs"),
    ],
)
def test_validate_rejects_malformed_metadata_shapes(tmp_path, fragment, expected):
    result = _check_cabs(tmp_path, "sample:\n  command: tool\n  " + fragment + "\n")
    assert result.exit_code == 1
    assert "Error:" in result.output and expected in result.output


@pytest.mark.parametrize("direction", ["input", "output"])
@pytest.mark.parametrize("dtype", ["MSv2", "FITSImage", "ProductFamily[FITSImage]"])
def test_validate_strict_defers_framework_pattern_attrs(tmp_path, direction, dtype):
    text = f"""
patterned:
  command: tool
  {direction}_patterns:
    - segments:
        - regex: '.+'
        - attrs:
            data:
              dtype: {dtype}
              family: {{}}
"""
    path = tmp_path / "patterns.yaml"
    path.write_text(text)
    result = CliRunner().invoke(cli.main, ["validate", str(path), "--strict"])
    assert result.exit_code == 1, result.output
    label = f"patterned.{direction}_patterns[0].segments[1].attrs.data"
    assert f"{label} ({dtype}): requires stimela-ninja to validate" in result.output
    assert (
        f"{label}.family (framework family declaration): requires stimela-ninja to validate"
        in result.output
    )
    assert "Strict validation failed" in result.output
    result = CliRunner().invoke(cli.main, ["validate", str(path)])
    assert result.exit_code == 0, result.output
    assert label in result.output


def test_show_displays_declared_pattern_attrs_and_framework_deferrals(monkeypatch):
    from dosho import registry
    from dosho.validation import parse_document

    definition = parse_document(
        "patterned",
        {
            "command": "tool",
            "input_patterns": [
                {
                    "segments": [
                        {"regex": ".+"},
                        {
                            "attrs": {
                                "data": {"dtype": "MSv2"},
                                "native": {"dtype": "int"},
                                "family": {"dtype": "ProductFamily[FITSImage]", "family": {}},
                            }
                        },
                    ]
                }
            ],
        },
    )
    monkeypatch.setattr(registry, "list_cabs", lambda: ["patterned"])
    monkeypatch.setattr(registry, "get", lambda name: definition)
    result = CliRunner().invoke(cli.main, ["show", "patterned"])
    assert result.exit_code == 0, result.output
    assert "input_patterns[0].segments[1].attrs.data: MSv2" in result.output
    assert "input_patterns[0].segments[1].attrs.native: int" in result.output
    assert result.output.count("requires stimela-ninja to validate") == 3


def test_validate_strict_native_pattern_succeeds(tmp_path):
    path = tmp_path / "native-pattern.yaml"
    path.write_text("""
patterned:
  command: tool
  input_patterns:
    - segments:
        - regex: '.+'
        - attrs: {count: {dtype: int}}
""")
    result = CliRunner().invoke(cli.main, ["validate", str(path), "--strict"])
    assert result.exit_code == 0, result.output
    assert "requires stimela-ninja" not in result.output


@pytest.mark.parametrize("presence", ["required: true", "default: 1"])
@pytest.mark.parametrize("bound", ["min_length: 2", "max_length: 2"])
@pytest.mark.parametrize("dtype", ["int", "float", "File", "Union[str, int]"])
def test_validate_rejects_length_constraints_on_native_scalar(tmp_path, presence, bound, dtype):
    result = _check_cabs(
        tmp_path,
        f"sample: {{command: tool, inputs: {{count: {{dtype: '{dtype}', {presence}, {bound}}}}}}}",
    )
    assert result.exit_code == 1
    assert "cabs.yaml" in result.output and "sample" in result.output
    assert "inputs.count" in result.output and "string or container" in result.output


@pytest.mark.parametrize(
    "dtype,extra",
    [
        ("str", "required: true"),
        ("List[int]", "required: true"),
        ("Tuple[int, int]", "required: true"),
        ("str", "choices: [abc, def], nullable: true"),
    ],
)
def test_validate_accepts_length_constraints_on_sized_native_types(tmp_path, dtype, extra):
    result = _check_cabs(
        tmp_path,
        f"sample: {{command: tool, inputs: {{value: {{dtype: '{dtype}', {extra}, min_length: 1}}}}}}",
    )
    assert result.exit_code == 0, result.output


@pytest.mark.parametrize("value", ["1", "false", "[]", "''"])
def test_validate_rejects_pattern_attr_nonmapping(tmp_path, value):
    result = _check_cabs(
        tmp_path,
        "sample: {command: tool, input_patterns: [{segments: [{attrs: {x: " + value + "}}]}]}",
    )
    assert result.exit_code == 1
    assert "sample" in result.output and "input_patterns[0].segments[0].attrs.x" in result.output
    assert "must be a mapping" in result.output


def test_validate_reports_invalid_pattern_regex(tmp_path):
    result = _check_cabs(
        tmp_path,
        "sample: {command: tool, input_patterns: [{segments: [{regex: '['}, {attrs: {x: {dtype: str}}}]}]}",
    )
    assert result.exit_code == 1
    assert "sample" in result.output and "input_patterns[0]" in result.output
    assert "not a valid pattern" in result.output


@pytest.mark.parametrize(
    "fragment,location",
    [
        ("policies: {prefx: '--'}", "policies"),
        ("inputs: {x: {dtype: str, policies: {positonal: true}}}", "inputs.x.policies"),
        (
            "input_patterns: [{segments: [{attrs: {x: {dtype: str, policies: {positonal: true}}}}]}]",
            "input_patterns[0].segments[0].attrs.x.policies",
        ),
    ],
)
def test_validate_rejects_unknown_policy_keys(tmp_path, fragment, location):
    result = _check_cabs(tmp_path, "sample:\n  command: tool\n  " + fragment + "\n")
    assert result.exit_code == 1
    assert location in result.output and "unknown policy keys" in result.output


@pytest.mark.parametrize("key", ["write_path", "writable", "required", "mutable"])
def test_validate_rejects_boolean_metadata_strings(tmp_path, key):
    result = _check_cabs(
        tmp_path, f"sample: {{command: tool, inputs: {{x: {{dtype: File, {key}: 'false'}}}}}}"
    )
    assert result.exit_code == 1
    assert f"inputs.x.{key}" in result.output and "must be a boolean" in result.output


@pytest.mark.parametrize("key", ["positional", "positional_head"])
def test_validate_rejects_boolean_field_policy_strings(tmp_path, key):
    result = _check_cabs(
        tmp_path,
        f"sample: {{command: tool, inputs: {{x: {{dtype: str, policies: {{{key}: 'false'}}}}}}}}",
    )
    assert result.exit_code == 1
    assert f"inputs.x.policies.{key}" in result.output


def test_validate_rejects_boolean_cab_policy_strings(tmp_path):
    result = _check_cabs(tmp_path, "sample: {command: tool, policies: {key_value: 'false'}}")
    assert result.exit_code == 1
    assert "policies.key_value must be a boolean" in result.output


def test_validate_accepts_boolean_false_safety_markers(tmp_path):
    result = _check_cabs(
        tmp_path,
        """
sample:
  command: tool
  inputs:
    x:
      dtype: File
      required: false
      mutable: false
      write_path: false
      writable: false
      policies: {positional: false, positional_head: false}
""",
    )
    assert result.exit_code == 0, result.output


def test_show_pattern_attrs_include_help_choices_and_nullable(monkeypatch):
    from dosho import registry
    from dosho.validation import parse_document

    definition = parse_document(
        "patterned",
        {
            "command": "tool",
            "input_patterns": [
                {
                    "segments": [
                        {"regex": ".+"},
                        {
                            "attrs": {
                                "mode": {
                                    "dtype": "str",
                                    "info": "Select a mode.",
                                    "choices": ["a", "b"],
                                    "nullable": False,
                                },
                            }
                        },
                    ]
                }
            ],
        },
    )
    monkeypatch.setattr(registry, "list_cabs", lambda: ["patterned"])
    monkeypatch.setattr(registry, "get", lambda name: definition)
    result = CliRunner().invoke(cli.main, ["show", "patterned"])
    assert result.exit_code == 0, result.output
    for text in (
        "input_patterns[0].segments[1].attrs.mode: str",
        "Select a mode.",
        "Choices: ['a', 'b']",
        "Nullable: False",
    ):
        assert text in result.output


def test_validate_defers_framework_length_applicability(tmp_path):
    result = _check_cabs(
        tmp_path,
        "sample: {command: tool, inputs: {ms: {dtype: MSv2, required: true, min_length: 2}}}",
    )
    assert result.exit_code == 0, result.output
    assert "inputs.ms (MSv2): requires stimela-ninja to validate" in result.output


@pytest.mark.parametrize("repeat", ["[list]", "{bad: true}", "false", "1", "wrong"])
@pytest.mark.parametrize("pattern", [False, True])
def test_validate_rejects_unsupported_field_repeat(tmp_path, repeat, pattern):
    field = f"{{dtype: 'List[str]', policies: {{repeat: {repeat}}}}}"
    content = (
        "input_patterns: [{segments: [{attrs: {x: " + field + "}}]}]"
        if pattern
        else "inputs: {x: " + field + "}"
    )
    path = tmp_path / "repeat.yaml"
    path.write_text("sample:\n  command: tool\n  " + content + "\n")
    result = CliRunner().invoke(cli.main, ["validate", str(path), "--strict"])
    assert result.exit_code == 1
    assert "policies.repeat must be 'list' or null" in result.output
    assert (
        "input_patterns[0].segments[0].attrs.x" in result.output
        if pattern
        else "inputs.x" in result.output
    )


@pytest.mark.parametrize("repeat", ["list", "null"])
@pytest.mark.parametrize("pattern", [False, True])
def test_validate_accepts_supported_field_repeat(tmp_path, repeat, pattern):
    field = f"{{dtype: 'List[str]', policies: {{repeat: {repeat}}}}}"
    content = (
        "input_patterns: [{segments: [{attrs: {x: " + field + "}}]}]"
        if pattern
        else "inputs: {x: " + field + "}"
    )
    result = _check_cabs(tmp_path, "sample:\n  command: tool\n  " + content + "\n")
    assert result.exit_code == 0, result.output


def test_validate_accepts_existing_cab_repeat_token(tmp_path):
    result = _check_cabs(tmp_path, "sample: {command: tool, policies: {repeat: '[]'}}")
    assert result.exit_code == 0, result.output


@pytest.mark.parametrize(
    "reference", ["1", "0", "false", "null", "''", "{}", "[{}]", "[[bad]]", "[good, 1]"]
)
def test_validate_rejects_nonstring_use_references(tmp_path, reference):
    result = _check_cabs(
        tmp_path, "good: {command: tool}\nsample: {command: tool, _use: " + reference + "}\n"
    )
    assert result.exit_code == 1
    assert "cabs.yaml" in result.output
    assert "_use reference must be a nonempty dotted-path string" in result.output


@pytest.mark.parametrize(
    "include",
    [
        "{1: file.yaml}",
        "{false: file.yaml}",
        "{'(dosho)': [1]}",
        "{'(dosho)': [false]}",
        "{'(dosho)': null}",
        "{'(dosho)': {bad: true}}",
        "{'(dosho)': [[]]}",
    ],
)
def test_validate_rejects_nonstring_include_keys_and_filenames(tmp_path, include):
    result = _check_cabs(tmp_path, "_include: " + include + "\ncabs: {sample: {command: tool}}\n")
    assert result.exit_code == 1
    assert "cabs.yaml" in result.output
    assert "_include" in result.output and "must be a string" in result.output


@pytest.mark.parametrize("target", ["1", "0", "false", "null", "text", "[]", "[one, two]"])
def test_validate_rejects_nonmapping_use_target(tmp_path, target):
    result = _check_cabs(
        tmp_path, f"lib: {target}\ncabs:\n  sample: {{command: tool, _use: lib}}\n"
    )
    assert result.exit_code == 1
    assert "_use target 'lib' must be a mapping" in result.output
    assert "checks passed" not in result.output


def test_validate_simms_defaults_pass_strict_checks():
    from dosho import registry

    path = Path(registry.__file__).parent / "documents" / "simms.yaml"
    result = CliRunner().invoke(cli.main, ["validate", str(path), "--strict"])
    assert result.exit_code == 0, result.output
    assert "Static definition checks passed: simms" in result.output
    assert "requires stimela-ninja to validate" not in result.output
