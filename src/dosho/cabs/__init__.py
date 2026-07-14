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

from dosho.cabs.aegean import aegean
from dosho.cabs.aimfast import aimfast
from dosho.cabs.aoflagger import aoflagger
from dosho.cabs.breizorro import breizorro
from dosho.cabs.casaplotms import plotms
from dosho.cabs.chgcentre import chgcentre
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
from dosho.cabs.eidos import eidos
from dosho.cabs.flagms import flagms
from dosho.cabs.mosaic_queen import mosaic_queen
from dosho.cabs.msutils import (
    addcol,
    addnoise,
    copycol,
    flagstats,
    summary,
    sumcols,
)
from dosho.cabs.owlcat_plotelev import owlcat_plotelev
from dosho.cabs.pyddi import pyddi
from dosho.cabs.quartical import (
    quartical,
    quartical_backup,
    quartical_plotter,
    quartical_restore,
)
from dosho.cabs.ragavi import gains as ragavi_gains, vis as ragavi_vis
from dosho.cabs.rfinder import rfinder
from dosho.cabs.rmtools import rmclean3d, rmsynth1d, rmsynth3d
from dosho.cabs.shadems import shadems
from dosho.cabs.simms import primary_beam, simms_classic, skysim, telsim
from dosho.cabs.smops import smops
from dosho.cabs.sofia2 import sofia2
from dosho.cabs.spimple import binterp as spimple_binterp, imconv as spimple_imconv, spifit as spimple_spifit
from dosho.cabs.tigger import convert as tigger_convert, restore as tigger_restore, tag as tigger_tag
from dosho.cabs.tricolour import tricolour
from dosho.cabs.wsclean import wsclean

__all__ = [
    "addcol",
    "addnoise",
    "aegean",
    "aimfast",
    "aoflagger",
    "applycal",
    "bandpass",
    "breizorro",
    "chgcentre",
    "clearcal",
    "copycol",
    "crystalball",
    "cubical",
    "eidos",
    "fixvis",
    "flagdata",
    "flagmanager",
    "flagms",
    "flagstats",
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
    "pyddi",
    "quartical",
    "quartical_backup",
    "quartical_plotter",
    "quartical_restore",
    "ragavi_gains",
    "ragavi_vis",
    "rfinder",
    "rmclean3d",
    "rmsynth1d",
    "rmsynth3d",
    "setjy",
    "shadems",
    "simms_classic",
    "skysim",
    "smops",
    "sofia2",
    "spimple_binterp",
    "spimple_imconv",
    "spimple_spifit",
    "summary",
    "sumcols",
    "telsim",
    "tigger_convert",
    "tigger_restore",
    "tigger_tag",
    "tricolour",
    "wsclean",
]
