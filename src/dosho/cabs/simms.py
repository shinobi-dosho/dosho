"""simms -- simms 3.0's sub-commands, one module-level object per
sub-command (matching `casatasks.py`'s multi-export convention).

All three transcribed field-by-field from cult-cargo's simms.yml:

* `skysim` -- simms 3.0's sky-model visibility simulator, replacing
  caracal 1.x's separate simulator worker (see stimela-ninja/caracal
  migration notes: simulator -> simms 3.0 skysim).
* `telsim` -- simms 3.0's telescope simulator (`simms telsim`, same `simms`
  image as `skysim` -- a sibling sub-command of the same binary, not a
  separate tool). Despite the name, it creates a brand-new MS from scratch
  given `telescope`/`direction`/timing/frequency parameters
  (`simms.telescope.generate_ms.create_ms`, real source verified in
  `simms/src/simms/apps/telsim.py`) -- SEFD/Tsys noise injection is an
  *optional* extra those parameters enable, not telsim's core job. Known
  `telescope` values include `"meerkat"`/`"meerkat-plus"` (real vendored
  subarrays of `simms/src/simms/telescope/layouts/skamid.geodetic.yaml` --
  MeerKAT/MeerKAT+ are modelled as SKA-Mid subarrays there).
* `simms_classic` -- the original (pre-3.0) `simms` command, a genuinely
  different tool from `skysim`/`telsim` (own `simms-classic` image, no
  sub-command in its `command`) -- exported as `simms_classic` rather
  than `simms` to avoid shadowing this module's own name in
  `from dosho.cabs.simms import simms_classic`. Its backing image is
  flagged deprecated in `images.yaml` ("unused by any worker -- slated for
  removal"); prefer `telsim` for new MS-creation use (see above).
"""

from __future__ import annotations

from shinobi.steps.schema import ParamMeta, Policies

from dosho import images
from dosho._builder import FieldSpec, define_cab

_SKYSIM_FIELDS: dict[str, FieldSpec] = {
    "ms": ("MS", True, None, ParamMeta(info="Measurement set", positional=True)),
    "ascii_sky": (
        "File",
        False,
        None,
        ParamMeta(
            nom_de_guerre="ascii-sky",
            info="Catalogue of sources. A full description of accepted units can be found in the documentation.",
        ),
    ),
    "fits_sky": (
        "Union[File, List[File]]",
        False,
        None,
        ParamMeta(nom_de_guerre="fits-sky", info="FITS file(s) containing the sky model"),
    ),
    "fits_sky_interp": (
        "str",
        False,
        "nearest",
        ParamMeta(
            nom_de_guerre="fits-sky-interp",
            info="Interpolation method when MS and FITS image grids do not match. Interpolation is only done within the overlap region.",
        ),
    ),
    "polarisation": (
        "bool",
        False,
        True,
        ParamMeta(
            info="Simulate all available stokes parameters (correlations). If false, only consider stokes I",
        ),
    ),
    "pol_basis": (
        "str",
        False,
        "linear",
        ParamMeta(
            nom_de_guerre="pol-basis",
            info="Polarization basis for the simulation. The default is circular polarization.",
        ),
    ),
    "pixel_tol": (
        "float",
        False,
        "1e-7",
        ParamMeta(
            nom_de_guerre="pixel-tol",
            info="minimum brightness for a pixel to be considered in direct Fourier transform",
        ),
    ),
    "fft_precision": (
        "str",
        False,
        "double",
        ParamMeta(
            nom_de_guerre="fft-precision",
            info="Precision of the FFT calculation. The default is double precision.",
        ),
    ),
    "do_wstacking": (
        "bool",
        False,
        True,
        ParamMeta(
            nom_de_guerre="do-wstacking",
            info="Whether to use w-stacking for FFT-based visibility prediction.",
        ),
    ),
    "ascii_delimiter": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="ascii-delimiter",
            info="Delimiter that is used in the ascii-sky",
        ),
    ),
    "column": ("str", False, "DATA", ParamMeta(info="Data column for simulation")),
    "nworkers": ("int", False, 4, ParamMeta(info="Number of workers (one per CPU)")),
    "row_chunks": (
        "int",
        False,
        10000,
        ParamMeta(nom_de_guerre="row-chunks", info="Chunking strategy for the simulation"),
    ),
    "field_id": ("int", False, 0, ParamMeta(nom_de_guerre="field-id", info="Field ID")),
    "spw_id": ("int", False, 0, ParamMeta(nom_de_guerre="spw-id", info="Spectral Window ID")),
    "sefd": ("float", False, None, ParamMeta(info="Add noise using the this SEFD value")),
    "ascii_species": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="ascii-species", info="Non-simms sky model type."),
    ),
    "input_column": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="input-column", info="Input column (see option --mode)"),
    ),
    "mode": (
        "str",
        False,
        "sim",
        ParamMeta(
            info='Simulation mode. To create a new column use "sim"; to add to column use "add"; to subtract from column use "subtract".',
        ),
    ),
    "source_schema": (
        "File",
        False,
        None,
        ParamMeta(
            nom_de_guerre="source-schema",
            info="Specify a custom source schema via a YAML file that specifies how to map columns in custom sky model to the columns expected by simms. See the bdsf_gaul schema file at 'https://github.com/wits-cfa/simms/tree/main/simms/schemas'",
        ),
    ),
    "primary_beam": (
        "File",
        False,
        None,
        ParamMeta(
            nom_de_guerre="primary-beam",
            info='Path to a beam-config YAML mapping each ANTENNA TELESCOPE_NAME to a beam model (e.g. "MK: {jimbeam: L}"). Applies a per-antenna, parallactic-rotating primary beam to component skies (ASCII/WSClean). Requires a linear pol basis.',
        ),
    ),
    "beam_band": (
        "str",
        False,
        "L",
        ParamMeta(
            nom_de_guerre="beam-band",
            info="Default band for JimBeam entries that omit an explicit model/CSV.",
        ),
    ),
    "beam_pa_step": (
        "float",
        False,
        1.0,
        ParamMeta(
            nom_de_guerre="beam-pa-step",
            info="Spacing (degrees) of the parallactic-angle grid the beam is sampled on and interpolated from. Smaller is more accurate but uses more memory/compute.",
        ),
    ),
    "beam_grid_max_gib": (
        "float",
        False,
        4.0,
        ParamMeta(
            nom_de_guerre="beam-grid-max-gib",
            info="Hard ceiling (GiB) on the sampled beam grid, which scales with parallactic-angle samples x sky components x channels and is held in memory for the whole run. skysim errors (rather than risking an out-of-memory kill) if the grid would exceed this; lower it with a coarser beam-pa-step or fewer components.",
        ),
    ),
    "beam_jones": (
        "str",
        False,
        "diagonal",
        ParamMeta(
            nom_de_guerre="beam-jones",
            info='Primary-beam application for component skies. "diagonal" applies a per-feed voltage (fast, linear correlations only). "full" applies the complete 2x2 E-Jones (models cross-hand leakage from FITS beam cubes and supports circular correlations); requires 4 correlations. Ignored on the FITS-image path.',
        ),
    ),
    "telescope_name_column": (
        "str",
        False,
        "TELESCOPE_NAME",
        ParamMeta(
            nom_de_guerre="telescope-name-column",
            info="Name of the ANTENNA-table column holding the per-antenna telescope/type label that maps to a beam model. Must match the column telsim/primary-beam tag-ms wrote. The primary beam requires this column; it is never inferred.",
        ),
    ),
}

skysim = define_cab(
    "simms-skysim",
    "simms skysim",
    images.SIMMS,
    _SKYSIM_FIELDS,
    # skysim writes simulated visibilities into column in place --
    # re-declare ms as an output so a dependent step can chain onto it.
    outputs={"ms": ("MS", False, None)},
    policies=Policies(),
    info="simms skysim: simulate visibilities from a sky model (simms 3.0)",
)

_TELSIM_FIELDS: dict[str, FieldSpec] = {
    "ms": ("MS", True, None, ParamMeta(info="Observation name/id/label", positional=True)),
    "telescope": ("str", True, None, ParamMeta(info="Name of telescope you are simulating")),
    "subarray_list": (
        "List[str]",
        False,
        None,
        ParamMeta(
            nom_de_guerre="subarray-list",
            info="Custom list of antennas to use, e.g., M000,M005,SKA009. If specified, this must be a subarray of the given telescope.",
        ),
    ),
    "subarray_range": (
        "List[int]",
        False,
        None,
        ParamMeta(
            nom_de_guerre="subarray-range",
            info="Custom range of antennas indices to use, e.g. start,end,step where step is optional. If specified, this must be a subarray of the given telescope.",
        ),
    ),
    "subarray_file": (
        "File",
        False,
        None,
        ParamMeta(
            nom_de_guerre="subarray-file",
            info="File with list of custom antennas to use, e.g., /path/to/subarray.yaml. File should contain antnames key, e.g., [M000,M005,SKA009]. This must be a subarray of the given telescope.",
        ),
    ),
    "direction": (
        "str",
        False,
        "J2000,1h0m0s,-31d0m0s",
        ParamMeta(
            info="Direction of field centre for MS. Example, J2000,0h24m20s,-30d12m33s or J2000,0:24:20,-30:12:33. Default is J2000,1h0m0s,-31d0m0s.",
        ),
    ),
    "starttime": (
        "str",
        False,
        None,
        ParamMeta(
            info="Observation start time in UTC. For example, '2024-03-14T06:15:10'. Default is the current machine time.",
        ),
    ),
    "startha": (
        "float",
        False,
        None,
        ParamMeta(info="Hour angle at start of observation. Can be used instead of date."),
    ),
    "dtime": (
        "float",
        False,
        8,
        ParamMeta(info="Integration/exposure time in seconds. Default is 8 seconds."),
    ),
    "ntime": ("int", False, 10, ParamMeta(info="Number of times slots for MS. Default is 10.")),
    "startfreq": (
        "Union[str, float]",
        False,
        "1420MHz",
        ParamMeta(
            info="Centre of first frequency channel/bin, e.g 0.55GHz. If given without units, Hertz are assumed. Default is 1420MHz.",
        ),
    ),
    "dfreq": (
        "Union[str, float]",
        False,
        "1MHz",
        ParamMeta(
            info="Channel width and units, e.g 2.4MHz. If given without units, Hertz are assumed. Default is 1MHz.",
        ),
    ),
    "nchan": ("int", False, 9, ParamMeta(info="Number of frequency channels. Default is 9.")),
    "correlations": (
        "str",
        False,
        "XX,YY",
        ParamMeta(info="Feed correlations for MS, e.g., 'XX,YY'. Default is 'XX,YY'."),
    ),
    "nworkers": ("int", False, 4, ParamMeta(info="Number of workers (one per CPU). Default is 4.")),
    "rowchunks": (
        "int",
        False,
        50000,
        ParamMeta(
            info="Number of chunks to divide the data into, larger number of chunks improves the computation speed. Default is 50000.",
        ),
    ),
    "column": (
        "str",
        False,
        "MODEL_DATA",
        ParamMeta(
            info="The column in which to corrupt the visibilities with noise. Default is MODEL_DATA column.",
        ),
    ),
    "sefd": ("float", False, None, ParamMeta(info="Antenna SEFD (one value for all frequencies)")),
    "tsys_over_eta": (
        "float",
        False,
        None,
        ParamMeta(
            nom_de_guerre="tsys-over-eta",
            info="Antenna system temperature over aperture efficiency (one value for all frequencies)",
        ),
    ),
    "sensitivity_file": (
        "File",
        False,
        None,
        ParamMeta(
            nom_de_guerre="sensitivity-file",
            info="File with antenna spectral sensitivity information. Allowed keys (column names) are 'freq, tsys, sefd, tsys_over_eta'",
        ),
    ),
    "low_source_limit": (
        "float",
        False,
        None,
        ParamMeta(
            nom_de_guerre="low-source-limit",
            info="Minimum source elevation in degrees that is considered reliable data. The data recorded when the source is below this value is flagged.",
        ),
    ),
    "high_source_limit": (
        "float",
        False,
        None,
        ParamMeta(
            nom_de_guerre="high-source-limit",
            info="Maximum source elevation in degrees that is considered reliable data. The data recorded when the source is above this value is flagged.",
        ),
    ),
    "freq_range": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="freq-range",
            info="A list containing the start frequency, end frequency, and number of channels, e.g., startfreq,endfreq,nchan.",
        ),
    ),
    "smooth": (
        "str",
        False,
        None,
        ParamMeta(
            info="If you have provided a sensitivity file with frequencies and their corresponding sefd or tsys_over_eta, then we will fit to get the approximate sefd matching the MS frequencies. There are two fitting options, polyn and spline.",
        ),
    ),
    "fit_order": (
        "int",
        False,
        None,
        ParamMeta(
            nom_de_guerre="fit-order",
            info="The fitting order to use when approximating the MS frequencies SEFDs.",
        ),
    ),
}

telsim = define_cab(
    "simms-telsim",
    "simms telsim",
    images.SIMMS,
    _TELSIM_FIELDS,
    # telsim creates `ms` fresh (see module docstring) -- re-declare it as
    # an output (same-named passthrough of the input path) so a dependent
    # step can chain onto the newly-created MS.
    outputs={"ms": ("MS", False, None)},
    policies=Policies(),
    info="simms telsim: simulate a telescope MS from scratch, optionally with noise (simms 3.0)",
)

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

# `simms` is a click *chained* multicommand (`simms COMMAND [ARGS] COMMAND
# [ARGS] ...`), so `primary-beam`'s mode selector is a trailing *positional*
# argument that must come AFTER primary-beam's options -- putting the mode
# before the options ends the sub-command early and the flags leak back to
# the top-level `simms` parser ("No such option"). Hence the command stops
# at `simms primary-beam` and `mode` (required, no default -- matches the
# real CLI, which has no default either) is a positional field, which
# `build_argv` emits last.
#
# Real `simms primary-beam` has four modes (`to-fits`/`tag-ms`/`apply`/
# `correct`), each using a subset of this flat field set (enforced by
# simms's own runtime `_require()` checks per mode, not by this schema --
# same "no choices=, no conditional-required" convention every other
# multi-valued field in this file follows): `tag-ms` uses
# `telescope_name_column`/`label`/`label_map`/`from_layout`; `apply`/
# `correct` use `beam_pattern`/`beam_band`/`beam_pa_step`/`ascii_sky`/
# `fits_sky`/`output`/`field_id`/`spw_id` (`correct` additionally uses
# `pb_cutoff`); `to-fits` uses `beam_pattern`/`beam_band`/`output`/
# `pixel_size`/`npix`/`start_freq`/`chan_width`/`nchan`/`nworkers`.
_PRIMARY_BEAM_FIELDS: dict[str, FieldSpec] = {
    "mode": (
        "str",
        True,
        None,
        ParamMeta(
            info="Operation to perform: to-fits/tag-ms/apply/correct (trailing positional -- see the comment above).",
            positional=True,
        ),
    ),
    "beam_pattern": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="beam-pattern",
            info="Beam model: a cosine-taper CSV path, a built-in name (e.g. MKAT-AA-L-JIM-2020), a band shorthand (L/UHF), or a FITS beam cube (.fits). Used by to-fits/apply/correct; required for those modes (enforced by simms itself, not this schema).",
        ),
    ),
    "beam_band": (
        "str",
        False,
        "L",
        ParamMeta(
            nom_de_guerre="beam-band",
            info="Default band for a built-in beam when beam-pattern omits one.",
        ),
    ),
    "beam_pa_step": (
        "float",
        False,
        1.0,
        ParamMeta(
            nom_de_guerre="beam-pa-step",
            info="Parallactic-angle sampling step (degrees) for the time-averaged beam.",
        ),
    ),
    "ms": (
        "MS",
        False,
        None,
        ParamMeta(
            info="Measurement set (time/PA range, array position, frequencies). Required for tag-ms/apply/correct.",
        ),
    ),
    "fits_sky": (
        "File",
        False,
        None,
        ParamMeta(
            nom_de_guerre="fits-sky",
            info="Input FITS image sky model (apply/correct). Exactly one of fits-sky/ascii-sky is required for those modes.",
        ),
    ),
    "ascii_sky": (
        "File",
        False,
        None,
        ParamMeta(
            nom_de_guerre="ascii-sky",
            info="Input ASCII component sky model (apply/correct). Exactly one of fits-sky/ascii-sky is required for those modes.",
        ),
    ),
    "ascii_delimiter": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="ascii-delimiter",
            info="Delimiter used in the ascii-sky file. Defaults to whitespace.",
        ),
    ),
    "source_schema": (
        "File",
        False,
        None,
        ParamMeta(
            nom_de_guerre="source-schema",
            info="Custom source schema (YAML) mapping the ascii-sky columns to the fields simms expects, as for skysim. Defaults to the built-in simms source schema.",
        ),
    ),
    "output": (
        "File",
        False,
        None,
        ParamMeta(
            info="Output path -- FITS beam (to-fits) or beamed/corrected sky model (apply/correct).",
        ),
    ),
    "telescope_name_column": (
        "str",
        False,
        "TELESCOPE_NAME",
        ParamMeta(
            nom_de_guerre="telescope-name-column",
            info="ANTENNA-table column holding the per-antenna telescope/type label (tag-ms).",
        ),
    ),
    "label": (
        "str",
        False,
        None,
        ParamMeta(info="Single telescope-name label applied to all antennas (tag-ms)."),
    ),
    "label_map": (
        "File",
        False,
        None,
        ParamMeta(
            nom_de_guerre="label-map",
            info="YAML mapping antenna NAME -> telescope-name label (tag-ms).",
        ),
    ),
    "from_layout": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="from-layout",
            info="simms layout whose per-antenna telescope_name is matched to the MS antenna names (tag-ms).",
        ),
    ),
    "pb_cutoff": (
        "float",
        False,
        0.1,
        ParamMeta(
            nom_de_guerre="pb-cutoff",
            info="In correct mode, drop sources whose averaged beam value falls below this level.",
        ),
    ),
    "field_id": (
        "int",
        False,
        0,
        ParamMeta(
            nom_de_guerre="field-id",
            info="FIELD_ID whose phase centre and time span define the beam (apply/correct).",
        ),
    ),
    "spw_id": (
        "int",
        False,
        0,
        ParamMeta(
            nom_de_guerre="spw-id",
            info="Spectral-window (DATA_DESC_ID) whose frequencies define the beam (apply/correct).",
        ),
    ),
    "pixel_size": (
        "str",
        False,
        "1arcmin",
        ParamMeta(
            nom_de_guerre="pixel-size",
            info='Angular pixel size for the to-fits grid, e.g. "1arcmin" or "0.02deg".',
        ),
    ),
    "npix": ("int", False, 256, ParamMeta(info="Number of pixels per side for the to-fits grid.")),
    "start_freq": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="start-freq",
            info="Start frequency of the to-fits cube. Defaults to the beam's own range.",
        ),
    ),
    "chan_width": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="chan-width",
            info="Channel width of the to-fits cube. Defaults to spanning --nchan.",
        ),
    ),
    "nchan": (
        "int",
        False,
        None,
        ParamMeta(
            info="Number of output channels in the to-fits cube. Defaults to the beam's own tabulation.",
        ),
    ),
    "nworkers": ("int", False, 4, ParamMeta(info="Number of worker threads.")),
}

primary_beam = define_cab(
    "simms-primary-beam",
    "simms primary-beam",
    images.SIMMS,
    _PRIMARY_BEAM_FIELDS,
    # tag-ms echoes `ms` back; apply/correct write to `output` -- both are
    # real same-named passthrough outputs (no `implicit=` needed).
    outputs={"ms": ("MS", False, None), "output": ("File", False, None)},
    policies=Policies(),
    info="simms primary-beam: PB utilities -- to-fits/tag-ms/apply/correct (simms 3.0)",
)
