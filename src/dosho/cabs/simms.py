"""simms -- simms 3.0's sub-commands.

As of simms 3.0 (`wits-cfa/simms`), `skysim`, `telsim` and `primary_beam`
are authored **inside simms itself** as `@shinobi.pystep` functions
(`simms.apps.{skysim,telsim,primary_beam}`), each returning a typed
outputs model and delegating to its module's own `runit(opts)`. dosho
therefore consumes them as pysteps rather than shelling out to the `simms`
CLI -- the same `@shinobi.pystep` + `ctx.import_func` pattern
`casatasks.py` uses (see its docstring for the full security/architecture
rationale): the wrappers below run *inside the simms container* at
step-execution time, importing `simms.apps.<app>.runit` there and never on
the host (the simms app modules `import dask/daskms/numpy` at top level, so
importing them on the host -- where dosho's registry discovery runs -- is
exactly what this pattern avoids).

Each wrapper transcribes its simms counterpart's signature field-for-field
(same names, same `Literal` choices, same `Field(json_schema_extra=
{"abbreviation": ...})` CLI short flags, same defaults) so validation and
`ninja run --help` match simms exactly, then builds the `SimpleNamespace`
`runit` expects and returns the passthrough MS/output path. Keeping the
parameter names identical to simms' own is load-bearing: `runit` reads them
straight off the namespace, just as simms' own pystep does with
`SimpleNamespace(**locals())`.

* `skysim` -- simms 3.0's sky-model visibility simulator (ASCII/FITS/WSClean
  skymodels, optional primary beam and thermal noise).
* `telsim` -- simms 3.0's telescope simulator: creates a brand-new MS from
  scratch given `telescope`/`direction`/timing/frequency parameters
  (optional SEFD/Tsys noise). Known `telescope` values include
  `"meerkat"`/`"meerkat-plus"`.
* `primary_beam` -- simms 3.0's primary-beam utilities
  (`to-fits`/`tag-ms`/`apply`/`correct`); no visibility simulation.
* `simms_classic` -- the original (pre-3.0) `simms` command, a genuinely
  different tool with its own `simms-classic` image and no sub-command in
  its `command`. Still a real binary, so it stays a `define_cab` `Cab`
  (not a pystep). Exported as `simms_classic` rather than `simms` to avoid
  shadowing this module's own name; its backing image is flagged deprecated
  in `images.yaml` ("unused by any worker -- slated for removal"), so prefer
  `telsim` for new MS-creation use.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Literal

import shinobi
from pydantic import BaseModel, Field

from dosho import images
from dosho._builder import FieldSpec, define_cab
from shinobi.steps.schema import ParamMeta, Policies


class SkysimOutputs(BaseModel):
    """Passthrough MS path, so `skysim` can be wired into a shinobi Recipe."""

    ms: str | None = None


class TelsimOutputs(BaseModel):
    """Passthrough MS path, so `telsim` can be wired into a shinobi Recipe."""

    ms: str | None = None


class PrimaryBeamOutputs(BaseModel):
    """Passthrough output path of the primary-beam operation."""

    output: str | None = None


@shinobi.pystep(
    name="simms-skysim",
    image=images.SIMMS,
    info="Predict model visibilities from a sky model into an MS (simms 3.0 skysim).",
)
def skysim(
    ctx,
    ms: str,
    ascii_sky: str | None = Field(
        None,
        description="Catalogue of sources. See the documentation for accepted units.",
        json_schema_extra={"abbreviation": "as"},
    ),
    fits_sky: str | None = Field(
        None,
        description="FITS file (or directory of Stokes cubes) containing the sky model.",
        json_schema_extra={"abbreviation": "fs"},
    ),
    wsclean_sky: str | None = Field(
        None,
        description="WSClean component list (point and Gaussian components, Stokes I).",
        json_schema_extra={"abbreviation": "ws"},
    ),
    fits_sky_interp: Literal["nearest", "linear", "cubic"] = Field(
        "linear",
        description="Interpolation method when the MS and FITS frequency grids do not match and the cube is kept.",
        json_schema_extra={"abbreviation": "fsi"},
    ),
    polarisation: bool = Field(
        True,
        description="Simulate all available Stokes parameters. If false, only Stokes I.",
        json_schema_extra={"abbreviation": "pol"},
    ),
    pol_basis: Literal["linear", "circular"] = Field(
        "linear", description="Polarization basis for the simulation."
    ),
    pixel_tol: float = Field(
        1e-7,
        description="Minimum brightness for a pixel to be considered in direct Fourier transform.",
        json_schema_extra={"abbreviation": "pt"},
    ),
    fits_spectrum: Literal["auto", "flat", "poly", "cube"] = Field(
        "auto",
        description="How the FITS sky model varies with frequency.",
        json_schema_extra={"abbreviation": "fsp"},
    ),
    fits_spi: list[str] | None = Field(
        None,
        description="Spectral-index (and higher-order) coefficient maps, ordered c1, c2, ... Requires --fits-ref-freq.",
    ),
    fits_ref_freq: float | None = Field(
        None,
        description="Reference frequency (Hz) of an analytic FITS spectrum. Defaults to the MS band centre.",
        json_schema_extra={"abbreviation": "frf"},
    ),
    fits_spectrum_order: int = Field(
        2, description="Order of the fitted log-polynomial spectrum. 1 is a plain spectral index."
    ),
    predict_backend: Literal["auto", "dft", "fft", "perchan"] = Field(
        "auto", description="Backend for FITS sky model prediction."
    ),
    fft_precision: Literal["single", "double"] = Field(
        "double", description="Precision of the FFT calculation."
    ),
    do_wstacking: bool = Field(
        True, description="Whether to use w-stacking for FFT-based visibility prediction."
    ),
    ascii_delimiter: str | None = Field(
        None,
        description="Delimiter used in the ascii-sky.",
        json_schema_extra={"abbreviation": "ad"},
    ),
    column: str = Field(
        "DATA", description="Data column for simulation.", json_schema_extra={"abbreviation": "col"}
    ),
    nworkers: int = Field(4, description="Number of workers (one per CPU)."),
    row_chunks: int = Field(
        10000,
        description="Number of rows per chunk. Controls the row-wise task/memory granularity.",
        json_schema_extra={"abbreviation": "rcs"},
    ),
    chan_chunks: int | None = Field(
        None,
        description="Number of channels per chunk. Defaults to all channels in one chunk.",
        json_schema_extra={"abbreviation": "ccs"},
    ),
    primary_beam: str | None = Field(
        None,
        description="Beam-config YAML mapping each ANTENNA telescope name to a beam model. Requires a linear pol basis.",
        json_schema_extra={"abbreviation": "pb"},
    ),
    beam_band: Literal["UHF", "L"] = Field(
        "L", description="Default band for JimBeam entries that omit an explicit model/CSV."
    ),
    beam_pa_step: float = Field(
        1.0, description="Spacing (degrees) of the parallactic-angle grid the beam is sampled on."
    ),
    beam_grid_max_gib: float = Field(
        4.0,
        description="Hard ceiling (GiB) on the sampled beam grid held in memory for the whole run.",
    ),
    beam_jones: Literal["diagonal", "full"] = Field(
        "diagonal",
        description="Primary-beam application for component skies: per-feed voltage or full 2x2 E-Jones.",
    ),
    telescope_name_column: str = Field(
        "TELESCOPE_NAME",
        description="ANTENNA-table column holding the per-antenna telescope/type label that maps to a beam model.",
        json_schema_extra={"abbreviation": "tnc"},
    ),
    field_id: int = Field(0, description="Field ID.", json_schema_extra={"abbreviation": "fi"}),
    spw_id: int = Field(0, description="Spectral Window ID."),
    sefd: float | None = Field(None, description="Add noise using this SEFD value."),
    seed: int | None = Field(
        None, description="Random seed for the thermal noise. Omit for a non-reproducible run."
    ),
    ascii_species: Literal["bdsf_gaul", "aegean", "wsclean"] | None = Field(
        None, description="Non-simms sky model type.", json_schema_extra={"abbreviation": "asp"}
    ),
    input_column: str | None = Field(
        None, description="Input column (see --mode).", json_schema_extra={"abbreviation": "ic"}
    ),
    mode: Literal["sim", "add", "subtract"] = Field(
        "sim",
        description="Simulation mode: 'sim' creates a new column, 'add' adds to it, 'subtract' subtracts from it.",
    ),
    source_schema: str | None = Field(
        None,
        description="Custom source schema (YAML) mapping columns in a custom sky model to the columns simms expects.",
    ),
    log_level: str = Field("INFO", description="Logging verbosity."),
) -> SkysimOutputs:
    """Predict model visibilities from a sky model into an MS.

    Transcribed from `simms.apps.skysim.skysim`; runs simms' own
    `simms.apps.skysim.runit` inside the simms container.
    """
    opts = SimpleNamespace(**{k: v for k, v in locals().items() if k != "ctx"})
    ctx.import_func("runit", "simms.apps.skysim")(opts)
    return SkysimOutputs(ms=ms)


@shinobi.pystep(
    name="simms-telsim",
    image=images.SIMMS,
    info="Create an empty Measurement Set from a telescope layout (simms 3.0 telsim).",
)
def telsim(
    ctx,
    ms: str,
    telescope: str = Field(
        ...,
        description="Name of telescope you are simulating.",
        json_schema_extra={"abbreviation": "tel"},
    ),
    subarray_list: list[str] | None = Field(
        None,
        description="Custom list of antennas to use, e.g. M000,M005,SKA009. Must be a subarray of the given telescope.",
        json_schema_extra={"abbreviation": "sublist"},
    ),
    subarray_range: list[int] | None = Field(
        None,
        description="Custom range of antenna indices to use, e.g. start,end,step (step optional). Must be a subarray of the given telescope.",
        json_schema_extra={"abbreviation": "subrange"},
    ),
    subarray_file: str | None = Field(
        None,
        description="File listing custom antennas to use (antnames key, e.g. [M000,M005,SKA009]). Must be a subarray of the given telescope.",
        json_schema_extra={"abbreviation": "subfile"},
    ),
    telescope_name_column: str = Field(
        "TELESCOPE_NAME",
        description="Name of the ANTENNA-table column that holds the per-antenna telescope/type label (used by skysim to select a primary beam).",
        json_schema_extra={"abbreviation": "tnc"},
    ),
    direction: str = Field(
        "J2000,1h0m0s,-31d0m0s",
        description="Direction of field centre for MS, e.g. J2000,0h24m20s,-30d12m33s.",
        json_schema_extra={"abbreviation": "dir"},
    ),
    starttime: str | None = Field(
        None,
        description="Observation start time in UTC, e.g. '2024-03-14T06:15:10'. Default is the current machine time.",
        json_schema_extra={"abbreviation": "st"},
    ),
    startha: float | None = Field(
        None,
        description="Hour angle at start of observation. Can be used instead of date.",
        json_schema_extra={"abbreviation": "sha"},
    ),
    dtime: float = Field(
        8,
        description="Integration/exposure time in seconds.",
        json_schema_extra={"abbreviation": "dt"},
    ),
    ntime: int = Field(
        10, description="Number of time slots for MS.", json_schema_extra={"abbreviation": "nt"}
    ),
    startfreq: str | float = Field(
        "1420MHz",
        description="Centre of first frequency channel, e.g 0.55GHz. Hertz assumed if no units.",
        json_schema_extra={"abbreviation": "sf"},
    ),
    dfreq: str | float = Field(
        "1MHz",
        description="Channel width, e.g 2.4MHz. Hertz assumed if no units.",
        json_schema_extra={"abbreviation": "df"},
    ),
    nchan: int = Field(
        9, description="Number of frequency channels.", json_schema_extra={"abbreviation": "nc"}
    ),
    correlations: str = Field(
        "XX,YY",
        description="Feed correlations for MS, e.g. 'XX,YY'.",
        json_schema_extra={"abbreviation": "corr"},
    ),
    nworkers: int = Field(4, description="Number of workers (one per CPU)."),
    rowchunks: int = Field(
        50000,
        description="Number of chunks to divide the data into; more chunks improves computation speed.",
        json_schema_extra={"abbreviation": "rc"},
    ),
    column: str = Field(
        "MODEL_DATA",
        description="The column in which to corrupt the visibilities with noise.",
        json_schema_extra={"abbreviation": "col"},
    ),
    sefd: float | None = Field(None, description="Antenna SEFD (one value for all frequencies)."),
    tsys_over_eta: float | None = Field(
        None,
        description="Antenna system temperature over aperture efficiency (one value for all frequencies).",
        json_schema_extra={"abbreviation": "tos"},
    ),
    sensitivity_file: str | None = Field(
        None,
        description="File with antenna spectral sensitivity info. Keys: 'freq, tsys, sefd, tsys_over_eta'.",
        json_schema_extra={"abbreviation": "sfile"},
    ),
    low_source_limit: float | None = Field(
        None,
        description="Minimum reliable source elevation (deg); data below this is flagged.",
        json_schema_extra={"abbreviation": "lsl"},
    ),
    high_source_limit: float | None = Field(
        None,
        description="Maximum reliable source elevation (deg); data above this is flagged.",
        json_schema_extra={"abbreviation": "hsl"},
    ),
    freq_range: str | None = Field(
        None,
        description="A list of start frequency, end frequency, and number of channels, e.g. startfreq,endfreq,nchan.",
        json_schema_extra={"abbreviation": "fr"},
    ),
    smooth: str | None = Field(
        None,
        description="SEFD fitting option when a sensitivity file is given: 'polyn' or 'spline'.",
    ),
    fit_order: int | None = Field(
        None,
        description="Fitting order used when approximating the MS-frequency SEFDs.",
        json_schema_extra={"abbreviation": "fo"},
    ),
    log_level: str = Field("INFO", description="Logging verbosity."),
) -> TelsimOutputs:
    """Create an empty Measurement Set from a telescope layout.

    Transcribed from `simms.apps.telsim.telsim`; runs simms' own
    `simms.apps.telsim.runit` inside the simms container.
    """
    opts = SimpleNamespace(**{k: v for k, v in locals().items() if k != "ctx"})
    ctx.import_func("runit", "simms.apps.telsim")(opts)
    return TelsimOutputs(ms=ms)


_SIMMS_CLASSIC_FIELDS: dict[str, FieldSpec] = {
    "msname": (
        "MS",
        True,
        None,
        ParamMeta(nom_de_guerre="name", info="Name of MS file to be created"),
    ),
    "telescope": (
        "str",
        True,
        None,
        ParamMeta(nom_de_guerre="tel", info="Name of telescope that being simulated"),
    ),
    "antenna_file": (
        "File",
        False,
        None,
        ParamMeta(
            nom_de_guerre="antenna-file",
            info="File that contains antenna coordinates",
        ),
    ),
    "type": ("str", False, "casa", ParamMeta(info="Type of antenna file")),
    "coord_sys": (
        "str",
        False,
        "itrf",
        ParamMeta(
            nom_de_guerre="coord-sys",
            info="Coordinate system of antenna coordinates in 'antenna-file'. Only needed if 'type' is 'ascii'; CASA tables are assumed to be in ITRF coords",
        ),
    ),
    "lon_lat_elv": (
        "List[float]",
        False,
        None,
        ParamMeta(
            nom_de_guerre="lon-lat-elv",
            info="Reference position of telescope. Comma seperated longitude,lattitude and elevation 'deg,deg,m'. Elevation is not crucial, lon,lat should be enough. If not specified, we'll try to get this info from the CASA database (assuming that your telescope is known to CASA)",
        ),
    ),
    "noup": (
        "bool",
        False,
        False,
        ParamMeta(
            info="Enable this to indicate that your ENU file does not have an 'up' dimension",
        ),
    ),
    "direction": (
        "List[str]",
        False,
        "J2000,0deg,-30deg",
        ParamMeta(
            info="Pointing direction. Example J2000,0h0m0s,-30d0m0d. Option --direction may be specified multiple times for multiple pointings. Provide a list of directions for multiple pointings; each pointing will have a unique field ID",
        ),
    ),
    "synthesis": ("float", False, 4, ParamMeta(info="Synthesis time in hours")),
    "scan_length": (
        "float",
        False,
        None,
        ParamMeta(
            nom_de_guerre="scan-length",
            info="Duration of a single scan in hours. Default is the entire observation (synthesis)",
        ),
    ),
    "dtime": ("int", False, 2, ParamMeta(info="Integration time in seconds")),
    "freq0": (
        "List[str]",
        False,
        "1.4GHz",
        ParamMeta(
            info="Start frequency. This is the middle of the first channel. Specify as val[unit]. E.g 700MHz, no unit => Hz. Use a comma seperated list for multiple start frequencies (for multiple subbands)",
        ),
    ),
    "dfreq": (
        "List[str]",
        False,
        "2MHz",
        ParamMeta(
            info="Channel width. Specify as val[unit]. E.g 700MHz, no unit => Hz. Use a comma separated list of channel widths (for multiple subbands)",
        ),
    ),
    "nband": ("int", False, 1, ParamMeta(info="Number of subbands")),
    "nchan": (
        "List[int]",
        False,
        1,
        ParamMeta(
            info="Number of channels. Can be used in tandem with 'freq0, dfreq, nband' to customise the partitioning of the subbands",
        ),
    ),
    "init_ha": (
        "float",
        False,
        None,
        ParamMeta(
            nom_de_guerre="init-ha",
            info="Initial hour angle. 'scan-length/2' is the default",
        ),
    ),
    "pol": ("str", False, "XX XY YX YY", ParamMeta(info="polarization")),
    "feed": ("str", False, "perfect X Y", ParamMeta(info="Feed type")),
    "scan_lag": (
        "float",
        False,
        0,
        ParamMeta(nom_de_guerre="scan-lag", info="Lag time between scans in hours"),
    ),
    "set_limits": (
        "bool",
        False,
        False,
        ParamMeta(
            nom_de_guerre="set-limits",
            info="Set telescope limits. Elevation and shadow limits. Works in tandem with 'shadow-limit, elevation-limit'",
        ),
    ),
    "elevation_limit": (
        "float",
        False,
        None,
        ParamMeta(
            nom_de_guerre="elevation-limit",
            info="Dish elevation limit. Will only be taken into account if 'set-limits' is enabled.",
        ),
    ),
    "shadow_limit": (
        "float",
        False,
        None,
        ParamMeta(
            nom_de_guerre="shadow-limit",
            info="Shadow limit. Will only be taken into account if 'set-limits' is enabled.",
        ),
    ),
    "auto_correlations": (
        "bool",
        False,
        False,
        ParamMeta(nom_de_guerre="auto-correlations", info="Don't flag autocorrelations"),
    ),
    "date": (
        "str",
        False,
        None,
        ParamMeta(
            info="Date of observation. Example UTC,2014/05/26 or UTC,2014/05/26/12:12:12: default is today (format EPOCH,yyyy/mm/dd/[h:m:s])",
        ),
    ),
}

simms_classic = define_cab(
    "simms",
    "simms",
    images.SIMMS_CLASSIC,
    _SIMMS_CLASSIC_FIELDS,
    # simms_classic's whole job is to create msname -- declare it as an
    # output so a dependent step can chain onto the new MS.
    outputs={"msname": ("MS", False, None)},
    policies=Policies(),
    info="simms (classic): simulate an empty MS from telescope/observation parameters (pre-3.0)",
)


@shinobi.pystep(
    name="simms-primary-beam",
    image=images.SIMMS,
    info="Primary-beam utilities (build/tag/apply/correct); no visibility simulation (simms 3.0).",
)
def primary_beam(
    ctx,
    mode: Literal["to-fits", "tag-ms", "apply", "correct"],
    beam_pattern: str | None = Field(
        None,
        description="Beam model: a cosine-taper CSV path, a built-in name, a band shorthand (L/UHF), or a FITS cube.",
        json_schema_extra={"abbreviation": "bp"},
    ),
    beam_band: Literal["UHF", "L"] = Field(
        "L", description="Default band for a built-in beam when beam-pattern omits one."
    ),
    beam_pa_step: float = Field(
        1.0, description="Parallactic-angle sampling step (degrees) for the time-averaged beam."
    ),
    ms: str | None = Field(
        None,
        description="Measurement set (time/PA range, array position and frequencies). Required for tag-ms/apply/correct.",
    ),
    fits_sky: str | None = Field(
        None,
        description="Input FITS image sky model (apply/correct).",
        json_schema_extra={"abbreviation": "fits"},
    ),
    ascii_sky: str | None = Field(
        None,
        description="Input ASCII component sky model (apply/correct).",
        json_schema_extra={"abbreviation": "ascii"},
    ),
    ascii_delimiter: str | None = Field(
        None,
        description="Delimiter used in the ascii-sky file. Defaults to whitespace.",
        json_schema_extra={"abbreviation": "ad"},
    ),
    source_schema: str | None = Field(
        None,
        description="Custom source schema (YAML) mapping the ascii-sky columns to the fields simms expects.",
    ),
    output: str | None = Field(
        None,
        description="Output path - FITS beam (to-fits) or beamed/corrected sky model (apply/correct).",
        json_schema_extra={"abbreviation": "o"},
    ),
    telescope_name_column: str = Field(
        "TELESCOPE_NAME",
        description="ANTENNA-table column holding the per-antenna telescope/type label (tag-ms).",
        json_schema_extra={"abbreviation": "tnc"},
    ),
    label: str | None = Field(
        None, description="Single telescope-name label applied to all antennas (tag-ms)."
    ),
    label_map: str | None = Field(
        None, description="YAML mapping antenna NAME -> telescope-name label (tag-ms)."
    ),
    from_layout: str | None = Field(
        None,
        description="simms layout whose per-antenna telescope_name is matched to the MS antenna names (tag-ms).",
    ),
    pb_cutoff: float = Field(
        0.1, description="In correct mode, blank (NaN) where the beam is below this level."
    ),
    field_id: int = Field(
        0,
        description="FIELD_ID whose phase centre and time span define the beam (apply/correct).",
        json_schema_extra={"abbreviation": "fi"},
    ),
    spw_id: int = Field(
        0,
        description="Spectral-window (DATA_DESC_ID) whose frequencies define the beam (apply/correct).",
    ),
    pixel_size: str = Field(
        "1arcmin", description="Angular pixel size for the to-fits grid, e.g. '1arcmin'."
    ),
    npix: int = Field(256, description="Number of pixels per side for the to-fits grid."),
    start_freq: str | None = Field(
        None,
        description="Start frequency of the to-fits cube, e.g. '856MHz'. Defaults to the beam's first frequency.",
        json_schema_extra={"abbreviation": "sf"},
    ),
    chan_width: str | None = Field(
        None,
        description="Channel width of the to-fits cube, e.g. '10MHz'. Defaults to spanning the beam range across nchan.",
        json_schema_extra={"abbreviation": "cw"},
    ),
    nchan: int | None = Field(
        None,
        description="Number of output channels in the to-fits cube. Defaults to the beam's channel count.",
        json_schema_extra={"abbreviation": "nc"},
    ),
    nworkers: int = Field(4, description="Number of worker threads."),
    log_level: str = Field("INFO", description="Logging verbosity."),
) -> PrimaryBeamOutputs:
    """Primary-beam utilities (build/tag/apply/correct); no visibility simulation.

    Transcribed from `simms.apps.primary_beam.primary_beam`; runs simms' own
    `simms.apps.primary_beam.runit` inside the simms container.
    """
    opts = SimpleNamespace(**{k: v for k, v in locals().items() if k != "ctx"})
    ctx.import_func("runit", "simms.apps.primary_beam")(opts)
    return PrimaryBeamOutputs(output=output)
