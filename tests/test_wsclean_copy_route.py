"""Admission proof for a separate native file creator beside a strict MS writer."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
from astropy.io import fits
from pydantic import BaseModel
from shinobi import Recipe
from shinobi.backends.native import NativeBackend
from shinobi.cabs import get
from shinobi.cache import get_cache_manifest
from shinobi.exceptions import CabRunError
from shinobi.results import BackendRun

from tests.test_flagversion_restore import _fixture
from tests.test_wsclean_runtime import fixture_products


class Empty(BaseModel):
    pass


@pytest.mark.parametrize("channels,niter,corrupt", [(1, 0, False), (3, 10, False), (3, 10, True)])
def test_ordinary_copy_cab_with_family_selector_is_admitted_after_strict_producer(
    tmp_path, monkeypatch, channels, niter, corrupt
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SHINOBI_OWNERSHIP_REGISTRY", str(tmp_path / "registry.json"))
    vis, _, _, _, _ = _fixture(tmp_path)
    from casacore.tables import makearrcoldesc, maketabdesc, table

    with table(str(vis), readonly=False, ack=False) as ms:
        ms.addcols(maketabdesc([makearrcoldesc("DATA", 0j, ndim=2)]))
        ms.putcol("DATA", np.ones((3, 3, 2), dtype=np.complex64))
    screen, parset = tmp_path / "screen.fits", tmp_path / "screen.parset"
    screen.write_bytes(b"fixture dependency")
    parset.write_text(f"aterms=[diagonal]\ndiagonal.images=[{screen}]\n")
    helper = get("wsclean-normalize-stokes-i").with_backend("native")
    helper.command = f"{sys.executable} -m dosho.cli wsclean-normalize-stokes-i"
    original_run = NativeBackend.run
    calls = []
    raw_before = {}

    def run(self, cab, argv, inputs, **kwargs):
        calls.append(cab.name)
        if cab.name == "wsclean-idg-aterm":
            _, paths = fixture_products(inputs["prefix"], channels=channels, niter=niter)
            if corrupt:
                with fits.open(paths[0, "image_pb"], mode="update") as hdus:
                    hdus[0].data[0, 0, 0, 0] = 999
            raw_before.update({p: (p.read_bytes(), p.stat().st_mtime_ns) for p in paths.values()})
            return BackendRun(returncode=0)
        return original_run(self, cab, argv, inputs, **kwargs)

    monkeypatch.setattr(NativeBackend, "run", run)
    recipe = Recipe(name="copy-route", inputs_model=Empty, outputs_model=Empty)
    recipe.add_step(
        "raw",
        get("wsclean-idg-aterm"),
        ms=vis,
        prefix=str(tmp_path / "raw"),
        size=[3, 2],
        scale="36asec",
        aterm_config=parset,
        aterm_image=screen,
        nchan=channels,
        niter=niter,
    )
    recipe.add_step(
        "normalized",
        helper,
        source_prefix=str(tmp_path / "raw"),
        prefix=str(tmp_path / "normalized"),
        nchan=channels,
        niter=niter,
        receipt=tmp_path / "normalized-normalization.json",
        **{
            "native_" + field: [
                recipe.outputs("raw", field).select(
                    time=0, frequency=freq, polarization="I", component="real"
                )
                for freq in ([*range(channels), "mfs"] if channels > 1 else [0])
            ]
            for field in (
                ("image", "image_pb", "beam", "model", "residual", "model_pb", "residual_pb")
                if niter
                else ("image", "image_pb", "beam")
            )
        },
    )
    if corrupt:
        with pytest.raises(CabRunError, match="normalized"):
            recipe(backend="native", cache=True, cache_dir=str(tmp_path / "cache"))
        assert {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in raw_before} == raw_before
        assert not list(tmp_path.glob("normalized*"))
        manifest = get_cache_manifest(str(tmp_path / "cache"))
        assert manifest.entry("copy-route.raw") is not None
        assert manifest.entry("copy-route.normalized") is None
        return
    result = recipe(backend="native", cache=True, cache_dir=str(tmp_path / "cache"))
    assert result.success and calls == ["wsclean-idg-aterm", "wsclean-normalize-stokes-i"]
    family = result.sub_results["normalized"].outputs.image_pb
    selected = family.select(time=0, frequency=0, polarization="I", component="real")
    native_name = "raw-0000-image-pb.fits" if channels > 1 else "raw-image-pb.fits"
    normalized_name = (
        "normalized-0000-image-pb.fits" if channels > 1 else "normalized-image-pb.fits"
    )
    assert Path(selected).absolute() == tmp_path / normalized_name

    assert fits.getheader(selected)["CRVAL4"] == 1
    assert fits.getheader(tmp_path / native_name)["CRVAL4"] == 4
    assert np.array_equal(
        fits.getdata(selected), fits.getdata(tmp_path / native_name), equal_nan=True
    )

    sources = list(tmp_path.glob("raw*.fits"))
    unchanged = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in sources}
    second = recipe(backend="native", cache=True, cache_dir=str(tmp_path / "cache"))
    assert second.success and second.sub_results["raw"].cached
    assert not second.sub_results["normalized"].cached
    assert calls.count("wsclean-idg-aterm") == 1
    assert calls.count("wsclean-normalize-stokes-i") == 2
    assert {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in sources} == unchanged
