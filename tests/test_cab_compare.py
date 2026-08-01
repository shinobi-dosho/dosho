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

from tests.cab_compare import cab_differences, cabs_equivalent


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
    """The failure a lossy dialect would actually produce."""
    original, other = pair
    kept = dict(list(other.inputs_model.model_fields.items())[:-1])
    trimmed = type(other.inputs_model)(other.inputs_model.__name__, (), {})
    trimmed.model_fields = kept
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
