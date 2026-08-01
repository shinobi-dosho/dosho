"""Read what a built `Cab` cannot remember, straight from dosho's source.

Two things are lost by the time `define_cab` returns, and both are needed to
serialise a cab faithfully (see `docs/design_data_registry.md` §4.5-4.6):

* **dtype strings.** `shinobi.loaders._modelgen.dtype_to_type` is many-to-one
  -- `Path` <- File/MS/Directory/URI, `list[Path]` <- their List forms -- so a
  built `Cab` cannot say which one a field was declared as. 237 of dosho's
  1523 declared fields (16%) collapse this way.
* **the image key.** A cab carries a resolved reference
  (`ghcr.io/shinobi-dosho/breizorro:0.2.0-d0.1.0`); the document should carry
  the manifest key (`BREIZORRO`) so a deployment's `$DOSHO_IMAGES` override
  still applies at load time rather than being baked in at generation time.

Everything else round-trips through the `Cab` itself, so this reads only what
it must. Field specs are literal tuples in every case -- verified across all
42 `define_cab` calls, 1437 input fields, zero exceptions.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

CABS_DIR = Path(__file__).resolve().parent.parent / "src" / "dosho" / "cabs"


@dataclass
class CabSource:
    """What source knows and the built object does not."""

    name: str
    module: str
    image_key: str | None = None
    # raw param name -> (dtype, required, default), exactly the triple
    # `build_model` consumes. Taken from source rather than rebuilt from the
    # model so it is faithful by construction: 3046 such values across the 42
    # cabs, every one a literal.
    inputs: dict[str, tuple] = field(default_factory=dict)
    outputs: dict[str, tuple] = field(default_factory=dict)


def _module_dicts(tree: ast.Module) -> dict[str, ast.Dict]:
    """Module-level `NAME = {...}` bindings.

    Both assignment forms, because dosho writes
    `_FIELDS: dict[str, FieldSpec] = {...}` -- an `AnnAssign`. Handling only
    `Assign` silently resolves nothing while looking like it worked.
    """
    out: dict[str, ast.Dict] = {}
    for node in tree.body:
        target = value = None
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            target, value = node.targets[0].id, node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target, value = node.target.id, node.value
        if target and isinstance(value, ast.Dict):
            out[target] = value
    return out


def _specs(node: ast.Dict | None) -> dict[str, tuple]:
    """`{raw_name: (dtype, required, default)}` from a field-spec mapping.

    The 4th element, when present, is a `ParamMeta(...)` call -- not read here.
    Its contents survive on the built `Cab` and are taken from there.
    """
    if node is None:
        return {}
    out: dict[str, tuple] = {}
    for key, value in zip(node.keys, node.values, strict=True):
        if not isinstance(key, ast.Constant):
            continue
        if not (isinstance(value, ast.Tuple) and value.elts):
            raise ValueError(f"field {key.value!r}: spec is not a literal tuple")
        dtype, required, default = value.elts[0], value.elts[1], value.elts[2]
        out[key.value] = (
            ast.literal_eval(dtype),
            ast.literal_eval(required),
            ast.literal_eval(default),
        )
    return out


def _resolve(node: ast.expr | None, bound: dict[str, ast.Dict]) -> ast.Dict | None:
    """A field-spec mapping given inline, or by the name of a module-level one."""
    if isinstance(node, ast.Name):
        return bound.get(node.id)
    return node if isinstance(node, ast.Dict) else None


def _image_key(node: ast.expr | None) -> str | None:
    """`images.WSCLEAN` -> `"WSCLEAN"`."""
    if (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "images"
    ):
        return node.attr
    return None


def read_sources() -> dict[str, CabSource]:
    """Every `define_cab` call in `src/dosho/cabs/`, keyed by cab name."""
    found: dict[str, CabSource] = {}
    for path in sorted(CABS_DIR.glob("*.py")):
        if path.name == "__init__.py":
            continue
        tree = ast.parse(path.read_text(), filename=str(path))
        bound = _module_dicts(tree)

        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "define_cab"):
                continue
            kw = {k.arg: k.value for k in node.keywords}
            args = node.args
            name_node = args[0] if args else kw.get("name")
            if not isinstance(name_node, ast.Constant):
                raise ValueError(f"{path.name}: define_cab with a non-literal name")
            found[name_node.value] = CabSource(
                name=name_node.value,
                module=path.name,
                image_key=_image_key(args[2] if len(args) > 2 else kw.get("image")),
                inputs=_specs(_resolve(args[3] if len(args) > 3 else kw.get("fields"), bound)),
                outputs=_specs(_resolve(kw.get("outputs"), bound)),
            )
    return found
