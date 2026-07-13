"""Every tool dosho ports, re-exported by name at package level, so a
pipeline author who knows what they want at write-time can do
`from dosho.cabs import wsclean` or `from dosho.cabs.casatasks import
listobs` directly -- no need to know or care whether a given tool is a
`Cab` (a real binary, argv-built and shelled out to) or a `StepRef` (a
Python-package tool with no standalone binary, run via `@shinobi.pystep`
and `ctx.import_func` inside a container instead -- CASA tasks are the
only example so far). Both shapes are first-class for `Recipe.add_step`.

For *runtime*/string-keyed lookup (the CLI, `shinobi.cabs` entry-point
discovery), use `dosho.get(name)`/`dosho.registry` instead -- that's a
second, parallel interface for a caller that doesn't know the name until
it runs, not a replacement for these direct imports.

Importing this module (or any of its submodules -- Python always
initializes a parent package first) eagerly constructs every `Cab`/
`StepRef` below. That's a deliberate, accepted tradeoff here: each one is
cheap (pydantic model + dict construction, no I/O), so the "don't pay for
what you don't use" laziness `dosho.registry`'s own submodule-path table
still gives a caller that only wants one specific tool is preserved
there, not here.
"""

from __future__ import annotations

from dosho.cabs.aoflagger import aoflagger
from dosho.cabs.casaplotms import plotms
from dosho.cabs.casatasks import (
    applycal,
    bandpass,
    clearcal,
    fixvis,
    flagdata,
    flagmanager,
    fluxscale,
    gaincal,
    initweights,
    listobs,
    mstransform,
    polcal,
    setjy,
)
from dosho.cabs.crystalball import crystalball
from dosho.cabs.cubical import cubical
from dosho.cabs.mosaic_queen import mosaic_queen
from dosho.cabs.owlcat_plotelev import owlcat_plotelev
from dosho.cabs.quartical import quartical
from dosho.cabs.ragavi import ragavi
from dosho.cabs.shadems import shadems
from dosho.cabs.simms import primary_beam, simms_classic, skysim, telsim
from dosho.cabs.sofia2 import sofia2
from dosho.cabs.tricolour import tricolour
from dosho.cabs.wsclean import wsclean

__all__ = [
    "aoflagger",
    "applycal",
    "bandpass",
    "clearcal",
    "crystalball",
    "cubical",
    "fixvis",
    "flagdata",
    "flagmanager",
    "fluxscale",
    "gaincal",
    "initweights",
    "listobs",
    "mosaic_queen",
    "mstransform",
    "owlcat_plotelev",
    "plotms",
    "polcal",
    "primary_beam",
    "quartical",
    "ragavi",
    "setjy",
    "shadems",
    "simms_classic",
    "skysim",
    "sofia2",
    "telsim",
    "tricolour",
    "wsclean",
]
