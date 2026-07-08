"""ragavi (ragavi-vis) -- interactive Bokeh-based MS visibility plots
(https://ragavi.readthedocs.io).

Ported field-by-field from cult-cargo's ragavi_vis.yml (flat, static
schema).
"""

from __future__ import annotations

from shinobi.steps.schema import ParamMeta, Policies

from dosho import images
from dosho._builder import define_cab

_FIELDS: dict[str, tuple[str, bool, object]] = {
    "ms": ("MS", True, None),
    "xaxis": ("str", True, None),
    "yaxis": ("str", True, None),
    "canvas_height": ("int", False, None),
    "canvas_width": ("int", False, None),
    "cbin": ("int", False, None),
    "ant": ("str", False, None),
    "chan": ("str", False, None),
    "chunks": ("str", False, None),
    "cmap": ("str", False, None),
    "colour_axis": ("str", False, None),
    "cols": ("int", False, None),
    "corr": ("str", False, None),
    "data_column": ("str", False, "DATA"),
    "debug": ("bool", False, None),
    "ddid": ("str", False, None),
    "field": ("str", False, None),
    "iter_axis": ("str", False, None),
    "logfile": ("str", False, None),
    "mem_limit": ("str", False, None),
    "include_flagged": ("bool", False, None),
    "num_cores": ("int", False, None),
    "scan": ("str", False, None),
    "taql": ("str", False, None),
    "tbin": ("float", False, None),
    "xmin": ("float", False, None),
    "xmax": ("float", False, None),
    "ymin": ("float", False, None),
    "ymax": ("float", False, None),
}

_FIELD_META: dict[str, ParamMeta] = {
    "ms": ParamMeta(info="MS to plot."),
    "xaxis": ParamMeta(info="X-axis to plot."),
    "yaxis": ParamMeta(info="Y-axis to plot."),
    "canvas_height": ParamMeta(
        nom_de_guerre="canvas-height", info="Set height of the resulting image."
    ),
    "canvas_width": ParamMeta(
        nom_de_guerre="canvas-width", info="Set width of the resulting image."
    ),
    "cbin": ParamMeta(info="Size of channel bins over which to average."),
    "ant": ParamMeta(info="Select baselines where ANTENNA1 corresponds to the supplied antenna(s)"),
    "chan": ParamMeta(info="Channels to select. Defaults to all."),
    "chunks": ParamMeta(
        info="Chunk sizes to be applied to the dataset. Defaults to 5,000 in the row axis."
    ),
    "cmap": ParamMeta(info="Colour or colour map to use. Defaults to blues."),
    "colour_axis": ParamMeta(nom_de_guerre="colour-axis", info="Select column to colourise by."),
    "cols": ParamMeta(info="Number columns in grid if iteration is active. Defaults to 5."),
    "corr": ParamMeta(
        info="Correlation index or subset to plot. Can be specified using normal python slicing syntax. Defaults to all."
    ),
    "data_column": ParamMeta(nom_de_guerre="data-column", info="MS column to use for data."),
    "debug": ParamMeta(info="Enable debugging messages"),
    "ddid": ParamMeta(
        info="DATA_DESC_ID(s) /spw to select. Can be specified as e.g. 5, 5,6,7, 5~7 (inclusive range), 5:8 (exclusive range), 5:(from 5 to last). Defaults to all"
    ),
    "field": ParamMeta(
        info="Field ID(s) / NAME(s) to plot. Can be specified as '0', '0,2,4', '0~3' (inclusive range), '0:3' (exclusive range), '3:' (from 3 to last) or using a field name or comma separated field names. Defaults to all."
    ),
    "iter_axis": ParamMeta(nom_de_guerre="iter-axis", info="Select column to iterate by."),
    "logfile": ParamMeta(info="Desired name of logfile. Default is ragavi.log"),
    "mem_limit": ParamMeta(
        nom_de_guerre="mem-limit", info="Memory limit per core. Default is 1GB."
    ),
    "include_flagged": ParamMeta(
        nom_de_guerre="include-flagged",
        info="Include flagged data in the generated plot. Default is false",
    ),
    "num_cores": ParamMeta(
        nom_de_guerre="num-cores",
        info="Number of CPU cores to be used by Dask. Defaults to 10 or less cores",
    ),
    "scan": ParamMeta(info="Scan Number to select. Defaults to all."),
    "taql": ParamMeta(info="TAQL where clause"),
    "tbin": ParamMeta(info="Time in seconds over which to average."),
    "xmin": ParamMeta(info="Minimum x value to plot"),
    "xmax": ParamMeta(info="Maximum x value to plot"),
    "ymin": ParamMeta(info="Minimum y value to plot"),
    "ymax": ParamMeta(info="Maximum y value to plot"),
    "htmlname": ParamMeta(info="Output HTML file name (without .html suffix)"),
}

_OUTPUTS: dict[str, tuple[str, bool, object]] = {
    "htmlname": ("str", False, None),
}

ragavi = define_cab(
    "ragavi",
    "ragavi-vis",
    images.RAGAVI,
    _FIELDS,
    outputs=_OUTPUTS,
    field_meta=_FIELD_META,
    policies=Policies(prefix="--"),
    info="ragavi-vis: interactive Bokeh-based MS visibility plots (https://ragavi.readthedocs.io)",
)
