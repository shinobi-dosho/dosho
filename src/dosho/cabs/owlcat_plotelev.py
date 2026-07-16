"""owlcat_plotelev -- Owlcat's plot-elevation-tracks.py, plots target
elevation over the course of an observation.

Ported field-by-field from cult-cargo's owlcat_plotelev.yml (flat,
static schema).
"""

from __future__ import annotations

from shinobi.steps.schema import ParamMeta, Policies

from dosho import images
from dosho._builder import define_cab

_FIELDS: dict[str, tuple[str, bool, object]] = {
    "msname": ("MS", True, None),
    "list": ("bool", False, None),
    "display": ("bool", False, False),
    # Output plot name, passed on the CLI (`--output-name`). File-typed so the
    # container binds its parent dir -- as an output-only field it was never
    # emitted, and the script fell back to `lst-elev.png` in the cwd (same
    # trap as ragavi-vis's `htmlname`).
    "output_name": ("File", False, None),
}

_FIELD_META: dict[str, ParamMeta] = {
    # the MS is a positional arg (`plot-elevation-tracks.py [options] MS`),
    # not `--msname`, so it must not take the `--` prefix.
    "msname": ParamMeta(positional=True, info="Name of Measurement set"),
    "list": ParamMeta(info="lists fields found in MS, then exits"),
    "display": ParamMeta(info="Display plot on screen"),
    "output_name": ParamMeta(nom_de_guerre="output-name", info="Output filename"),
}

_OUTPUTS: dict[str, tuple[str, bool, object]] = {
    "output_name": ("File", False, "lst-elev.png"),
}

owlcat_plotelev = define_cab(
    "owlcat_plotelev",
    "plot-elevation-tracks.py",
    images.OWLCAT,
    _FIELDS,
    outputs=_OUTPUTS,
    field_meta=_FIELD_META,
    policies=Policies(prefix="--"),
    info="Owlcat plot-elevation-tracks.py: plot target elevation over time",
)
