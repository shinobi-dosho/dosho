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
from dosho.cabs.bdsf import catalog as bdsf_catalog
from dosho.cabs.breizorro import breizorro
from dosho.cabs.casaplotms import plotms
from dosho.cabs.chgcentre import chgcentre
from dosho.cabs.casatasks import (
    accor,
    apparentsens,
    appendantab,
    applycal,
    bandpass,
    blcal,
    clearcal,
    clearstat,
    concat,
    conjugatevis,
    cvel,
    cvel2,
    deconvolve,
    defintent,
    delmod,
    feather,
    fixplanets,
    fixvis,
    flagcmd,
    flagdata,
    flagmanager,
    fluxscale,
    fringefit,
    ft,
    gaincal,
    gencal,
    getantposalma,
    getcalmodvla,
    hanningsmooth,
    impbcor,
    initweights,
    listobs,
    makemask,
    mstransform,
    msuvbin,
    msuvbinflag,
    partition,
    pccor,
    phaseshift,
    polcal,
    polfromgain,
    predictcomp,
    rerefant,
    rmtables,
    sdintimaging,
    setjy,
    smoothcal,
    split,
    statwt,
    tclean,
    uvcontsub,
    uvcontsub_old,
    uvmodelfit,
    uvsub,
    virtualconcat,
    widebandpbcor,
    wvrgcal,
)
from dosho.cabs.crystalball import crystalball
from dosho.cabs.cubical import cubical
from dosho.cabs.ddfacet import ddfacet
from dosho.cabs.eidos import eidos
from dosho.cabs.flagms import flagms
from dosho.cabs.killms import killms
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
    "accor",
    "addcol",
    "addnoise",
    "aegean",
    "aimfast",
    "aoflagger",
    "apparentsens",
    "appendantab",
    "applycal",
    "bandpass",
    "bdsf_catalog",
    "blcal",
    "breizorro",
    "chgcentre",
    "clearcal",
    "clearstat",
    "concat",
    "conjugatevis",
    "copycol",
    "crystalball",
    "cubical",
    "cvel",
    "cvel2",
    "ddfacet",
    "deconvolve",
    "defintent",
    "delmod",
    "eidos",
    "feather",
    "fixplanets",
    "fixvis",
    "flagcmd",
    "flagdata",
    "flagmanager",
    "flagms",
    "flagstats",
    "fluxscale",
    "fringefit",
    "ft",
    "gaincal",
    "gencal",
    "getantposalma",
    "getcalmodvla",
    "hanningsmooth",
    "impbcor",
    "initweights",
    "killms",
    "listobs",
    "makemask",
    "mosaic_queen",
    "mstransform",
    "msuvbin",
    "msuvbinflag",
    "owlcat_plotelev",
    "partition",
    "pccor",
    "phaseshift",
    "plotms",
    "polcal",
    "polfromgain",
    "predictcomp",
    "primary_beam",
    "pyddi",
    "quartical",
    "quartical_backup",
    "quartical_plotter",
    "quartical_restore",
    "ragavi_gains",
    "ragavi_vis",
    "rerefant",
    "rfinder",
    "rmclean3d",
    "rmsynth1d",
    "rmsynth3d",
    "rmtables",
    "sdintimaging",
    "setjy",
    "shadems",
    "simms_classic",
    "skysim",
    "smoothcal",
    "smops",
    "sofia2",
    "spimple_binterp",
    "spimple_imconv",
    "spimple_spifit",
    "split",
    "statwt",
    "summary",
    "sumcols",
    "tclean",
    "telsim",
    "tigger_convert",
    "tigger_restore",
    "tigger_tag",
    "tricolour",
    "uvcontsub",
    "uvcontsub_old",
    "uvmodelfit",
    "uvsub",
    "virtualconcat",
    "widebandpbcor",
    "wsclean",
    "wvrgcal",
]
