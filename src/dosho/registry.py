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

# registered name -> "dosho.cabs:<attribute>". The registered name is the
# tool's own real name (may be hyphenated, e.g. "simms-skysim",
# "mosaic-queen" -- not a valid Python identifier), while the attribute is
# whatever `dosho/cabs/__init__.py` re-exports it as (a valid identifier,
# e.g. `skysim`, `mosaic_queen`). Every entry resolves through the same
# `dosho.cabs` module now that it re-exports everything -- `get()`
# doesn't care whether a given entry is a `Cab` (real binary-flavour
# tool) or a `StepRef` (from `@shinobi.pystep`, e.g. a CASA task) --
# `Recipe.add_step` accepts either identically.
_ENTRIES: dict[str, str] = {
    "wsclean": "dosho.cabs:wsclean",
    "cubical": "dosho.cabs:cubical",
    "quartical": "dosho.cabs:quartical",
    "aoflagger": "dosho.cabs:aoflagger",
    "tricolour": "dosho.cabs:tricolour",
    "crystalball": "dosho.cabs:crystalball",
    "owlcat_plotelev": "dosho.cabs:owlcat_plotelev",
    "shadems": "dosho.cabs:shadems",
    "ragavi": "dosho.cabs:ragavi",
    "sofia2": "dosho.cabs:sofia2",
    "simms-skysim": "dosho.cabs:skysim",
    "mosaic-queen": "dosho.cabs:mosaic_queen",
    "listobs": "dosho.cabs:listobs",
    "mstransform": "dosho.cabs:mstransform",
    "fixvis": "dosho.cabs:fixvis",
    "clearcal": "dosho.cabs:clearcal",
    "initweights": "dosho.cabs:initweights",
    "flagdata": "dosho.cabs:flagdata",
    "setjy": "dosho.cabs:setjy",
    "gaincal": "dosho.cabs:gaincal",
    "polcal": "dosho.cabs:polcal",
    "bandpass": "dosho.cabs:bandpass",
    "applycal": "dosho.cabs:applycal",
    "fluxscale": "dosho.cabs:fluxscale",
    "flagmanager": "dosho.cabs:flagmanager",
    "plotms": "dosho.cabs:plotms",
}


def get(name: str) -> "Cab | StepRef":
    """Resolve a cab/pystep by name. Raises `KeyError` if `name` isn't
    one of this repo's entries -- the contract `shinobi.cabs.get` relies
    on to fall through to the next installed provider.
    """
    target = _ENTRIES[name]
    module_name, attr = target.split(":", 1)
    module = importlib.import_module(module_name)
    return getattr(module, attr)


def list_cabs() -> list[str]:
    return list(_ENTRIES)
