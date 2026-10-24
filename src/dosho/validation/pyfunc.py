"""Framework-independent schemas for trusted, annotated Python functions."""

from __future__ import annotations

import inspect
import types
from collections.abc import Callable, Sequence
from typing import (
    Annotated,
    Any,
    Literal,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

from pydantic import BaseModel, Field, create_model
from pydantic.fields import FieldInfo

from dosho._pystep import (
    PystepDefinition as PystepDefinition,
    get_pystep_definition as get_pystep_definition,
    pystep as pystep,
)

from .modelgen import narrow_choices
from .schema import ParamMeta

_UNSUPPORTED_KINDS = (
    inspect.Parameter.VAR_POSITIONAL,
    inspect.Parameter.VAR_KEYWORD,
    inspect.Parameter.POSITIONAL_ONLY,
)


def _pascal(func_name: str) -> str:
    return "".join(word.capitalize() for word in func_name.split("_") if word)


def _param_meta_from_extra(extra: Any, meta_class=ParamMeta) -> ParamMeta | None:
    if not isinstance(extra, dict):
        return None
    value = extra.get("param_meta")
    if isinstance(value, ParamMeta):
        return value
    if isinstance(value, dict):
        return meta_class.model_validate(value)
    if extra.get("choices"):
        return meta_class(choices=extra["choices"])
    return None


def _param_meta_from_annotation(annotation: Any) -> tuple[Any, ParamMeta | None]:
    """Remove ``ParamMeta`` from an ``Annotated`` type.

    ``ParamMeta`` is a Pydantic model, not Pydantic's own validation metadata,
    so passing it through to ``create_model`` makes Pydantic validate a string
    as a ``ParamMeta`` instance. The metadata is therefore extracted before
    model creation and choices are applied as a real ``Literal`` constraint.
    Other ``Annotated`` metadata is retained.

    Only the outermost ``Annotated`` layers are stripped; see
    ``_nested_param_meta`` for why anything deeper is reported rather than
    unwrapped.
    """
    metadata: list[Any] = []
    while get_origin(annotation) is Annotated:
        args = get_args(annotation)
        annotation = args[0]
        metadata.extend(args[1:])

    param_meta = next((value for value in metadata if isinstance(value, ParamMeta)), None)
    remaining = [value for value in metadata if not isinstance(value, ParamMeta)]
    if remaining:
        annotation = Annotated[annotation, *remaining]
    return annotation, param_meta


def _nested_param_meta(annotation: Any) -> bool:
    """Whether `annotation` still carries a `ParamMeta` below its top level.

    `get_type_hints(..., include_extras=True)` keeps every `Annotated`
    layer, but the outermost one is the only place this module can lift
    metadata *off* the annotation: a `ParamMeta` inside
    `Optional[Annotated[str, ParamMeta(...)]]` or
    `list[Annotated[str, ParamMeta(...)]]` would otherwise survive into
    `create_model`, and pydantic would then validate the parameter's value
    as a `ParamMeta` instance. Rebuilding an arbitrary generic without that
    member is not worth the fragility when
    `Annotated[str | None, ParamMeta(...)]` says the same thing, so this
    reports the case and the caller names it at decoration time.
    """
    pending = [annotation]
    while pending:
        current = pending.pop()
        if get_origin(current) is Annotated:
            args = get_args(current)
            if any(isinstance(value, ParamMeta) for value in args[1:]):
                return True
            pending.append(args[0])
            continue
        pending.extend(get_args(current))
    return False


class _UnsupportedChoices(Exception):
    """`_narrow_choices` was handed an annotation no `Literal` can narrow."""


_CHOICE_SCALARS = (str, int, float, bool)
_CHOICE_SEQUENCES = (list, set, frozenset)


def _narrow_choices(annotation: Any, choices: list[Any] | None) -> Any:
    """Apply `choices` to the annotation's scalar leaf, leaving the shape
    around that leaf intact.

    `Annotated[list[str], ParamMeta(choices=[...])]` means "every element is
    one of these", so the narrowing has to land on the *element* type:
    replacing the whole annotation with `Literal[...]` would reject the list
    at validation and also lose the `multiple=True` that
    `clickutil.build_options` derives from `is_list`. The same holds for the
    `| None` arm of an optional field. Building the `Literal` itself is
    delegated to `loaders._modelgen.narrow_choices` -- shinobi's one
    enum-like schema mechanism -- so the two callers cannot drift.

    Raises:
        _UnsupportedChoices: the leaf is not a scalar a `Literal` can stand
            in for. A `Path` is the case that matters: narrowing it away
            would leave `path_fields` (and so the backends' bind-mounting
            and `click.Path`) unable to see that the field is a path at all,
            which is a silent change of behaviour rather than a constraint.
    """
    if not choices:
        return annotation
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin is Annotated:
        return Annotated[_narrow_choices(args[0], choices), *args[1:]]
    if origin is Union or origin is types.UnionType:
        arms = [arg for arg in args if arg is not type(None)]
        if len(arms) == 1:
            return _narrow_choices(arms[0], choices) | None
        raise _UnsupportedChoices
    if origin in _CHOICE_SEQUENCES and len(args) == 1:
        return origin[_narrow_choices(args[0], choices)]
    if origin is tuple and len(args) == 2 and args[1] is Ellipsis:
        return tuple[_narrow_choices(args[0], choices), ...]
    if origin is Literal or annotation in _CHOICE_SCALARS:
        return narrow_choices(annotation, choices)
    raise _UnsupportedChoices


def _field_default_with_meta(default: Any, meta: ParamMeta | None) -> Any:
    """Carry extracted metadata on the generated field for model consumers.

    `ParamMeta.info` is copied onto the field's `description`, which is the
    channel every consumer already reads (`clickutil.build_options` turns it
    into the option's `--help` text), so the same declaration documents a
    pystep's parameter and a cab's.

    A `FieldInfo` default is *merged*, never written into: it lives in the
    decorated function's `__defaults__` and a module-level `Field(...)` spec
    may be shared by several functions, so writing into it would leak this
    parameter's metadata onto theirs (and permanently alter the function's
    own signature default). `merge_field_infos` returns a fresh `FieldInfo`
    and leaves both inputs alone.

    Merging is also the only spelling that survives model construction.
    Setting `json_schema_extra` as an attribute on a copy looks equivalent
    but is not: `create_model` rebuilds every field through
    `FieldInfo.from_annotated_attribute`, which reads a `FieldInfo` default
    back out of its `_attributes_set` -- the constructor arguments -- so an
    attribute assigned after construction is silently dropped and the whole
    `ParamMeta` never reaches `clickutil._field_meta`. Choices would still
    appear (`_narrow_choices` rewrites the annotation), but `abbreviation`
    and a `ParamMeta`-supplied `info` would vanish for exactly the
    parameters that spell both halves -- `Annotated[T, ParamMeta(...)] =
    Field(...)`.
    """
    if meta is None:
        return default
    if isinstance(default, FieldInfo):
        overlay: dict[str, Any] = {"json_schema_extra": {"param_meta": meta}}
        if meta.info and not default.description:
            overlay["description"] = meta.info
        # pydantic merges the two `json_schema_extra` dicts, so a cab-style
        # flat key already on the field (`{"abbreviation": "as"}`) is kept
        # alongside the `param_meta` this adds.
        return FieldInfo.merge_field_infos(default, Field(**overlay))
    return Field(default, description=meta.info, json_schema_extra={"param_meta": meta})


def _inputs_model_from_signature(
    func: Callable, write_paths: Sequence[str] = (), *, meta_class=ParamMeta
) -> tuple[type[BaseModel], bool, dict[str, ParamMeta]]:
    """Derive the inputs model from `func`'s signature.

    Returns `(inputs_model, wants_ctx, field_meta)`. If the first parameter is
    named `ctx` it is treated as the execution-context injection point
    (matching `@shinobi.step`'s convention) rather than an input field: it is
    skipped when building the model and needs no type hint. The adapter then
    calls `func(ctx, **inputs)`.

    `write_paths` (the decorator's own argument) is folded into each named
    parameter's `ParamMeta` *here*, before the model is built, so the copy
    embedded in a field's `json_schema_extra` and the one in
    `Scope.field_meta` are the same object rather than two spellings that
    can disagree. Names it holds that are not parameters are left for the
    caller to report against the finished model.
    """
    write_path_names = set(write_paths)
    sig = inspect.signature(func)
    params = list(sig.parameters.items())
    wants_ctx = bool(params) and params[0][0] == "ctx"
    if wants_ctx:
        params = params[1:]
    hints = get_type_hints(func, include_extras=True)
    fields: dict[str, tuple[Any, Any]] = {}
    field_meta: dict[str, ParamMeta] = {}
    for pname, param in params:
        if param.kind in _UNSUPPORTED_KINDS:
            raise TypeError(
                f"pystep {func.__name__!r}: parameter {pname!r} is {param.kind.description} -- only plain positional-or-keyword parameters (with a real type hint) are supported"
            )
        if pname not in hints:
            raise TypeError(
                f"pystep {func.__name__!r}: parameter {pname!r} has no type hint -- every parameter needs one so its inputs_model can be derived from the signature"
            )
        annotation, annotation_meta = _param_meta_from_annotation(hints[pname])
        if _nested_param_meta(annotation):
            raise TypeError(
                f"pystep {func.__name__!r}: parameter {pname!r} nests ParamMeta inside its annotation "
                f"({hints[pname]!r}) -- ParamMeta has to annotate the parameter's whole type "
                f"(Annotated[str | None, ParamMeta(...)], Annotated[list[str], ParamMeta(...)]), since anything "
                f"deeper cannot be lifted off before the model is built"
            )
        default_meta = (
            _param_meta_from_extra(param.default.json_schema_extra, meta_class)
            if isinstance(param.default, FieldInfo)
            else None
        )
        meta = annotation_meta or default_meta
        if meta is not None and not isinstance(meta, meta_class):
            meta = meta_class.model_validate(meta.model_dump(mode="python"))
        if pname in write_path_names:
            meta = (meta or meta_class()).model_copy(update={"write_path": True})
        try:
            annotation = _narrow_choices(annotation, meta.choices if meta else None)
        except _UnsupportedChoices:
            raise TypeError(
                f"pystep {func.__name__!r}: parameter {pname!r} declares ParamMeta choices on {hints[pname]!r} -- "
                f"choices narrow a str/int/float/bool leaf, optionally inside Optional[...] or a "
                f"list/set/tuple[...] around it, so that the field keeps the shape it declares"
            ) from None
        required = param.default is inspect.Parameter.empty
        default = ... if required else param.default
        fields[pname] = (annotation, _field_default_with_meta(default, meta))
        if meta is not None:
            field_meta[pname] = meta
    return create_model(f"{_pascal(func.__name__)}Inputs", **fields), wants_ctx, field_meta


def _outputs_model_from_return(func: Callable) -> tuple[type[BaseModel], bool]:
    hints = get_type_hints(func)
    ret = hints.get("return")
    if ret is None or ret is type(None):
        return create_model(f"{_pascal(func.__name__)}Outputs"), True
    if isinstance(ret, type) and issubclass(ret, BaseModel):
        return ret, False
    raise TypeError(
        f"pystep {func.__name__!r}: return type {ret!r} isn't a BaseModel "
        "subclass (or None) -- declare a BaseModel and return an instance "
        "of it, rather than a bare scalar/dict/list, so outputs stay "
        "explicitly named and typed"
    )


# Public schema access also used by execution adapters.
inputs_model_from_signature = _inputs_model_from_signature
outputs_model_from_return = _outputs_model_from_return
