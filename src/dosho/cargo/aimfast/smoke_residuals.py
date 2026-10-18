"""Exercise AIMFAST's residual FITS workflow, including Bokeh and JSON output."""

import json
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from astropy.io import fits

with TemporaryDirectory() as work:
    root = Path(work)
    yy, xx = np.indices((128, 128))
    source = 0.05 * np.exp(-((xx - 64) ** 2 + (yy - 64) ** 2) / 32)
    noise = np.random.default_rng(7).normal(0, 0.001, source.shape)
    header = fits.Header()
    for axis, ctype, crval, cdelt in (
        (1, "RA---SIN", 180.0, -0.0005555555555555556),
        (2, "DEC--SIN", -30.0, 0.0005555555555555556),
        (3, "FREQ", 1.4e9, 1e6),
        (4, "STOKES", 1.0, 1.0),
    ):
        header[f"CTYPE{axis}"] = ctype
        header[f"CRPIX{axis}"] = 64.0 if axis <= 2 else 1.0
        header[f"CRVAL{axis}"] = crval
        header[f"CDELT{axis}"] = cdelt
    header["BMAJ"] = 0.002777777777777778
    header["BMIN"] = 0.002777777777777778
    header["BPA"] = 0.0
    for name, scale in (("first.fits", 1.0), ("second.fits", 1.1)):
        data = (source * scale + noise).astype(np.float32)[None, None]
        fits.writeto(root / name, data, header)
    result = subprocess.run(
        ["aimfast", "--compare-residuals", "first.fits", "second.fits", "--outfile", "result.json"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stdout[-2000:] + result.stderr[-2000:])
    if not json.loads((root / "result.json").read_text()):
        raise RuntimeError("AIMFAST wrote an empty result")
    if not (root / "RandomResidualNoiseRatio.html").stat().st_size:
        raise RuntimeError("AIMFAST wrote an empty residual plot")
