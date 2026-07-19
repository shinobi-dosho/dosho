"""chgcentre -- recompute UVWs and rotate visibilities to a new phase centre
(https://wsclean.readthedocs.io). `chgcentre` is a companion binary built
alongside `wsclean` itself (same source tree, same `make install`), so this
reuses dosho's existing `WSCLEAN` image rather than a new one.

Transcribed from cult-cargo's `chgcentre.yml` (flat, static, no
`dynamic_schema`) -- unlike most other ports in this batch, this one
couldn't be cross-checked against a locally installed `chgcentre --help`
(wsclean is a compiled C++ tool, not pip-installable), so cult-cargo's YAML
is the primary source here, not just a secondary one.
"""

from __future__ import annotations

from shinobi.steps.schema import ParamMeta, Policies

from dosho import images
from dosho._builder import FieldSpec, define_cab

_FIELDS: dict[str, FieldSpec] = {
    "geozenith": (
        "bool",
        False,
        None,
        ParamMeta(
            info="Calculate the RA/dec of zenith for each timestep and move there (makes the set "
            "non-standard)",
        ),
    ),
    "flipuvwsign": (
        "bool",
        False,
        None,
        ParamMeta(info="Flip the UVW sign (necessary for LOFAR, for unknown reasons)"),
    ),
    "minw": (
        "bool",
        False,
        None,
        ParamMeta(info="Calculate the direction that gives the minimum w-values for the array"),
    ),
    "zenith": ("bool", False, None, ParamMeta(info="Shift to the average zenith value")),
    "only_uvw": (
        "bool",
        False,
        None,
        ParamMeta(
            nom_de_guerre="only-uvw",
            info="Only update the UVW values, do not apply the phase shift",
        ),
    ),
    "shiftback": (
        "bool",
        False,
        None,
        ParamMeta(
            info="After changing the phase centre, project visibilities back to the old phase "
            "centre",
        ),
    ),
    "force": (
        "bool",
        False,
        None,
        ParamMeta(
            nom_de_guerre="f",
            info="Force recalculation even if the destination equals the original phase direction",
        ),
    ),
    "datacolumn": (
        "str",
        False,
        None,
        ParamMeta(
            info="Only phase-rotate this column [default: DATA, MODEL_DATA, CORRECTED_DATA if "
            "present]",
        ),
    ),
    "from_ms": (
        "MS",
        False,
        None,
        ParamMeta(
            nom_de_guerre="from-ms",
            info="Rotate to the same direction as specified in this measurement set",
        ),
    ),
    "ms": (
        "MS",
        True,
        None,
        ParamMeta(info="Measurement set to rotate (edited in place)", positional=True),
    ),
    "ra": (
        "str",
        True,
        None,
        ParamMeta(info="New Right Ascension (00h00m00.0s or 00:00:00.0 format)", positional=True),
    ),
    "dec": (
        "str",
        True,
        None,
        ParamMeta(info="New Declination (00d00m00.0s or 00.00.00.0 format)", positional=True),
    ),
}

chgcentre = define_cab(
    "chgcentre",
    "chgcentre",
    images.WSCLEAN,
    _FIELDS,
    outputs={"ms": ("MS", False, None)},
    policies=Policies(prefix="-"),
    info="chgcentre: recompute UVWs and rotate visibilities to a new phase centre "
    "(https://wsclean.readthedocs.io)",
)
