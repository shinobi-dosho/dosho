"""ragavi -- Radio Astronomy Gain and Visibility Inspector
(https://ragavi.readthedocs.io). Two sibling console scripts, one cab each,
named for their sub-tool so a caller addresses them consistently as
`dosho.cabs.ragavi:vis` / `dosho.cabs.ragavi:gains`:

* `vis` -- `ragavi-vis`, interactive Bokeh-based MS *visibility* plots.
* `gains` -- `ragavi-gains`, plots of *gain tables* (K/G/B/F/D...),
  used by crosscal/polcal to render each solved caltable. `htmlname`/
  `plotname` are output filenames the tool writes, but they are passed *on
  the command line*, so each is declared as both an input (emitted as
  `--htmlname`/`--plotname`) and a same-named passthrough output.

Ported field-by-field from cult-cargo's ragavi_vis.yml / ragavi.yml (flat,
static schemas).
"""

from __future__ import annotations

from shinobi.steps.schema import ParamMeta, Policies

from dosho import images
from dosho._builder import FieldSpec, define_cab

_FIELDS: dict[str, FieldSpec] = {
    "ms": ("MS", True, None, ParamMeta(info="MS to plot.")),
    "xaxis": ("str", True, None, ParamMeta(info="X-axis to plot.")),
    "yaxis": ("str", True, None, ParamMeta(info="Y-axis to plot.")),
    "canvas_height": (
        "int",
        False,
        None,
        ParamMeta(nom_de_guerre="canvas-height", info="Set height of the resulting image."),
    ),
    "canvas_width": (
        "int",
        False,
        None,
        ParamMeta(nom_de_guerre="canvas-width", info="Set width of the resulting image."),
    ),
    "cbin": ("int", False, None, ParamMeta(info="Size of channel bins over which to average.")),
    "ant": (
        "str",
        False,
        None,
        ParamMeta(
            info="Select baselines where ANTENNA1 corresponds to the supplied antenna(s)",
        ),
    ),
    "chan": ("str", False, None, ParamMeta(info="Channels to select. Defaults to all.")),
    "chunks": (
        "str",
        False,
        None,
        ParamMeta(
            info="Chunk sizes to be applied to the dataset. Defaults to 5,000 in the row axis.",
        ),
    ),
    "cmap": ("str", False, None, ParamMeta(info="Colour or colour map to use. Defaults to blues.")),
    "colour_axis": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="colour-axis", info="Select column to colourise by."),
    ),
    "cols": (
        "int",
        False,
        None,
        ParamMeta(info="Number columns in grid if iteration is active. Defaults to 5."),
    ),
    "corr": (
        "str",
        False,
        None,
        ParamMeta(
            info="Correlation index or subset to plot. Can be specified using normal python slicing syntax. Defaults to all.",
        ),
    ),
    "data_column": (
        "str",
        False,
        "DATA",
        ParamMeta(nom_de_guerre="data-column", info="MS column to use for data."),
    ),
    "debug": ("bool", False, None, ParamMeta(info="Enable debugging messages")),
    "ddid": (
        "str",
        False,
        None,
        ParamMeta(
            info="DATA_DESC_ID(s) /spw to select. Can be specified as e.g. 5, 5,6,7, 5~7 (inclusive range), 5:8 (exclusive range), 5:(from 5 to last). Defaults to all",
        ),
    ),
    "field": (
        "str",
        False,
        None,
        ParamMeta(
            info="Field ID(s) / NAME(s) to plot. Can be specified as '0', '0,2,4', '0~3' (inclusive range), '0:3' (exclusive range), '3:' (from 3 to last) or using a field name or comma separated field names. Defaults to all.",
        ),
    ),
    "iter_axis": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="iter-axis", info="Select column to iterate by."),
    ),
    "logfile": (
        "str",
        False,
        None,
        ParamMeta(info="Desired name of logfile. Default is ragavi.log"),
    ),
    "mem_limit": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="mem-limit", info="Memory limit per core. Default is 1GB."),
    ),
    "include_flagged": (
        "bool",
        False,
        None,
        ParamMeta(
            nom_de_guerre="include-flagged",
            info="Include flagged data in the generated plot. Default is false",
        ),
    ),
    "num_cores": (
        "int",
        False,
        None,
        ParamMeta(
            nom_de_guerre="num-cores",
            info="Number of CPU cores to be used by Dask. Defaults to 10 or less cores",
        ),
    ),
    "scan": ("str", False, None, ParamMeta(info="Scan Number to select. Defaults to all.")),
    "taql": ("str", False, None, ParamMeta(info="TAQL where clause")),
    "tbin": ("float", False, None, ParamMeta(info="Time in seconds over which to average.")),
    "xmin": ("float", False, None, ParamMeta(info="Minimum x value to plot")),
    "xmax": ("float", False, None, ParamMeta(info="Maximum x value to plot")),
    "ymin": ("float", False, None, ParamMeta(info="Minimum y value to plot")),
    "ymax": ("float", False, None, ParamMeta(info="Maximum y value to plot")),
    # Output HTML name, passed on the CLI (`--htmlname`). File-typed so the
    # container binds its parent dir -- otherwise ragavi-vis falls back to its
    # auto-generated name in the cwd (there's no other path input under the
    # output dir to pull the bind-mount in, unlike ragavi-gains' `table`).
    "htmlname": (
        "File",
        False,
        None,
        ParamMeta(info="Output HTML file name (without .html suffix)"),
    ),
}

_OUTPUTS: dict[str, FieldSpec] = {
    # File to match the same-named File input it passes through (the output is
    # filled from the input value, a Path).
    "htmlname": ("File", False, None),
}

vis = define_cab(
    "ragavi-vis",
    "ragavi-vis",
    images.RAGAVI,
    _FIELDS,
    outputs=_OUTPUTS,
    policies=Policies(prefix="--"),
    info="ragavi-vis: interactive Bokeh-based MS visibility plots (https://ragavi.readthedocs.io)",
)

# ragavi-gains: plot gain tables. `htmlname`/`plotname` are output filenames
# passed on the CLI, so they are inputs (emitted as flags) AND same-named
# passthrough outputs. File-typed (not str) so they behave like ragavi-vis'
# `htmlname`: the container binds their parent dir, and under a sandbox they
# get absolutized back to the workspace / their parent dir pre-created --
# str-typed write targets get neither, so ragavi crashes writing a relative
# path into the empty sandbox cwd (no `mkdir -p` of its own output stem).
_GAINS_FIELDS: dict[str, FieldSpec] = {
    "table": (
        "List[File]",
        True,
        None,
        ParamMeta(info="Gain table(s) to plot. Specify space separated list for multiple."),
    ),
    "ant": (
        "str",
        False,
        None,
        ParamMeta(
            info="Plot only a specific antenna, or comma-separated list of antennas. Defaults to all.",
        ),
    ),
    "corr": (
        "str",
        False,
        None,
        ParamMeta(info="Correlation index(ices) to plot. Defaults to all."),
    ),
    "cmap": (
        "str",
        False,
        "coolwarm",
        ParamMeta(info="Matplotlib colour map to use for antennas. Defaults to coolwarm."),
    ),
    "ddid": ("str", False, None, ParamMeta(info="Spectral window to plot. Defaults to all.")),
    "debug": ("bool", False, None, ParamMeta(info="Enable debugging messages.")),
    "doplot": (
        "str",
        False,
        None,
        ParamMeta(
            info="Y-axes to plot: amplitude & phase (ap), real and imaginary (ri), or (all). Defaults to ap.",
        ),
    ),
    "field": (
        "List[str]",
        False,
        None,
        ParamMeta(info="Field ID(s) / NAME(s) to plot. Defaults to all."),
    ),
    "gaintype": (
        "List[str]",
        False,
        None,
        ParamMeta(
            info="Type of gain table(s) to be plotted (e.g. K/G/B/F/D). Table type is auto-detected.",
        ),
    ),
    "logfile": (
        "str",
        False,
        None,
        ParamMeta(info="File in which to store logs. Default is ragavi.log."),
    ),
    "xaxis": (
        "str",
        False,
        None,
        ParamMeta(
            info="Choose an x-axis for the plots, otherwise an appropriate one is chosen automatically.",
        ),
    ),
    "t0": (
        "float",
        False,
        None,
        ParamMeta(info="Min time to plot [in seconds]. Defaults to full range."),
    ),
    "t1": (
        "float",
        False,
        None,
        ParamMeta(info="Max time to plot [in seconds]. Defaults to full range."),
    ),
    "taql": ("str", False, None, ParamMeta(info="TAQL where clause.")),
    "htmlname": (
        "File",
        False,
        None,
        ParamMeta(info="Output HTML file name (with or without .html suffix)."),
    ),
    "plotname": (
        "File",
        False,
        None,
        ParamMeta(
            info="Static output file name (with suffix). '.png' or '.svg' determines the output type.",
        ),
    ),
}

_GAINS_OUTPUTS: dict[str, FieldSpec] = {
    # File to match the same-named File inputs they pass through (filled from
    # the input Path value), mirroring ragavi-vis' `htmlname` output.
    "htmlname": ("File", False, None),
    "plotname": ("File", False, None),
}

gains = define_cab(
    "ragavi-gains",
    "ragavi-gains",
    images.RAGAVI,
    _GAINS_FIELDS,
    outputs=_GAINS_OUTPUTS,
    policies=Policies(prefix="--"),
    info="ragavi-gains: plots of gain tables (https://ragavi.readthedocs.io)",
)
