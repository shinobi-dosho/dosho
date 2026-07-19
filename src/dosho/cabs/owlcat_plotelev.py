"""owlcat_plotelev -- Owlcat's plot-elevation-tracks.py, plots target
elevation over the course of an observation.

Ported field-by-field from cult-cargo's owlcat_plotelev.yml (flat,
static schema).
"""

from __future__ import annotations

from shinobi.steps.schema import ParamMeta, Policies

from dosho import images
from dosho._builder import FieldSpec, define_cab

_FIELDS: dict[str, FieldSpec] = {
    # the MS is a positional arg (`plot-elevation-tracks.py [options] MS`),
    # not `--msname`, so it must not take the `--` prefix.
    "msname": ("MS", True, None, ParamMeta(positional=True, info="Name of Measurement set")),
    "list": ("bool", False, None, ParamMeta(info="lists fields found in MS, then exits")),
    "display": ("bool", False, False, ParamMeta(info="Display plot on screen")),
    # Output plot name, passed on the CLI (`--output-name`). File-typed so the
    # container binds its parent dir -- as an output-only field it was never
    # emitted, and the script fell back to `lst-elev.png` in the cwd (same
    # trap as ragavi-vis's `htmlname`).
    "output_name": (
        "File",
        False,
        None,
        ParamMeta(nom_de_guerre="output-name", info="Output filename"),
    ),
}

_OUTPUTS: dict[str, FieldSpec] = {
    "output_name": ("File", False, "lst-elev.png"),
}

owlcat_plotelev = define_cab(
    "owlcat_plotelev",
    "plot-elevation-tracks.py",
    images.OWLCAT,
    _FIELDS,
    outputs=_OUTPUTS,
    policies=Policies(prefix="--"),
    info="Owlcat plot-elevation-tracks.py: plot target elevation over time",
)
