"""Tigger sky-model tools (https://github.com/ska-sa/tigger-lsm). One
shared `TIGGER_LSM` image, three sibling commands
(`tigger-convert`/`tigger-restore`/`tigger-tag`).

Ported field-by-field from each real `--help` (astro-tigger-lsm 1.8.0).
All three are `optparse`-based, so every repeatable option is "append"-style
(the flag itself repeats once per value, e.g. `-a f1.txt -a f2.txt`) --
`optparse` has no argparse-style `nargs='+'` -- hence the shared cab-level
`Policies(repeat_list=True)` rather than any per-field `repeat_as_tokens`.
"""

from __future__ import annotations

from shinobi.steps.schema import ParamMeta, Policies

from dosho import images
from dosho._builder import FieldSpec, define_cab

_POLICIES = Policies(prefix="--", repeat_list=True)

# --- tigger-convert ----------------------------------------------------------
_CONVERT_FIELDS: dict[str, FieldSpec] = {
    "sky_model": (
        "File",
        True,
        None,
        ParamMeta(info="Input sky model, any format importable by Tigger", positional=True),
    ),
    "output_model": (
        "File",
        False,
        None,
        ParamMeta(
            info="Output model (always native Tigger format); auto-generated if omitted",
            positional=True,
        ),
    ),
    "force": (
        "bool",
        False,
        None,
        ParamMeta(nom_de_guerre="force", info="Force overwrite of output model"),
    ),
    "type": (
        "str",
        False,
        "auto",
        ParamMeta(
            info="Input model type: Tigger, ASCII, BBS, NEWSTAR, AIPSCC, AIPSCCFITS, Gaul, auto",
        ),
    ),
    "output_type": (
        "str",
        False,
        "auto",
        ParamMeta(
            nom_de_guerre="output-type",
            info="Output model type: Tigger, ASCII, BBS, NEWSTAR, auto",
        ),
    ),
    "append": (
        "List[File]",
        False,
        None,
        ParamMeta(
            nom_de_guerre="append",
            info="Append another model to the input model (repeatable)",
        ),
    ),
    "append_type": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="append-type", info="Appended model type"),
    ),
    "format": (
        "str",
        False,
        None,
        ParamMeta(
            info='Input format for ASCII/BBS tables, e.g. "name ra_h ra_m ra_s dec_d dec_m dec_s i q u v spi rm emaj_s emin_s pa_d freq0 tags..."',
        ),
    ),
    "append_format": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="append-format",
            info="Format of the appended file (default: --format)",
        ),
    ),
    "output_format": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="output-format", info="Output format for ASCII/BBS tables"),
    ),
    "help_format": (
        "bool",
        False,
        None,
        ParamMeta(nom_de_guerre="help-format", info="Print help on format strings"),
    ),
    "min_extent": (
        "float",
        False,
        0.0,
        ParamMeta(
            nom_de_guerre="min-extent",
            info="Minimal source extent (arcsec) when importing NEWSTAR/ASCII; smaller sources become point sources",
        ),
    ),
    "tags": ("str", False, None, ParamMeta(info="Extract sources with the specified tags")),
    "select": (
        "List[str]",
        False,
        None,
        ParamMeta(
            info="Select a subset of sources by tag<>value comparison (repeatable, logical-AND)",
        ),
    ),
    "remove_nans": (
        "bool",
        False,
        None,
        ParamMeta(
            nom_de_guerre="remove-nans",
            info="Removes the named source(s) from the model (NAME may use */? wildcards)",
        ),
    ),
    "app_to_int": (
        "bool",
        False,
        None,
        ParamMeta(
            nom_de_guerre="app-to-int",
            info="Treat fluxes as apparent, rescale to intrinsic via the primary beam model",
        ),
    ),
    "int_to_app": (
        "bool",
        False,
        None,
        ParamMeta(
            nom_de_guerre="int-to-app",
            info="Treat fluxes as intrinsic, rescale to apparent via the primary beam model",
        ),
    ),
    "newstar_app_to_int": (
        "bool",
        False,
        None,
        ParamMeta(
            nom_de_guerre="newstar-app-to-int",
            info="Convert NEWSTAR apparent fluxes to intrinsic",
        ),
    ),
    "newstar_int_to_app": (
        "bool",
        False,
        None,
        ParamMeta(
            nom_de_guerre="newstar-int-to-app",
            info="Convert NEWSTAR intrinsic fluxes to apparent",
        ),
    ),
    "center": (
        "str",
        False,
        None,
        ParamMeta(
            info='Override the nominal field centre, e.g. "Xdeg,Ydeg" or a pyrap.measures direction string',
        ),
    ),
    "refresh_r": (
        "bool",
        False,
        None,
        ParamMeta(
            nom_de_guerre="refresh-r",
            info="Recompute each source's radial distance from the current field centre",
        ),
    ),
    "ref_freq": (
        "float",
        False,
        None,
        ParamMeta(
            nom_de_guerre="ref-freq",
            info="Set or change the model's reference frequency (MHz)",
        ),
    ),
    "primary_beam": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="primary-beam",
            info="Primary beam expression (in r, fq) or FITS beam pattern to estimate apparent fluxes",
        ),
    ),
    "linear_pol": (
        "bool",
        False,
        None,
        ParamMeta(
            nom_de_guerre="linear-pol",
            info="Use XY basis for beam filenames/Mueller matrices [default: RL]",
        ),
    ),
    "fits_l_axis": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="fits-l-axis",
            info="CTYPE for the L axis in the FITS PB file",
        ),
    ),
    "fits_m_axis": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="fits-m-axis",
            info="CTYPE for the M axis in the FITS PB file",
        ),
    ),
    "beam_freq": (
        "float",
        False,
        None,
        ParamMeta(
            nom_de_guerre="beam-freq",
            info="Frequency (MHz) to use for the primary beam model",
        ),
    ),
    "beam_clip": (
        "float",
        False,
        0.001,
        ParamMeta(nom_de_guerre="beam-clip", info="Clip (power) beam gains at this level"),
    ),
    "beam_spi": (
        "float",
        False,
        None,
        ParamMeta(
            nom_de_guerre="beam-spi",
            info="Bandwidth (MHz, centred on --beam-freq) for a beam-based spectral index fit",
        ),
    ),
    "force_beam_spi_wo_spectrum": (
        "bool",
        False,
        None,
        ParamMeta(
            nom_de_guerre="force-beam-spi-wo-spectrum",
            info="Apply beam-derived spectral indices even to sources without an intrinsic spectrum",
        ),
    ),
    "beam_nopol": (
        "bool",
        False,
        None,
        ParamMeta(
            nom_de_guerre="beam-nopol",
            info="Apply intensity beam model only, ignoring polarization",
        ),
    ),
    "beam_diag": (
        "bool",
        False,
        None,
        ParamMeta(
            nom_de_guerre="beam-diag",
            info="Use diagonal Jones terms only for the beam model",
        ),
    ),
    "pa": (
        "float",
        False,
        None,
        ParamMeta(
            info="Rotate the primary beam pattern through this parallactic angle (degrees)",
        ),
    ),
    "pa_range": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="pa-range",
            info="Rotate through a parallactic angle range FROM,TO and average",
        ),
    ),
    "pa_from_ms": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="pa-from-ms",
            info="Rotate through the parallactic angle range from MS1[:FIELD1],... and average",
        ),
    ),
    "beam_average_jones": (
        "bool",
        False,
        None,
        ParamMeta(
            nom_de_guerre="beam-average-jones",
            info="Convert Jones(PA) to Mueller(PA) before averaging over PA",
        ),
    ),
    "cluster_dist": (
        "float",
        False,
        60.0,
        ParamMeta(
            nom_de_guerre="cluster-dist",
            info="Distance (arcsec) for source clustering, 0 to disable",
        ),
    ),
    "rename": ("bool", False, None, ParamMeta(info="Rename sources using the COPART scheme")),
    "radial_step": (
        "float",
        False,
        10.0,
        ParamMeta(
            nom_de_guerre="radial-step",
            info="Radial-distance step size (arcmin) for the COPART scheme",
        ),
    ),
    "merge_clusters": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="merge-clusters",
            info="Merge source clusters bearing the given tag(s) (comma-separated, or 'ALL')",
        ),
    ),
    "prefix": ("str", False, None, ParamMeta(info="Prefix all source names with the given string")),
    "remove_source": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="remove-source",
            info="Remove the named source(s) (NAME may use */? wildcards)",
        ),
    ),
    "add_brick": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="add-brick",
            info="Add a uv-brick: NAME:FILE[:PAD_FACTOR:[TAGS:...]]",
        ),
    ),
    "recenter": (
        "str",
        False,
        None,
        ParamMeta(info="Shift the sky model to a different field centre (see --center)"),
    ),
    "verbose": ("bool", False, None, ParamMeta(info="Increases verbosity")),
    "debug": (
        "List[str]",
        False,
        None,
        ParamMeta(
            info="Set verbosity of a named Python context: Context=Level (repeatable)",
        ),
    ),
    "enable_plots": (
        "bool",
        False,
        None,
        ParamMeta(nom_de_guerre="enable-plots", info="Enable various diagnostic plots"),
    ),

}

convert = define_cab(
    "tigger-convert",
    "tigger-convert",
    images.TIGGER_LSM,
    _CONVERT_FIELDS,
    policies=_POLICIES,
    info="tigger-convert: convert sky models into Tigger format (https://github.com/ska-sa/tigger-lsm)",
)

# --- tigger-restore ----------------------------------------------------------
_RESTORE_FIELDS: dict[str, FieldSpec] = {
    "input_image": (
        "File",
        True,
        None,
        ParamMeta(info="Input FITS image to restore sources into", positional=True),
    ),
    "sky_model": ("File", True, None, ParamMeta(info="Sky model to restore from", positional=True)),
    "output_image": (
        "File",
        False,
        None,
        ParamMeta(info="Output image; auto-generated if omitted", positional=True),
    ),
    "type": (
        "str",
        False,
        None,
        ParamMeta(
            info="Input model type: ASCII, Tigger, BBS, NEWSTAR, AIPSCC, AIPSCCFITS, Gaul, auto",
        ),
    ),
    "format": ("str", False, None, ParamMeta(info="Input format for ASCII/BBS tables")),
    "num_sources": (
        "int",
        False,
        None,
        ParamMeta(
            nom_de_guerre="num-sources",
            info="Only restore the NSRC brightest sources",
        ),
    ),
    "scale": (
        "str",
        False,
        None,
        ParamMeta(info="Rescale model fluxes by FLUXSCALE[,N] (N brightest only if given)"),
    ),
    "restoring_beam": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="restoring-beam",
            info="Restoring beam size, overriding the image's BMAJ/BMIN/BPA: BMAJ[,BMIN,PA]",
        ),
    ),
    "psf_file": (
        "File",
        False,
        None,
        ParamMeta(
            nom_de_guerre="psf-file",
            info="Determine the restoring beam by fitting this PSF file",
        ),
    ),
    "clear": (
        "bool",
        False,
        None,
        ParamMeta(info="Clear the contents of the FITS file before adding in sources"),
    ),
    "pb": (
        "bool",
        False,
        None,
        ParamMeta(
            info="Apply the model primary beam function during restoration where defined",
        ),
    ),
    "beamgain": (
        "bool",
        False,
        None,
        ParamMeta(info="Apply the beamgain attribute during restoration where defined"),
    ),
    "ignore_nobeam": (
        "bool",
        False,
        None,
        ParamMeta(
            nom_de_guerre="ignore-nobeam",
            info="Apply PB or beamgain even if a source is tagged 'nobeam'",
        ),
    ),
    "freq": (
        "float",
        False,
        None,
        ParamMeta(info="Frequency (MHz) to use for spectral indices and primary beams"),
    ),
    "force": (
        "bool",
        False,
        None,
        ParamMeta(info="Overwrite the output image even if it already exists"),
    ),
    "verbose": (
        "int",
        False,
        None,
        ParamMeta(info="Verbosity level (0 is silent, higher is more verbose)"),
    ),
    "timestamps": ("bool", False, None, ParamMeta(info="Enable timestamps in debug messages")),

}

restore = define_cab(
    "tigger-restore",
    "tigger-restore",
    images.TIGGER_LSM,
    _RESTORE_FIELDS,
    policies=_POLICIES,
    info="tigger-restore: restore sky-model sources into a FITS image (https://github.com/ska-sa/tigger-lsm)",
)

# --- tigger-tag ----------------------------------------------------------
_TAG_FIELDS: dict[str, FieldSpec] = {
    "sky_model": ("File", True, None, ParamMeta(info="Sky model to tag", positional=True)),
    "selectors": (
        "List[str]",
        False,
        None,
        ParamMeta(
            info="Source selector(s) (NAME, =SELTAG, or SELTAG<>SELVAL) followed by tag expressions (TAG=[TYPE:]VALUE, +TAG, !TAG, /TAG)",
            positional=True,
            repeat_as_tokens=True,
        ),
    ),
    "list_sources": (
        "bool",
        False,
        None,
        ParamMeta(
            nom_de_guerre="list",
            info="List selected sources only; does not apply any tags",
        ),
    ),
    "output": (
        "File",
        False,
        None,
        ParamMeta(info="Save changes to a different output model [default: save in place]"),
    ),
    "force": (
        "bool",
        False,
        None,
        ParamMeta(info="Save changes without prompting [default: prompt]"),
    ),
    "transfer_tags": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="transfer-tags",
            info="Transfer tags from a reference LSM (FROM_LSM:TOL) to this model, within TOL arcsec",
        ),
    ),
    "debug": (
        "List[str]",
        False,
        None,
        ParamMeta(
            info="Set verbosity of a named Python context: Context=Level (repeatable)",
        ),
    ),
}

tag = define_cab(
    "tigger-tag",
    "tigger-tag",
    images.TIGGER_LSM,
    _TAG_FIELDS,
    policies=_POLICIES,
    info="tigger-tag: set or change tags of selected sources in a sky model (https://github.com/ska-sa/tigger-lsm)",
)
