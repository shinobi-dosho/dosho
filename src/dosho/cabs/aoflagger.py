"""aoflagger -- automatic RFI flagger (https://aoflagger.readthedocs.io).

Ported field-by-field from cult-cargo's aoflagger.yml (a flat, static
schema -- no dynamic_schema, no package-scoped _include -- so this is a
mechanical transcription, not a structural fix like wsclean/cubical/
quartical).
"""

from __future__ import annotations

from shinobi.steps.schema import ParamMeta, Policies

from dosho import images
from dosho._builder import define_cab

_FIELDS: dict[str, tuple[str, bool, object]] = {
    "msname": ("MS", True, None),
    "verbose": ("bool", False, False),
    "threads": ("int", False, None),
    "strategy": ("File", False, None),
    "indirect_read": ("bool", False, True),
    "memory_read": ("bool", False, False),
    "auto_read_mode": ("bool", False, True),
    "uvw": ("bool", False, False),
    "column": ("str", False, "DATA"),
    "skip_flagged": ("bool", False, False),
    "bands": ("int", False, None),
    "fields": ("int", False, None),
}

_FIELD_META: dict[str, ParamMeta] = {
    "msname": ParamMeta(info="MS name(s) to be flagged"),
    "verbose": ParamMeta(nom_de_guerre="v", info="Produce verbose output"),
    "threads": ParamMeta(
        nom_de_guerre="j",
        info="overrides the number of threads specified in the strategy (default: one thread for each CPU core)",
    ),
    "strategy": ParamMeta(info="specifies a possible customized strategy"),
    "indirect_read": ParamMeta(
        nom_de_guerre="indirect-read",
        info="will reorder the measurement set before starting, which is normally faster but requires free disk space to reorder the data to",
    ),
    "memory_read": ParamMeta(
        nom_de_guerre="memory-read",
        info="will read the entire measurement set in memory. This is the fastest, but requires much memory.",
    ),
    "auto_read_mode": ParamMeta(
        nom_de_guerre="auto-read-mode",
        info="will select either memory or direct mode based on available memory",
    ),
    "uvw": ParamMeta(info="reads uvw values (some exotic strategies require these)"),
    "column": ParamMeta(info="specify column to flag"),
    "skip_flagged": ParamMeta(
        nom_de_guerre="skip-flagged",
        info="will skip an ms if it has already been processed by AOFlagger according to its HISTORY table.",
    ),
    "bands": ParamMeta(info="comma separated list of (zero-indexed) band ids to process"),
    "fields": ParamMeta(info="Field ID(s). Comma separated string if more than one field"),
}

cab = define_cab(
    "aoflagger",
    "aoflagger",
    images.AOFLAGGER,
    _FIELDS,
    field_meta=_FIELD_META,
    policies=Policies(prefix="-"),
    info="AOFlagger automatic RFI flagger (https://aoflagger.readthedocs.io)",
)
