import pytest

import dosho
from dosho import registry


def test_list_cabs_returns_registered_names():
    assert set(registry.list_cabs()) == set(registry._entries())


def test_get_unknown_cab_raises_key_error():
    with pytest.raises(KeyError):
        registry.get("no-such-cab")


def test_top_level_reexports_match_registry():
    assert dosho.get is registry.get
    assert dosho.list_cabs is registry.list_cabs


def test_every_registered_cab_resolves_and_has_a_matching_name(monkeypatch):
    """Once cabs are registered, each entry must actually resolve to a
    `Cab` whose own `.name` matches the registry key it's filed under --
    catches a copy-paste mistake where a module's registry entry points at
    the wrong module/attribute or the cab was renamed without updating
    the registry key.
    """
    for name in registry.list_cabs():
        cab = registry.get(name)
        assert cab.name == name


def test_direct_import_matches_registry_lookup():
    """`from dosho.cabs import wsclean`/`from dosho.cabs.casatasks import
    listobs` (write-time-known) must resolve to the exact same object as
    `dosho.get(...)` (runtime-known) -- two interfaces, one underlying set
    of objects.
    """
    from dosho.cabs import listobs, wsclean
    from dosho.cabs.casatasks import listobs as listobs_submodule
    from dosho.cabs.simms import simms_classic, skysim, telsim

    assert wsclean is dosho.get("wsclean")
    assert listobs is dosho.get("listobs")
    assert listobs_submodule is listobs
    assert skysim is dosho.get("simms-skysim")
    assert telsim is dosho.get("simms-telsim")
    assert simms_classic is dosho.get("simms")
