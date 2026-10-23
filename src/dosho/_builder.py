"""Python cab authoring over the same static compiler used by documents.

Importing this module needs only Dosho's validation extra. The execution
adapter is imported lazily when a runnable cab is requested.
"""

from __future__ import annotations

from typing import Any

from .validation.schema import ParamMeta, ParamPattern, Policies

FieldSpec = tuple[str, bool, Any] | tuple[str, bool, Any, ParamMeta]
EXPERIMENTAL_CABS: dict[str, str] = {}


def _parameter(spec: FieldSpec) -> dict[str, Any]:
    dtype, required, default = spec[:3]
    value = {"dtype": dtype, "required": required}
    if default is not None:
        value["default"] = default
    if len(spec) == 4:
        meta = spec[3]
        data = meta.model_dump(mode="python", exclude_defaults=True)
        policy = {}
        for key in ("positional", "positional_head"):
            if data.pop(key, False):
                policy[key] = True
        if data.pop("repeat_as_tokens", False):
            policy["repeat"] = "list"
        if policy:
            data["policies"] = policy
        value.update(data)
    return value


def define_cab(
    name: str,
    command: str,
    image: str,
    fields: dict[str, FieldSpec],
    *,
    outputs=None,
    input_mutability=None,
    policies: Policies | None = None,
    input_patterns: list[ParamPattern] | None = None,
    output_patterns: list[ParamPattern] | None = None,
    flavour="binary",
    wranglers=None,
    info=None,
    sandbox=None,
    harvest=None,
    scratch=None,
    experimental=None,
):
    """Build a runnable cab from raw names and (dtype, required, default[, meta]).

    Raw names are sanitized by the shared compiler. Metadata, nullability,
    choices, and write declarations have exactly the document semantics.
    Install stimela-ninja for this lazy execution bridge; dosho[run] is retired.
    """
    from .registry import _build_document

    _build_document()  # Verify the execution adapter generation before constructing.
    from shinobi.loaders.yaml_cab import _compile

    from .validation.compiled import CabSpec

    unknown = sorted(set(input_mutability or {}) - set(fields))
    if unknown:
        raise ValueError(
            f"input_mutability names {unknown}, which are not input fields of this cab"
        )
    inputs = {key: _parameter(value) for key, value in fields.items()}
    for key, mutability in (input_mutability or {}).items():
        if mutability not in {"mutable", "immutable"}:
            raise ValueError(f"invalid input mutability for {key!r}: {mutability!r}")
        inputs[key]["mutable"] = mutability == "mutable"
    if experimental:
        EXPERIMENTAL_CABS[name] = experimental
        info = f"EXPERIMENTAL: {info or experimental}"

    def patterns(values):
        result = []
        for pattern in values or []:
            data = pattern.model_dump(mode="python")
            for segment, original in zip(data["segments"], pattern.segments, strict=True):
                if original.attrs is not None:
                    segment["attrs"] = {
                        key: _parameter((meta.dtype or "str", False, None, meta))
                        for key, meta in original.attrs.items()
                    }
            result.append(data)
        return result

    document = dict(  # noqa: C408 -- named document fields mirror the cab API
        command=command,
        image=image,
        flavour=flavour,
        info=info,
        inputs=inputs,
        outputs={key: _parameter(value) for key, value in (outputs or {}).items()},
        policies=(policies or Policies()).model_dump(mode="python"),
        input_patterns=patterns(input_patterns),
        output_patterns=patterns(output_patterns),
        management={"wranglers": wranglers or {}},
        sandbox=sandbox,
        harvest=harvest or [],
        scratch=scratch or [],
    )
    # Python authors are trusted source, as are their typed defaults and
    # implicit values. Do not send those through the untrusted JSON parser.
    # Compilation still uses the identical parameter and metadata algorithms.
    return _compile(CabSpec.model_construct(name=name, document=document, images={}))
