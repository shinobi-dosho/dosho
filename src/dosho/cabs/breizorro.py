"""breizorro -- mask creation and manipulation for radio astronomy images
(https://github.com/ratt-ru/breizorro).

Ported field-by-field from `breizorro --help` (breizorro 0.2.0), cross-checked
against cult-cargo's `genesis/breizorro/breizorro.yaml`. `merge`/`subtract`/
`remove-islands`/`extract-islands` are all click `multiple=True` options
(repeatable flags), the same shape as `msutils.py`'s `flagstats`
`field`/`antenna` -- cab-level `repeat_list` policy.

`outfile`'s cult-cargo default is an `=IFSET(...)` expression (derive the
output name from whichever of `restored-image`/`mask-image` was given) --
per AGENTS.md, expression languages aren't resolved here, so `outfile` is
left as a plain optional output with no `implicit` template: breizorro
already computes its own default filename internally when `-o` is omitted,
so nothing is lost by not modelling that computation here.
"""

from __future__ import annotations

from shinobi.steps.schema import ParamMeta, Policies

from dosho import images
from dosho._builder import define_cab

_FIELDS: dict[str, tuple[str, bool, object]] = {
    "restored_image": ("File", False, None),
    "mask_image": ("File", False, None),
    "threshold": ("float", False, 6.5),
    "boxsize": ("int", False, 50),
    "savenoise": ("bool", False, None),
    "merge": ("List[File]", False, None),
    "subtract": ("List[File]", False, None),
    "number_islands": ("bool", False, None),
    "remove_islands": ("List[Union[int,str]]", False, None),
    "ignore_missing_islands": ("bool", False, None),
    "extract_islands": ("List[Union[int,str]]", False, None),
    "minimum_size": ("int", False, None),
    "make_binary": ("bool", False, None),
    "invert": ("bool", False, None),
    "dilate": ("int", False, None),
    "erode": ("int", False, None),
    "fill_holes": ("bool", False, None),
    "sum_peak": ("float", False, None),
    "ncpu": ("int", False, None),
    "beam_size": ("float", False, None),
    "gui": ("bool", False, None),
    "outfile": ("File", False, None),
    "outcatalog": ("File", False, None),
    "outregion": ("File", False, None),
}

_FIELD_META: dict[str, ParamMeta] = {
    "restored_image": ParamMeta(
        nom_de_guerre="restored-image",
        info="Restored image file from which to build the mask",
    ),
    "mask_image": ParamMeta(
        nom_de_guerre="mask-image",
        info="Input mask file(s). Either restored-image or mask-image must be specified.",
    ),
    "threshold": ParamMeta(info="Sigma threshold for masking (default = 6.5)"),
    "boxsize": ParamMeta(info="Box size over which to compute stats (default = 50)"),
    "savenoise": ParamMeta(info="Export noise image as FITS file"),
    "merge": ParamMeta(info="Merge one or more masks or region files"),
    "subtract": ParamMeta(info="Subtract one or more masks or region files"),
    "number_islands": ParamMeta(nom_de_guerre="number-islands", info="Number the islands detected"),
    "remove_islands": ParamMeta(
        nom_de_guerre="remove-islands",
        info="Remove islands from input mask (list by number or coordinates), "
        "e.g. --remove-islands 1,18,20,20h10m13s:14d15m20s",
    ),
    "ignore_missing_islands": ParamMeta(
        nom_de_guerre="ignore-missing-islands",
        info="Do not throw an error if an island specified by coordinates does not exist",
    ),
    "extract_islands": ParamMeta(
        nom_de_guerre="extract-islands",
        info="Extract islands from input mask (list by number or coordinates), "
        "e.g. --extract-islands 1,18,20,20h10m13s:14d15m20s",
    ),
    "minimum_size": ParamMeta(
        nom_de_guerre="minimum-size",
        info="Remove islands with areas fewer than or equal to the specified number of pixels",
    ),
    "make_binary": ParamMeta(nom_de_guerre="make-binary", info="Replace all island numbers with 1"),
    "invert": ParamMeta(info="Invert the mask"),
    "dilate": ParamMeta(info="Apply dilation with a radius of R pixels"),
    "erode": ParamMeta(info="Apply N iterations of erosion"),
    "fill_holes": ParamMeta(nom_de_guerre="fill-holes", info="Fill holes (closed regions) in the mask"),
    "sum_peak": ParamMeta(
        nom_de_guerre="sum-peak", info="Sum-to-peak ratio of flux islands to mask in original image"
    ),
    "ncpu": ParamMeta(info="Number of processors to use for cataloging"),
    "beam_size": ParamMeta(
        nom_de_guerre="beam-size", info="Average beam size in arcsec if missing in the image header"
    ),
    "gui": ParamMeta(info="Open mask in bokeh html gui"),
    "outfile": ParamMeta(info="The output mask image (default based on input name)"),
    "outcatalog": ParamMeta(info="Generate a catalog based on the region mask"),
    "outregion": ParamMeta(info="Generate polygon regions from the mask"),
}

breizorro = define_cab(
    "breizorro",
    "breizorro",
    images.BREIZORRO,
    _FIELDS,
    outputs={
        "outfile": ("File", False, None),
        "outcatalog": ("File", False, None),
        "outregion": ("File", False, None),
    },
    field_meta=_FIELD_META,
    policies=Policies(prefix="--", repeat_list=True),
    info="breizorro: mask creation and manipulation for radio astronomy images "
    "(https://github.com/ratt-ru/breizorro)",
)
