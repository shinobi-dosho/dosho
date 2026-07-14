"""crystalball -- predicts model visibilities from a WSClean-format sky
model (https://github.com/caracal-pipeline/crystalball).

Ported field-by-field from cult-cargo's crystalball.yml (flat, static
schema).
"""

from __future__ import annotations

from shinobi.steps.schema import ParamMeta, Policies

from dosho import images
from dosho._builder import define_cab

_FIELDS: dict[str, tuple[str, bool, object]] = {
    "ms": ("MS", True, None),
    "field": ("str", False, None),
    "output_column": ("str", True, None),
    "sky_model": ("File", True, None),
    "within": ("File", False, None),
    "num_sources": ("int", False, None),
    "points_only": ("bool", False, False),
    "memory_fraction": ("float", False, 0.1),
    "num_workers": ("int", False, 4),
}

_FIELD_META: dict[str, ParamMeta] = {
    "ms": ParamMeta(positional=True),
    "field": ParamMeta(
        info="The field name or id to be predicted. If not provided, only a single field may be present in the MS."
    ),
    "output_column": ParamMeta(nom_de_guerre="output-column"),
    "sky_model": ParamMeta(nom_de_guerre="sky-model", info="Wsclean format sky model file."),
    "within": ParamMeta(
        info="A JS9 region file to constrain the model. Only sources within those regions will be included."
    ),
    "num_sources": ParamMeta(nom_de_guerre="num-sources", info="Select only N brightest sources"),
    "points_only": ParamMeta(nom_de_guerre="points-only", info="Select only point-type sources"),
    "memory_fraction": ParamMeta(
        nom_de_guerre="memory-fraction",
        info="Fraction of system RAM that can be used. Used when setting automatically the chunk size.",
    ),
    "num_workers": ParamMeta(
        nom_de_guerre="num-workers", info="Explicitly set the number of worker threads."
    ),
}

crystalball = define_cab(
    "crystalball",
    "crystalball",
    images.CRYSTALBALL,
    _FIELDS,
    # crystalball writes model visibilities into output_column in place --
    # re-declare ms as an output so a dependent step can chain onto it.
    outputs={"ms": ("MS", False, None)},
    field_meta=_FIELD_META,
    policies=Policies(),
    info="Crystalball: predict model visibilities from a sky model (https://github.com/caracal-pipeline/crystalball)",
)
