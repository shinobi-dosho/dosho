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
from shinobi.steps.schema import Mutability, ParamMeta, ParamPattern, Policies

# A field spec as a tool's own `--help`/docs give it to you -- `(dtype,
# required, default)` -- plus an optional 4th element carrying the field's
# `ParamMeta` (`nom_de_guerre`, `positional`, `repeat_as_tokens`,
# `implicit`, `info`, `choices`, `abbreviation`, ...) when the CLI needs more
# than the bare triple. `choices`/`abbreviation` are threaded through to
# `build_model` (real `Literal` validation / a `-<abbrev>` CLI short flag),
# not just stored on `field_meta` -- see `define_cab`.
FieldSpec = tuple[str, bool, Any] | tuple[str, bool, Any, ParamMeta]


def _resolve(
    specs: dict[str, FieldSpec],
) -> tuple[dict[str, tuple[str, bool, Any]], dict[str, ParamMeta], dict[str, str]]:
    """Split raw `{name: spec}` into build_model-ready fields and field_meta,
    plus the raw-name -> field-name map the sanitisation produced.

    Sanitises each raw name to a valid pydantic field name; a raw name that
    changes under sanitisation auto-derives a `nom_de_guerre`, which an
    explicit `ParamMeta` 4th element overrides only if it sets its own. The
    third return value lets `define_cab` accept other per-field keyword
    arguments (`input_mutability`) keyed by the *same* raw names the caller
    already used in `fields`, rather than by the sanitised names only this
    function knows.
    """
    resolved_fields: dict[str, tuple[str, bool, Any]] = {}
    resolved_meta: dict[str, ParamMeta] = {}
    raw_to_field: dict[str, str] = {}
    seen: dict[str, str] = {}
    for raw_name, spec in specs.items():
        field = sanitize_unique(raw_name, seen)
        raw_to_field[raw_name] = field
        core, meta = (spec[:3], spec[3]) if len(spec) == 4 else (spec, None)
        resolved_fields[field] = core
        if field != raw_name:
            if meta is None:
                meta = ParamMeta(nom_de_guerre=raw_name)
            elif meta.nom_de_guerre is None:
                meta = meta.model_copy(update={"nom_de_guerre": raw_name})
        if meta is not None:
            resolved_meta[field] = meta
    return resolved_fields, resolved_meta, raw_to_field


def _choices(metas: dict[str, ParamMeta]) -> dict[str, list[Any]]:
    """Per-field allowed-value lists for `build_model(choices=...)`, so a
    `ParamMeta.choices` narrows the model's field to `Literal[*choices]`."""
    return {field: meta.choices for field, meta in metas.items() if meta.choices}


def _mutability(
    declared: dict[str, Mutability] | None,
    raw_to_field: dict[str, str],
) -> dict[str, Mutability]:
    """Re-key a caller's `{raw_input_name: Mutability}` onto the sanitised
    field names `Scope.input_mutability` is looked up by.

    A raw name with no matching input field raises rather than being
    dropped: an unnoticed mutability declaration is exactly the silent
    failure this argument exists to fix (shinobi defaults an undeclared
    field to `IMMUTABLE`, so a typo'd key would leave the cab keying its
    cache on content it overwrites, with nothing to notice).
    """
    if not declared:
        return {}
    unknown = sorted(set(declared) - set(raw_to_field))
    if unknown:
        raise ValueError(
            f"input_mutability names {unknown}, which are not input fields "
            f"of this cab -- key it by the same raw names used in `fields` "
            f"(e.g. 'input_ms.path', not 'input_ms_path')"
        )
    return {raw_to_field[raw]: value for raw, value in declared.items()}


def _extras(metas: dict[str, ParamMeta]) -> dict[str, dict[str, Any]]:
    """Per-field `json_schema_extra` dicts for `build_model(extras=...)`,
    carrying a `ParamMeta.abbreviation` onto the field so `ninja run` can
    emit a `-<abbrev>` short flag (mirrors `cultcargo._build_cabdef`)."""
    return {
        field: {"abbreviation": meta.abbreviation}
        for field, meta in metas.items()
        if meta.abbreviation
    }


# Registered name -> why the cab is experimental. Populated by `define_cab`'s
# `experimental=` argument and read by `dosho.registry.get`, which warns, and by
# the docs. Some upstreams are not dependable enough for dosho to keep patching
# around: DDFacet and killMS publish `.cfg` schemas with no usable `#type:`
# tags, mangle their own output names internally (killMS's `reformat(MSName)`),
# and name output families by letter code. Rather than accumulate per-gap fixes
# for tools dosho does not control, such a cab is marked here and its
# unsupported modes are stated outright -- to the reader, and at run time.
EXPERIMENTAL_CABS: dict[str, str] = {}


def define_cab(
    name: str,
    command: str,
    image: str,
    fields: dict[str, FieldSpec],
    *,
    outputs: dict[str, FieldSpec] | None = None,
    input_mutability: dict[str, Mutability] | None = None,
    policies: Policies | None = None,
    input_patterns: list[ParamPattern] | None = None,
    output_patterns: list[ParamPattern] | None = None,
    flavour: str = "binary",
    wranglers: dict[str, list[str]] | None = None,
    info: str | None = None,
    sandbox: bool | None = None,
    harvest: list[str] | None = None,
    experimental: str | None = None,
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

    A `ParamMeta`'s `choices`/`abbreviation` are honoured, not just stored:
    `choices` narrows the built model's field to `typing.Literal[*choices]`
    (an out-of-set value fails pydantic validation, same as shinobi's own
    scabha-dialect loaders -- see `narrow_choices`), and `abbreviation` is
    carried onto the field's `json_schema_extra` so `ninja run` can emit a
    `-<abbrev>` short flag. Both are threaded into `build_model` below,
    mirroring `shinobi.loaders.cultcargo._build_cabdef`.

    `input_mutability` declares which path inputs the tool rewrites *in
    place*, keyed by the same raw names used in `fields` (e.g.
    `{"input_ms.path": Mutability.MUTABLE}`) and re-keyed here onto the
    sanitised field names `Scope.mutability_of` looks up. This is the
    second of the two spellings `shinobi.steps.schema.mutated_path_fields`
    recognises, and the only one available to a cab whose output field is
    *not* named after the input it echoes: shinobi's other spelling is
    `input_paths & output_paths`, a plain name intersection, so an output
    declared as `"ms": ParamMeta(implicit="{input_ms_path}")` looks like a
    brand-new artifact no matter that it resolves to the very path the
    input named. Undeclared, such a cab keys its cache on the content of
    the MS it is about to overwrite (never a hit on a re-run) and the
    Tier 1 snapshotter sees nothing to protect. Declaring it costs the
    field its content hash in the cache key -- "unchanged" then means
    params unchanged plus the declared output still present -- which is
    the same trade the same-named-output spelling already makes.

    `sandbox`/`harvest` pass straight through to the `Cab` (see
    stimela-ninja's `shinobi.sandbox` and the fields on `Scope`): `harvest`
    declares the keep-globs for dynamically-named output *files* a
    sandboxed run must rescue (e.g. wsclean's `"{prefix}-*"` family) --
    note this is a different thing from `output_patterns`, which match
    dynamic output parameter *names* for wiring validation only.

    `experimental` marks a cab dosho supports on a best-effort basis and
    says why, in one sentence naming the modes that are *not* covered. It
    prefixes the cab's `info` with `EXPERIMENTAL:` -- so `ninja cabs
    list/show` and the generated catalog carry it without any extra
    plumbing -- and registers the reason in `EXPERIMENTAL_CABS`, which
    `dosho.registry.get` warns from. Use it instead of a patch when the gap
    belongs to an upstream dosho cannot rely on; use a real declaration for
    everything else.
    """
    input_fields, input_meta, input_names = _resolve(fields)
    output_fields, output_meta, _ = _resolve(outputs or {})

    if experimental:
        EXPERIMENTAL_CABS[name] = experimental
        info = f"EXPERIMENTAL: {info}" if info else f"EXPERIMENTAL: {experimental}"

    return Cab(
        name=name,
        command=command,
        image=image,
        info=info,
        flavour=flavour,
        inputs_model=build_model(
            f"{name}_Inputs",
            input_fields,
            allow_extra=bool(input_patterns),
            choices=_choices(input_meta),
            extras=_extras(input_meta),
        ),
        outputs_model=build_model(
            f"{name}_Outputs",
            output_fields,
            choices=_choices(output_meta),
            extras=_extras(output_meta),
        ),
        field_meta={**input_meta, **output_meta},
        input_mutability=_mutability(input_mutability, input_names),
        policies=policies or Policies(),
        input_patterns=input_patterns or [],
        output_patterns=output_patterns or [],
        wranglers=wranglers or {},
        sandbox=sandbox,
        harvest=harvest or [],
    )
