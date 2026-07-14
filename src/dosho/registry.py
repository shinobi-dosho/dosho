"""name -> `Cab`/`StepRef` map, registered under shinobi's `shinobi.cabs`
entry-point group (see this package's `pyproject.toml`). String-keyed
runtime lookup, for a caller that doesn't know the tool name until it
runs (`ninja cabs list/show`, `shinobi.cabs` entry-point discovery) --
for the write-time-known case, `from dosho.cabs import <tool>` (see
`dosho/cabs/__init__.py`) is the more ergonomic, direct interface.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from shinobi import Cab
    from shinobi.steps.schema import StepRef

# registered name -> re-exported attribute, for the handful of tools whose
# real (possibly hyphenated) name doesn't match the identifier
# `dosho/cabs/__init__.py` re-exports it as. Every other entry in
# `dosho.cabs.__all__` registers under its own attribute name unchanged --
# see `_build_entries` below. Keeping just the exceptions here (instead of
# a full name -> attribute table) means a new cab only has to be added
# once, in `dosho/cabs/__init__.py`'s imports/`__all__`, unless its real
# name needs to differ from its attribute name.
_NAME_OVERRIDES: dict[str, str] = {
    "skysim": "simms-skysim",
    "telsim": "simms-telsim",
    "primary_beam": "simms-primary-beam",
    "simms_classic": "simms",
    "mosaic_queen": "mosaic-queen",
    "ragavi_gains": "ragavi-gains",
    "ragavi_vis": "ragavi-vis",
    "summary": "msutils-summary",
    "addcol": "msutils-addcol",
    "copycol": "msutils-copycol",
    "sumcols": "msutils-sumcols",
    "addnoise": "msutils-addnoise",
    "flagstats": "msutils-flagstats",
    "bdsf_catalog": "bdsf-catalog",
    "quartical_backup": "quartical-backup",
    "quartical_restore": "quartical-restore",
    "quartical_plotter": "quartical-plotter",
    "spimple_binterp": "spimple-binterp",
    "spimple_imconv": "spimple-imconv",
    "spimple_spifit": "spimple-spifit",
    "tigger_convert": "tigger-convert",
    "tigger_restore": "tigger-restore",
    "tigger_tag": "tigger-tag",
}


_entries_cache: dict[str, str] | None = None


def _entries() -> dict[str, str]:
    """registered name -> "dosho.cabs:<attribute>" for every tool
    `dosho.cabs` re-exports. Every entry resolves through the same
    `dosho.cabs` module now that it re-exports everything -- `get()`
    doesn't care whether a given entry is a `Cab` (real binary-flavour
    tool) or a `StepRef` (from `@shinobi.pystep`, e.g. a CASA task) --
    `Recipe.add_step` accepts either identically.

    Computed lazily and cached: reading `dosho.cabs.__all__` requires
    importing that module, which -- per its own docstring -- eagerly
    constructs every `Cab`/`StepRef` in the repo. Deferring this to first
    use keeps `import dosho.registry` itself cheap, matching this
    module's own "lazy, string-keyed lookup" contract.
    """
    global _entries_cache
    if _entries_cache is None:
        from dosho import cabs

        _entries_cache = {
            _NAME_OVERRIDES.get(attr, attr): f"dosho.cabs:{attr}" for attr in cabs.__all__
        }
    return _entries_cache


def get(name: str) -> "Cab | StepRef":
    """Resolve a cab/pystep by name. Raises `KeyError` if `name` isn't
    one of this repo's entries -- the contract `shinobi.cabs.get` relies
    on to fall through to the next installed provider.
    """
    target = _entries()[name]
    module_name, attr = target.split(":", 1)
    module = importlib.import_module(module_name)
    return getattr(module, attr)


def list_cabs() -> list[str]:
    """List every tool name registered in this repository.

    Returns:
        The registered names (may be hyphenated, e.g. `"simms-skysim"`),
        in no particular order.
    """
    return list(_entries())
