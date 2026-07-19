"""tricolour -- RFI flagger (https://github.com/ratt-ru/tricolour).

Ported field-by-field from cult-cargo's tricolour.yml (flat, static
schema).
"""

from __future__ import annotations

from shinobi.steps.schema import ParamMeta, Policies

from dosho import images
from dosho._builder import FieldSpec, define_cab

_FIELDS: dict[str, FieldSpec] = {
    "ms": ("MS", False, None, ParamMeta(positional=True)),
    "config": ("File", False, None),
    "ignore-flags": ("bool", False, None),
    "flagging-strategy": ("str", False, None),
    "row-chunks": ("int", False, None),
    "baseline-chunks": ("int", False, None),
    "nworkers": ("int", False, None),
    "dilate-masks": ("Union[int,str]", False, None),
    "data-column": ("str", False, None),
    "field-names": ("str", False, None),
    "scan_numbers": ("str", False, None),
    "disable-post-mortem": ("bool", False, True),
    "window-backend": ("str", False, None),
    "temporary-directory": ("Directory", False, None),
    "subtract-model-column": ("str", False, None),
}

tricolour = define_cab(
    "tricolour",
    "tricolour",
    images.TRICOLOUR,
    _FIELDS,
    # tricolour flags in place -- re-declare ms as an output so a
    # dependent step can chain onto the flagged MS.
    outputs={"ms": ("MS", False, None)},
    policies=Policies(),
    info="Tricolour RFI flagger (https://github.com/ratt-ru/tricolour)",
)
