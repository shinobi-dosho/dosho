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

# A field spec as a tool's own `--help`/docs give it to you -- `(dtype,
# required, default)` -- plus an optional 4th element carrying the field's
# `ParamMeta` (`nom_de_guerre`, `positional`, `repeat_as_tokens`,
# `implicit`, `info`, ...) when the CLI needs more than the bare triple.
FieldSpec = tuple[str, bool, Any] | tuple[str, bool, Any, ParamMeta]


def _resolve(specs: dict[str, FieldSpec]) -> tuple[dict[str, tuple[str, bool, Any]], dict[str, ParamMeta]]:
    """Split raw `{name: spec}` into build_model-ready fields and field_meta.

    Sanitises each raw name to a valid pydantic field name; a raw name that
    changes under sanitisation auto-derives a `nom_de_guerre`, which an
    explicit `ParamMeta` 4th element overrides only if it sets its own.
    """
    resolved_fields: dict[str, tuple[str, bool, Any]] = {}
    resolved_meta: dict[str, ParamMeta] = {}
    seen: dict[str, str] = {}
    for raw_name, spec in specs.items():
        field = sanitize_unique(raw_name, seen)
        core, meta = (spec[:3], spec[3]) if len(spec) == 4 else (spec, None)
        resolved_fields[field] = core
        if field != raw_name:
            if meta is None:
                meta = ParamMeta(nom_de_guerre=raw_name)
            elif meta.nom_de_guerre is None:
                meta = meta.model_copy(update={"nom_de_guerre": raw_name})
        if meta is not None:
            resolved_meta[field] = meta
    return resolved_fields, resolved_meta


def define_cab(
    name: str,
    command: str,
    image: str,
    fields: dict[str, FieldSpec],
    *,
    outputs: dict[str, FieldSpec] | None = None,
    policies: Policies | None = None,
    input_patterns: list[ParamPattern] | None = None,
    output_patterns: list[ParamPattern] | None = None,
    flavour: str = "binary",
    wranglers: dict[str, list[str]] | None = None,
    info: str | None = None,
    sandbox: bool | None = None,
    harvest: list[str] | None = None,
) -> Cab:
    """Build a `Cab` from a flat `{raw_param_name: (dtype, required,
    default)}` dict -- the shape a tool's own `--help`/docs naturally give
    you (e.g. `"data-ms": ("MS", True, None)`). Hyphenated/dotted raw
    names are sanitised to valid pydantic field names, with the original
    kept as a `nom_de_guerre` so the built cab's `build_argv` still emits
    the tool's real flag.

    A field whose CLI needs more than the bare triple carries its
    `ParamMeta` as the spec's optional 4th element, right next to the raw
    name it belongs to -- e.g. `"ms": ("List[MS]", True, None,
    ParamMeta(positional=True, repeat_as_tokens=True))`, or an output's
    `implicit` path template. An explicit meta that doesn't set its own
    `nom_de_guerre` keeps the auto-derived one rather than losing it.

    `sandbox`/`harvest` pass straight through to the `Cab` (see
    stimela-ninja's `shinobi.sandbox` and the fields on `Scope`): `harvest`
    declares the keep-globs for dynamically-named output *files* a
    sandboxed run must rescue (e.g. wsclean's `"{prefix}-*"` family) --
    note this is a different thing from `output_patterns`, which match
    dynamic output parameter *names* for wiring validation only.
    """
    input_fields, input_meta = _resolve(fields)
    output_fields, output_meta = _resolve(outputs or {})

    return Cab(
        name=name,
        command=command,
        image=image,
        info=info,
        flavour=flavour,
        inputs_model=build_model(
            f"{name}_Inputs", input_fields, allow_extra=bool(input_patterns)
        ),
        outputs_model=build_model(f"{name}_Outputs", output_fields),
        field_meta={**input_meta, **output_meta},
        policies=policies or Policies(),
        input_patterns=input_patterns or [],
        output_patterns=output_patterns or [],
        wranglers=wranglers or {},
        sandbox=sandbox,
        harvest=harvest or [],
    )
