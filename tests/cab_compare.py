"""Structural comparison of two `Cab`s, for the document round-trip gate.

`Cab` is a pydantic model, so `a == b` looks like it should work. It does not,
and the way it fails is quiet: `Scope.inputs_model`/`outputs_model` hold *class
objects* built by `pydantic.create_model`, which returns a fresh class per
call. Equality on a field whose value is a class falls back to identity, so two
cabs specified identically never compare equal -- measured across dosho's own
cabs, `==` says equal for 0 of 42 against an identically rebuilt copy.

That matters because `docs/design_data_registry.md` proposes proving the
Python -> document migration lossless by round-tripping every cab and comparing.
With `==` that gate can never open, whatever the dialect does. This module is
what the gate actually rests on, which makes its own correctness load-bearing:
a comparison that quietly ignores a field would bless a dialect that silently
drops it. Hence `cab_differences` returning *what* differs rather than a bool
-- a failing round-trip has to say which field it lost -- and hence
`test_cab_compare.py` checking it against known-*unequal* pairs, not only
known-equal ones.

Not for pysteps: a `StepRef` carries a function, and two functions are not
comparable in any useful structural sense. Pysteps stay Python under the split
this exists to enable (see the design doc's §4.1).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

# The two fields holding generated classes. Everything else on Scope/Cab is
# plain data and round-trips through `model_dump`.
_MODEL_FIELDS = ("inputs_model", "outputs_model")


def model_shape(model: type[BaseModel]) -> dict[str, tuple]:
    """The structural fingerprint of a generated model: per field, what
    `create_model` was given.

    `annotation` compares by value for the types cabs use -- `Literal["a","b"]`
    equals an identically-spelled `Literal`, so the `choices` narrowing
    `shinobi.loaders._modelgen.narrow_choices` performs is covered. `alias`
    carries the `nom_de_guerre` sanitisation and `json_schema_extra` the
    `abbreviation` short flags, both of which a dialect could plausibly drop.
    """
    return {
        name: (
            f.annotation,
            f.default,
            f.is_required(),
            f.alias,
            f.description,
            f.json_schema_extra,
        )
        for name, f in model.model_fields.items()
    }


def _diff_models(label: str, a: type[BaseModel], b: type[BaseModel]) -> list[str]:
    sa, sb = model_shape(a), model_shape(b)
    out: list[str] = []
    for missing in sorted(set(sa) - set(sb)):
        out.append(f"{label}: field {missing!r} present in A, absent in B")
    for extra in sorted(set(sb) - set(sa)):
        out.append(f"{label}: field {extra!r} present in B, absent in A")
    for name in sorted(set(sa) & set(sb)):
        if sa[name] != sb[name]:
            for attr, va, vb in zip(
                ("annotation", "default", "required", "alias", "description", "json_schema_extra"),
                sa[name],
                sb[name],
                strict=True,
            ):
                if va != vb:
                    out.append(f"{label}: field {name!r} {attr}: A={va!r} B={vb!r}")
    return out


def cab_differences(a: Any, b: Any) -> list[str]:
    """Every structural difference between two `Cab`s. Empty iff equivalent.

    Compares the plain-data fields via `model_dump` and the two generated
    models via `model_shape`.
    """
    out: list[str] = []
    da = a.model_dump(exclude=set(_MODEL_FIELDS))
    db = b.model_dump(exclude=set(_MODEL_FIELDS))
    for key in sorted(set(da) | set(db)):
        if da.get(key) != db.get(key):
            out.append(f"{key}: A={da.get(key)!r} B={db.get(key)!r}")
    for field in _MODEL_FIELDS:
        out.extend(_diff_models(field, getattr(a, field), getattr(b, field)))
    return out


def cabs_equivalent(a: Any, b: Any) -> bool:
    """`cab_differences(a, b) == []`, for callers that only want the verdict."""
    return not cab_differences(a, b)
