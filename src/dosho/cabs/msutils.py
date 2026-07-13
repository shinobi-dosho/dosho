"""msutils -- MS manipulation utilities, one module-level object per
``msutils`` sub-command (matching `simms.py`/`casatasks.py`'s
multi-export convention).

Transcribed field-by-field from msutils 2.x's click CLI
(https://github.com/sphemakh/msutils, `src/msutils/cli.py`). msutils 2.0
was a ground-up refactor: the package/console script is now the lowercase
`msutils` binary exposing a click *group* (`msutils COMMAND [ARGS]`),
replacing the old flat `msutils.py`/`MSUtils` module functions. Each
sub-command below is a sibling of the same `msutils` binary (one shared
`MSUTILS` image), not a separate tool.

Sub-commands:

* `summary`  -- dump MS metadata (fields/SPWs/antennas/scans/corrs),
  optionally to JSON.
* `addcol`   -- add a column, cloning shape/type from an existing one.
* `copycol`  -- copy one column's data to another.
* `sumcols`  -- sum (or, with ``--subtract``, difference) columns.
* `addnoise` -- add Gaussian visibility noise from an SEFD (or stddev).
* `flagstats`-- out-of-core flag statistics + matplotlib summary plot
  (needs the image's ``msutils[flagstats]`` extra).

The column-mutating sub-commands (`addcol`/`copycol`/`sumcols`/`addnoise`)
edit the MS in place, so each re-declares `ms` as an output.
"""

from __future__ import annotations

from shinobi.steps.schema import ParamMeta, Policies

from dosho import images
from dosho._builder import define_cab

# --- summary ---------------------------------------------------------------
# `json_out` (not `json`) avoids pydantic's "field shadows BaseModel.json"
# warning; `nom_de_guerre="json"` keeps the tool's real `--json` flag.
_SUMMARY_FIELDS: dict[str, tuple[str, bool, object]] = {
    "ms": ("MS", True, None),
    "json_out": ("File", False, None),
    "quiet": ("bool", False, None),
}

_SUMMARY_FIELD_META: dict[str, ParamMeta] = {
    "ms": ParamMeta(info="Measurement set to summarise", positional=True),
    "json_out": ParamMeta(
        nom_de_guerre="json", info="Also write the summary to this JSON file."
    ),
    "quiet": ParamMeta(info="Do not print the summary."),
}

summary = define_cab(
    "msutils-summary",
    "msutils summary",
    images.MSUTILS,
    _SUMMARY_FIELDS,
    outputs={"json_out": ("File", False, None)},
    field_meta=_SUMMARY_FIELD_META,
    policies=Policies(),
    info="msutils summary: dump MS metadata (fields, SPWs, antennas, scans, correlations)",
)

# --- addcol ----------------------------------------------------------------
_ADDCOL_FIELDS: dict[str, tuple[str, bool, object]] = {
    "ms": ("MS", True, None),
    "colname": ("str", True, None),
    "clone": ("str", False, "DATA"),
    "valuetype": ("str", False, None),
    "init-with": ("float", False, None),
}

_ADDCOL_FIELD_META: dict[str, ParamMeta] = {
    "ms": ParamMeta(info="Measurement set to add the column to", positional=True),
    "colname": ParamMeta(info="Name of the column to add", positional=True),
    "clone": ParamMeta(info="Existing column to clone shape/type from."),
    "valuetype": ParamMeta(info="Column value type, e.g. 'complex', 'float', 'scalar'."),
    "init_with": ParamMeta(info="Initialise the new column with this (float) value."),
}

addcol = define_cab(
    "msutils-addcol",
    "msutils addcol",
    images.MSUTILS,
    _ADDCOL_FIELDS,
    outputs={"ms": ("MS", False, None)},
    field_meta=_ADDCOL_FIELD_META,
    policies=Policies(),
    info="msutils addcol: add a column to an MS, cloning shape/type from an existing one",
)

# --- copycol ---------------------------------------------------------------
_COPYCOL_FIELDS: dict[str, tuple[str, bool, object]] = {
    "ms": ("MS", True, None),
    "fromcol": ("str", True, None),
    "tocol": ("str", True, None),
}

_COPYCOL_FIELD_META: dict[str, ParamMeta] = {
    "ms": ParamMeta(info="Measurement set to operate on", positional=True),
    "fromcol": ParamMeta(info="Source column to copy from", positional=True),
    "tocol": ParamMeta(info="Destination column (created if it does not exist)", positional=True),
}

copycol = define_cab(
    "msutils-copycol",
    "msutils copycol",
    images.MSUTILS,
    _COPYCOL_FIELDS,
    outputs={"ms": ("MS", False, None)},
    field_meta=_COPYCOL_FIELD_META,
    policies=Policies(),
    info="msutils copycol: copy one column's data to another (creating it if needed)",
)

# --- sumcols ---------------------------------------------------------------
_SUMCOLS_FIELDS: dict[str, tuple[str, bool, object]] = {
    "ms": ("MS", True, None),
    "cols": ("List[str]", True, None),
    "out": ("str", True, None),
    "subtract": ("bool", False, None),
}

_SUMCOLS_FIELD_META: dict[str, ParamMeta] = {
    "ms": ParamMeta(info="Measurement set to operate on", positional=True),
    "cols": ParamMeta(
        info="Columns to combine (two or more; exactly two with --subtract).",
        positional=True,
        repeat_as_tokens=True,
    ),
    "out": ParamMeta(info="Output column."),
    "subtract": ParamMeta(
        info="Subtract the second column from the first (needs exactly 2 cols)."
    ),
}

sumcols = define_cab(
    "msutils-sumcols",
    "msutils sumcols",
    images.MSUTILS,
    _SUMCOLS_FIELDS,
    outputs={"ms": ("MS", False, None)},
    field_meta=_SUMCOLS_FIELD_META,
    policies=Policies(),
    info="msutils sumcols: sum (or, with --subtract, difference) MS columns into a new column",
)

# --- addnoise --------------------------------------------------------------
_ADDNOISE_FIELDS: dict[str, tuple[str, bool, object]] = {
    "ms": ("MS", True, None),
    "column": ("str", False, "MODEL_DATA"),
    "sefd": ("float", False, 551.0),
    "noise": ("float", False, 0.0),
    "add-to": ("str", False, None),
}

_ADDNOISE_FIELD_META: dict[str, ParamMeta] = {
    "ms": ParamMeta(info="Measurement set to operate on", positional=True),
    "column": ParamMeta(info="Column to write noisy visibilities into."),
    "sefd": ParamMeta(info="SEFD (Jy) used to compute per-visibility noise."),
    "noise": ParamMeta(info="Noise stddev; if 0, computed from --sefd."),
    "add_to": ParamMeta(
        info="Add the noise to this column's data instead of writing pure noise."
    ),
}

addnoise = define_cab(
    "msutils-addnoise",
    "msutils addnoise",
    images.MSUTILS,
    _ADDNOISE_FIELDS,
    outputs={"ms": ("MS", False, None)},
    field_meta=_ADDNOISE_FIELD_META,
    policies=Policies(),
    info="msutils addnoise: add Gaussian visibility noise to an MS (from an SEFD or stddev)",
)

# --- flagstats -------------------------------------------------------------
# `--field`/`--antenna` are click `multiple=True` options (the flag is
# repeated per value: `--field 0 --field 1`), so this cab uses the
# cab-level `repeat_list` policy -- the only list-valued fields here are
# exactly those two.
_FLAGSTATS_FIELDS: dict[str, tuple[str, bool, object]] = {
    "ms": ("MS", True, None),
    "plot": ("File", False, None),
    "json_out": ("File", False, None),
    "field": ("List[str]", False, None),
    "antenna": ("List[str]", False, None),
}

_FLAGSTATS_FIELD_META: dict[str, ParamMeta] = {
    "ms": ParamMeta(info="Measurement set to compute flag statistics for", positional=True),
    "plot": ParamMeta(info="Output PNG plot file."),
    "json_out": ParamMeta(nom_de_guerre="json", info="Output JSON statistics file."),
    "field": ParamMeta(info="Field id/name to include (repeatable)."),
    "antenna": ParamMeta(info="Antenna id/name to include (repeatable)."),
}

flagstats = define_cab(
    "msutils-flagstats",
    "msutils flagstats",
    images.MSUTILS,
    _FLAGSTATS_FIELDS,
    outputs={"plot": ("File", False, None), "json_out": ("File", False, None)},
    field_meta=_FLAGSTATS_FIELD_META,
    policies=Policies(repeat_list=True),
    info="msutils flagstats: out-of-core flag statistics + matplotlib summary plot",
)
