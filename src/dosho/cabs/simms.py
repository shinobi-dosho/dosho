"""simms -- simms 3.0's sub-commands, one module-level object per
sub-command (matching `casatasks.py`'s multi-export convention).

All three transcribed field-by-field from cult-cargo's simms.yml:

* `skysim` -- simms 3.0's sky-model visibility simulator, replacing
  caracal 1.x's separate simulator worker (see stimela-ninja/caracal
  migration notes: simulator -> simms 3.0 skysim).
* `telsim` -- simms 3.0's telescope/noise-only simulator (`simms telsim`,
  same `simms` image as `skysim` -- a sibling sub-command of the same
  binary, not a separate tool).
* `simms_classic` -- the original (pre-3.0) `simms` command, a genuinely
  different tool from `skysim`/`telsim` (own `simms-classic` image, no
  sub-command in its `command`) -- exported as `simms_classic` rather
  than `simms` to avoid shadowing this module's own name in
  `from dosho.cabs.simms import simms_classic`.
"""

from __future__ import annotations

from shinobi.steps.schema import ParamMeta, Policies

from dosho import images
from dosho._builder import define_cab

_SKYSIM_FIELDS: dict[str, tuple[str, bool, object]] = {
    "ms": ("MS", True, None),
    "ascii_sky": ("File", False, None),
    "fits_sky": ("Union[File, List[File]]", False, None),
    "fits_sky_interp": ("str", False, "nearest"),
    "polarisation": ("bool", False, True),
    "pol_basis": ("str", False, "linear"),
    "pixel_tol": ("float", False, "1e-7"),
    "fft_precision": ("str", False, "double"),
    "do_wstacking": ("bool", False, True),
    "ascii_delimiter": ("str", False, None),
    "column": ("str", False, "DATA"),
    "nworkers": ("int", False, 4),
    "row_chunks": ("int", False, 10000),
    "field_id": ("int", False, 0),
    "spw_id": ("int", False, 0),
    "sefd": ("float", False, None),
    "ascii_species": ("str", False, None),
    "input_column": ("str", False, None),
    "mode": ("str", False, "sim"),
    "source_schema": ("File", False, None),
}

_SKYSIM_FIELD_META: dict[str, ParamMeta] = {
    "ms": ParamMeta(info="Measurement set", positional=True),
    "ascii_sky": ParamMeta(
        nom_de_guerre="ascii-sky",
        info="Catalogue of sources. A full description of accepted units can be found in the documentation.",
    ),
    "fits_sky": ParamMeta(nom_de_guerre="fits-sky", info="FITS file(s) containing the sky model"),
    "fits_sky_interp": ParamMeta(
        nom_de_guerre="fits-sky-interp",
        info="Interpolation method when MS and FITS image grids do not match. Interpolation is only done within the overlap region.",
    ),
    "polarisation": ParamMeta(
        info="Simulate all available stokes parameters (correlations). If false, only consider stokes I"
    ),
    "pol_basis": ParamMeta(
        nom_de_guerre="pol-basis",
        info="Polarization basis for the simulation. The default is circular polarization.",
    ),
    "pixel_tol": ParamMeta(
        nom_de_guerre="pixel-tol",
        info="minimum brightness for a pixel to be considered in direct Fourier transform",
    ),
    "fft_precision": ParamMeta(
        nom_de_guerre="fft-precision",
        info="Precision of the FFT calculation. The default is double precision.",
    ),
    "do_wstacking": ParamMeta(
        nom_de_guerre="do-wstacking",
        info="Whether to use w-stacking for FFT-based visibility prediction.",
    ),
    "ascii_delimiter": ParamMeta(
        nom_de_guerre="ascii-delimiter", info="Delimiter that is used in the ascii-sky"
    ),
    "column": ParamMeta(info="Data column for simulation"),
    "nworkers": ParamMeta(info="Number of workers (one per CPU)"),
    "row_chunks": ParamMeta(
        nom_de_guerre="row-chunks", info="Chunking strategy for the simulation"
    ),
    "field_id": ParamMeta(nom_de_guerre="field-id", info="Field ID"),
    "spw_id": ParamMeta(nom_de_guerre="spw-id", info="Spectral Window ID"),
    "sefd": ParamMeta(info="Add noise using the this SEFD value"),
    "ascii_species": ParamMeta(nom_de_guerre="ascii-species", info="Non-simms sky model type."),
    "input_column": ParamMeta(
        nom_de_guerre="input-column", info="Input column (see option --mode)"
    ),
    "mode": ParamMeta(
        info='Simulation mode. To create a new column use "sim"; to add to column use "add"; to subtract from column use "subtract".'
    ),
    "source_schema": ParamMeta(
        nom_de_guerre="source-schema",
        info="Specify a custom source schema via a YAML file that specifies how to map columns in custom sky model to the columns expected by simms. See the bdsf_gaul schema file at 'https://github.com/wits-cfa/simms/tree/main/simms/schemas'",
    ),
}

skysim = define_cab(
    "simms-skysim",
    "simms skysim",
    images.SIMMS,
    _SKYSIM_FIELDS,
    field_meta=_SKYSIM_FIELD_META,
    policies=Policies(),
    info="simms skysim: simulate visibilities from a sky model (simms 3.0)",
)

_TELSIM_FIELDS: dict[str, tuple[str, bool, object]] = {
    "ms": ("MS", True, None),
    "telescope": ("str", True, None),
    "subarray_list": ("List[str]", False, None),
    "subarray_range": ("List[int]", False, None),
    "subarray_file": ("File", False, None),
    "direction": ("str", False, "J2000,1h0m0s,-31d0m0s"),
    "starttime": ("str", False, None),
    "startha": ("float", False, None),
    "dtime": ("float", False, 8),
    "ntime": ("int", False, 10),
    "startfreq": ("Union[str, float]", False, "1420MHz"),
    "dfreq": ("Union[str, float]", False, "1MHz"),
    "nchan": ("int", False, 9),
    "correlations": ("str", False, "XX,YY"),
    "nworkers": ("int", False, 4),
    "rowchunks": ("int", False, 50000),
    "column": ("str", False, "MODEL_DATA"),
    "sefd": ("float", False, None),
    "tsys_over_eta": ("float", False, None),
    "sensitivity_file": ("File", False, None),
    "low_source_limit": ("float", False, None),
    "high_source_limit": ("float", False, None),
    "freq_range": ("str", False, None),
    "smooth": ("str", False, None),
    "fit_order": ("int", False, None),
}

_TELSIM_FIELD_META: dict[str, ParamMeta] = {
    "ms": ParamMeta(info="Observation name/id/label", positional=True),
    "telescope": ParamMeta(info="Name of telescope you are simulating"),
    "subarray_list": ParamMeta(
        nom_de_guerre="subarray-list",
        info="Custom list of antennas to use, e.g., M000,M005,SKA009. If specified, this must be a subarray of the given telescope.",
    ),
    "subarray_range": ParamMeta(
        nom_de_guerre="subarray-range",
        info="Custom range of antennas indices to use, e.g. start,end,step where step is optional. If specified, this must be a subarray of the given telescope.",
    ),
    "subarray_file": ParamMeta(
        nom_de_guerre="subarray-file",
        info="File with list of custom antennas to use, e.g., /path/to/subarray.yaml. File should contain antnames key, e.g., [M000,M005,SKA009]. This must be a subarray of the given telescope.",
    ),
    "direction": ParamMeta(
        info="Direction of field centre for MS. Example, J2000,0h24m20s,-30d12m33s or J2000,0:24:20,-30:12:33. Default is J2000,1h0m0s,-31d0m0s."
    ),
    "starttime": ParamMeta(
        info="Observation start time in UTC. For example, '2024-03-14T06:15:10'. Default is the current machine time."
    ),
    "startha": ParamMeta(info="Hour angle at start of observation. Can be used instead of date."),
    "dtime": ParamMeta(info="Integration/exposure time in seconds. Default is 8 seconds."),
    "ntime": ParamMeta(info="Number of times slots for MS. Default is 10."),
    "startfreq": ParamMeta(
        info="Centre of first frequency channel/bin, e.g 0.55GHz. If given without units, Hertz are assumed. Default is 1420MHz."
    ),
    "dfreq": ParamMeta(
        info="Channel width and units, e.g 2.4MHz. If given without units, Hertz are assumed. Default is 1MHz."
    ),
    "nchan": ParamMeta(info="Number of frequency channels. Default is 9."),
    "correlations": ParamMeta(info="Feed correlations for MS, e.g., 'XX,YY'. Default is 'XX,YY'."),
    "nworkers": ParamMeta(info="Number of workers (one per CPU). Default is 4."),
    "rowchunks": ParamMeta(
        info="Number of chunks to divide the data into, larger number of chunks improves the computation speed. Default is 50000."
    ),
    "column": ParamMeta(
        info="The column in which to corrupt the visibilities with noise. Default is MODEL_DATA column."
    ),
    "sefd": ParamMeta(info="Antenna SEFD (one value for all frequencies)"),
    "tsys_over_eta": ParamMeta(
        nom_de_guerre="tsys-over-eta",
        info="Antenna system temperature over aperture efficiency (one value for all frequencies)",
    ),
    "sensitivity_file": ParamMeta(
        nom_de_guerre="sensitivity-file",
        info="File with antenna spectral sensitivity information. Allowed keys (column names) are 'freq, tsys, sefd, tsys_over_eta'",
    ),
    "low_source_limit": ParamMeta(
        nom_de_guerre="low-source-limit",
        info="Minimum source elevation in degrees that is considered reliable data. The data recorded when the source is below this value is flagged.",
    ),
    "high_source_limit": ParamMeta(
        nom_de_guerre="high-source-limit",
        info="Maximum source elevation in degrees that is considered reliable data. The data recorded when the source is above this value is flagged.",
    ),
    "freq_range": ParamMeta(
        nom_de_guerre="freq-range",
        info="A list containing the start frequency, end frequency, and number of channels, e.g., startfreq,endfreq,nchan.",
    ),
    "smooth": ParamMeta(
        info="If you have provided a sensitivity file with frequencies and their corresponding sefd or tsys_over_eta, then we will fit to get the approximate sefd matching the MS frequencies. There are two fitting options, polyn and spline."
    ),
    "fit_order": ParamMeta(
        nom_de_guerre="fit-order",
        info="The fitting order to use when approximating the MS frequencies SEFDs.",
    ),
}

telsim = define_cab(
    "simms-telsim",
    "simms telsim",
    images.SIMMS,
    _TELSIM_FIELDS,
    field_meta=_TELSIM_FIELD_META,
    policies=Policies(),
    info="simms telsim: simulate telescope noise/sensitivity (simms 3.0)",
)

_SIMMS_CLASSIC_FIELDS: dict[str, tuple[str, bool, object]] = {
    "msname": ("MS", True, None),
    "telescope": ("str", True, None),
    "antenna_file": ("File", False, None),
    "type": ("str", False, "casa"),
    "coord_sys": ("str", False, "itrf"),
    "lon_lat_elv": ("List[float]", False, None),
    "noup": ("bool", False, False),
    "direction": ("List[str]", False, "J2000,0deg,-30deg"),
    "synthesis": ("float", False, 4),
    "scan_length": ("float", False, None),
    "dtime": ("int", False, 2),
    "freq0": ("List[str]", False, "1.4GHz"),
    "dfreq": ("List[str]", False, "2MHz"),
    "nband": ("int", False, 1),
    "nchan": ("List[int]", False, 1),
    "init_ha": ("float", False, None),
    "pol": ("str", False, "XX XY YX YY"),
    "feed": ("str", False, "perfect X Y"),
    "scan_lag": ("float", False, 0),
    "set_limits": ("bool", False, False),
    "elevation_limit": ("float", False, None),
    "shadow_limit": ("float", False, None),
    "auto_correlations": ("bool", False, False),
    "date": ("str", False, None),
}

_SIMMS_CLASSIC_FIELD_META: dict[str, ParamMeta] = {
    "msname": ParamMeta(nom_de_guerre="name", info="Name of MS file to be created"),
    "telescope": ParamMeta(nom_de_guerre="tel", info="Name of telescope that being simulated"),
    "antenna_file": ParamMeta(
        nom_de_guerre="antenna-file", info="File that contains antenna coordinates"
    ),
    "type": ParamMeta(info="Type of antenna file"),
    "coord_sys": ParamMeta(
        nom_de_guerre="coord-sys",
        info="Coordinate system of antenna coordinates in 'antenna-file'. Only needed if 'type' is 'ascii'; CASA tables are assumed to be in ITRF coords",
    ),
    "lon_lat_elv": ParamMeta(
        nom_de_guerre="lon-lat-elv",
        info="Reference position of telescope. Comma seperated longitude,lattitude and elevation 'deg,deg,m'. Elevation is not crucial, lon,lat should be enough. If not specified, we'll try to get this info from the CASA database (assuming that your telescope is known to CASA)",
    ),
    "noup": ParamMeta(
        info="Enable this to indicate that your ENU file does not have an 'up' dimension"
    ),
    "direction": ParamMeta(
        info="Pointing direction. Example J2000,0h0m0s,-30d0m0d. Option --direction may be specified multiple times for multiple pointings. Provide a list of directions for multiple pointings; each pointing will have a unique field ID"
    ),
    "synthesis": ParamMeta(info="Synthesis time in hours"),
    "scan_length": ParamMeta(
        nom_de_guerre="scan-length",
        info="Duration of a single scan in hours. Default is the entire observation (synthesis)",
    ),
    "dtime": ParamMeta(info="Integration time in seconds"),
    "freq0": ParamMeta(
        info="Start frequency. This is the middle of the first channel. Specify as val[unit]. E.g 700MHz, no unit => Hz. Use a comma seperated list for multiple start frequencies (for multiple subbands)"
    ),
    "dfreq": ParamMeta(
        info="Channel width. Specify as val[unit]. E.g 700MHz, no unit => Hz. Use a comma separated list of channel widths (for multiple subbands)"
    ),
    "nband": ParamMeta(info="Number of subbands"),
    "nchan": ParamMeta(
        info="Number of channels. Can be used in tandem with 'freq0, dfreq, nband' to customise the partitioning of the subbands"
    ),
    "init_ha": ParamMeta(
        nom_de_guerre="init-ha", info="Initial hour angle. 'scan-length/2' is the default"
    ),
    "pol": ParamMeta(info="polarization"),
    "feed": ParamMeta(info="Feed type"),
    "scan_lag": ParamMeta(nom_de_guerre="scan-lag", info="Lag time between scans in hours"),
    "set_limits": ParamMeta(
        nom_de_guerre="set-limits",
        info="Set telescope limits. Elevation and shadow limits. Works in tandem with 'shadow-limit, elevation-limit'",
    ),
    "elevation_limit": ParamMeta(
        nom_de_guerre="elevation-limit",
        info="Dish elevation limit. Will only be taken into account if 'set-limits' is enabled.",
    ),
    "shadow_limit": ParamMeta(
        nom_de_guerre="shadow-limit",
        info="Shadow limit. Will only be taken into account if 'set-limits' is enabled.",
    ),
    "auto_correlations": ParamMeta(
        nom_de_guerre="auto-correlations", info="Don't flag autocorrelations"
    ),
    "date": ParamMeta(
        info="Date of observation. Example UTC,2014/05/26 or UTC,2014/05/26/12:12:12: default is today (format EPOCH,yyyy/mm/dd/[h:m:s])"
    ),
}

simms_classic = define_cab(
    "simms",
    "simms",
    images.SIMMS_CLASSIC,
    _SIMMS_CLASSIC_FIELDS,
    field_meta=_SIMMS_CLASSIC_FIELD_META,
    policies=Policies(),
    info="simms (classic): simulate an empty MS from telescope/observation parameters (pre-3.0)",
)

# `simms` is a click *chained* multicommand (`simms COMMAND [ARGS] COMMAND
# [ARGS] ...`), so `primary-beam`'s action selector (`tag-ms`) is a trailing
# *positional* argument that must come AFTER primary-beam's options -- putting
# `tag-ms` before the options ends the sub-command early and the flags leak
# back to the top-level `simms` parser ("No such option"). Hence the command
# stops at `simms primary-beam` and `action` (default "tag-ms") is a positional
# field, which `build_argv` emits last.
_PRIMARY_BEAM_TAG_MS_FIELDS: dict[str, tuple[str, bool, object]] = {
    "ms": ("MS", True, None),
    "telescope_name_column": ("str", False, "TELESCOPE_NAME"),
    "label": ("str", False, None),
    "label_map": ("File", False, None),
    "from_layout": ("str", False, None),
    "action": ("str", False, "tag-ms"),
}

_PRIMARY_BEAM_TAG_MS_FIELD_META: dict[str, ParamMeta] = {
    "ms": ParamMeta(info="Measurement set whose ANTENNA table to tag"),
    "telescope_name_column": ParamMeta(
        nom_de_guerre="telescope-name-column",
        info="Name of the ANTENNA-table column to store the per-antenna telescope-name labels in.",
    ),
    "label": ParamMeta(info="Apply a single telescope-name label uniformly to all antennas."),
    "label_map": ParamMeta(
        nom_de_guerre="label-map",
        info="YAML file mapping antenna names to telescope-name labels.",
    ),
    "from_layout": ParamMeta(
        nom_de_guerre="from-layout",
        info="Name of a simms layout; per-antenna telescope names are matched against the MS antenna names.",
    ),
    "action": ParamMeta(
        positional=True,
        info="primary-beam action selector (trailing positional); 'tag-ms' tags the ANTENNA table.",
    ),
}

primary_beam = define_cab(
    "simms-primary-beam",
    "simms primary-beam",
    images.SIMMS,
    _PRIMARY_BEAM_TAG_MS_FIELDS,
    outputs={"ms": ("MS", False, None)},
    field_meta=_PRIMARY_BEAM_TAG_MS_FIELD_META,
    policies=Policies(),
    info="simms primary-beam tag-ms: tag the MS ANTENNA table with per-antenna telescope-name labels (simms 3.0)",
)
