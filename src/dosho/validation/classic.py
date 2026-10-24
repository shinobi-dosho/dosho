"""Static Stimela classic JSON to compiled parameter contracts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .compiled import CompiledCab as Cab, CompiledParamMeta as ParamMeta
from .exceptions import CabLoadError
from .modelgen import sanitize_unique, validate_choices


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


def parse_classic(text: str):
    """Normalize classic JSON into the shared neutral document dialect."""
    return _parse_cabdef(json.loads(text))


def _parse_cabdef(spec):
    from .compiled import CabSpec

    base = spec.get("base") or ""
    fields = {}
    seen = {}
    for param in spec.get("parameters", []):
        original = param["name"]
        field = sanitize_unique(original, seen)
        (dtype, required, default), meta = _build_param(param, original=original, field=field)
        value = {"dtype": dtype, "required": required, "default": default}
        if meta is not None:
            value.update(meta.model_dump(mode="python", exclude_defaults=True))
        fields[original] = value
    return CabSpec(
        name=spec["task"],
        document={
            "command": spec.get("binary", spec["task"]),
            "info": spec.get("description"),
            "image": base or None,
            "flavour": "casa-task" if "casa" in base else "binary",
            "inputs": fields,
        },
    )


def _build_cabdef(spec: dict[str, Any], *, type_bindings=None) -> Cab:
    from .compiler import compile_cab

    return compile_cab(_parse_cabdef(spec), type_bindings=type_bindings)


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
