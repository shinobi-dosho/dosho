"""eidos -- create a primary beam model of MeerKAT (https://github.com/ratt-ru/eidos).

Ported field-by-field from `eidos --help` (eidos 1.1.2). cult-cargo's
`eidos.yml` is stale relative to the current CLI (missing `-r/--scale` and
`-T/--thresh`/`-S/--Stokes`, has a `normalise` flag the real tool no longer
has, and only lists 2 of `--coeff`'s 3 real choices) -- transcribed from the
real `--help` instead, per AGENTS.md.

No outputs are modelled: eidos writes one or more beam FITS files named
from `--prefix` plus tool-internal suffixes (frequency/Stokes-dependent,
not knowable statically), the same "no dynamic-naming implicit" call as
`breizorro.py`'s `outfile`.
"""

from __future__ import annotations

from shinobi.steps.schema import ParamMeta, Policies

from dosho import images
from dosho._builder import define_cab

_FIELDS: dict[str, tuple[str, bool, object]] = {
    "pixels": ("int", False, 256),
    "diameter": ("float", False, None),
    "scale": ("float", False, None),
    "freq": ("List[float]", True, None),
    "coeff": ("str", True, None),
    "coefficients_file": ("File", False, None),
    "prefix": ("str", False, None),
    "output_eight": ("bool", False, None),
    "thresh": ("int", False, None),
    "stokes": ("str", False, None),
}

_FIELD_META: dict[str, ParamMeta] = {
    "pixels": ParamMeta(info="Number of pixels on one side"),
    "diameter": ParamMeta(info="Diameter of the required beam"),
    "scale": ParamMeta(info="Pixel scale in degrees"),
    "freq": ParamMeta(
        info="A single freq, or the start, end freqs, and channel width in MHz",
        repeat_as_tokens=True,
    ),
    "coeff": ParamMeta(
        info="Which coefficients to use: mh for MeerKAT holography, me for MeerKAT "
        "EM simulation, vh for VLA holography"
    ),
    "coefficients_file": ParamMeta(nom_de_guerre="coefficients-file", info="Coefficients file"),
    "prefix": ParamMeta(info="Prefix of output beam file(s)"),
    "output_eight": ParamMeta(nom_de_guerre="output-eight", info="Output complex voltage beams (8 files)"),
    "thresh": ParamMeta(info="How many Zernike coefficients to use. Must be <=20."),
    "stokes": ParamMeta(
        nom_de_guerre="Stokes",
        info="Output in Stokes (Mueller) formalism instead of the default Jones formalism: "
        "'I','Q','U','V' for the Stokes beams, 'M' for the full Mueller matrix, or e.g. "
        "'IQ' for the Q-to-I leakage",
    ),
}

eidos = define_cab(
    "eidos",
    "eidos",
    images.EIDOS,
    _FIELDS,
    field_meta=_FIELD_META,
    policies=Policies(prefix="--"),
    info="eidos: create a primary beam model of MeerKAT (https://github.com/ratt-ru/eidos)",
)
