"""dosho -- a shinobi's tool bag. The native shinobi (stimela-ninja) cab
repository. See AGENTS.md for the design rationale.
"""

from importlib.metadata import PackageNotFoundError, version as _dist_version

from dosho import images
from dosho._builder import define_cab
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
