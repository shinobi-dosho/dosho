"""flag-ms.py -- manipulates flags (bitflags and legacy FLAG/FLAG_ROW
columns) in a measurement set (part of owlcat,
https://github.com/ratt-ru/owlcat). Reuses dosho's existing `OWLCAT` image
(the same package already ports `owlcat_plotelev.py`'s
`plot-elevation-tracks.py`).

Ported field-by-field from `flag-ms.py --help` (owlcat 1.8.1), matching
cult-cargo's `flagms.yml`.
"""

from __future__ import annotations

from shinobi.steps.schema import ParamMeta, Policies

from dosho import images
from dosho._builder import define_cab

_FIELDS: dict[str, tuple[str, bool, object]] = {
    "ms": ("MS", True, None),
    "channels": ("str", False, None),
    "timeslots": ("str", False, None),
    "timeslot_multiplier": ("float", False, 1.0),
    "corrs": ("str", False, None),
    "stations": ("str", False, None),
    "ifrs": ("str", False, None),
    "ddid": ("str", False, None),
    "field": ("str", False, None),
    "taql": ("str", False, None),
    "above": ("float", False, None),
    "below": ("float", False, None),
    "nan": ("bool", False, None),
    "fm_above": ("float", False, None),
    "fm_below": ("float", False, None),
    "data_column": ("str", False, "CORRECTED_DATA"),
    "data_flagmask": ("str", False, "ALL"),
    "flagged_any": ("str", False, None),
    "flagged_all": ("str", False, None),
    "flag": ("str", False, None),
    "unflag": ("str", False, None),
    "copy_flags": ("str", False, None),
    "copy_legacy": ("str", False, None),
    "fill_legacy": ("str", False, None),
    "create": ("bool", False, None),
    "init_bitflags": ("int", False, None),
    "reinit_bitflags": ("int", False, None),
    "incr_stman": ("bool", False, None),
    "list_info": ("bool", False, None),
    "stats": ("bool", False, None),
    "remove": ("str", False, None),
    "export": ("File", False, None),
    "import_": ("File", False, None),
    "restore": ("str", False, None),
    "save": ("str", False, None),
    "force": ("bool", False, None),
    "verbose": ("int", False, 0),
    "timestamps": ("bool", False, None),
    "chunk_size": ("int", False, 200000),
}

_FIELD_META: dict[str, ParamMeta] = {
    "ms": ParamMeta(info="Measurement set to operate on", positional=True),
    "channels": ParamMeta(
        nom_de_guerre="channels", info="Channel selection: N, or start:end[:step] / start~end[:step]"
    ),
    "timeslots": ParamMeta(info="Timeslot selection: N, or start:end / start~end"),
    "timeslot_multiplier": ParamMeta(
        nom_de_guerre="timeslot-multiplier", info="Multiplies the timeslot numbers given via --timeslots"
    ),
    "corrs": ParamMeta(info="Correlation selection: comma-separated list of indices"),
    "stations": ParamMeta(info="Station (antenna) selection: comma-separated list of indices"),
    "ifrs": ParamMeta(info='Interferometer selection (use "-I help" for syntax help)'),
    "ddid": ParamMeta(info="DATA_DESC_ID selection: single number, or comma-separated list"),
    "field": ParamMeta(info="FIELD_ID selection: single number, or comma-separated list"),
    "taql": ParamMeta(info="Additional TaQL selection to restrict the subset"),
    "above": ParamMeta(info="Select on abs(data) > X"),
    "below": ParamMeta(info="Select on abs(data) < X"),
    "nan": ParamMeta(info="Select on invalid data (NaN or infinite)"),
    "fm_above": ParamMeta(nom_de_guerre="fm-above", info="Select on mean(abs(data)) > X over frequencies"),
    "fm_below": ParamMeta(nom_de_guerre="fm-below", info="Select on mean(abs(data)) < X over frequencies"),
    "data_column": ParamMeta(
        nom_de_guerre="data-column", info="Data column for --above/--below/--nan"
    ),
    "data_flagmask": ParamMeta(
        nom_de_guerre="data-flagmask", info="Flags to apply to the data column when e.g. computing the mean"
    ),
    "flagged_any": ParamMeta(
        nom_de_guerre="flagged-any", info="Selects if any of the specified FLAGS are raised"
    ),
    "flagged_all": ParamMeta(
        nom_de_guerre="flagged-all", info="Selects if all of the specified FLAGS are raised"
    ),
    "flag": ParamMeta(info="Raise the specified FLAGS (added to the output FLAGS)"),
    "unflag": ParamMeta(info="Clear the specified FLAGS (removed from the output FLAGS)"),
    "copy_flags": ParamMeta(nom_de_guerre="copy", info="Copy the selection to the specified FLAGS (replaces output FLAGS)"),
    "copy_legacy": ParamMeta(
        nom_de_guerre="copy-legacy", info="Shortcut for --flagged-any +L --copy FLAGS --fill-legacy -"
    ),
    "fill_legacy": ParamMeta(
        nom_de_guerre="fill-legacy",
        info="Fill legacy FLAG/FLAG_ROW columns using the specified FLAGS (use '-' to skip, '0' to clear)",
    ),
    "create": ParamMeta(info="With --flag: create the named flagset if it doesn't exist"),
    "init_bitflags": ParamMeta(
        nom_de_guerre="init-bitflags", info="Initialise a BITFLAG column with this many bits (8, 16 or 32)"
    ),
    "reinit_bitflags": ParamMeta(
        nom_de_guerre="reinit-bitflags",
        info="Remove (if any) and reinitialise a BITFLAG column with this many bits (8, 16 or 32)",
    ),
    "incr_stman": ParamMeta(
        nom_de_guerre="incr-stman",
        info="Force the incremental storage manager for new BITFLAG columns [default: same as DATA]",
    ),
    "list_info": ParamMeta(nom_de_guerre="list", info="List MS info: flagsets, CASA flagversions if available"),
    "stats": ParamMeta(info="Print per-flagset flagging stats"),
    "remove": ParamMeta(info="Unflag and remove the named flagset(s) (comma-separated list)"),
    "export": ParamMeta(
        info="Export all flags to this flag file (.gz for gzip-compressed); done after any flagging actions"
    ),
    "import_": ParamMeta(
        nom_de_guerre="import",
        info="Import flags from this flag file; done before any flagging actions",
    ),
    "restore": ParamMeta(info="Restore flags from a CASA-style flagversion (see --list for names)"),
    "save": ParamMeta(info="Save flags to a CASA-style flagversion"),
    "force": ParamMeta(info="With --save: force overwrite of an existing CASA-style flagversion"),
    "verbose": ParamMeta(info="Verbosity level for messages (higher is more verbose)"),
    "timestamps": ParamMeta(info="Add timestamps to verbosity messages"),
    "chunk_size": ParamMeta(nom_de_guerre="chunk-size", info="Number of rows to process at once"),
}

flagms = define_cab(
    "flagms",
    "flag-ms.py",
    images.OWLCAT,
    _FIELDS,
    field_meta=_FIELD_META,
    policies=Policies(prefix="--"),
    info="flag-ms.py: manipulates flags (bitflags and legacy FLAG/FLAG_ROW) in a measurement set",
)
