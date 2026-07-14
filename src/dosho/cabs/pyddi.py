"""pyddi -- finds directions subject to direction-dependent effects
(https://github.com/IanHeywood/pyddi).

Ported field-by-field from `pyddi --help` (pyddi 0.0.4), matching
cult-cargo's `pyddi.yml` (a flat, static, up-to-date schema).
"""

from __future__ import annotations

from shinobi.steps.schema import ParamMeta, Policies

from dosho import images
from dosho._builder import define_cab

_FIELDS: dict[str, tuple[str, bool, object]] = {
    "image": ("File", True, None),
    "psf_image": ("File", False, None),
    "catalog": ("File", False, None),
    "flux_thresh": ("float", False, 10.0),
    "variance_thresh": ("float", False, 5.0),
    "variance_size": ("int", False, 10),
    "correlation_thresh": ("float", False, 0.5),
    "correlation_size": ("int", False, 5),
    "group_pixels": ("int", False, 20),
    "exclude_radius": ("float", False, 0.0),
    "use_catalog": ("bool", False, None),
    "output_prefix": ("str", False, None),
}

_FIELD_META: dict[str, ParamMeta] = {
    "image": ParamMeta(nom_de_guerre="image", info="Image of interest"),
    "psf_image": ParamMeta(nom_de_guerre="psf-image", info="The psf image"),
    "catalog": ParamMeta(
        nom_de_guerre="catalog",
        info='Sky model as LSM/txt, in Tigger format: "#format:name, ra_d, dec_d, i"',
    ),
    "flux_thresh": ParamMeta(
        nom_de_guerre="flux-thresh",
        info="Flux threshold. Regions in an image with flux > fth * noise are considered.",
    ),
    "variance_thresh": ParamMeta(
        nom_de_guerre="variance-thresh",
        info="Local variance threshold. Sources with variance > vth * noise are considered.",
    ),
    "variance_size": ParamMeta(
        nom_de_guerre="variance-size", info="Size of the region to compute the local variance"
    ),
    "correlation_thresh": ParamMeta(
        nom_de_guerre="correlation-thresh",
        info="Correlation threshold. Sources with correlation factor > cth are considered.",
    ),
    "correlation_size": ParamMeta(
        nom_de_guerre="correlation-size", info="Size of the region to compute correlation"
    ),
    "group_pixels": ParamMeta(
        nom_de_guerre="group-pixels",
        info="Size of the region to group the pixels, in terms of psf-size",
    ),
    "exclude_radius": ParamMeta(nom_de_guerre="exclude-radius", info="Radius to exclude, in arcseconds"),
    "use_catalog": ParamMeta(
        nom_de_guerre="use-catalog", info="Use the catalog for identification, not only the image"
    ),
    "output_prefix": ParamMeta(
        nom_de_guerre="prefix",
        info="Prefix for the output file containing directions (RA/Dec in degrees, peak flux)",
    ),
}

pyddi = define_cab(
    "pyddi",
    "pyddi",
    images.PYDDI,
    _FIELDS,
    field_meta=_FIELD_META,
    policies=Policies(prefix="--"),
    info="pyddi: finds directions subject to direction-dependent effects "
    "(https://github.com/IanHeywood/pyddi)",
)
