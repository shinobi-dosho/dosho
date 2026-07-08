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
from dosho._builder import define_cab

_FIELDS: dict[str, tuple[str, bool, object]] = {
    "input": ("Directory", True, None),
    "target_images": ("List[File]", True, None),
    "name": ("str", True, None),
    "num_workers": ("int", False, 0),
    "associated_mosaics": ("List[File]", False, None),
    "regrid": ("bool", False, None),
    "force_regrid": ("bool", False, None),
    "beam_cutoff": ("float", False, 0.1),
    "mosaic_cutoff": ("float", False, 0.2),
    "unity_weights": ("bool", False, None),
    "statistic": ("str", False, "mad"),
    "guess_std": ("float", False, 0.02),
    "ra": ("float", False, None),
    "dec": ("float", False, None),
    "velocity": ("float", False, None),
    "dra": ("float", False, None),
    "ddec": ("float", False, None),
    "dv": ("float", False, None),
}

_FIELD_META: dict[str, ParamMeta] = {
    "input": ParamMeta(
        info="Directory containing the (2D or 3D) images and beams.", positional=True
    ),
    "target_images": ParamMeta(
        nom_de_guerre="target-images",
        info="Space-separated list of images to be mosaicked; 'image.fits' automatically replaced by 'pb.fits' to locate beams.",
        positional=True,
    ),
    "name": ParamMeta(info="Prefix to be used for output files.", positional=True),
    "num_workers": ParamMeta(
        nom_de_guerre="num-workers", info="Number of worker threads; 0 uses all available threads."
    ),
    "associated_mosaics": ParamMeta(
        nom_de_guerre="associated-mosaics",
        info="Also make mosaics of associated files; space-separated list. e.g masks, models or residuals",
    ),
    "regrid": ParamMeta(info="Use montage for regridding images and beams."),
    "force_regrid": ParamMeta(
        nom_de_guerre="force-regrid", info="Force newly-regridded files even if they exist."
    ),
    "beam_cutoff": ParamMeta(
        nom_de_guerre="beam-cutoff", info="Cutoff in the primary beam (e.g., 0.1 = 10% level)."
    ),
    "mosaic_cutoff": ParamMeta(
        nom_de_guerre="mosaic-cutoff",
        info="Sensitivity cutoff in final mosaic; pixels with noise > min_noise / cutoff are blanked.",
    ),
    "unity_weights": ParamMeta(
        nom_de_guerre="unity-weights", info="Use weight=1 instead of weight=1/noise**2."
    ),
    "statistic": ParamMeta(info="Statistic to use for estimating noise in input images."),
    "guess_std": ParamMeta(
        nom_de_guerre="guess-std", info="Initial guess of noise level for '--statistic fit'."
    ),
    "ra": ParamMeta(info="Central RA (deg) of output mosaic if not imaging full FoV."),
    "dec": ParamMeta(info="Central Dec (deg) of output mosaic if not imaging full FoV."),
    "velocity": ParamMeta(info="Central velocity/frequency of output mosaic cube."),
    "dra": ParamMeta(info="RA range of output mosaic image/cube."),
    "ddec": ParamMeta(info="Dec range of output mosaic image/cube."),
    "dv": ParamMeta(info="Velocity/frequency range of output mosaic cube."),
    "output": ParamMeta(info="Directory for all output files.", positional=True),
}

_OUTPUTS: dict[str, tuple[str, bool, object]] = {
    "output": ("Directory", True, None),
}

cab = define_cab(
    "mosaic-queen",
    "mosaic-queen",
    images.MOSAIC_QUEEN,
    _FIELDS,
    outputs=_OUTPUTS,
    field_meta=_FIELD_META,
    policies=Policies(prefix="--", replace={"_": "-"}),
    info="mosaic-queen: FITS image mosaicking (https://github.com/caracal-pipeline/mosaic-queen)",
)
