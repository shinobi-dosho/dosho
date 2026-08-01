"""Serialise dosho's Python cabs to yaml_cab documents.

Hybrid by necessity, per `docs/design_data_registry.md` §4.6: the built `Cab`
is faithful for everything except the two things it forgets -- dtype strings
and the image key -- which come from source via `cab_source`.

The `(dtype, required, default)` triple is taken from source too, even though
two thirds of it survives on the model. It is the exact triple `build_model`
consumes, so emitting it verbatim makes that half of every field faithful by
construction rather than by reconstruction.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shinobi.loaders import sanitize_unique
from shinobi.steps.schema import Cab, Policies

from tools.cab_source import CabSource, read_sources

_DEFAULT_POLICIES = Policies().model_dump()


def _field_names(raw_names: list[str]) -> dict[str, str]:
    """raw param name -> built field name, replaying the loader's own
    sanitisation in declaration order so collisions resolve identically.
    Inputs and outputs each get a fresh `seen`, matching both
    `dosho._builder._resolve` and `yaml_cab._collect`.
    """
    seen: dict[str, str] = {}
    return {raw: sanitize_unique(raw, seen) for raw in raw_names}


def _meta_spec(
    meta: Any, *, auto_nom: str | None = None, with_dtype: bool = False
) -> dict[str, Any]:
    """A `ParamMeta` as the dialect's param-spec keys.

    `with_dtype` mirrors the loader's own asymmetry: a declared field's dtype
    lives in its model annotation and must not be repeated here, while a
    pattern attr has no model field and carries dtype on the meta itself.
    """
    out: dict[str, Any] = {}
    # The loader derives nom_de_guerre from the key when sanitising changed it,
    # so only an explicit one that differs needs writing down.
    if meta.nom_de_guerre and meta.nom_de_guerre != auto_nom:
        out["nom_de_guerre"] = meta.nom_de_guerre
    if meta.info is not None:
        out["info"] = meta.info
    if meta.implicit is not None:
        out["implicit"] = meta.implicit
    if meta.choices:
        out["choices"] = meta.choices
    if meta.abbreviation:
        out["abbreviation"] = meta.abbreviation
    if meta.write_path:
        out["write_path"] = True
    if with_dtype and meta.dtype is not None:
        out["dtype"] = meta.dtype

    policies: dict[str, Any] = {}
    if meta.positional:
        policies["positional"] = True
    if meta.positional_head:
        policies["positional_head"] = True
    if meta.repeat_as_tokens:
        policies["repeat"] = "list"
    if policies:
        out["policies"] = policies
    return out


def _patterns(patterns: list) -> list[dict[str, Any]]:
    """`ParamPattern`s as documents. An attr always gets a mapping, even an
    empty one -- the attr *names* are what the pattern matches on, so an
    omitted entry is a deleted attr, not a defaulted one.
    """
    out = []
    for pattern in patterns:
        entry: dict[str, Any] = {}
        if pattern.separator != ".":
            entry["separator"] = pattern.separator
        entry["segments"] = [
            {"attrs": {name: _meta_spec(m, with_dtype=True) for name, m in seg.attrs.items()}}
            if seg.attrs is not None
            else {"regex": seg.regex}
            for seg in pattern.segments
        ]
        out.append(entry)
    return out


def _param(raw: str, field: str, spec: tuple, cab: Cab, *, is_input: bool) -> dict[str, Any]:
    dtype, required, default = spec
    out: dict[str, Any] = {"dtype": dtype}
    if required:
        out["required"] = True
    if default is not None:
        out["default"] = default

    meta = cab.field_meta.get(field)
    if meta is not None:
        # `info` is emitted on `is not None` rather than truthiness: two cabs
        # carry an empty-string info, and dropping it turns `""` into `None` on
        # the way back -- a difference the comparator sees, and rightly.
        out.update(_meta_spec(meta, auto_nom=raw if raw != field else None))

    if (
        is_input
        and field in cab.input_mutability
        and cab.input_mutability[field].value == "mutable"
    ):
        out["mutable"] = True
    return out


def document_for(cab: Cab, src: CabSource) -> dict[str, Any]:
    """One cab as a yaml_cab document body (the value under its name)."""
    body: dict[str, Any] = {"command": cab.command}
    if src.image_key:
        # The manifest key, not the resolved reference, so a deployment's
        # $DOSHO_IMAGES override still applies at load time (§4.5).
        body["image"] = src.image_key
    if cab.info:
        body["info"] = cab.info
    if cab.flavour != "binary":
        body["flavour"] = cab.flavour

    policies = {k: v for k, v in cab.policies.model_dump().items() if v != _DEFAULT_POLICIES.get(k)}
    if policies:
        body["policies"] = policies
    if cab.harvest:
        body["harvest"] = list(cab.harvest)
    if cab.scratch:
        body["scratch"] = list(cab.scratch)
    if cab.sandbox is not None:
        body["sandbox"] = cab.sandbox
    if cab.wranglers:
        body["management"] = {"wranglers": cab.wranglers}
    if cab.input_patterns:
        body["input_patterns"] = _patterns(cab.input_patterns)
    if cab.output_patterns:
        body["output_patterns"] = _patterns(cab.output_patterns)

    for section, specs, is_input in (("inputs", src.inputs, True), ("outputs", src.outputs, False)):
        if not specs:
            continue
        names = _field_names(list(specs))
        body[section] = {
            raw: _param(raw, names[raw], spec, cab, is_input=is_input)
            for raw, spec in specs.items()
        }
    return body


def documents() -> dict[str, dict[str, Any]]:
    """`{cab name: document body}` for every binary cab dosho defines."""
    import dosho.cabs as C

    sources = read_sources()
    built = {c.name: c for n in C.__all__ if isinstance(c := getattr(C, n), Cab)}
    missing = set(sources) - set(built)
    if missing:
        raise ValueError(f"source defines cabs that are not exported: {sorted(missing)}")
    return {name: document_for(built[name], src) for name, src in sources.items()}
