"""simms (classic) -- the original, pre-3.0 `simms` command.

A genuinely different tool from the simms 3.0 sub-commands in
`dosho/cabs/simms.py`, not an older interface to the same one: it has its
own `simms-classic` image, takes no sub-command in its `command`, and is a
real standalone binary -- so it is a `define_cab` `Cab` here, where simms
3.0's `skysim`/`telsim`/`primary_beam` are `@shinobi.pystep` `StepRef`s
authored inside simms itself.

It lives in its own module for that reason. Keeping it beside the 3.0
pysteps put a `Cab` and three `StepRef`s in one file whose name matched
neither, and made `from dosho.cabs.simms import ...` a statement that
pulled two unrelated tools; the split is along the seam that already
existed.

Exported as `simms_classic` rather than `simms` to avoid shadowing the
`simms` module, and registered under its real name `simms` via
`dosho.registry._NAME_OVERRIDES`. Its backing image is flagged deprecated
in `images.yaml` ("unused by any worker -- slated for removal"), so prefer
`telsim` for new MS-creation use.
"""

from __future__ import annotations

from shinobi.steps.schema import ParamMeta, Policies

from dosho import images
from dosho._builder import FieldSpec, define_cab

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
