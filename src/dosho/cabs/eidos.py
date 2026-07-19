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
from dosho._builder import FieldSpec, define_cab

_FIELDS: dict[str, FieldSpec] = {
    "pixels": ("int", False, 256, ParamMeta(info="Number of pixels on one side")),
    "diameter": ("float", False, None, ParamMeta(info="Diameter of the required beam")),
    "scale": ("float", False, None, ParamMeta(info="Pixel scale in degrees")),
    "freq": (
        "List[float]", True, None,
        ParamMeta(
            info="A single freq, or the start, end freqs, and channel width in MHz",
            repeat_as_tokens=True,
        ),
    ),
    "coeff": (
        "str", True, None,
        ParamMeta(
            info="Which coefficients to use: mh for MeerKAT holography, me for MeerKAT EM "
            "simulation, vh for VLA holography",
        ),
    ),
    "coefficients_file": (
        "File", False, None,
        ParamMeta(nom_de_guerre="coefficients-file", info="Coefficients file"),
    ),
    "prefix": ("str", False, None, ParamMeta(info="Prefix of output beam file(s)")),
    "output_eight": (
        "bool", False, None,
        ParamMeta(nom_de_guerre="output-eight", info="Output complex voltage beams (8 files)"),
    ),
    "thresh": (
        "int", False, None,
        ParamMeta(info="How many Zernike coefficients to use. Must be <=20."),
    ),
    "stokes": (
        "str", False, None,
        ParamMeta(
            nom_de_guerre="Stokes",
            info="Output in Stokes (Mueller) formalism instead of the default Jones formalism: "
            "'I','Q','U','V' for the Stokes beams, 'M' for the full Mueller matrix, or e.g. 'IQ' "
            "for the Q-to-I leakage",
        ),
    ),
}

eidos = define_cab(
    "eidos",
    "eidos",
    images.EIDOS,
    _FIELDS,
    policies=Policies(prefix="--"),
    info="eidos: create a primary beam model of MeerKAT (https://github.com/ratt-ru/eidos)",
)
