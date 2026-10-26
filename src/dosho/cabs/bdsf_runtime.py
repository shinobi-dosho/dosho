"""Small native PyBDSF and multiprocessing runtime qualification step."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

import dosho
from dosho import images


class RuntimeProbeOutputs(BaseModel):
    scratch: Path
    receipt: Path
    catalog: Path
    fitted_sources: int
    socket_address_bytes: int


@dosho.pystep(
    name="bdsf-runtime-probe",
    image=images.BDSF,
    cache=False,
    write_paths=["scratch", "receipt", "catalog"],
)
def probe(
    ctx,
    scratch: Path,
    receipt: Path,
    catalog: Path,
    expected_tmp: str = "/ninja-tmp",
) -> RuntimeProbeOutputs:
    """Exercise the real container image, manager socket and blended source fit."""
    import json
    import multiprocessing
    import os
    import tempfile

    np = ctx.import_module("numpy")
    fits = ctx.import_module("astropy.io.fits")
    bdsf = ctx.import_module("bdsf")

    if tempfile.gettempdir() != expected_tmp or os.environ.get("TMPDIR") != expected_tmp:
        raise ValueError("native TMPDIR is not the private container mount")
    scratch = Path(scratch)
    scratch.mkdir(mode=0o700, parents=True, exist_ok=True)
    if scratch.is_symlink() or receipt.parent != scratch or catalog.parent != scratch:
        raise ValueError("probe outputs must be inside its private scratch directory")

    manager = multiprocessing.Manager()
    try:
        address = manager._address
        if not isinstance(address, str):
            raise ValueError(f"manager did not use an AF_UNIX pathname: {address!r}")
        if not Path(address).is_relative_to(expected_tmp):
            raise ValueError(f"manager socket escaped native TMPDIR: {address}")
        address_bytes = len(os.fsencode(address))
        if address_bytes >= 108:
            raise ValueError(f"manager AF_UNIX address too long: {address_bytes} bytes")
        shared = manager.dict()
        shared["probe"] = "ready"
        if shared["probe"] != "ready":
            raise ValueError("manager IPC round trip failed")
    finally:
        manager.shutdown()

    y, x = np.mgrid[0:160, 0:160]
    centres = [(64, 64), (76, 70), (88, 76), (76, 88), (64, 78), (94, 88), (88, 62)]
    data = np.random.default_rng(0).normal(0, 1, (160, 160)) + sum(
        500 * np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / 13.52) for cx, cy in centres
    )
    header = fits.Header(
        {
            "CTYPE1": "RA---SIN",
            "CRVAL1": 0.0,
            "CDELT1": -0.5 / 3600,
            "CRPIX1": 80,
            "CUNIT1": "deg",
            "CTYPE2": "DEC--SIN",
            "CRVAL2": -30.0,
            "CDELT2": 0.5 / 3600,
            "CRPIX2": 80,
            "CUNIT2": "deg",
            "BMAJ": 3 / 3600,
            "BMIN": 3 / 3600,
            "BPA": 0.0,
            "BUNIT": "Jy/beam",
        }
    )
    image = scratch / "blended-seven.fits"
    fits.writeto(image, data.astype("float32"), header, overwrite=False)
    process_image = ctx.import_func("process_image", "bdsf")
    fitted = process_image(
        str(image),
        thresh_isl=3.0,
        thresh_pix=5.0,
        frequency=1.4e9,
        ncores=2,
        quiet=True,
    )
    if fitted.nsrc < 1:
        raise ValueError("PyBDSF fitted no sources in the blended seven source image")
    fitted.write_catalog(outfile=str(catalog), format="ascii", catalog_type="gaul", clobber=False)
    if not catalog.is_file() or catalog.stat().st_size == 0:
        raise ValueError("PyBDSF wrote no Gaussian catalogue")
    report = {
        "tmpdir": tempfile.gettempdir(),
        "manager_address": address,
        "socket_address_bytes": address_bytes,
        "bdsf_version": bdsf.__version__,
        "numpy_version": np.__version__,
        "fitted_sources": int(fitted.nsrc),
        "catalog": str(catalog),
    }
    with receipt.open("x") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
    return RuntimeProbeOutputs(
        scratch=scratch,
        receipt=receipt,
        catalog=catalog,
        fitted_sources=report["fitted_sources"],
        socket_address_bytes=address_bytes,
    )
