import pytest

import dosho
from dosho import registry


def test_list_cabs_returns_registered_names():
    assert set(registry.list_cabs()) == set(registry._index())


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
    from dosho.cabs import listobs, simms_classic, wsclean
    from dosho.cabs.casatasks import listobs as listobs_submodule
    from dosho.cabs.simms import skysim, telsim

    # Pysteps are still Python objects, so identity holds and is worth
    # pinning: the registry must hand back *the* StepRef, not a copy.
    assert listobs is dosho.get("listobs")
    assert listobs_submodule is listobs
    assert skysim is dosho.get("simms-skysim")
    assert telsim is dosho.get("simms-telsim")

    # Binary cabs are built from their document now, so `get` returns a fresh
    # equivalent rather than the module-level object. Equivalence is the real
    # contract; identity was only ever an artefact of both coming from the
    # same import. Once the Python definitions go, `dosho.cabs` will serve
    # these through the registry too and identity returns.
    from tests.cab_compare import cab_differences

    assert cab_differences(wsclean, dosho.get("wsclean")) == []
    assert cab_differences(simms_classic, dosho.get("simms")) == []


def _document_cab_name() -> str:
    """Any document-backed name -- the pysteps never reach `build_document`."""
    return next(n for n, e in registry._index().items() if "document" in e)


def test_stale_shinobi_names_the_version_to_upgrade_to(monkeypatch):
    """A shinobi predating the yaml_cab loader must fail with the version to
    install, not with a raw `ImportError` about a private import path.

    Nothing else enforces the pairing: shinobi is dosho's `run` extra, so
    `pip install stimela-ninja dosho` resolves both with no edge between them.
    This message is the only thing standing between a user and 61 document
    cabs failing on an import name they have no reason to recognise.
    """
    import shinobi.cabs

    monkeypatch.delattr(shinobi.cabs, "build_document")
    monkeypatch.setattr(registry, "_cab_cache", {})

    with pytest.raises(ImportError) as excinfo:
        registry.get(_document_cab_name())

    message = str(excinfo.value)
    assert "stimela-ninja" in message
    # The requirement is quoted from dosho's own metadata, so the test cannot
    # drift from the pin the way a hardcoded version string would.
    assert registry._required_shinobi() in message
    assert "pysteps are unaffected" in message


def test_absent_shinobi_says_to_install_the_run_extra(monkeypatch):
    """Missing shinobi is a different fix from a stale one, and says so."""
    import builtins

    real_import = builtins.__import__

    def refuse_shinobi(name, *args, **kwargs):
        if name == "shinobi.cabs":
            raise ModuleNotFoundError("No module named 'shinobi'", name="shinobi")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", refuse_shinobi)
    monkeypatch.setattr(registry, "_cab_cache", {})

    with pytest.raises(ModuleNotFoundError, match=r"dosho\[run\]"):
        registry.get(_document_cab_name())


def test_required_shinobi_comes_from_the_run_extra():
    """The guard quotes dosho's declared requirement rather than restating it,
    so bumping `pyproject.toml` is the only edit a shinobi bump needs.
    """
    required = registry._required_shinobi()
    assert required is not None
    assert required.startswith("stimela-ninja")
    assert ";" not in required and "extra" not in required
