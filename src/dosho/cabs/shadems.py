"""shadems -- fast MS visibility plotting via datashader
(https://github.com/ratt-ru/shadeMS).

Ported field-by-field from cult-cargo's shadems.yml. Several fields
(ant/ant_num/baseline/spw/field/scan/corr) are real Union[...]-typed
(e.g. Union[int, str, List[str], List[int]]), now resolving to real
Python union types via stimela-ninja's dtype_to_type support instead
of falling back to str.
"""

from __future__ import annotations

from shinobi.steps.schema import ParamMeta, Policies

from dosho import images
from dosho._builder import FieldSpec, define_cab

_FIELDS: dict[str, FieldSpec] = {
    "ms": ("MS", True, None, ParamMeta(info="Measurement set to plot", positional=True)),
    "xaxis": (
        "str",
        False,
        None,
        ParamMeta(
            info="Xaxis to plot. Can be any MS column name, also: CHAN, FREQ, CORR, ROW, WAVEL, U, V, W, UV, and, for complex columns, keywords such as: 'amp', 'phase', 'real', 'imag'. You can also specify correlations, e.g. 'DATA:phase:XX'. The order of specifiers does not matter."
        ),
    ),
    "yaxis": (
        "str",
        False,
        None,
        ParamMeta(info="Y axis to plot. Must be given the same number of times as --xaxis."),
    ),
    "aaxis": (
        "str",
        False,
        None,
        ParamMeta(
            info="Intensity axis. If none, plot intensity (a.k.a. alpha channel) is proportional to density of points.Otherwise, a reduction function (--ared) is applied to the given values, and the result is used to determine intensity."
        ),
    ),
    "ared": ("str", False, None, ParamMeta(info="Alpha axis reduction function.")),
    "colour_by": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="colour-by",
            info="Colour axis. All columns and variations listed under --xaxis are available for colouring by.",
        ),
    ),
    "col": (
        "str",
        False,
        None,
        ParamMeta(
            info="Name of visibility column. Default is DATA. Two-column arithmetic is recognized."
        ),
    ),
    "noflags": ("bool", False, None, ParamMeta(info="Ignore flags. Default is to honour")),
    "noconj": (
        "bool",
        False,
        None,
        ParamMeta(info="Do not show conjugate points in u,v plots. Default is true."),
    ),
    "xmin": ("float", False, None, ParamMeta(info="Minimum x-axis value. Default is data min.")),
    "xmax": (
        "float",
        False,
        None,
        ParamMeta(info="Maximum x-axis value to plot. Default is data max."),
    ),
    "ymin": ("float", False, None, ParamMeta(info="Minimum y-axis value. Default is data min.")),
    "ymax": (
        "float",
        False,
        None,
        ParamMeta(info="Maximum y-axis value to plot. Default is data max."),
    ),
    "cmin": ("float", False, None, ParamMeta(info="Minimum colouring value. Default is data-min.")),
    "cmax": (
        "float",
        False,
        None,
        ParamMeta(info="Maximum colouring value.  Default is data-max."),
    ),
    "cnum": ("int", False, None, ParamMeta(info="Number of colours to use.")),
    "iter_field": (
        "bool",
        False,
        None,
        ParamMeta(
            nom_de_guerre="iter-field", info="Separate plots per field. Default is combine all."
        ),
    ),
    "iter_antenna": (
        "bool",
        False,
        None,
        ParamMeta(
            nom_de_guerre="iter-antenna", info="Separate plots per antenna. Default is combine all."
        ),
    ),
    "iter_spw": (
        "bool",
        False,
        None,
        ParamMeta(nom_de_guerre="iter-spw", info="Separate plots per spw. Default is combine all."),
    ),
    "iter_scan": (
        "bool",
        False,
        None,
        ParamMeta(
            nom_de_guerre="iter-scan", info="Separate plots per scan. Default is combine all."
        ),
    ),
    "iter_corr": (
        "bool",
        False,
        None,
        ParamMeta(
            nom_de_guerre="iter-corr",
            info="Separate plots per correlation / Stokes. Default is combine all.",
        ),
    ),
    "ant": (
        "Union[str, List[str]]",
        False,
        None,
        ParamMeta(info="Antennas to plot (comma-separated list of names). Default is all."),
    ),
    "ant_num": (
        "Union[str, List[int]]",
        False,
        None,
        ParamMeta(
            nom_de_guerre="ant-num",
            info="Antennas to plot (comma-separated list of numbers, or a [start]:[stop][:step] slice, overrides --ant).",
        ),
    ),
    "baseline": (
        "Union[str, List[str]]",
        False,
        None,
        ParamMeta(info="Baselines to plot, as 'ant1-ant2' (comma-separated list). Default is all."),
    ),
    "spw": (
        "Union[int, List[int]]",
        False,
        None,
        ParamMeta(info="Spectral windows (DDIDs) to plot (comma-separated list) Default is all."),
    ),
    "field": (
        "Union[int, str, List[str], List[int]]",
        False,
        None,
        ParamMeta(info="Field ID(s) to plot (comma-separated list). Default is all."),
    ),
    "scan": (
        "Union[int, List[int]]",
        False,
        None,
        ParamMeta(info="Scans to plot (comma-separated list). Default is all."),
    ),
    "corr": (
        "Union[str, List[str]]",
        False,
        None,
        ParamMeta(
            info="Correlations or Stokes to plot, use indices or labels (comma-separated list). Default is all."
        ),
    ),
    "chan": (
        "str",
        False,
        None,
        ParamMeta(info="Channel slice, as [start]:[stop][:step].  Default is to plot all."),
    ),
    "xcanvas": ("int", False, None, ParamMeta(info="Canvas x-size in pixels.")),
    "ycanvas": ("int", False, None, ParamMeta(info="Canvas y-size in pixels.")),
    "norm": (
        "str",
        False,
        None,
        ParamMeta(
            info="Pixel scale normalization. Default is 'log' when colouring, and 'eq_hist' when not."
        ),
    ),
    "cmap": ("str", False, None, ParamMeta(info="Colorcet map used without --colour-by.")),
    "bmap": (
        "str",
        False,
        None,
        ParamMeta(info="Colorcet map used when colouring by a continuous axis."),
    ),
    "dmap": (
        "str",
        False,
        None,
        ParamMeta(info="Colorcet map used when colouring by a discrete axis."),
    ),
    "spread_pix": (
        "int",
        False,
        None,
        ParamMeta(
            nom_de_guerre="spread-pix", info="Dynamically spread rendered pixels to this size."
        ),
    ),
    "spread_thr": (
        "float",
        False,
        None,
        ParamMeta(nom_de_guerre="spread-thr", info="Threshold parameter for spreading (0 to 1)."),
    ),
    "bgcol": (
        "str",
        False,
        None,
        ParamMeta(info="RGB hex code for background colour. Default FFFFFF (white)."),
    ),
    "fontsize": ("float", False, None, ParamMeta(info="Font size for all text elements.")),
    "suffix": ("str", False, None, ParamMeta(info="Suffix to be included in filenames.")),
    "png": (
        "str",
        False,
        None,
        ParamMeta(
            info="Output PNG name. Default is plot-{ms}{_field}{_Spw}{_Scan}{_Ant}-{label}{_alphalabel}{_colorlabel}{_suffix}.png"
        ),
    ),
    "title": (
        "str",
        False,
        None,
        ParamMeta(
            info="Template for plot titles. Default title includes ms name, field, spw, scan, antenna, plot title, alpha title and colour title."
        ),
    ),
    "xlabel": (
        "str",
        False,
        None,
        ParamMeta(info="Template for X axis labels. Default is x-axis name and unit"),
    ),
    "ylabel": (
        "str",
        False,
        None,
        ParamMeta(info="Template for Y axis labels. Default is y-axis name and unit"),
    ),
    "debug": ("bool", False, None, ParamMeta(info="Enable debugging output.")),
    "row_chunk_size": (
        "int",
        False,
        None,
        ParamMeta(
            nom_de_guerre="row-chunk-size",
            info="Row chunk size for dask-ms. Larger chunks may or may not be faster, but will certainly use more RAM.",
        ),
    ),
    "num_parallel": (
        "int",
        False,
        None,
        ParamMeta(
            nom_de_guerre="num-parallel",
            info="Run up to N renderers in parallel. Default is serial. Use -j0 to auto-set this to half the available cores.",
        ),
    ),
    "profile": ("bool", False, None, ParamMeta(info="Enable dask profiling output.")),
}

_OUTPUTS: dict[str, FieldSpec] = {
    "dir": ("Directory", False, None, ParamMeta(info="Send all plots to this output directory")),
}

shadems = define_cab(
    "shadems",
    "shadems",
    images.SHADEMS,
    _FIELDS,
    outputs=_OUTPUTS,
    policies=Policies(prefix="--"),
    info="ShadeMS: rendering MS data via datashader (https://github.com/ratt-ru/shadeMS)",
)
