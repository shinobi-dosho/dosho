"""name -> `Cab`/`StepRef` map, registered under shinobi's `shinobi.cabs`
entry-point group (see this package's `pyproject.toml`). String-keyed
runtime lookup, for a caller that doesn't know the tool name until it
runs (`ninja cabs list/show`, `shinobi.cabs` entry-point discovery) --
for the write-time-known case, `from dosho.cabs import <tool>` (see
`dosho/cabs/__init__.py`) is the more ergonomic, direct interface.
"""

from __future__ import annotations

import importlib
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from shinobi import Cab
    from shinobi.steps.schema import StepRef

_INDEX_PATH = Path(__file__).with_name("cab_index.yaml")
_DOCUMENT_DIR = Path(__file__).with_name("documents")
_index_cache: dict[str, dict[str, Any]] | None = None
_cab_cache: dict[str, Any] = {}


def _index() -> dict[str, dict[str, Any]]:
    """registered name -> where its definition lives, from the generated index.

    Read from a file rather than derived from `dosho.cabs.__all__`, which
    would import every cab in the repo and, through `_builder`, shinobi
    itself. Everything on this side of the module -- `list_cabs`,
    `get_document`, the experimental warning -- stays usable by a consumer
    that wants dosho's definitions without the framework that runs them.

    Regenerate with `python -m tools.generate_documents`.
    """
    global _index_cache
    if _index_cache is None:
        _index_cache = yaml.safe_load(_INDEX_PATH.read_text())["cabs"]
    return _index_cache


def registered_name_for_attr(attr: str) -> str | None:
    """The registered name a `dosho.cabs` attribute stands for, or None.

    `dosho.cabs.__getattr__` is keyed by attribute (`simms_classic`) and
    everything else by registered name (`simms`); 31 tools differ between the
    two. The index records both, so the mapping is written down once rather
    than inferred in reverse from a table of exceptions.

    Both kinds resolve here now that `dosho.cabs` imports nothing eagerly:
    a document-backed cab is built from its file, a pystep is fetched from the
    module the index names.
    """
    for name, entry in _index().items():
        if entry.get("attr") == attr:
            return name
    return None


def get_document(name: str) -> tuple[str, str]:
    """`(dialect, text)` for a cab defined by a document.

    The `shinobi.cabs` provider protocol's preferred entry: shinobi builds the
    `Cab`, so nothing here parses the document or imports the schema. Raises
    `KeyError` for a pystep, whose definition is a Python function and cannot
    be a document -- the protocol then falls through to `get` on this same
    module.
    """
    entry = _index()[name]
    if "document" not in entry:
        raise KeyError(name)
    _warn_if_experimental(name)
    return "yaml_cab", (_DOCUMENT_DIR / entry["document"]).read_text()


def loader_options() -> dict[str, Any]:
    """What dosho's documents need in order to be loaded.

    They name images by manifest key (`image: WSCLEAN`) so a deployment's
    `$DOSHO_IMAGES`/`$DOSHO_IMAGE_<KEY>` overrides still decide the reference
    at load time. shinobi has no manifest; this is how it gets one.
    """
    from dosho import images

    return {"images": {k: getattr(images, k) for k in dir(images) if k.isupper()}}


_warned_experimental: set[str] = set()


def _warn_if_experimental(name: str) -> None:
    """Warn, once per name per process, that a cab is experimental and which
    modes it doesn't cover.

    `get()` is the hook because it is where a name becomes a cab -- for the
    CLI, for `shinobi.cabs` discovery, and for any recipe built by name. A
    direct `from dosho.cabs import ddfacet` bypasses it, which is why the
    marker also rides on the cab's own `info` (see `_builder.define_cab`):
    warning at construction time instead would fire for every importer of
    `dosho.cabs`, which builds every cab in the repo.
    """
    reason = _index().get(name, {}).get("experimental")
    if reason is None or name in _warned_experimental:
        return
    _warned_experimental.add(name)
    warnings.warn(
        f"dosho cab '{name}' is EXPERIMENTAL: {reason}",
        UserWarning,
        stacklevel=3,
    )


def get(name: str) -> Cab | StepRef:
    """Resolve a cab/pystep by name. Raises `KeyError` if `name` isn't
    one of this repo's entries -- the contract `shinobi.cabs.get` relies
    on to fall through to the next installed provider.

    Warns (once per name) if the cab is marked experimental -- see
    the generated index.
    """
    entry = _index()[name]
    # Before the cache, not after: whether a caller hears about an experimental
    # cab should not depend on whether someone else already built it. The
    # once-per-name guard lives in the warning itself.
    _warn_if_experimental(name)
    if "document" in entry:
        # Cached, so a name resolves to one object however it is reached --
        # `dosho.get("wsclean")` and `dosho.cabs.wsclean` included. These were
        # module-level singletons before the documents replaced them and
        # callers may still compare them by identity; rebuilding per call
        # would also re-parse ddfacet's 274 fields every lookup.
        if name in _cab_cache:
            return _cab_cache[name]
        # One code path with `shinobi.cabs.get`: the same document, the same
        # builder, the same options. A second path here would be a second
        # place for the two to disagree about what a cab is.
        from shinobi.cabs import build_document

        dialect, text = get_document(name)
        cab = build_document(dialect, text, name=name, **loader_options())
        _cab_cache[name] = cab
        return cab
    # The pystep's own module, not `dosho.cabs` -- that package resolves
    # names *through here*, so reaching back into it would be a cycle.
    module = importlib.import_module(entry["module"])
    return getattr(module, entry["symbol"])


def list_cabs() -> list[str]:
    """List every tool name registered in this repository.

    Returns:
        The registered names (may be hyphenated, e.g. `"simms-skysim"`),
        in no particular order.
    """
    return list(_index())
