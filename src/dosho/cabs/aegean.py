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
from dosho._builder import FieldSpec, define_cab

_FIELDS: dict[str, FieldSpec] = {
    "image": ("File", False, None, ParamMeta(info="Input FITS image", positional=True)),
    # Configuration
    "config": ("File", False, None, ParamMeta(info="Path to the config file")),
    "find": (
        "bool",
        False,
        None,
        ParamMeta(info="Source finding mode [default: true, unless --save or --measure]"),
    ),
    "hdu_index": (
        "int",
        False,
        0,
        ParamMeta(
            nom_de_guerre="hdu", info="HDU index (0-based) for cubes with multiple extensions"
        ),
    ),
    "beam": (
        "List[float]",
        False,
        None,
        ParamMeta(
            info='The beam parameters to use as "major minor pa" (all in degrees) [default: from FITS header]',
            repeat_as_tokens=True,
        ),
    ),
    "slice": (
        "int",
        False,
        None,
        ParamMeta(info="For cube input, the array index of the image slice to process"),
    ),
    "progress": (
        "bool",
        False,
        None,
        ParamMeta(info="Show a progress bar as islands are being fit"),
    ),
    "cores": (
        "int",
        False,
        None,
        ParamMeta(info="Number of CPU cores to use for calculating background/rms images"),
    ),
    # Input
    "forcerms": ("float", False, None, ParamMeta(info="Assume a single image noise of rms")),
    "forcebkg": ("float", False, None, ParamMeta(info="Assume a single image background of bkg")),
    "noise": (
        "File",
        False,
        None,
        ParamMeta(info="A FITS file representing the image noise (rms); from --save or BANE"),
    ),
    "background": (
        "File",
        False,
        None,
        ParamMeta(info="A FITS file representing the background level; from --save or BANE"),
    ),
    "psf": ("File", False, None, ParamMeta(info="A FITS file representing the local PSF")),
    "autoload": (
        "bool",
        False,
        None,
        ParamMeta(
            info="Automatically look for background/noise/region/psf files using the input filename as a hint"
        ),
    ),
    # Output
    "out": ("File", False, None, ParamMeta(info="Destination of the Aegean catalog output")),
    "table": (
        "str",
        False,
        None,
        ParamMeta(info="Additional table outputs, format inferred from extension"),
    ),
    "tformats": (
        "bool",
        False,
        None,
        ParamMeta(info="Show the table formats supported by this install"),
    ),
    "blankout": (
        "bool",
        False,
        None,
        ParamMeta(info="Create a blanked output image (only works if cores=1)"),
    ),
    "colprefix": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="colprefix", info='Prepend each column name with "prefix_"'),
    ),
    # Source finding/fitting
    "maxsummits": (
        "int",
        False,
        None,
        ParamMeta(
            info="If more than maxsummits summits are detected in an island, only estimation is done, no fitting"
        ),
    ),
    "seedclip": (
        "float",
        False,
        5.0,
        ParamMeta(info="The clipping value (in sigmas) for seeding islands"),
    ),
    "floodclip": (
        "float",
        False,
        4.0,
        ParamMeta(info="The clipping value (in sigmas) for growing islands"),
    ),
    "island": (
        "bool",
        False,
        None,
        ParamMeta(info="Also calculate the island flux in addition to individual components"),
    ),
    "nopositive": (
        "bool",
        False,
        None,
        ParamMeta(info="Don't report sources with positive fluxes"),
    ),
    "negative": ("bool", False, None, ParamMeta(info="Report sources with negative fluxes")),
    "region": (
        "File",
        False,
        None,
        ParamMeta(info="Restrict source finding to this MIMAS region (.mim) file"),
    ),
    "nocov": (
        "bool",
        False,
        None,
        ParamMeta(info="Don't use the covariance of the data in the fitting process"),
    ),
    # Priorized fitting
    "priorized": (
        "int",
        False,
        None,
        ParamMeta(
            info="Enable priorized fitting level n=[1,2,3]: 1=flux, 2=flux/position, 3=flux/position/shape"
        ),
    ),
    "ratio": (
        "float",
        False,
        None,
        ParamMeta(
            info="Ratio of synthesized beam sizes (image psf / input catalog psf), for priorized fitting"
        ),
    ),
    "noregroup": (
        "bool",
        False,
        None,
        ParamMeta(info="Do not regroup islands before priorized fitting"),
    ),
    "input": (
        "File",
        False,
        None,
        ParamMeta(info="For --priorized, a catalog of locations at which fluxes will be measured"),
    ),
    "catpsf": ("File", False, None, ParamMeta(info="A psf map corresponding to the input catalog")),
    "regroup_eps": (
        "float",
        False,
        None,
        ParamMeta(
            nom_de_guerre="regroup-eps",
            info="Size in arcminutes used to regroup nearby components to be solved simultaneously",
        ),
    ),
    # Extra
    "save": (
        "bool",
        False,
        None,
        ParamMeta(info="Save the background and noise images (sets --find to false)"),
    ),
    "outbase": (
        "str",
        False,
        None,
        ParamMeta(info="Base name of the background/noise images when --save is set"),
    ),
    "debug": ("bool", False, None, ParamMeta(info="Enable debug mode")),
}

aegean = define_cab(
    "aegean",
    "aegean",
    images.AEGEAN,
    _FIELDS,
    outputs={"out": ("File", False, None)},
    policies=Policies(prefix="--"),
    info="aegean: source finding in radio astronomical images (https://github.com/PaulHancock/Aegean)",
)
