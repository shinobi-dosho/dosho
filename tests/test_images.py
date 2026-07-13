"""Tests for the image manifest loader + override layer (`dosho.images`)."""

import importlib

import pytest

from dosho import images


def test_manifest_exposed_with_metadata_and_images():
    assert set(images.manifest) >= {"metadata", "images"}
    md = images.manifest["metadata"]
    assert md["registry"] and md["bundle_version"]


def test_every_manifest_key_is_exposed_as_a_resolved_string_constant():
    """Backward-compat: cabs read `images.<KEY>`; every manifest image key
    must resolve to a non-empty string module attribute.
    """
    for key in images.manifest["images"]:
        value = getattr(images, key)
        assert isinstance(value, str) and value


def test_ref_entry_is_used_verbatim():
    entry = {"ref": "quay.io/x/y:1.2.3"}
    assert images._resolve_ref("Y", entry, {}) == "quay.io/x/y:1.2.3"


def test_build_entry_composes_registry_name_version_bundle():
    metadata = {"registry": "ghcr.io/dosho", "bundle_version": "d0.1.0"}
    entry = {"build": {"version": "3.4"}}
    assert images._resolve_ref("AOFLAGGER", entry, metadata) == "ghcr.io/dosho/aoflagger:3.4-d0.1.0"


def test_build_entry_honours_explicit_name():
    metadata = {"registry": "ghcr.io/dosho", "bundle_version": "d0.1.0"}
    entry = {"name": "mosaic-queen", "build": {"version": "1.0"}}
    assert images._resolve_ref("MOSAIC_QUEEN", entry, metadata) == "ghcr.io/dosho/mosaic-queen:1.0-d0.1.0"


def test_entry_with_neither_ref_nor_build_raises():
    with pytest.raises(ValueError):
        images._resolve_ref("BROKEN", {}, {})


def test_env_var_override_wins_over_manifest():
    refs = {"WSCLEAN": "quay.io/stimela2/wsclean:orig"}
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("DOSHO_IMAGE_WSCLEAN", "ghcr.io/dosho/wsclean:new")
        out = images._apply_overrides(dict(refs))
    assert out["WSCLEAN"] == "ghcr.io/dosho/wsclean:new"


def test_dosho_images_file_override_merges(tmp_path):
    ovr = tmp_path / "overrides.yaml"
    ovr.write_text("WSCLEAN: ghcr.io/dosho/wsclean:from-file\n")
    refs = {"WSCLEAN": "quay.io/stimela2/wsclean:orig"}
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("DOSHO_IMAGES", str(ovr))
        mp.delenv("DOSHO_IMAGE_WSCLEAN", raising=False)
        out = images._apply_overrides(dict(refs))
    assert out["WSCLEAN"] == "ghcr.io/dosho/wsclean:from-file"


def test_precedence_env_beats_file_beats_manifest(tmp_path):
    ovr = tmp_path / "overrides.yaml"
    ovr.write_text("WSCLEAN: from-file\n")
    refs = {"WSCLEAN": "from-manifest"}
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("DOSHO_IMAGES", str(ovr))
        mp.setenv("DOSHO_IMAGE_WSCLEAN", "from-env")
        out = images._apply_overrides(dict(refs))
    assert out["WSCLEAN"] == "from-env"


def test_import_time_override_reaches_the_module_constant():
    """End-to-end: setting the env before (re)import repoints the constant."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("DOSHO_IMAGE_CASA6", "ghcr.io/dosho/casa6:test")
        reloaded = importlib.reload(images)
        assert reloaded.CASA6 == "ghcr.io/dosho/casa6:test"
    # restore the module to its unfudged state for any later tests
    importlib.reload(images)
