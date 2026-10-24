"""Tests for the docs cab-catalog Sphinx extension (docs/_ext/cab_catalog.py).

The extension lives under docs/, not the package, so it's imported by path here.
These guard the catalog against silent breakage if the registry / image-manifest
/ cab-schema APIs it introspects change.
"""

import importlib.util
import sys
import types
from pathlib import Path
from typing import Literal

import pytest

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
    assert (
        meta["key"] == "WSCLEAN" and meta["kind"] == "build" and meta["version"] == "3.6-idg-noble"
    )


def test_schema_obj_resolves_binary_and_function_definitions():
    from dosho import registry

    # a Cab exposes inputs_model directly
    assert cab_catalog._schema_obj(registry.get("wsclean")).inputs["ms"].dtype == "List[MSv2]"
    # a StepRef (casatask) exposes it via .step
    listobs = registry.get("listobs")
    assert cab_catalog._schema_obj(listobs).inputs_model is not None


def test_generate_writes_catalog_with_cabs_and_image_linkage(tmp_path):
    app = types.SimpleNamespace(srcdir=str(tmp_path))
    cab_catalog._generate(app)
    text = (tmp_path / "reference" / "cabs.rst").read_text()

    # a Cab, a StepRef, and their resolved images all appear
    assert "\nwsclean\n" in text and "\nlistobs\n" in text
    assert "ghcr.io/shinobi-dosho/wsclean:3.6-idg-noble-d0.1.0" in text
    assert "ghcr.io/shinobi-dosho/casa-tasks:6.7.0.31-d0.1.0" in text  # listobs' image
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


@pytest.mark.parametrize(
    "dtype",
    [
        "MSv2",
        "CasaTab",
        "List[MSv2]",
        "FITSImage",
        "FITSTable",
        "ProductFamily[FITSImage]",
        "ProductMember[FITSTable]",
    ],
)
def test_declared_framework_types_render_without_binding(dtype):
    from dosho.validation import describe_cab, parse_document

    description = describe_cab(
        parse_document(
            "x", {"command": "x", "inputs": {"data": {"dtype": dtype, "required": True}}}
        )
    )
    text = "\n".join(cab_catalog._field_table(description.inputs, with_default=True))
    assert f"``{dtype}``" in text
    assert "*required*" in text


def test_the_catalog_shows_a_real_cab_as_strict():
    from dosho import registry

    cab = cab_catalog._schema_obj(registry.get("tricolour"))
    assert cab.inputs["ms"].dtype == cab.outputs["ms"].dtype == "MSv2"


@pytest.mark.parametrize(
    "annotation,expected",
    [
        (list[Path], "list[Path]"),
        (list[Path] | None, "list[Path] | None"),
        (dict[str, list[Path | None]], "dict[str, list[Path | None]]"),
        (list[Literal["ms.image.fits", "other"]], "list[Literal['ms.image.fits', 'other']]"),
    ],
)
def test_python_annotations_render_stably(annotation, expected):
    assert cab_catalog._type_name(annotation) == expected


@pytest.mark.parametrize(
    "cab_name,names",
    [
        (
            "wsclean",
            (
                "image",
                "dirty",
                "residual",
                "model",
                "psf",
                "continued_beam_model",
                "continued_facet_beam_model",
            ),
        ),
        ("ddfacet", ("dirty", "restored", "model", "residual", "psf")),
    ],
)
def test_image_families_render_public_fits_contracts(cab_name, names):
    from dosho import registry

    cab = cab_catalog._schema_obj(registry.get(cab_name))
    for name in names:
        assert cab.outputs[name].dtype == "ProductFamily[FITSImage]"


def test_descriptive_table_keeps_validation_constraints():
    from dosho.validation import describe_cab, parse_document

    fields = describe_cab(
        parse_document(
            "x",
            {
                "command": "x",
                "inputs": {
                    "mode": {
                        "dtype": "str",
                        "default": "aa",
                        "nullable": False,
                        "choices": ["aa", "bb"],
                        "min_length": 2,
                        "max_length": 3,
                        "string_pattern": "[ab]+",
                    }
                },
            },
        )
    ).inputs
    text = "\n".join(cab_catalog._field_table(fields, with_default=True))
    assert "``str``" in text
    for expected in (
        "Choices:",
        "'aa'",
        "'bb'",
        "Nullable: False",
        "Minimum length: 2",
        "Maximum length: 3",
        "Pattern: [ab]+",
    ):
        assert expected in text
