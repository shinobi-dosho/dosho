"""The documents are the cabs now, so these check what that means.

Until the Python definitions were deleted there were two independent
descriptions of every cab and a gate comparing them, which is what made the
migration safe (see `docs/design_data_registry.md` §4.6). There is one
description now. Nothing here can prove a document *right* -- there is nothing
left to be right against -- so these check the things that are still
checkable: that every document loads, that the index and the documents agree
about what exists, and that the properties a cab needs in order to work at all
survive the load.
"""

from __future__ import annotations

import pathlib

import pytest
import yaml
from shinobi.steps.schema import Cab, StepRef

import dosho
import dosho.cabs as C
from dosho.registry import _DOCUMENT_DIR, _index

DOCUMENTS = sorted(_DOCUMENT_DIR.glob("*.yaml"))


def test_there_are_documents():
    assert len(DOCUMENTS) > 40, "the document directory looks empty or misnamed"


@pytest.mark.parametrize("path", DOCUMENTS, ids=lambda p: p.stem)
def test_every_document_loads_into_a_cab(path: pathlib.Path):
    cab = dosho.get(path.stem)
    assert isinstance(cab, Cab)
    assert cab.name == path.stem
    assert cab.command


@pytest.mark.parametrize("path", DOCUMENTS, ids=lambda p: p.stem)
def test_every_document_resolves_its_image(path: pathlib.Path):
    """A document names its image by manifest key so a deployment can override
    it. If the key is missing from the manifest it survives the load as a bare
    word and fails much later, at pull time, in a container runtime.
    """
    cab = dosho.get(path.stem)
    assert "/" in cab.image or ":" in cab.image, f"{cab.image!r} looks like an unresolved key"


@pytest.mark.parametrize("path", DOCUMENTS, ids=lambda p: p.stem)
def test_every_declared_input_has_a_dtype(path: pathlib.Path):
    """`dtype` is the one field the loader cannot reconstruct from anything
    else, and it silently defaults to `str`. A document that lost one would
    load fine and mistype the parameter.
    """
    body = yaml.safe_load(path.read_text())["cabs"][path.stem]
    for section in ("inputs", "outputs"):
        for name, spec in (body.get(section) or {}).items():
            assert spec.get("dtype"), f"{path.stem}.{section}.{name} has no dtype"


def test_index_and_documents_agree():
    """Each is the other's check: a document with no entry is unreachable by
    name, and an entry with no document resolves to a missing file at import.
    """
    indexed = {name for name, e in _index().items() if "document" in e}
    on_disk = {p.stem for p in DOCUMENTS}
    assert indexed == on_disk


def test_every_index_entry_resolves():
    """Both kinds, through the attribute the index claims `dosho.cabs` exports
    -- which is the only place that mapping is written down now.
    """
    for name, entry in _index().items():
        obj = getattr(C, entry["attr"])
        assert isinstance(obj, (Cab, StepRef)), f"{name} -> {entry['attr']} is {type(obj).__name__}"


def test_pysteps_are_still_python():
    """The half that is not documents, and cannot be: a pystep is a function."""
    pysteps = [n for n, e in _index().items() if "document" not in e]
    assert len(pysteps) > 60
    assert all(isinstance(dosho.get(n), StepRef) for n in pysteps)


def test_pattern_cabs_kept_their_patterns():
    """The last thing the dialect learned to carry, and the easiest to lose
    silently: a cab without its patterns rejects every dynamic parameter.
    """
    for name in ("cubical", "quartical", "wsclean"):
        cab = dosho.get(name)
        assert cab.input_patterns or cab.output_patterns, f"{name} lost its patterns"
    cubical = dosho.get("cubical")
    assert cubical.inputs_model.model_config.get("extra") == "allow"
    assert cubical.match_pattern("g1-solvable") is not None
