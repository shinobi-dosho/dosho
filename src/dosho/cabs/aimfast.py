"""aimfast -- astronomical image fidelity assessment tool
(https://github.com/Athanaseus/aimfast).

Ported field-by-field from `aimfast --help` (aimfast 1.3.4). aimfast's real
CLI is considerably larger than cult-cargo's `aimfast.yml` (which only
covers ~12 of aimfast's ~65 top-level flags) -- this port covers the full
top-level `aimfast [options]` invocation, cross-checked against the real
`argparse` usage/arity of each flag. It does not model the separate
`aimfast source-finder ...` subcommand (a distinct sub-parser with its own
argument set) -- neither did cult-cargo's version, and that's a big enough
surface to be its own follow-up cab if a pipeline ever needs it.

nargs=2/nargs='+' flags (`--compare-models`, `--compare-residuals`,
`--compare-residual-subimages`, the flux/position label lists) use
`repeat_as_tokens` -- one flag occurrence, then each item as its own bare
token (`--compare-models a.lsm.html b.lsm.html`), matching argparse's own
multi-value-per-flag arity. `-y-mojar-labels-size` is aimfast's own typo
(not a transcription error here) -- `nom_de_guerre` preserves the real flag
verbatim.
"""

from __future__ import annotations

from shinobi.steps.schema import ParamMeta, Policies

from dosho import images
from dosho._builder import FieldSpec, define_cab

_FIELDS: dict[str, FieldSpec] = {
    "compare_models": (
        "List[File]",
        False,
        None,
        ParamMeta(
            nom_de_guerre="compare-models",
            info="List of tigger model (text/lsm.html) files to compare, "
            "e.g. --compare-models model1.lsm.html model2.lsm.html",
            repeat_as_tokens=True,
        ),
    ),
    "compare_images": (
        "List[File]",
        False,
        None,
        ParamMeta(
            nom_de_guerre="compare-images",
            info="List of restored image (fits) files to compare (runs a source finder first)",
            repeat_as_tokens=True,
        ),
    ),
    "compare_online": (
        "File",
        False,
        None,
        ParamMeta(
            nom_de_guerre="compare-online",
            info="Catalog model (html/ascii, fits) or restored image (fits) file to compare "
            "with an online catalog",
        ),
    ),
    "compare_residuals": (
        "List[File]",
        False,
        None,
        ParamMeta(
            nom_de_guerre="compare-residuals",
            info="List of noise-like (fits) files to compare, "
            "e.g. --compare-residuals residual1.fits residual2.fits",
            repeat_as_tokens=True,
        ),
    ),
    "compare_residual_subimages": (
        "List[File]",
        False,
        None,
        ParamMeta(
            nom_de_guerre="compare-residual-subimages",
            info="List of noise-like (fits) files to compare (sub-image variant)",
            repeat_as_tokens=True,
        ),
    ),
    "tigger_model": (
        "File",
        False,
        None,
        ParamMeta(
            nom_de_guerre="tigger-model",
            info="Name of the tigger model lsm.html file or any supported catalog",
        ),
    ),
    "restored_image": (
        "File",
        False,
        None,
        ParamMeta(nom_de_guerre="restored-image", info="Name of the restored image fits file"),
    ),
    "psf_image": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="psf-image",
            info="Name of the point spread function file or psf size in arcsec",
        ),
    ),
    "residual_image": (
        "File",
        False,
        None,
        ParamMeta(nom_de_guerre="residual-image", info="Name of the residual image fits file"),
    ),
    "mask_image": (
        "File",
        False,
        None,
        ParamMeta(nom_de_guerre="mask-image", info="Name of the mask image fits file"),
    ),
    "fidelity_results": (
        "File",
        False,
        None,
        ParamMeta(
            nom_de_guerre="fidelity-results", info="aimfast fidelity results file (JSON format)"
        ),
    ),
    "input_regions": (
        "File",
        False,
        None,
        ParamMeta(nom_de_guerre="input-regions", info="Region file with regions to generate stats"),
    ),
    "config": (
        "File",
        False,
        None,
        ParamMeta(info="Config file to run source finder of choice (YAML format)"),
    ),
    "source_finder": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="source-finder", info="Source finder to run if comparing restored images"
        ),
    ),
    "online_catalog_name": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="online-catalog-name", info="Prefix of output catalog file name"),
    ),
    "online_catalog": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="online-catalog", info="Online catalog to compare local image/model"
        ),
    ),
    "centre_coord": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="centre_coord",
            info='Centre of online catalog to compare local image/model in "RA hh:mm:ss, Dec deg:min:sec"',
        ),
    ),
    "width": (
        "float",
        False,
        None,
        ParamMeta(info="Field of view width to query online catalog in degrees, e.g. 3.0d"),
    ),
    "normality_test": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="normality-test",
            info="Name of model to use for normality testing (shapiro, normaltest)",
        ),
    ),
    "data_range": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="data-range", info="Data range to perform normality testing"),
    ),
    "threshold": (
        "float",
        False,
        None,
        ParamMeta(
            info="Get stats of channels with pixel flux above thresh in Jy/Beam; also filters online-catalog sources"
        ),
    ),
    "channels": (
        "str",
        False,
        None,
        ParamMeta(info='Get stats of specified channels, e.g. "10~20;100~1000"'),
    ),
    "centre_pixels_size": (
        "List[str]",
        False,
        None,
        ParamMeta(
            nom_de_guerre="centre-pixels-size",
            info="List of subimage centre pixels and their sizes to compute stats, e.g. 500,500,20 200,10,5",
            repeat_as_tokens=True,
        ),
    ),
    "data_points": (
        "int",
        False,
        None,
        ParamMeta(
            nom_de_guerre="data-points", info="Data points to sample the residual/noise image"
        ),
    ),
    "flux_plot": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="flux-plot", info="Type of plot for flux comparison of the two catalogs"
        ),
    ),
    "units": ("str", False, None, ParamMeta(info="Units to represent the results")),
    "decimals": (
        "int",
        False,
        None,
        ParamMeta(info="Number of decimal places to round off results"),
    ),
    "only_off_axis": (
        "float",
        False,
        None,
        ParamMeta(
            nom_de_guerre="only-off-axis",
            info="Plot only cross-matched sources with distance from the phase centre less than this value",
        ),
    ),
    "area_factor": (
        "float",
        False,
        None,
        ParamMeta(
            nom_de_guerre="area-factor",
            info="Factor to multiply the beam area to get target peak area",
        ),
    ),
    "fov_factor": (
        "float",
        False,
        None,
        ParamMeta(
            nom_de_guerre="fov-factor",
            info="Factor to multiply the field of view for random points (0.0-1.0)",
        ),
    ),
    "tolerance": (
        "float",
        False,
        None,
        ParamMeta(info="Tolerance to cross-match sources in arcsec"),
    ),
    "all_source": (
        "bool",
        False,
        False,
        ParamMeta(
            nom_de_guerre="all-source",
            info="Compare all sources irrespective of shape, otherwise only point-like sources are compared",
        ),
    ),
    "closest": (
        "bool",
        False,
        None,
        ParamMeta(info="Use the closest source only when cross matching sources"),
    ),
    "shape_limit": (
        "float",
        False,
        None,
        ParamMeta(
            nom_de_guerre="shape-limit",
            info="Cross-match only sources with a maj-axis equal or less than this value",
        ),
    ),
    "label": (
        "str",
        False,
        None,
        ParamMeta(
            info="Use this label instead of the FITS image path when saving data as JSON file"
        ),
    ),
    "x_col_data": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="x-col-data", info="Catalog column name to plot on the x-axis"),
    ),
    "y_col_data": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="y-col-data", info="Catalog column name to plot on the y-axis"),
    ),
    "x_col_err_data": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="x-col-err-data",
            info="Catalog column name to plot error data on the x-axis",
        ),
    ),
    "y_col_err_data": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="y-col-err-data",
            info="Catalog column name to plot error data on the y-axis",
        ),
    ),
    "x_label": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="x-label", info="x-axis labels for the plot"),
    ),
    "y_label": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="y-label", info="y-axis labels for the plots"),
    ),
    "plot_title": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="plot-title", info="Title label for the basic catalog plot"),
    ),
    "flux_xlabels": (
        "List[str]",
        False,
        None,
        ParamMeta(
            nom_de_guerre="flux-xlabels",
            info="x-axis labels for the Flux plots",
            repeat_as_tokens=True,
        ),
    ),
    "flux_ylabels": (
        "List[str]",
        False,
        None,
        ParamMeta(
            nom_de_guerre="flux-ylabels",
            info="y-axis labels for the Flux plots",
            repeat_as_tokens=True,
        ),
    ),
    "flux_plot_titles": (
        "List[str]",
        False,
        None,
        ParamMeta(
            nom_de_guerre="flux-plot-title",
            info="Title labels for the Flux plots",
            repeat_as_tokens=True,
        ),
    ),
    "position_xlabels1": (
        "List[str]",
        False,
        None,
        ParamMeta(
            nom_de_guerre="position-xlabels1",
            info="x-axis labels for the comparison position plots",
            repeat_as_tokens=True,
        ),
    ),
    "position_ylabels1": (
        "List[str]",
        False,
        None,
        ParamMeta(
            nom_de_guerre="position-ylabels1",
            info="y-axis labels for the comparison position plots",
            repeat_as_tokens=True,
        ),
    ),
    "position_plot_title1": (
        "List[str]",
        False,
        None,
        ParamMeta(
            nom_de_guerre="position-plot-title1",
            info="Title labels for the comparison position plots",
            repeat_as_tokens=True,
        ),
    ),
    "position_xlabels2": (
        "List[str]",
        False,
        None,
        ParamMeta(
            nom_de_guerre="position-xlabels2",
            info="x-axis labels for the overlay position plots",
            repeat_as_tokens=True,
        ),
    ),
    "position_ylabels2": (
        "List[str]",
        False,
        None,
        ParamMeta(
            nom_de_guerre="position-ylabels2",
            info="y-axis labels for the overlay position plots",
            repeat_as_tokens=True,
        ),
    ),
    "position_plot_title2": (
        "List[str]",
        False,
        None,
        ParamMeta(
            nom_de_guerre="position-plot-title2",
            info="Title labels for the overlay position plots",
            repeat_as_tokens=True,
        ),
    ),
    "colorbar_major_labels_size": (
        "int",
        False,
        None,
        ParamMeta(nom_de_guerre="colorbar-major-labels-size", info="x-axis label size for plots"),
    ),
    "colorbar_labels_size": (
        "int",
        False,
        None,
        ParamMeta(nom_de_guerre="colorbar-labels-size", info="x-axis label size for plots"),
    ),
    "xlabels_size": (
        "int",
        False,
        None,
        ParamMeta(nom_de_guerre="xlabels-size", info="x-axis label size for plots"),
    ),
    "ylabels_size": (
        "int",
        False,
        None,
        ParamMeta(nom_de_guerre="ylabels-size", info="y-axis label size for plots"),
    ),
    "x_major_labels_size": (
        "int",
        False,
        None,
        ParamMeta(nom_de_guerre="x-major-labels-size", info="x-axis major label size for plots"),
    ),
    # aimfast's own flag has a typo ("mojar", not "major") -- preserved verbatim.
    "y_major_labels_size": (
        "int",
        False,
        None,
        ParamMeta(nom_de_guerre="y-mojar-labels-size", info="y-axis major label size for plots"),
    ),
    "legend_font_size": (
        "int",
        False,
        None,
        ParamMeta(nom_de_guerre="legend-font-size", info="Label size for legends on the plots"),
    ),
    "plot_title_size": (
        "int",
        False,
        None,
        ParamMeta(nom_de_guerre="plot-title-size", info="Title label size for plots"),
    ),
    "html_prefix": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="html-prefix", info="Prefix of output html files"),
    ),
    "outfile": (
        "File",
        False,
        None,
        ParamMeta(info="Name of output file name (default: fidelity_results.json)"),
    ),
    "save_svg": (
        "bool",
        False,
        None,
        ParamMeta(nom_de_guerre="save-svg", info="Save plots in SVG format"),
    ),
}

aimfast = define_cab(
    "aimfast",
    "aimfast",
    images.AIMFAST,
    _FIELDS,
    outputs={"outfile": ("File", False, None)},
    policies=Policies(prefix="--"),
    info="aimfast: astronomical image fidelity assessment tool (https://github.com/Athanaseus/aimfast)",
)
