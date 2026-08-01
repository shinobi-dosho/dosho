"""Every tool dosho provides, by name.

`from dosho.cabs import wsclean` gives you the `Cab`; `from dosho.cabs import
listobs` gives you the pystep `StepRef`. Both are first-class for
`Recipe.add_step`, and a pipeline author does not need to know which one a
given tool is.

Nothing is imported eagerly. A name resolves on first access, through
`dosho.registry.get` -- the same path `shinobi.cabs.get` takes -- so there is
one answer to "what is this tool" and one place for it to be wrong. Repeated
access returns the same object, as it did when these were module-level
assignments.

That laziness is also what makes shinobi optional. Building a `Cab` from its
document, or importing a pystep, needs the schema; *naming* one does not. So
`import dosho.cabs` costs nothing and works without shinobi installed, and
only attribute access requires the `dosho[run]` extra.

For runtime, string-keyed lookup -- the CLI, `shinobi.cabs` entry-point
discovery -- use `dosho.get(name)` instead. Same objects, keyed by registered
name (`msutils-addcol`) rather than by the attribute this module exports it
as (`addcol`).
"""

from __future__ import annotations


def __getattr__(name: str):
    from dosho.registry import get, registered_name_for_attr

    registered = registered_name_for_attr(name)
    if registered is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    try:
        obj = get(registered)
    except ImportError as exc:  # shinobi absent
        raise ImportError(
            f"dosho.cabs.{name} needs stimela-ninja, which is not installed. "
            "dosho ships its cab definitions without it -- install `dosho[run]` "
            "to build and run them."
        ) from exc
    globals()[name] = obj
    return obj


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
