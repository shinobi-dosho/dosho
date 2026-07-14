"""`@shinobi.pystep` wrapper for PyBDSF's source-finding catalog workflow
(`bdsf.process_image` + `Image.write_catalog`,
https://github.com/lofar-astron/PyBDSF).

PyBDSF has no standalone CLI binary -- `process_image`/`write_catalog` are
plain Python functions taking `**kwargs` validated against an internal
options registry (`bdsf.opts.Opts`, 158 traits), not a fixed signature --
cult-cargo's own `bdsf.yml` is `flavour: python-code` for exactly this
reason. Per `AGENTS.md` ("never import/execute an external Cab's own
schema-generation code"), this is a `@shinobi.pystep` instead (matching
`casatasks.py`), calling `ctx.import_func("process_image", "bdsf")` inside
the running container.

The 15 `process_image` options here, plus `write_catalog`'s `catalog_format`,
are the same curated subset cult-cargo's own `bdsf.yml` exposes (out of
158 real `Opts` traits) -- not arbitrarily chosen, but cross-checked
field-by-field against `bdsf.opts.Opts` (introspected directly: every trait
has a `.doc()`/`._default`/`._type`), which caught two real staleness bugs
in cult-cargo's version: `rms_map`'s real type is a tri-state
`True`/`False`/`None` enum, not a plain `bool`, and `src_radius_pix` is a
`float`, not an `int`. `write_catalog`'s real default `format` is `"bbs"`,
not cult-cargo's claimed `"ascii"`. Only options the caller actually sets
are forwarded to `process_image`/`write_catalog`, so every other one of the
158 traits still gets PyBDSF's own default -- exactly `AGENTS.md`'s "leave
the field out and come back when a real pipeline needs it" for the
remaining ~140.
"""

from __future__ import annotations

from pathlib import Path

import shinobi
from pydantic import BaseModel

from dosho import images


class BdsfCatalogOutputs(BaseModel):
    """Outputs of the `bdsf.catalog` step."""

    outfile_gaul: Path | None = None
    outfile_srl: Path | None = None
    outdir: Path


@shinobi.pystep(name="bdsf-catalog", image=images.BDSF)
def catalog(
    ctx,
    image: Path,
    outfile_gaul: Path | None = None,
    outfile_srl: Path | None = None,
    catalog_format: str = "bbs",
    detection_image: Path | None = None,
    thresh_isl: float = 3.0,
    thresh_pix: float = 5.0,
    rms_box: tuple[int, int] | None = None,
    rms_map: bool | None = None,
    adaptive_rms_box: bool = False,
    trim_box: tuple[int, int, int, int] | None = None,
    flagging_opts: bool = False,
    flag_maxsize_bm: float | None = None,
    spectralindex_do: bool = False,
    polarisation_do: bool = False,
    advanced_opts: bool = False,
    src_ra_dec: list[tuple[float, float]] | None = None,
    src_radius_pix: float | None = None,
) -> BdsfCatalogOutputs:
    """Source-find within an image (PyBDSF's `process_image`) and write a
    Gaussian and/or source catalog (`write_catalog`).

    Args:
        ctx: The pystep execution context.
        image: Input image (FITS or CASA 2/3/4-D cube) to source-find.
        outfile_gaul: Path to write the Gaussian-list catalog to. At least
            one of `outfile_gaul`/`outfile_srl` must be given.
        outfile_srl: Path to write the source-list catalog to.
        catalog_format: Output catalog format -- one of "fits", "ascii",
            "bbs", "ds9", "star", "kvis", "sagecal", "csv", "casabox".
        detection_image: Separate image used only for detecting islands of
            emission; source measurement is still done on `image`.
        thresh_isl: Island-boundary threshold, in sigma above the mean.
        thresh_pix: Source-detection (island-peak) threshold, in sigma
            above the mean.
        rms_box: `(box, step)` in pixels for the rms/mean map calculation.
        rms_map: Background rms map: `True` for a 2-D map, `False` for a
            constant rms, `None` to let PyBDSF decide.
        adaptive_rms_box: Use an adaptive `rms_box` when computing the
            rms/mean maps.
        trim_box: `(xmin, xmax, ymin, ymax)` in pixels -- source-detect on
            only this part of the image.
        flagging_opts: Enable Gaussian-flagging options (e.g.
            `flag_maxsize_bm`).
        flag_maxsize_bm: Flag a Gaussian if its area exceeds this many
            times the beam area.
        spectralindex_do: Calculate spectral indices (multi-channel image).
        polarisation_do: Find polarisation properties.
        advanced_opts: Enable PyBDSF's advanced options.
        src_ra_dec: Source positions (RA, Dec in degrees) at which to force
            fitting.
        src_radius_pix: Fitting radius (pixels) around each `src_ra_dec`
            position; defaults to the beam major-axis FWHM.

    Returns:
        `BdsfCatalogOutputs` with whichever of `outfile_gaul`/`outfile_srl`
        were written, and their common `outdir`.
    """
    if outfile_gaul is None and outfile_srl is None:
        raise ValueError("bdsf.catalog: at least one of outfile_gaul/outfile_srl must be given")

    process_image_kwargs = {
        k: v
        for k, v in dict(
            detection_image=str(detection_image) if detection_image else None,
            thresh_isl=thresh_isl,
            thresh_pix=thresh_pix,
            rms_box=rms_box,
            rms_map=rms_map,
            adaptive_rms_box=adaptive_rms_box,
            trim_box=trim_box,
            flagging_opts=flagging_opts,
            flag_maxsize_bm=flag_maxsize_bm,
            spectralindex_do=spectralindex_do,
            polarisation_do=polarisation_do,
            advanced_opts=advanced_opts,
            src_ra_dec=src_ra_dec,
            src_radius_pix=src_radius_pix,
        ).items()
        if v is not None
    }

    process_image = ctx.import_func("process_image", "bdsf")
    img = process_image(str(image), quiet=True, **process_image_kwargs)

    if outfile_gaul is not None:
        img.write_catalog(
            outfile=str(outfile_gaul), format=catalog_format, catalog_type="gaul", clobber=True
        )
    if outfile_srl is not None:
        img.write_catalog(
            outfile=str(outfile_srl), format=catalog_format, catalog_type="srl", clobber=True
        )

    outdir = (outfile_gaul or outfile_srl).parent
    return BdsfCatalogOutputs(outfile_gaul=outfile_gaul, outfile_srl=outfile_srl, outdir=outdir)
