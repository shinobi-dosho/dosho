"""mowjsub -- continuum subtraction for radio interferometric data
(https://github.com/laduma-dev/mowjsub).

Ported from mowjsub 2.0rc1's own CLI definition,
`src/mowjsub/parser/vis_mowjsub.yaml`, which *is* the source of truth here:
the package builds its click interface from that file via scabha's
`clickify_parameters`, so the YAML's names, dtypes, defaults and choices are
exactly what the binary accepts. No cult-cargo YAML exists to cross-check
against -- mowjsub postdates it.

Only `vis-mowjsub` (visibility-plane subtraction) is defined here. The
package also ships `im-mowjsub` for the image plane; it is a different
parameter set over FITS cubes and gets its own cab when something needs it.

Two things worth knowing before wiring this in.

**It has no line-free channel selection.** Unlike CASA `mstransform`'s
`douvcontsub`, there is no `fitspw` -- the continuum is modelled across the
whole band with a spline/polynomial/median filter, and the line is excluded
by the fit being too stiff to follow it rather than by naming channels.
`--fit-model median-filter` in particular can subsume low-SNR line emission,
which mowjsub's own help warns about. This is a different method occupying
the same slot, not a drop-in replacement.

**Both `ms` and `output-ms` are declared outputs, and which one a caller
wires from is which mode it asked for.** The tool's default mode adds
`--output-column` to the *input* MS and writes nothing new, so `ms` is
echoed back: that echo is the only thing that can carry the in-place write
into a DAG, since a mutation with no output ref behind it is a *sibling* of
the next step rather than its producer. Pass `--output-ms` and it produces a
fresh MS instead, and `output-ms` is what downstream should take.

`ms` is additionally declared MUTABLE. That is belt-and-braces --
`mutated_path_fields` already sees it via the input/output name
intersection -- but it says in one place what the echo only implies, and the
cost of getting this wrong is not cosmetic: an undeclared in-place write
keys its cache on the content of a table the step is about to rewrite, and
shinobi's Tier 1 snapshotter can roll it away under a later cache hit
(stimela-ninja#52).
"""

from __future__ import annotations

from shinobi.steps.schema import Mutability, ParamMeta, Policies

from dosho import images
from dosho._builder import FieldSpec, define_cab

_DOPPLER_FRAMES = [
    "topo",
    "geo",
    "bary",
    "lsrk",
    "lsrd",
    "galacto",
    "lgroup",
    "cmb",
    "source",
]

_FIELDS: dict[str, FieldSpec] = {
    "ms": ("MS", True, None, ParamMeta(positional=True, info="Input MS file")),
    "input-column": (
        "str",
        False,
        "DATA",
        ParamMeta(info="Column which contains the data to be continuum subtracted."),
    ),
    "output-column": (
        "str",
        False,
        "LINE_DATA",
        ParamMeta(info="Column name to write the continuum subtracted data to"),
    ),
    "fit-model": (
        "str",
        False,
        "b-spline",
        ParamMeta(
            choices=[
                "b-spline",
                "spline",
                "polynomial",
                "median-filter",
                "scipy-median-filter",
                "gcv-spline",
            ],
            info="Fit function to model the continuum. The 'scipy-median-filter' model is much "
            "faster than 'median-filter', but treats band edges and masked channels differently, "
            "so the two do not give identical continuum models. WARNING: A median-filter continuum "
            "model may subsume low SNR line emission, use it with great care.",
        ),
    ),
    "order": (
        "int",
        False,
        None,
        ParamMeta(
            info="Order of spline/polynomial or number of top coefficients to use for DCT reconstruction"
        ),
    ),
    "vel-width": (
        "float",
        False,
        None,
        ParamMeta(info="Width of spline segments or median filter window in km/s."),
    ),
    "chan-width": (
        "int",
        False,
        None,
        ParamMeta(info="Width of spline segments or median filter window in number of channels."),
    ),
    "gcv-lambda": (
        "float",
        False,
        None,
        ParamMeta(
            info="GCV spline penalty. Zero is equivalent to an interpolating spline, high values "
            "lead to a flatter curve. If unset the parameter will be estimated using the GCV "
            "criterion; this can be very slow. Experience suggests that values chanwidth/nchan "
            "work best."
        ),
    ),
    "segments": (
        "float",
        False,
        None,
        ParamMeta(
            info="## This has been replaced by --vel-width. It will be removed in future releases "
            "## Width of spline segments or median filter window in km/s. If given as a list, then "
            "it must have same size as --order."
        ),
    ),
    "spwid": ("int", False, 0, ParamMeta(info="Spectral Window ID")),
    "field-id": ("int", False, 0, ParamMeta(info="Field ID")),
    "row-chunks": (
        "int",
        False,
        10000,
        ParamMeta(info="Chunking strategy (Done along the time axis)"),
    ),
    "time-chunks": ("int", False, 64, ParamMeta(info="Chunk size for time axis")),
    "bl-chunks": ("int", False, 10, ParamMeta(info="Chunk size for baseline axis")),
    "cont-fit-tol": (
        "float",
        False,
        0,
        ParamMeta(
            info="Minimum percentage of valid spectrum data points required to do a fit. If the "
            "percentage of data points is below this percentage, original data will be returned."
        ),
    ),
    "nworkers": (
        "int",
        False,
        4,
        ParamMeta(
            info="Number of parallel worker threads (roughly one per CPU core). Runtime for "
            "fitting-bound models scales with this, so raise it to speed up large datasets."
        ),
    ),
    "output-ms": (
        "MS",
        False,
        None,
        ParamMeta(
            info="If provided, write the output to a new MS with this name. Otherwise, add new "
            "column to the input MS."
        ),
    ),
    "load-from-cache": (
        "File",
        False,
        None,
        ParamMeta(
            info="Load the MS from a cache (give Zarr file name) if available, otherwise create it."
        ),
    ),
    "doppler-frame": (
        "str",
        False,
        None,
        ParamMeta(
            choices=_DOPPLER_FRAMES,
            info="Spectral reference frame to Doppler-correct the output to. When set, the "
            "continuum-subtracted visibilities are resampled onto a channel grid fixed in this "
            "frame, as CASA mstransform does with regridms=True. The continuum is always fitted "
            "on the native topocentric grid first, so the fit sees the bandpass structure where "
            "it is stationary. Requires --output-ms, since the output channel grid differs from "
            "the input. Leave unset to skip Doppler correction.",
        ),
    ),
    "doppler-chan-grid": (
        "str",
        False,
        "auto",
        ParamMeta(
            info="Output channel grid for the Doppler correction. 'auto' derives the grid that "
            "every timestamp of this observation covers. Otherwise give 'nchan,chan0,chanwidth' "
            "with frequency units, e.g. '1000,1419.5MHz,26.1kHz'; use this to place several MSs "
            "on one common grid, since 'auto' only ever sees a single MS."
        ),
    ),
    "doppler-interpolation": (
        "str",
        False,
        "nearest",
        ParamMeta(
            choices=["nearest", "linear"],
            info="Interpolation used when resampling onto the Doppler-corrected grid. 'nearest' "
            "is what caracal asks of CASA mstransform and leaves channel noise uncorrelated; "
            "'linear' is smoother but correlates adjacent channels.",
        ),
    ),
    "doppler-source-vel": (
        "float",
        False,
        None,
        ParamMeta(
            info="Systemic radial velocity of the source in km/s, positive for recession. Only "
            "used with --doppler-frame=source; when unset it is read from the MS SOURCE::SYSVEL "
            "column."
        ),
    ),
}

vis_mowjsub = define_cab(
    "vis-mowjsub",
    "vis-mowjsub",
    images.MOWJSUB,
    _FIELDS,
    outputs={"ms": ("MS", False, None), "output-ms": ("MS", False, None)},
    input_mutability={"ms": Mutability.MUTABLE},
    policies=Policies(prefix="--"),
    info="mowjsub: visibility-plane continuum subtraction (https://github.com/laduma-dev/mowjsub)",
)
