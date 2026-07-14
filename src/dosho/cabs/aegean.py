"""aegean -- source finding in radio astronomical images
(https://github.com/PaulHancock/Aegean).

Ported field-by-field from `aegean --help` (AegeanTools 2.3.5), grouped to
match the real CLI's own section headers (Configuration/Input/Output/Source
finding/Priorized fitting/Extra). Does not model `--versions`/`--cite`
(informational actions, not pipeline options -- the same call as skipping
`-h`/`--help` elsewhere).
"""

from __future__ import annotations

from shinobi.steps.schema import ParamMeta, Policies

from dosho import images
from dosho._builder import define_cab

_FIELDS: dict[str, tuple[str, bool, object]] = {
    "image": ("File", False, None),
    # Configuration
    "config": ("File", False, None),
    "find": ("bool", False, None),
    "hdu_index": ("int", False, 0),
    "beam": ("List[float]", False, None),
    "slice": ("int", False, None),
    "progress": ("bool", False, None),
    "cores": ("int", False, None),
    # Input
    "forcerms": ("float", False, None),
    "forcebkg": ("float", False, None),
    "noise": ("File", False, None),
    "background": ("File", False, None),
    "psf": ("File", False, None),
    "autoload": ("bool", False, None),
    # Output
    "out": ("File", False, None),
    "table": ("str", False, None),
    "tformats": ("bool", False, None),
    "blankout": ("bool", False, None),
    "colprefix": ("str", False, None),
    # Source finding/fitting
    "maxsummits": ("int", False, None),
    "seedclip": ("float", False, 5.0),
    "floodclip": ("float", False, 4.0),
    "island": ("bool", False, None),
    "nopositive": ("bool", False, None),
    "negative": ("bool", False, None),
    "region": ("File", False, None),
    "nocov": ("bool", False, None),
    # Priorized fitting
    "priorized": ("int", False, None),
    "ratio": ("float", False, None),
    "noregroup": ("bool", False, None),
    "input": ("File", False, None),
    "catpsf": ("File", False, None),
    "regroup_eps": ("float", False, None),
    # Extra
    "save": ("bool", False, None),
    "outbase": ("str", False, None),
    "debug": ("bool", False, None),
}

_FIELD_META: dict[str, ParamMeta] = {
    "image": ParamMeta(info="Input FITS image", positional=True),
    "config": ParamMeta(info="Path to the config file"),
    "find": ParamMeta(info="Source finding mode [default: true, unless --save or --measure]"),
    "hdu_index": ParamMeta(nom_de_guerre="hdu", info="HDU index (0-based) for cubes with multiple extensions"),
    "beam": ParamMeta(
        info='The beam parameters to use as "major minor pa" (all in degrees) [default: from FITS header]',
        repeat_as_tokens=True,
    ),
    "slice": ParamMeta(info="For cube input, the array index of the image slice to process"),
    "progress": ParamMeta(info="Show a progress bar as islands are being fit"),
    "cores": ParamMeta(info="Number of CPU cores to use for calculating background/rms images"),
    "forcerms": ParamMeta(info="Assume a single image noise of rms"),
    "forcebkg": ParamMeta(info="Assume a single image background of bkg"),
    "noise": ParamMeta(info="A FITS file representing the image noise (rms); from --save or BANE"),
    "background": ParamMeta(info="A FITS file representing the background level; from --save or BANE"),
    "psf": ParamMeta(info="A FITS file representing the local PSF"),
    "autoload": ParamMeta(info="Automatically look for background/noise/region/psf files using the input filename as a hint"),
    "out": ParamMeta(info="Destination of the Aegean catalog output"),
    "table": ParamMeta(info="Additional table outputs, format inferred from extension"),
    "tformats": ParamMeta(info="Show the table formats supported by this install"),
    "blankout": ParamMeta(info="Create a blanked output image (only works if cores=1)"),
    "colprefix": ParamMeta(nom_de_guerre="colprefix", info='Prepend each column name with "prefix_"'),
    "maxsummits": ParamMeta(
        info="If more than maxsummits summits are detected in an island, only estimation is done, no fitting"
    ),
    "seedclip": ParamMeta(info="The clipping value (in sigmas) for seeding islands"),
    "floodclip": ParamMeta(info="The clipping value (in sigmas) for growing islands"),
    "island": ParamMeta(info="Also calculate the island flux in addition to individual components"),
    "nopositive": ParamMeta(info="Don't report sources with positive fluxes"),
    "negative": ParamMeta(info="Report sources with negative fluxes"),
    "region": ParamMeta(info="Restrict source finding to this MIMAS region (.mim) file"),
    "nocov": ParamMeta(info="Don't use the covariance of the data in the fitting process"),
    "priorized": ParamMeta(
        info="Enable priorized fitting level n=[1,2,3]: 1=flux, 2=flux/position, 3=flux/position/shape"
    ),
    "ratio": ParamMeta(info="Ratio of synthesized beam sizes (image psf / input catalog psf), for priorized fitting"),
    "noregroup": ParamMeta(info="Do not regroup islands before priorized fitting"),
    "input": ParamMeta(info="For --priorized, a catalog of locations at which fluxes will be measured"),
    "catpsf": ParamMeta(info="A psf map corresponding to the input catalog"),
    "regroup_eps": ParamMeta(
        nom_de_guerre="regroup-eps",
        info="Size in arcminutes used to regroup nearby components to be solved simultaneously",
    ),
    "save": ParamMeta(info="Save the background and noise images (sets --find to false)"),
    "outbase": ParamMeta(info="Base name of the background/noise images when --save is set"),
    "debug": ParamMeta(info="Enable debug mode"),
}

aegean = define_cab(
    "aegean",
    "aegean",
    images.AEGEAN,
    _FIELDS,
    outputs={"out": ("File", False, None)},
    field_meta=_FIELD_META,
    policies=Policies(prefix="--"),
    info="aegean: source finding in radio astronomical images (https://github.com/PaulHancock/Aegean)",
)
