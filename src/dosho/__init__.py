"""dosho -- a shinobi's tool bag. The native shinobi (stimela-ninja) cab
repository. See AGENTS.md for the design rationale.
"""

from importlib.metadata import PackageNotFoundError, version as _dist_version

from dosho import images
from dosho.registry import get, list_cabs

# Read the version off the installed distribution rather than restating it
# here. A hand-maintained literal is a second place to bump, and it rotted:
# it still said "0.1.0a1" while the distribution was 0.1.0b3, so
# `docs/conf.py` -- which imports this -- published the whole documentation
# site under a version two releases stale. Derived, it cannot drift from
# pyproject.toml. Mirrors stimela-ninja's own fix for the same bug.
#
# The fallback only applies when `dosho` is importable but the distribution
# is not installed -- a source tree on PYTHONPATH. Nothing legitimate ships
# that way, so it is a marker, not a version anyone should see.
try:
    __version__ = _dist_version("dosho")
except PackageNotFoundError:  # pragma: no cover -- uninstalled source tree
    __version__ = "0+unknown"

__all__ = ["__version__", "define_cab", "get", "images", "list_cabs"]


def __getattr__(name: str):
    """`define_cab`, imported only when asked for.

    It is the authoring helper, and it is the only thing in this package that
    needs shinobi at import time -- `_builder` builds real `Cab` objects, so it
    imports the schema. Importing it eagerly here made `import dosho` pull in
    29 shinobi modules, which means a consumer that only wants dosho's cab
    *definitions* -- to read, diff, pin, or serve them -- had to install the
    framework that runs them.

    Deferring it costs nothing: `dosho.cabs.*` reach `_builder` directly, so
    the authoring path is unaffected, and `define_cab` still resolves through
    `from dosho import define_cab` (PEP 562 covers that form).

    `registry` and `images` are already shinobi-free at runtime -- registry's
    shinobi imports are under `TYPE_CHECKING`, and `get()` reaches the cab
    modules lazily. `tests/test_import_is_shinobi_free.py` pins the property.
    """
    if name == "define_cab":
        from dosho._builder import define_cab

        return define_cab
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(__all__)
