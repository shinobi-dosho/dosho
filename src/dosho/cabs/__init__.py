from __future__ import annotations

from dosho.cabs.bdsf import catalog as bdsf_catalog
from dosho.cabs.casaplotms import plotms
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
from dosho.cabs.fitstoolz import (
    add_axis as fitstoolz_add_axis,
    header as fitstoolz_header,
    remove_axis as fitstoolz_remove_axis,
    slice_ as fitstoolz_slice,
    stack as fitstoolz_stack,
    stats as fitstoolz_stats,
)
from dosho.cabs.simms import primary_beam, skysim, telsim

# --- documents ------------------------------------------------------------
#
# The 43 binary cabs are defined by the documents under `dosho/documents/`,
# not by Python. They are served here on attribute access so
# `from dosho.cabs import wsclean` keeps working and keeps returning a `Cab`,
# which is what every recipe written against this package expects.
#
# Lazy for two reasons. It keeps `import dosho.cabs` from building 43 cabs
# nobody asked for, which is what the eager imports used to do. And it is what
# lets the document half stay reachable without shinobi: building a `Cab`
# needs the schema, so the import that needs it happens only when someone
# actually wants one.
#
# Resolution goes through `dosho.registry.get`, the same path
# `shinobi.cabs.get` takes, so there is one answer to "what is this cab" and
# one place for it to be wrong.


def __getattr__(name: str):
    from dosho.registry import registered_name_for_attr

    registered = registered_name_for_attr(name)
    if registered is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from dosho.registry import get

    # `registry.get` caches, so this is the same object `dosho.get(name)`
    # returns -- one name, one cab, however it is reached. Binding it here as
    # well just stops `__getattr__` firing again.
    cab = get(registered)
    globals()[name] = cab
    return cab


def __dir__() -> list[str]:
    return sorted(__all__)


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
    "fitstoolz_add_axis",
    "fitstoolz_header",
    "fitstoolz_remove_axis",
    "fitstoolz_slice",
    "fitstoolz_stack",
    "fitstoolz_stats",
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
    "sumcols",
    "summary",
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
    "vis_mowjsub",
    "widebandpbcor",
    "wsclean",
    "wvrgcal",
]
