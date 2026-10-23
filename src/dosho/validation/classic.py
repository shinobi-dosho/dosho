"""Static Stimela classic JSON to compiled parameter contracts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .compiled import CompiledCab as Cab, CompiledParamMeta as ParamMeta
from .exceptions import CabLoadError
from .modelgen import DtypeError, build_model, sanitize_unique, validate_choices


def load_file(path: str | Path) -> Cab:
    """Load a stimela-classic cab definition (JSON) file into a `Cab`.

    Args:
        path: Path to the JSON cab definition file.

    Returns:
        The built `Cab` instance.
    """
    return loads(Path(path).read_text())


def loads(text: str, *, type_bindings=None) -> Cab:
    """Parse a stimela-classic cab definition from a JSON string.

    Args:
        text: JSON text of the cab definition.

    Returns:
        The built `Cab` instance.
    """
    return _build_cabdef(json.loads(text), type_bindings=type_bindings)


def _build_cabdef(spec: dict[str, Any], *, type_bindings=None) -> Cab:
    base = spec.get("base") or ""
    flavour = "casa-task" if "casa" in base else "binary"

    name = spec["task"]
    fields: dict[str, tuple[str, bool, Any]] = {}
    metas: dict[str, ParamMeta] = {}
    seen: dict[str, str] = {}
    for param in spec.get("parameters", []):
        field = sanitize_unique(param["name"], seen)
        dtype, meta = _build_param(param, original=param["name"], field=field)
        fields[field] = dtype
        if meta is not None:
            metas[field] = meta

    choices = {field: meta.choices for field, meta in metas.items() if meta.choices}

    try:
        return Cab(
            name=name,
            command=spec.get("binary", name),
            info=spec.get("description"),
            image=base or None,
            flavour=flavour,
            inputs_model=build_model(
                f"{name}_Inputs", fields, choices=choices, type_bindings=type_bindings
            ),
            outputs_model=build_model(f"{name}_Outputs", {}),
            field_meta=metas,
        )
    except DtypeError as exc:
        raise CabLoadError(f"cab {name!r}: {exc}") from exc


def _build_param(
    param: dict[str, Any], *, original: str, field: str
) -> tuple[tuple[str, bool, Any], ParamMeta | None]:
    dtype = param.get("dtype", "str")
    if isinstance(dtype, list):
        dtype = dtype[0] if dtype else "str"
    dtype = str(dtype)

    if param.get("io") == "msfile":
        dtype = "MS"

    choices = validate_choices(param.get("choices"), error=CabLoadError)
    info = param.get("info")
    if choices:
        choices_text = f"choices: {', '.join(str(c) for c in choices)}"
        info = f"{info} ({choices_text})" if info else choices_text

    # the tool's real flag name: classic's `mapping`, else the original
    # param name if sanitising the field name changed it.
    nom = param.get("mapping") or (original if original != field else None)
    field_spec = (dtype, bool(param.get("required", False)), param.get("default"))
    meta = (
        ParamMeta(nom_de_guerre=nom, info=info, choices=choices)
        if (nom or info or choices)
        else None
    )
    return field_spec, meta
