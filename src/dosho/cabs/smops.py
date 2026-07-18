"""smops -- "Smooth Operator": frequency axis upsampling for WSClean-derived
model images (https://github.com/ratt-ru/smops).

Ported field-by-field from `smops --help` (smops 0.1.7), matching cult-cargo's
`smops.yml` (a flat, static, up-to-date schema).
"""

from __future__ import annotations

from shinobi.steps.schema import ParamMeta, Policies

from dosho import images
from dosho._builder import FieldSpec, define_cab

_FIELDS: dict[str, FieldSpec] = {
    "ms": ("MS", True, None, ParamMeta(info="Input MS. Used for getting reference frequency")),
    "input_prefix": (
        "str", True, None,
        ParamMeta(
            nom_de_guerre="input-prefix",
            info="The input image prefix, same as the one used for wsclean",
        ),
    ),
    "channels_out": (
        "int", True, None,
        ParamMeta(nom_de_guerre="channels-out", info="Number of channels to generate out"),
    ),
    "polynomial_order": (
        "int", True, None,
        ParamMeta(nom_de_guerre="polynomial-order", info="Order of the spectral polynomial"),
    ),
    "max_mem": (
        "int", False, None,
        ParamMeta(
            nom_de_guerre="max-mem",
            info="Approximate memory cap in GB. Default is 10% of available memory.",
        ),
    ),
    "num_threads": (
        "int", False, None,
        ParamMeta(
            nom_de_guerre="num-threads",
            info="Number of threads to use while writing out output images",
        ),
    ),
    "output_prefix": (
        "str", False, None,
        ParamMeta(
            nom_de_guerre="output-prefix",
            info="What to prefix the new interpolated model name with",
        ),
    ),
    "stokes": (
        "str", False, None,
        ParamMeta(
            info="Which stokes model to extrapolate, e.g. 'IQUV'. Required when there are "
            "multiple Stokes images in a directory. Default I.",
        ),
    ),
}

smops = define_cab(
    "smops",
    "smops",
    images.SMOPS,
    _FIELDS,
    policies=Policies(prefix="--"),
    info="smops: Smooth Operator, frequency axis upsampling for WSClean-derived model images "
    "(https://github.com/ratt-ru/smops)",
)
