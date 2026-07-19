"""mosaic-queen -- FITS image mosaicking tool
(https://github.com/caracal-pipeline/mosaic-queen).

Ported field-by-field from cult-cargo's mosaic-queen.yml (flat, static
schema). Note: caracal2's mosaic worker (mosaic/__init__.py) sets this
cab's own `name` input field directly on `recipe.steps[-1].params`
after `add_step`, since Recipe.add_step's own first positional
parameter is itself called `name` -- see that worker's own comments,
unrelated to this port.
"""

from __future__ import annotations

from shinobi.steps.schema import ParamMeta, Policies

from dosho import images
from dosho._builder import FieldSpec, define_cab

_FIELDS: dict[str, FieldSpec] = {
    "input": (
        "Directory",
        True,
        None,
        ParamMeta(info="Directory containing the (2D or 3D) images and beams.", positional=True),
    ),
    "target_images": (
        "List[File]",
        True,
        None,
        ParamMeta(
            nom_de_guerre="target-images",
            info="Space-separated list of images to be mosaicked; 'image.fits' automatically "
            "replaced by 'pb.fits' to locate beams.",
            positional=True,
        ),
    ),
    "name": (
        "str",
        True,
        None,
        ParamMeta(info="Prefix to be used for output files.", positional=True),
    ),
    "num_workers": (
        "int",
        False,
        0,
        ParamMeta(
            nom_de_guerre="num-workers",
            info="Number of worker threads; 0 uses all available threads.",
        ),
    ),
    "associated_mosaics": (
        "List[File]",
        False,
        None,
        ParamMeta(
            nom_de_guerre="associated-mosaics",
            info="Also make mosaics of associated files; space-separated list. e.g masks, models "
            "or residuals",
        ),
    ),
    "regrid": ("bool", False, None, ParamMeta(info="Use montage for regridding images and beams.")),
    "force_regrid": (
        "bool",
        False,
        None,
        ParamMeta(
            nom_de_guerre="force-regrid",
            info="Force newly-regridded files even if they exist.",
        ),
    ),
    "beam_cutoff": (
        "float",
        False,
        0.1,
        ParamMeta(
            nom_de_guerre="beam-cutoff",
            info="Cutoff in the primary beam (e.g., 0.1 = 10% level).",
        ),
    ),
    "mosaic_cutoff": (
        "float",
        False,
        0.2,
        ParamMeta(
            nom_de_guerre="mosaic-cutoff",
            info="Sensitivity cutoff in final mosaic; pixels with noise > min_noise / cutoff are "
            "blanked.",
        ),
    ),
    "unity_weights": (
        "bool",
        False,
        None,
        ParamMeta(nom_de_guerre="unity-weights", info="Use weight=1 instead of weight=1/noise**2."),
    ),
    "statistic": (
        "str",
        False,
        "mad",
        ParamMeta(info="Statistic to use for estimating noise in input images."),
    ),
    "guess_std": (
        "float",
        False,
        0.02,
        ParamMeta(
            nom_de_guerre="guess-std",
            info="Initial guess of noise level for '--statistic fit'.",
        ),
    ),
    "ra": (
        "float",
        False,
        None,
        ParamMeta(info="Central RA (deg) of output mosaic if not imaging full FoV."),
    ),
    "dec": (
        "float",
        False,
        None,
        ParamMeta(info="Central Dec (deg) of output mosaic if not imaging full FoV."),
    ),
    "velocity": (
        "float",
        False,
        None,
        ParamMeta(info="Central velocity/frequency of output mosaic cube."),
    ),
    "dra": ("float", False, None, ParamMeta(info="RA range of output mosaic image/cube.")),
    "ddec": ("float", False, None, ParamMeta(info="Dec range of output mosaic image/cube.")),
    "dv": ("float", False, None, ParamMeta(info="Velocity/frequency range of output mosaic cube.")),
}

_OUTPUTS: dict[str, FieldSpec] = {
    "output": (
        "Directory",
        True,
        None,
        ParamMeta(info="Directory for all output files.", positional=True),
    ),
}

mosaic_queen = define_cab(
    "mosaic-queen",
    "mosaic-queen",
    images.MOSAIC_QUEEN,
    _FIELDS,
    outputs=_OUTPUTS,
    policies=Policies(prefix="--", replace={"_": "-"}),
    info="mosaic-queen: FITS image mosaicking (https://github.com/caracal-pipeline/mosaic-queen)",
)
