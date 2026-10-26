"""Generated native-shaped products; tiny stock/fixed parity is qualified separately."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from astropy.io import fits

from dosho.cabs.wsclean_runtime import normalize_stokes_i


def fixture_products(prefix, channels=3, niter=10, stokes=4, checksum=False):
    prefix = Path(prefix)
    prefix.parent.mkdir(exist_ok=True)
    kinds = ["image", "model", "residual"] if niter else ["image"]
    arrays, headers, outputs = {}, {}, {}
    weights = [1.0 + i / 10 for i in range(channels)]
    for i in range(channels):
        beam = np.array([[2, 0.5, 1e-6], [0, -1, 5e-7]], np.float32)
        arrays[i, "beam"] = beam
        for kind in kinds:
            array = np.full((2, 3), (i + 1) * (kinds.index(kind) + 1), np.float32)
            arrays[i, kind] = array
            corrected = np.full(array.shape, np.nan, np.float32)
            np.divide(array, beam, out=corrected, where=beam > 1e-6)
            arrays[i, kind + "_pb"] = corrected
    if channels > 1:
        for field in ["beam", *kinds, *(k + "_pb" for k in kinds)]:
            total, denominator = np.zeros((2, 3), np.float32), np.zeros((2, 3), np.float64)
            for i, weight in enumerate(weights):
                data = arrays[i, field].astype(np.float64)
                finite = np.isfinite(data)
                total += np.where(finite, data * weight, 0)
                denominator += np.where(finite, weight, 0)
            with np.errstate(invalid="ignore", divide="ignore"):
                arrays["mfs", field] = (total.astype(np.float64) / denominator).astype(np.float32)
    for (freq, field), array in arrays.items():
        suffix = "" if channels == 1 else "-MFS" if freq == "mfs" else f"-{freq:04d}"
        name = field.replace("_pb", "-pb")
        path = Path(str(prefix) + suffix + "-" + name + ".fits")
        h = fits.Header()
        for axis, ctype in enumerate(("RA---SIN", "DEC--SIN", "FREQ", "STOKES"), 1):
            h[f"CTYPE{axis}"] = ctype
            h[f"CRPIX{axis}"] = 1.0
            h[f"CRVAL{axis}"] = (
                0.1,
                -0.2,
                1.4e9 + (0 if freq == "mfs" else freq) * 1e6,
                stokes if field.endswith("_pb") else 1,
            )[axis - 1]
            h[f"CDELT{axis}"] = (-0.01, 0.01, channels * 1e6 if freq == "mfs" else 1e6, 1.0)[
                axis - 1
            ]
        h["CUNIT1"], h["CUNIT2"], h["CUNIT3"] = "deg", "deg", "Hz"
        if freq == "mfs":
            h["CRVAL3"] = 1.4e9 + (channels - 1) * 0.5e6
        h["BSCALE"], h["BZERO"] = 1.0, 0.0
        h["BUNIT"] = "JY/PIXEL" if field == "model" and freq != "mfs" else "JY/BEAM"
        if (field != "beam" or freq == "mfs") and not (
            niter and freq == "mfs" and field in ("image", "image_pb")
        ):
            h["WSCIMGWG"] = sum(weights) if freq == "mfs" else weights[freq]
        fits.PrimaryHDU(array[None, None], h).writeto(path, checksum=checksum, overwrite=True)
        headers[freq, field] = path
        if field != "beam":
            outputs.setdefault(field, {"resolved": True, "members": []})["members"].append(
                {
                    "coordinates": {
                        "time": 0,
                        "frequency": freq,
                        "polarization": "I",
                        "component": "real",
                    },
                    "value": path,
                }
            )
    return outputs, headers


def context(tmp_path, channels=3, niter=10, stokes=4, checksum=False):
    source_prefix = tmp_path / "native"
    _, paths = fixture_products(source_prefix, channels, niter, stokes, checksum)
    fields = ("image", "model", "residual", "image_pb", "model_pb", "residual_pb", "beam")
    sources = {field: [p for (_, f), p in paths.items() if f == field] for field in fields}
    return {
        "source_prefix": source_prefix,
        "prefix": tmp_path / "normalized",
        "nchan": channels,
        "niter": niter,
        "sources": sources,
        "receipt": tmp_path / "normalization.json",
    }, paths


@pytest.mark.parametrize(
    "channels,niter,checksum", [(1, 0, False), (3, 0, True), (3, 10, False), (3, 10, True)]
)
def test_v_header_only_normalization_and_exact_payload(tmp_path, channels, niter, checksum):
    params, paths = context(tmp_path, channels, niter, checksum=checksum)
    before = {p: p.read_bytes() for p in paths.values()}
    if checksum:
        with pytest.raises(ValueError, match="existing CHECKSUM"):
            normalize_stokes_i(**params)
        assert {p: p.read_bytes() for p in paths.values()} == before
        assert not list(tmp_path.glob("normalized*"))
        return
    report = normalize_stokes_i(**params)
    assert report["input_stokes"] == 4 and report["output_stokes"] == 1
    assert json.loads(params["receipt"].read_text()) == report
    for record in report["products"]:
        if "destination" not in record:
            continue
        source, destination = Path(record["path"]), Path(record["destination"])
        assert source.read_bytes() == before[source]
        assert fits.getheader(destination)["CRVAL4"] == 1
        with fits.open(destination) as hdus:
            offset = hdus[0].fileinfo()["datLoc"]
            assert destination.read_bytes()[offset:] == before[source][offset:]
            if checksum:
                assert hdus[0].verify_checksum() == hdus[0].verify_datasum() == 1
                assert hdus[0].header["DATASUM"] == fits.getheader(source)["DATASUM"]
    assert {p: p.read_bytes() for p in paths.values()} == before


@pytest.mark.parametrize("checksum", [False, True])
def test_i_products_are_validated_and_copied_without_source_writes(tmp_path, checksum):
    params, paths = context(tmp_path, stokes=1, checksum=checksum)
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in paths.values()}
    report = normalize_stokes_i(**params)
    assert {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in paths.values()} == before
    for record in report["products"]:
        if "destination" in record:
            assert Path(record["destination"]).read_bytes() == Path(record["path"]).read_bytes()
            assert Path(record["destination"]).stat().st_ino != Path(record["path"]).stat().st_ino


@pytest.mark.parametrize(
    "change",
    [
        "q",
        "u",
        "mixed",
        "grid",
        "units",
        "ordinary_stokes",
        "channel",
        "mask",
        "mfs",
        "weight",
        "frequency",
        "missing",
        "extra",
        "symlink",
        "hardlink",
        "extension",
        "scaling",
    ],
)
def test_invalid_product_refuses_before_any_copy(tmp_path, change):
    params, paths = context(tmp_path)
    target = paths[0, "image_pb"]
    if change in (
        "q",
        "u",
        "mixed",
        "grid",
        "units",
        "ordinary_stokes",
        "weight",
        "frequency",
        "scaling",
    ):
        path = paths[0, "image"] if change == "ordinary_stokes" else target
        key, value = {
            "q": ("CRVAL4", 2),
            "u": ("CRVAL4", 3),
            "mixed": ("CRVAL4", 1),
            "grid": ("CRVAL1", 9),
            "units": ("BUNIT", "K"),
            "ordinary_stokes": ("CRVAL4", 4),
            "weight": ("WSCIMGWG", 9),
            "frequency": ("CRVAL3", 9),
            "scaling": ("BSCALE", 2),
        }[change]
        with fits.open(path, mode="update") as hdus:
            hdus[0].header[key] = value
    elif change in ("channel", "mask", "mfs"):
        path = paths["mfs", "residual_pb"] if change == "mfs" else target
        with fits.open(path, mode="update") as hdus:
            hdus[0].data[0, 0, 0, 0] = np.nan if change == "mask" else 900
    elif change == "missing":
        target.unlink()
    elif change == "extra":
        params["sources"]["image_pb"].append(target)
    elif change == "symlink":
        target.unlink()
        target.symlink_to(paths[0, "image"])
    elif change == "hardlink":
        target.unlink()
        target.hardlink_to(paths[0, "image"])
    else:
        with fits.open(target, mode="append") as hdus:
            hdus.append(fits.ImageHDU(np.ones((2, 3))))
    before = {p: p.read_bytes() for p in paths.values() if p.exists()}
    with pytest.raises((ValueError, FileNotFoundError)):
        normalize_stokes_i(**params)
    assert {p: p.read_bytes() for p in before} == before
    assert not list(tmp_path.glob("normalized*"))
    assert not params["receipt"].exists()


@pytest.mark.parametrize("patch", [{"nchan": 0}, {"niter": -1}, {"nchan": 2}])
def test_invalid_shapes_refuse_without_outputs(tmp_path, patch):
    params, _ = context(tmp_path)
    params.update(patch)
    with pytest.raises(ValueError):
        normalize_stokes_i(**params)
    assert not list(tmp_path.glob("normalized*"))


def test_disjoint_output_required(tmp_path):
    params, paths = context(tmp_path)
    params["prefix"] = params["source_prefix"]
    before = {p: p.read_bytes() for p in paths.values()}
    with pytest.raises(ValueError, match="disjoint"):
        normalize_stokes_i(**params)
    assert {p: p.read_bytes() for p in paths.values()} == before


def test_copy_failure_cleans_only_own_outputs_and_preserves_sources(tmp_path, monkeypatch):
    import errno

    from fitstoolz.apps import header

    params, paths = context(tmp_path)
    before = {p: p.read_bytes() for p in paths.values()}
    unrelated = tmp_path / "normalized-unrelated.txt"
    unrelated.write_text("keep")

    def full(opts):
        Path(opts.outfile).write_bytes(b"partial")
        raise OSError(errno.ENOSPC, "fixture quota")

    monkeypatch.setattr(header, "runit", full)
    with pytest.raises(OSError, match="fixture quota"):
        normalize_stokes_i(**params)
    assert {p: p.read_bytes() for p in paths.values()} == before
    assert list(tmp_path.glob("normalized*")) == [unrelated]
    assert not params["receipt"].exists()


def test_native_rendered_mfs_omits_weight_while_residual_model_keep_aggregate(tmp_path):
    params, paths = context(tmp_path, channels=3, niter=10)
    assert "WSCIMGWG" not in fits.getheader(paths["mfs", "image"])
    assert "WSCIMGWG" not in fits.getheader(paths["mfs", "image_pb"])
    assert fits.getheader(paths["mfs", "residual"])["WSCIMGWG"] > 0
    assert normalize_stokes_i(**params)["output_stokes"] == 1
