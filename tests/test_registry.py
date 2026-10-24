"""The registry exposes neutral definitions; runtime adaptation is explicit."""

import inspect

import pytest

import dosho
from dosho import registry
from dosho._pystep import get_pystep_definition
from dosho.validation import CabSpec, describe_cab


def test_list_cabs_returns_registered_names():
    assert set(registry.list_cabs()) == set(registry._index())


def test_get_unknown_cab_raises_key_error():
    with pytest.raises(KeyError):
        registry.get("no-such-cab")


def test_top_level_reexports_match_registry():
    assert dosho.get is registry.get
    assert dosho.list_cabs is registry.list_cabs


def test_every_registered_definition_has_a_matching_name():
    for name, entry in registry._index().items():
        definition = registry.get(name)
        if "document" in entry:
            assert isinstance(definition, CabSpec)
            assert describe_cab(definition).name == name
        else:
            assert inspect.isfunction(definition)
            marker = get_pystep_definition(definition)
            assert marker is not None
            assert (marker.options["name"] or definition.__name__) == name


def test_direct_import_matches_registry_lookup():
    from dosho.cabs import listobs, simms_classic, wsclean
    from dosho.cabs.casatasks import listobs as listobs_submodule
    from dosho.cabs.simms import skysim, telsim

    assert listobs is dosho.get("listobs")
    assert listobs_submodule is listobs
    assert wsclean is dosho.get("wsclean")
    assert simms_classic is dosho.get("simms")
    assert skysim is dosho.get("simms-skysim")
    assert telsim is dosho.get("simms-telsim")


def test_provider_documents_negotiate_the_compiler_contract():
    name = next(n for n, e in registry._index().items() if "document" in e)
    dialect, text = registry.get_document(name)
    assert dialect == "dosho-cab-v1"
    assert text
