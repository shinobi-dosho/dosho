"""Container image references for every cab, resolved from the `images.yaml`
manifest and exposed as one module constant per tool (``images.WSCLEAN``,
``images.CASA6``, ...). Cab modules import these unchanged.

The manifest is the single source of truth linking each cab to its image (and,
once dosho builds its own images, to a build recipe -- see the build subsystem
and `images.yaml`'s own header for the schema). Each entry resolves to a full
image reference:

* ``ref:``   -- used verbatim (an existing published image / placeholder);
* ``build:`` -- composed as ``{registry}/{name}:{version}-{bundle_version}``
  from ``metadata`` (``name`` defaults to the lower-cased key).

`manifest` (the parsed dict: ``metadata`` + ``images``) is exposed for the
build tooling; the resolved string constants are what cabs consume.

Per-deployment overrides let a site repoint any image without editing dosho.
Precedence, lowest to highest:

1. the manifest (``images.yaml``);
2. a YAML file (same ``{KEY: ref}`` shape) named by ``$DOSHO_IMAGES``;
3. per-tool ``$DOSHO_IMAGE_<KEY>`` environment variables.

Overrides are applied at import time -- a cab's ``image`` is baked when the cab
is constructed -- so they must be set *before* the process starts, not toggled
at runtime.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

_DATA_PATH = Path(__file__).with_name("images.yaml")


def _load_manifest(path: Path) -> dict[str, Any]:
    with path.open() as f:
        return yaml.safe_load(f) or {}


def _resolve_ref(key: str, entry: dict[str, Any], metadata: dict[str, Any]) -> str:
    """Resolve one manifest entry to a full image reference."""
    if "ref" in entry:
        return entry["ref"]
    if "build" in entry:
        build = entry["build"] or {}
        registry = metadata["registry"]
        name = entry.get("name", key.lower())
        version = build["version"]
        bundle = metadata["bundle_version"]
        return f"{registry}/{name}:{version}-{bundle}"
    raise ValueError(f"image {key!r} in {_DATA_PATH.name} has neither 'ref' nor 'build'")


def _apply_overrides(refs: dict[str, str]) -> dict[str, str]:
    """Layer the DOSHO_IMAGES file then DOSHO_IMAGE_<KEY> env vars over `refs`."""
    override_file = os.environ.get("DOSHO_IMAGES")
    if override_file:
        with open(override_file) as f:
            refs.update(yaml.safe_load(f) or {})
    for key in list(refs):
        env_ref = os.environ.get(f"DOSHO_IMAGE_{key}")
        if env_ref:
            refs[key] = env_ref
    return refs


manifest: dict[str, Any] = _load_manifest(_DATA_PATH)
_metadata: dict[str, Any] = manifest.get("metadata", {})
_images: dict[str, Any] = manifest.get("images", {})

_refs: dict[str, str] = {key: _resolve_ref(key, entry, _metadata) for key, entry in _images.items()}
_refs = _apply_overrides(_refs)

# Expose each resolved reference as a module constant (images.WSCLEAN, ...).
globals().update(_refs)
