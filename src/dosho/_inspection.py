"""Private schema readers shared by catalogue rendering and CLI inspection."""

from __future__ import annotations

import re
from types import UnionType
from typing import Annotated, Any, Literal, Union, get_args, get_origin

_SECTIONS = ("Args:", "Arguments:", "Returns:", "Yields:", "Raises:", "Parameters:")

# The dotted module path in front of a type name in `str(annotation)`:
# `list[pathlib._local.Path] | None` -> `list[Path] | None`. Stripping whole
# qualifiers rather than named prefixes is what makes this survive the standard
# library moving a class between modules -- 3.13 split `pathlib` into
# `pathlib._local`/`pathlib._abc`, so a hardcoded `"pathlib."` strip leaves
# `_local.Path` behind on 3.13+ and `Path` on 3.12, which is exactly the
# interpreter-dependent output the freshness gates diff against.
#
# The lookbehind keeps it out of quoted `Literal[...]` values: a member like
# `'ms.image.fits'` is preceded by a quote (or, mid-value, by a dot), so no
# part of it is mistaken for a module path.
_MODULE_QUALIFIER = re.compile(r"""(?<!['"\w.])(?:[A-Za-z_]\w*\.)+(?=[A-Za-z_])""")


def _schema_obj(definition: Any) -> Any:
    """Read neutral binary descriptions or trusted Python function schemas."""
    import inspect
    from types import SimpleNamespace

    from dosho.validation import CabSpec, describe_cab
    from dosho.validation.pyfunc import (
        get_pystep_definition,
        inputs_model_from_signature,
        outputs_model_from_return,
    )

    if isinstance(definition, CabSpec):
        return describe_cab(definition)
    declaration = get_pystep_definition(definition)
    if declaration is None:
        raise TypeError("catalogue entry is not a neutral definition")
    options = declaration.options
    inputs, _, _ = inputs_model_from_signature(definition, options.get("write_paths") or ())
    outputs, _ = outputs_model_from_return(definition)
    return SimpleNamespace(
        info=options.get("info") if options.get("info") is not None else inspect.getdoc(definition),
        image=options.get("image"),
        inputs_model=inputs,
        outputs_model=outputs,
    )


def _summary(info: str | None) -> str:
    """First prose paragraph of an info/docstring, stopping before a napoleon
    section (``Args:``/``Returns:``/...)."""
    if not info:
        return ""
    out: list[str] = []
    for line in info.strip().splitlines():
        s = line.strip()
        if s in _SECTIONS:
            break
        if not s:
            if out:
                break
            continue
        out.append(s)
    return " ".join(out)


# shinobi's strict dataset annotations, by their declared kind. A strict
# field's annotation is a plain `Path` with the declaration in its metadata, so
# without this the catalog would print `Path` for an `MSv2` and hide the one
# thing that distinguishes it from a path-only `MS`.
_DATASET_LABELS = {
    "measurement-set-v2": "MSv2",
    "casa-table": "CasaTab",
    "fits-image": "FITSImage",
    "fits-table": "FITSTable",
}


def _dataset_label(metadata: Any) -> str | None:
    """`"MSv2"`/`"CasaTab"` when `metadata` carries a strict dataset
    declaration, else None. Duck-typed on `.kind.value` rather than importing
    shinobi's `DatasetType`, so the extension still renders a catalog for a
    shinobi without one."""
    for item in metadata:
        kind = getattr(getattr(item, "kind", None), "value", None)
        if kind in _DATASET_LABELS:
            return _DATASET_LABELS[kind]
    return None


def _type_name(annotation: Any, metadata: tuple = ()) -> str:
    """Version-stable rendering of a field annotation. `__name__` is only
    trusted for plain classes: for parameterized/union annotations it
    varies by Python version (3.10 presents `list[X] | None` as
    `typing.Optional[list[X]]`, whose `__name__` is just "Optional"),
    and the catalog text must not depend on which interpreter generated
    it -- the committed copy is diffed against a fresh regeneration by
    the freshness gates (CI, pre-commit, pytest). `Optional[X]` is
    normalised to the `X | None` spelling 3.11+ produces natively.

    A strict dataset field renders as its shinobi name (`MSv2`), whether
    pydantic moved the declaration onto the field's `metadata` (a required
    field) or left it `Annotated` inside a union or generic container.
    """
    label = _dataset_label(metadata)
    if label:
        return label
    if annotation is type(None):
        return "None"
    if annotation is Ellipsis:
        return "..."
    # Pydantic's concrete generic model classes store origin/args separately
    # from typing aliases; their generated __name__ embeds Annotated internals.
    generic = getattr(annotation, "__pydantic_generic_metadata__", None)
    if generic and generic.get("origin") is not None and generic.get("args"):
        return f"{_type_name(generic['origin'])}[{', '.join(_type_name(arg) for arg in generic['args'])}]"
    origin = get_origin(annotation)
    if origin is Annotated:
        return _dataset_label(annotation.__metadata__) or _type_name(get_args(annotation)[0])
    args = get_args(annotation)
    if origin in (Union, UnionType):
        return " | ".join(_type_name(arg) for arg in args)
    # Generic arguments are types, except Literal choices, which are values
    # whose quoted spelling must survive module-qualifier stripping.
    if origin is not None and args and origin is not Literal:
        return f"{_type_name(origin)}[{', '.join(_type_name(arg) for arg in args)}]"
    # The __args__ guard matters on <=3.10, where a parameterized generic
    # like `list[Path]` still passes isinstance(..., type) (its __name__ is
    # a bare "list"); 3.11+ made those fail the isinstance check.
    if isinstance(annotation, type) and not getattr(annotation, "__args__", None):
        return annotation.__name__
    text = _MODULE_QUALIFIER.sub("", str(annotation))
    match = re.fullmatch(r"Optional\[(.*)\]", text)
    return f"{match.group(1)} | None" if match else text


def _literal_choices(annotation):
    origin = get_origin(annotation)
    if origin is Literal:
        return list(get_args(annotation))
    if origin in (list, set, frozenset):
        return _literal_choices(get_args(annotation)[0])
    if origin is Annotated:
        return _literal_choices(get_args(annotation)[0])
    if origin in (Union, UnionType):
        choices = []
        for arg in get_args(annotation):
            if arg is type(None):
                continue
            values = _literal_choices(arg)
            if values is None:
                return None
            choices.extend(value for value in values if value not in choices)
        return choices or None
    return None


def _fields(model):
    """Normalize descriptive parameters and Python model fields for readers."""
    fields = model if isinstance(model, dict) else getattr(model, "model_fields", {})
    for name, field in fields.items():
        binary = hasattr(field, "dtype")
        constraints = []
        if binary:
            choices = field.choices
            if field.nullable is not None:
                constraints.append(f"Nullable: {field.nullable}")
            for key, label in (
                ("min_length", "Minimum length"),
                ("max_length", "Maximum length"),
                ("string_pattern", "Pattern"),
            ):
                value = getattr(field.meta, key)
                if value is not None:
                    constraints.append(f"{label}: {value}")
        else:
            choices = _literal_choices(field.annotation)
            for item in field.metadata:
                choices = getattr(item, "choices", None) or choices
                for key, label in (
                    ("min_length", "Minimum length"),
                    ("max_length", "Maximum length"),
                    ("pattern", "Pattern"),
                    ("ge", "Minimum"),
                    ("le", "Maximum"),
                    ("gt", "Greater than"),
                    ("lt", "Less than"),
                ):
                    value = getattr(item, key, None)
                    if value is not None:
                        constraints.append(f"{label}: {value}")
        if choices and binary:
            constraints.insert(0, f"Choices: {choices!r}")
        yield (
            name,
            {
                "dtype": field.dtype
                if binary
                else _type_name(field.annotation, tuple(field.metadata)),
                "required": field.required if binary else field.is_required(),
                "default": field.default,
                "choices": choices,
                "description": field.description or "",
                "constraints": constraints,
            },
        )
