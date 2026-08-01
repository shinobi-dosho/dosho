"""Tests for the round-trip comparator.

The comparator is what `docs/design_data_registry.md`'s migration gate rests
on, so these check it in both directions. Showing it returns "equal" for equal
cabs proves nothing on its own -- a comparator that always returns "equal"
would pass that. The load-bearing tests here are the ones feeding it pairs that
differ in exactly one field, and the sweep over every distinct pair of dosho's
real cabs.
"""

from __future__ import annotations

import importlib
import itertools
import sys

import pytest
from shinobi.steps.schema import Cab

from tests.cab_compare import FIELD_ATTRS, cab_differences, cabs_equivalent


def _fresh_cabs() -> dict[str, Cab]:
    """Import `dosho.cabs` from scratch, so every `Cab` is a distinct object
    built by a distinct `create_model` call -- which is the situation the
    migration is actually in: two builds of the same definition.

    `sys.modules` is put back exactly as found. Without that, the rest of the
    suite inherits freshly-imported dosho modules with their module-level state
    reset -- `images`' import-time override constants and `registry`'s
    warned-once set both live there, and both have tests that then fail for
    reasons having nothing to do with them.
    """
    saved = {m: sys.modules[m] for m in list(sys.modules) if m.startswith("dosho")}
    try:
        for mod in saved:
            del sys.modules[mod]
        pkg = importlib.import_module("dosho.cabs")
        return {n: obj for n in pkg.__all__ if isinstance(obj := getattr(pkg, n), Cab)}
    finally:
        for mod in [m for m in sys.modules if m.startswith("dosho")]:
            del sys.modules[mod]
        sys.modules.update(saved)


@pytest.fixture(scope="module")
def rebuilt() -> tuple[dict[str, Cab], dict[str, Cab]]:
    return _fresh_cabs(), _fresh_cabs()


def test_pydantic_equality_is_useless_here(rebuilt):
    """The premise. If this ever starts passing, the comparator is redundant
    and should be deleted rather than maintained.
    """
    a, b = rebuilt
    assert a, "no binary cabs found -- the sweep below would be vacuous"
    assert not any(a[n] == b[n] for n in a), (
        "pydantic == now compares generated models structurally; "
        "re-evaluate whether this module is still needed"
    )


def test_every_cab_matches_an_identical_rebuild(rebuilt):
    """The property the migration needs: same definition, built twice, equal."""
    a, b = rebuilt
    mismatched = {n: cab_differences(a[n], b[n]) for n in a if not cabs_equivalent(a[n], b[n])}
    assert mismatched == {}


def test_no_two_distinct_cabs_compare_equal(rebuilt):
    """The direction that actually tests discrimination: across every distinct
    pair, the comparator must never say "equal". A comparator ignoring a field
    would start failing here long before it failed above.
    """
    a, _ = rebuilt
    names = sorted(a)
    false_positives = [
        (x, y) for x, y in itertools.combinations(names, 2) if cabs_equivalent(a[x], a[y])
    ]
    assert false_positives == []


# --- one field at a time -------------------------------------------------
#
# Each of these mutates exactly one thing and asserts the comparator notices.
# They are the guard against the comparator quietly narrowing over time.


@pytest.fixture
def pair(rebuilt) -> tuple[Cab, Cab]:
    a, b = rebuilt
    name = "breizorro" if "breizorro" in a else min(a)
    return a[name], b[name].model_copy(deep=True)


def test_detects_a_changed_scalar(pair):
    original, other = pair
    other = other.model_copy(update={"command": "not-the-same"})
    assert any(d.startswith("command:") for d in cab_differences(original, other))


def test_detects_a_changed_flavour(pair):
    original, other = pair
    other = other.model_copy(update={"flavour": "casa-task"})
    assert any(d.startswith("flavour:") for d in cab_differences(original, other))


def test_detects_a_dropped_input_field(pair):
    """The failure a lossy dialect would actually produce.

    Built with `create_model` rather than by poking `model_fields` onto a bare
    class: the comparator reads `model_config` too, and a hand-made class has
    none, so the shortcut tested the comparator against something pydantic
    would never hand it.
    """
    from pydantic import create_model

    original, other = pair
    fields = {
        name: (f.annotation, f.default)
        for name, f in list(other.inputs_model.model_fields.items())[:-1]
    }
    trimmed = create_model(other.inputs_model.__name__, **fields)
    diffs = cab_differences(original, other.model_copy(update={"inputs_model": trimmed}))
    assert any("present in A, absent in B" in d for d in diffs)


def test_detects_a_changed_default(pair):
    from pydantic import create_model

    original, other = pair
    fields = {}
    for i, (n, f) in enumerate(other.inputs_model.model_fields.items()):
        fields[n] = (f.annotation, "MUTATED" if i == 0 else f.default)
    mutated = create_model(other.inputs_model.__name__, **fields)
    diffs = cab_differences(original, other.model_copy(update={"inputs_model": mutated}))
    assert any("default" in d for d in diffs), diffs


def test_differences_name_the_field_that_differs(pair):
    """A failing gate has to say what it lost, not just that it lost."""
    original, other = pair
    diffs = cab_differences(original, other.model_copy(update={"image": "elsewhere/img:1"}))
    assert len(diffs) == 1
    assert diffs[0].startswith("image:")
    assert "elsewhere/img:1" in diffs[0]


# --------------------------------------------------------------------------
# Mutation sweep: does the comparator notice every kind of change?
# --------------------------------------------------------------------------
#
# The comparator is the migration gate. Its failure mode is silence -- it has
# had two blind spots already (`dtype`, then `model_config["extra"]`), both
# found by using its output rather than by reading it. This sweep changes one
# thing at a time and insists it is reported.
#
# Every case asserts the mutation *took* before asserting it was seen. A
# perturbation that sets a value to what it already was reads exactly like a
# blind spot, and two of the first run's apparent misses were that.


def _cab():
    import dosho.cabs as C

    return C.cubical


CAB_MUTATIONS = {
    "name": "other",
    "info": "changed",
    "image": "other/img:1",
    "command": "other",
    "flavour": "casa-task",
    "backend": "native",
    "venv": "/venv",
    "cache": False,
    "cache_dir": "/cache",
    "sandbox": True,
    "harvest": ["x-*.fits"],
    "scratch": ["y/*"],
    "wranglers": {"stdout": ["ERROR"]},
}


@pytest.mark.parametrize(("field", "value"), sorted(CAB_MUTATIONS.items()))
def test_comparator_notices_a_changed_cab_field(field, value):
    cab = _cab()
    assert getattr(cab, field) != value, f"{field} mutation is a no-op -- pick another value"
    assert cab_differences(cab, cab.model_copy(update={field: value})) != []


def test_comparator_notices_changed_field_meta():
    cab = _cab()
    name = min(cab.field_meta)
    meta = dict(cab.field_meta)
    meta[name] = meta[name].model_copy(update={"info": "tampered"})
    assert meta[name] != cab.field_meta[name]
    assert cab_differences(cab, cab.model_copy(update={"field_meta": meta})) != []


def test_comparator_notices_changed_patterns():
    cab = _cab()
    assert cab.input_patterns, "cubical should have input patterns"
    mutated = [p.model_copy(update={"separator": "~"}) for p in cab.input_patterns]
    assert mutated != cab.input_patterns
    assert cab_differences(cab, cab.model_copy(update={"input_patterns": mutated})) != []


def test_comparator_notices_a_changed_extra_policy():
    """The blind spot that let a broken cubical through the gate: identical
    fields, and a model that rejects every dynamic parameter it exists for.
    """
    from pydantic import create_model

    cab = _cab()
    fields = {
        n: (f.annotation, f.default) for n, f in list(cab.inputs_model.model_fields.items())[:3]
    }
    permissive = create_model("X", __config__={"extra": "allow"}, **fields)
    strict = create_model("X", **fields)
    assert permissive.model_config.get("extra") != strict.model_config.get("extra")
    assert (
        cab_differences(
            cab.model_copy(update={"inputs_model": permissive}),
            cab.model_copy(update={"inputs_model": strict}),
        )
        != []
    )


@pytest.mark.parametrize("attr", [a for a in FIELD_ATTRS if a not in {"annotation", "default"}])
def test_comparator_notices_every_field_attribute(attr):
    """Generic over `FieldInfo.__slots__`, so an attribute pydantic adds in a
    future version is covered the day it appears rather than the day someone
    remembers to add it here.
    """
    from pydantic import Field, create_model

    cab = _cab()
    fields = {
        n: (f.annotation, f.default) for n, f in list(cab.inputs_model.model_fields.items())[:3]
    }
    first = next(iter(fields))
    annotation, default = fields[first]

    probes = {
        "alias": {"alias": "aliased"},
        "alias_priority": {"alias": "aliased", "alias_priority": 1},
        "deprecated": {"deprecated": "gone"},
        "description": {"description": "described"},
        "discriminator": None,  # needs a tagged union; not reachable for a cab
        "examples": {"examples": [1]},
        "exclude": {"exclude": True},
        "exclude_if": None,  # callable; no stable value to compare
        "field_title_generator": None,  # callable
        "default_factory": None,  # mutually exclusive with a default
        "default_factory_takes_validated_data": None,
        "frozen": {"frozen": True},
        "init": {"init": False},
        "init_var": {"init_var": True},
        "json_schema_extra": {"json_schema_extra": {"abbreviation": "z"}},
        "kw_only": {"kw_only": True},
        "metadata": {"gt": 0},
        "repr": {"repr": False},
        "serialization_alias": {"serialization_alias": "ser"},
        "title": {"title": "titled"},
        "validate_default": {"validate_default": True},
        "validation_alias": {"validation_alias": "val"},
    }
    kwargs = probes.get(attr, "unhandled")
    if kwargs == "unhandled":
        pytest.fail(f"FieldInfo gained {attr!r} -- add a probe for it or say why it has none")
    if kwargs is None:
        pytest.skip(f"{attr} has no stable value a cab could carry")

    ann = int if attr == "metadata" else annotation
    ref = create_model("X", **{**fields, first: (ann, Field(default))})
    mutated = create_model("X", **{**fields, first: (ann, Field(default, **kwargs))})
    a, b = ref.model_fields[first], mutated.model_fields[first]
    assert getattr(a, attr, None) != getattr(b, attr, None), f"{attr} probe is a no-op"
    assert (
        cab_differences(
            cab.model_copy(update={"inputs_model": ref}),
            cab.model_copy(update={"inputs_model": mutated}),
        )
        != []
    )
