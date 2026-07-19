"""aoflagger -- automatic RFI flagger (https://aoflagger.readthedocs.io).

Ported field-by-field from cult-cargo's aoflagger.yml (a flat, static
schema -- no dynamic_schema, no package-scoped _include -- so this is a
mechanical transcription, not a structural fix like wsclean/cubical/
quartical).
"""

from __future__ import annotations

from shinobi.steps.schema import ParamMeta, Policies

from dosho import images
from dosho._builder import FieldSpec, define_cab

_FIELDS: dict[str, FieldSpec] = {
    "msname": ("MS", True, None, ParamMeta(info="MS name(s) to be flagged")),
    "verbose": ("bool", False, False, ParamMeta(nom_de_guerre="v", info="Produce verbose output")),
    "threads": (
        "int", False, None,
        ParamMeta(
            nom_de_guerre="j",
            info="overrides the number of threads specified in the strategy (default: one thread "
            "for each CPU core)",
        ),
    ),
    "strategy": ("File", False, None, ParamMeta(info="specifies a possible customized strategy")),
    "indirect_read": (
        "bool", False, True,
        ParamMeta(
            nom_de_guerre="indirect-read",
            info="will reorder the measurement set before starting, which is normally faster but "
            "requires free disk space to reorder the data to",
        ),
    ),
    "memory_read": (
        "bool", False, False,
        ParamMeta(
            nom_de_guerre="memory-read",
            info="will read the entire measurement set in memory. This is the fastest, but "
            "requires much memory.",
        ),
    ),
    "auto_read_mode": (
        "bool", False, True,
        ParamMeta(
            nom_de_guerre="auto-read-mode",
            info="will select either memory or direct mode based on available memory",
        ),
    ),
    "uvw": (
        "bool", False, False,
        ParamMeta(info="reads uvw values (some exotic strategies require these)"),
    ),
    "column": ("str", False, "DATA", ParamMeta(info="specify column to flag")),
    "skip_flagged": (
        "bool", False, False,
        ParamMeta(
            nom_de_guerre="skip-flagged",
            info="will skip an ms if it has already been processed by AOFlagger according to its "
            "HISTORY table.",
        ),
    ),
    "bands": (
        "int", False, None,
        ParamMeta(info="comma separated list of (zero-indexed) band ids to process"),
    ),
    "fields": (
        "int", False, None,
        ParamMeta(info="Field ID(s). Comma separated string if more than one field"),
    ),
}

aoflagger = define_cab(
    "aoflagger",
    "aoflagger",
    images.AOFLAGGER,
    _FIELDS,
    # aoflagger flags in place -- re-declare msname as an output so a
    # dependent step can chain onto the flagged MS.
    outputs={"msname": ("MS", False, None)},
    policies=Policies(prefix="-"),
    info="AOFlagger automatic RFI flagger (https://aoflagger.readthedocs.io)",
)
