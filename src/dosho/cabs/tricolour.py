"""tricolour -- RFI flagger (https://github.com/ratt-ru/tricolour).

Ported field-by-field from cult-cargo's tricolour.yml (flat, static
schema).
"""

from __future__ import annotations

from shinobi.steps.schema import ParamMeta, Policies

from dosho import images
from dosho._builder import define_cab

_FIELDS: dict[str, tuple[str, bool, object]] = {
    "ms": ("MS", False, None),
    "config": ("File", False, None),
    "ignore_flags": ("bool", False, None),
    "flagging_strategy": ("str", False, None),
    "row_chunks": ("int", False, None),
    "baseline_chunks": ("int", False, None),
    "nworkers": ("int", False, None),
    "dilate_masks": ("Union[int,str]", False, None),
    "data_column": ("str", False, None),
    "field_names": ("str", False, None),
    "scan_numbers": ("str", False, None),
    "disable_post_mortem": ("bool", False, True),
    "window_backend": ("str", False, None),
    "temporary_directory": ("Directory", False, None),
    "subtract_model_column": ("str", False, None),
}

_FIELD_META: dict[str, ParamMeta] = {
    "ms": ParamMeta(positional=True),
    "ignore_flags": ParamMeta(nom_de_guerre="ignore-flags"),
    "flagging_strategy": ParamMeta(nom_de_guerre="flagging-strategy"),
    "row_chunks": ParamMeta(nom_de_guerre="row-chunks"),
    "baseline_chunks": ParamMeta(nom_de_guerre="baseline-chunks"),
    "dilate_masks": ParamMeta(nom_de_guerre="dilate-masks"),
    "data_column": ParamMeta(nom_de_guerre="data-column"),
    "field_names": ParamMeta(nom_de_guerre="field-names"),
    "disable_post_mortem": ParamMeta(nom_de_guerre="disable-post-mortem"),
    "window_backend": ParamMeta(nom_de_guerre="window-backend"),
    "temporary_directory": ParamMeta(nom_de_guerre="temporary-directory"),
    "subtract_model_column": ParamMeta(nom_de_guerre="subtract-model-column"),
}

tricolour = define_cab(
    "tricolour",
    "tricolour",
    images.TRICOLOUR,
    _FIELDS,
    # tricolour flags in place -- re-declare ms as an output so a
    # dependent step can chain onto the flagged MS.
    outputs={"ms": ("MS", False, None)},
    field_meta=_FIELD_META,
    policies=Policies(),
    info="Tricolour RFI flagger (https://github.com/ratt-ru/tricolour)",
)
