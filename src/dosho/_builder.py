"""Thin builder for authoring a native `dosho` cab: wraps `shinobi.Cab` +
`shinobi.loaders.build_model` + `shinobi.loaders.sanitize_unique` to remove
the boilerplate of hand-transcribing a real tool's parameter list, without
inventing any new schema surface.

Generalises the `cab_from_defaults` helper first proven in
stimela-ninja's `examples/ninja_selfcal.py`. Deliberately not a
signature-introspecting decorator (`@cab`) -- that shape was tried once in
shinobi itself (`ba2bd48`) and removed (`605b6f8`): it can't express
`nom_de_guerre` (hyphenated CLI names aren't valid Python parameter
names), `input_patterns`, `Policies`, `positional`, or `implicit`. Raw
`Cab(...)` stays fully available for anything this helper doesn't cover --
it's sugar, not a wall.
"""

from __future__ import annotations

from typing import Any

from shinobi import Cab
from shinobi.loaders import build_model, sanitize_unique
from shinobi.steps.schema import ParamMeta, ParamPattern, Policies


def define_cab(
    name: str,
    command: str,
    image: str,
    fields: dict[str, tuple[str, bool, Any]],
    *,
    outputs: dict[str, tuple[str, bool, Any]] | None = None,
    field_meta: dict[str, ParamMeta] | None = None,
    policies: Policies | None = None,
    input_patterns: list[ParamPattern] | None = None,
    output_patterns: list[ParamPattern] | None = None,
    flavour: str = "binary",
    wranglers: dict[str, list[str]] | None = None,
    info: str | None = None,
) -> Cab:
    """Build a `Cab` from a flat `{raw_param_name: (dtype, required,
    default)}` dict -- the shape a tool's own `--help`/docs naturally give
    you (e.g. `"data-ms": ("MS", True, None)`). Hyphenated/dotted raw
    names are sanitised to valid pydantic field names, with the original
    kept as a `nom_de_guerre` so the built cab's `build_argv` still emits
    the tool's real flag.

    `field_meta` entries the caller passes explicitly (keyed by the
    *sanitised* field name -- e.g. an output field's `implicit` template,
    or a `positional`/`repeat_as_tokens` override) are merged in on top of
    the auto-derived `nom_de_guerre`s; an explicit entry that doesn't set
    its own `nom_de_guerre` keeps the auto-derived one rather than losing
    it.
    """
    resolved_fields: dict[str, tuple[str, bool, Any]] = {}
    resolved_meta: dict[str, ParamMeta] = {}
    seen: dict[str, str] = {}
    for raw_name, spec in fields.items():
        field = sanitize_unique(raw_name, seen)
        resolved_fields[field] = spec
        if field != raw_name:
            resolved_meta[field] = ParamMeta(nom_de_guerre=raw_name)

    for field, meta in (field_meta or {}).items():
        auto = resolved_meta.get(field)
        if auto is not None and meta.nom_de_guerre is None:
            meta = meta.model_copy(update={"nom_de_guerre": auto.nom_de_guerre})
        resolved_meta[field] = meta

    return Cab(
        name=name,
        command=command,
        image=image,
        info=info,
        flavour=flavour,
        inputs_model=build_model(
            f"{name}_Inputs", resolved_fields, allow_extra=bool(input_patterns)
        ),
        outputs_model=build_model(f"{name}_Outputs", outputs or {}),
        field_meta=resolved_meta,
        policies=policies or Policies(),
        input_patterns=input_patterns or [],
        output_patterns=output_patterns or [],
        wranglers=wranglers or {},
    )
