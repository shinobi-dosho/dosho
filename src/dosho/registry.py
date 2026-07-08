"""Lazy name -> cab-module map, registered under shinobi's `shinobi.cabs`
entry-point group (see this package's `pyproject.toml`). Never imports a
`dosho.cabs.<tool>` module until something actually asks for that cab, so
`ninja cabs list` (which only needs names) doesn't pay the cost of every
tool module.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from shinobi import Cab

# name -> "dosho.cabs.<module>:<attribute>". A module that vends several
# related cabs (e.g. a tool with a backup/restore/plotter sibling command)
# lists each one here under its own cab name, all pointing at the same
# module.
_CABS: dict[str, str] = {
    "wsclean": "dosho.cabs.wsclean:cab",
    "cubical": "dosho.cabs.cubical:cab",
    "quartical": "dosho.cabs.quartical:cab",
    "aoflagger": "dosho.cabs.aoflagger:cab",
    "tricolour": "dosho.cabs.tricolour:cab",
    "crystalball": "dosho.cabs.crystalball:cab",
    "owlcat_plotelev": "dosho.cabs.owlcat_plotelev:cab",
    "shadems": "dosho.cabs.shadems:cab",
    "ragavi": "dosho.cabs.ragavi:cab",
    "sofia2": "dosho.cabs.sofia2:cab",
    "simms-skysim": "dosho.cabs.simms_skysim:cab",
    "mosaic-queen": "dosho.cabs.mosaic_queen:cab",
}


def get(name: str) -> "Cab":
    """Resolve a cab by name. Raises `KeyError` if `name` isn't one of
    this repo's cabs -- the contract `shinobi.cabs.get` relies on to fall
    through to the next installed provider.
    """
    target = _CABS[name]
    module_name, attr = target.split(":", 1)
    module = importlib.import_module(module_name)
    return getattr(module, attr)


def list_cabs() -> list[str]:
    return list(_CABS)
