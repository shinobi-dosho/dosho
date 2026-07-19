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
from dosho._builder import FieldSpec, define_cab

_FIELDS: dict[str, FieldSpec] = {
    "restored_image": (
        "File", False, None,
        ParamMeta(
            nom_de_guerre="restored-image",
            info="Restored image file from which to build the mask",
        ),
    ),
    "mask_image": (
        "File", False, None,
        ParamMeta(
            nom_de_guerre="mask-image",
            info="Input mask file(s). Either restored-image or mask-image must be specified.",
        ),
    ),
    "threshold": (
        "float", False, 6.5,
        ParamMeta(info="Sigma threshold for masking (default = 6.5)"),
    ),
    "boxsize": (
        "int", False, 50,
        ParamMeta(info="Box size over which to compute stats (default = 50)"),
    ),
    "savenoise": ("bool", False, None, ParamMeta(info="Export noise image as FITS file")),
    "merge": ("List[File]", False, None, ParamMeta(info="Merge one or more masks or region files")),
    "subtract": (
        "List[File]", False, None,
        ParamMeta(info="Subtract one or more masks or region files"),
    ),
    "number_islands": (
        "bool", False, None,
        ParamMeta(nom_de_guerre="number-islands", info="Number the islands detected"),
    ),
    "remove_islands": (
        "List[Union[int,str]]", False, None,
        ParamMeta(
            nom_de_guerre="remove-islands",
            info="Remove islands from input mask (list by number or coordinates), e.g. "
            "--remove-islands 1,18,20,20h10m13s:14d15m20s",
        ),
    ),
    "ignore_missing_islands": (
        "bool", False, None,
        ParamMeta(
            nom_de_guerre="ignore-missing-islands",
            info="Do not throw an error if an island specified by coordinates does not exist",
        ),
    ),
    "extract_islands": (
        "List[Union[int,str]]", False, None,
        ParamMeta(
            nom_de_guerre="extract-islands",
            info="Extract islands from input mask (list by number or coordinates), e.g. "
            "--extract-islands 1,18,20,20h10m13s:14d15m20s",
        ),
    ),
    "minimum_size": (
        "int", False, None,
        ParamMeta(
            nom_de_guerre="minimum-size",
            info="Remove islands with areas fewer than or equal to the specified number of pixels",
        ),
    ),
    "make_binary": (
        "bool", False, None,
        ParamMeta(nom_de_guerre="make-binary", info="Replace all island numbers with 1"),
    ),
    "invert": ("bool", False, None, ParamMeta(info="Invert the mask")),
    "dilate": ("int", False, None, ParamMeta(info="Apply dilation with a radius of R pixels")),
    "erode": ("int", False, None, ParamMeta(info="Apply N iterations of erosion")),
    "fill_holes": (
        "bool", False, None,
        ParamMeta(nom_de_guerre="fill-holes", info="Fill holes (closed regions) in the mask"),
    ),
    "sum_peak": (
        "float", False, None,
        ParamMeta(
            nom_de_guerre="sum-peak",
            info="Sum-to-peak ratio of flux islands to mask in original image",
        ),
    ),
    "ncpu": ("int", False, None, ParamMeta(info="Number of processors to use for cataloging")),
    "beam_size": (
        "float", False, None,
        ParamMeta(
            nom_de_guerre="beam-size",
            info="Average beam size in arcsec if missing in the image header",
        ),
    ),
    "gui": ("bool", False, None, ParamMeta(info="Open mask in bokeh html gui")),
    "outfile": (
        "File", False, None,
        ParamMeta(info="The output mask image (default based on input name)"),
    ),
    "outcatalog": (
        "File", False, None,
        ParamMeta(info="Generate a catalog based on the region mask"),
    ),
    "outregion": ("File", False, None, ParamMeta(info="Generate polygon regions from the mask")),
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
    policies=Policies(prefix="--", repeat_list=True),
    info="breizorro: mask creation and manipulation for radio astronomy images "
    "(https://github.com/ratt-ru/breizorro)",
)
