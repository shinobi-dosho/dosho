"""Tests for the docs cab-catalog Sphinx extension (docs/_ext/cab_catalog.py).

The extension lives under docs/, not the package, so it's imported by path here.
These guard the catalog against silent breakage if the registry / image-manifest
/ cab-schema APIs it introspects change.
"""

import importlib.util
import sys
import types
from pathlib import Path

_EXT = Path(__file__).resolve().parents[1] / "docs" / "_ext" / "cab_catalog.py"
_spec = importlib.util.spec_from_file_location("cab_catalog", _EXT)
cab_catalog = importlib.util.module_from_spec(_spec)
sys.modules["cab_catalog"] = cab_catalog
_spec.loader.exec_module(cab_catalog)


def test_summary_stops_at_napoleon_section():
    info = "Write a listobs summary.\n\nArgs:\n    vis: the MS\n"
    assert cab_catalog._summary(info) == "Write a listobs summary."


def test_summary_of_empty_is_blank():
    assert cab_catalog._summary(None) == ""
    assert cab_catalog._summary("") == ""


def test_rst_cell_neutralises_inline_markup():
    assert cab_catalog._rst_cell("") == "\\-"
    out = cab_catalog._rst_cell("use *this* and `that` | pipe")
    for ch in ("*", "`", "|"):
        assert ch not in out.replace("\\" + ch, "")


def test_image_index_maps_a_built_ref_to_its_key():
    idx = cab_catalog._image_index()
    # WSCLEAN is a build: entry -> its resolved ref appears with key + version
    from dosho import images

    meta = idx[images.WSCLEAN]
    assert meta["key"] == "WSCLEAN" and meta["kind"] == "build" and meta["version"] == "3.6"


def test_schema_obj_resolves_cab_and_stepref():
    from dosho import registry

    # a Cab exposes inputs_model directly
    assert cab_catalog._schema_obj(registry.get("wsclean")).inputs_model is not None
    # a StepRef (casatask) exposes it via .step
    listobs = registry.get("listobs")
    assert cab_catalog._schema_obj(listobs).inputs_model is not None


def test_generate_writes_catalog_with_cabs_and_image_linkage(tmp_path):
    app = types.SimpleNamespace(srcdir=str(tmp_path))
    cab_catalog._generate(app)
    text = (tmp_path / "reference" / "cabs.rst").read_text()

    # a Cab, a StepRef, and their resolved images all appear
    assert "\nwsclean\n" in text and "\nlistobs\n" in text
    assert "ghcr.io/shinobi-dosho/wsclean:3.6-d0.1.0" in text
    assert "ghcr.io/shinobi-dosho/casa6:6.7-d0.1.0" in text  # listobs' image
    # schema tables rendered
    assert "**Inputs**" in text and ".. list-table::" in text


def test_committed_catalog_is_fresh(tmp_path):
    """The same staleness gate CI applies, but at `pytest` speed: the
    committed docs/reference/cabs.rst must match what the live registry
    generates. If this fails, run `uv run python docs/_ext/cab_catalog.py`
    and commit the result (the pre-commit hook does exactly that for you).
    """
    app = types.SimpleNamespace(srcdir=str(tmp_path))
    cab_catalog._generate(app)
    generated = (tmp_path / "reference" / "cabs.rst").read_text()
    committed = (
        Path(__file__).resolve().parents[1] / "docs" / "reference" / "cabs.rst"
    ).read_text()
    assert generated == committed, (
        "docs/reference/cabs.rst is stale -- regenerate with "
        "`uv run python docs/_ext/cab_catalog.py` and commit it"
    )


def test_main_reports_fresh_catalog():
    # After the freshness test above, main() must agree and exit 0 -- and
    # must not have modified the file (idempotent regeneration).
    committed = Path(__file__).resolve().parents[1] / "docs" / "reference" / "cabs.rst"
    before = committed.read_text()
    assert cab_catalog.main() == 0
    assert committed.read_text() == before
