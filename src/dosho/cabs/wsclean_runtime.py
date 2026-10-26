"""Guarded native IDG Stokes-I normalization into independently owned copies."""

from __future__ import annotations


def normalize_stokes_i(*, source_prefix, prefix, nchan, niter, sources, receipt):
    """Prove the bounded native I/V signature, then create normalized copies.

    Sources are explicit readonly paths from the native producer's captured
    families. This command is deliberately uncached; it never modifies source
    products, opens an MS, or publishes a producer's dataset successor.
    """
    import hashlib
    import json
    import stat
    from contextlib import ExitStack
    from pathlib import Path
    from types import SimpleNamespace

    import numpy as np
    from astropy.io import fits
    from fitstoolz import __version__ as fitstoolz_version
    from fitstoolz.apps.header import runit as header_operation

    if fitstoolz_version != "0.2.2":
        raise ValueError("header normalization requires qualified fitstoolz==0.2.2")

    channels = nchan
    if type(channels) is not int or channels < 1 or type(niter) is not int or niter < 0:
        raise ValueError("invalid native channel/iteration count")
    kinds = ["image", "model", "residual"] if niter > 0 else ["image"]
    frequencies = [*range(channels), "mfs"] if channels > 1 else [0]
    source_prefix, output_prefix, receipt = (
        Path(source_prefix).absolute(),
        Path(prefix).absolute(),
        Path(receipt).absolute(),
    )
    fields = ["image", "model", "residual", "image_pb", "model_pb", "residual_pb", "beam"]
    if set(sources) != set(fields):
        raise ValueError("all seven native source families must be explicit")
    products, identities = {}, set()
    for field in fields:
        expected = frequencies if field == "beam" or field.removesuffix("_pb") in kinds else []
        paths = [Path(p).absolute() for p in sources[field]]
        if len(paths) != len(expected) or len(set(paths)) != len(paths):
            raise ValueError(f"incomplete, duplicate or unexpected source family: {field}")
        for freq in expected:
            suffix = "" if channels == 1 else "-MFS" if freq == "mfs" else f"-{freq:04d}"
            wanted = Path(str(source_prefix) + suffix + "-" + field.replace("_pb", "-pb") + ".fits")
            if wanted not in paths:
                raise ValueError(f"unexpected native source name: {field}")
            products[freq, field] = wanted
    for path in products.values():
        info = path.lstat()
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1
            or any(p.is_symlink() for p in (path, *path.parents))
        ):
            raise ValueError(f"native source must be a nonaliased regular file: {path}")
        identity = (info.st_dev, info.st_ino)
        if identity in identities:
            raise ValueError("aliased native sources")
        identities.add(identity)
    destinations = {
        key: Path(str(output_prefix) + str(path)[len(str(source_prefix)) :])
        for key, path in products.items()
        if key[1].endswith("_pb")
    }
    targets = [*destinations.values(), receipt]
    if len(set(targets)) != len(targets) or any(p in products.values() for p in targets):
        raise ValueError("normalization requires disjoint owned outputs")
    for path in targets:
        if (
            path.exists()
            or any(p.is_symlink() for p in (path, *path.parents))
            or any(
                source.is_relative_to(path) or path.is_relative_to(source)
                for source in products.values()
            )
        ):
            raise ValueError("normalization output exists, aliases or overlaps a native source")

    def payload(path, offset, size):
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            stream.seek(offset)
            while size:
                block = stream.read(min(size, 1024 * 1024))
                if not block:
                    raise ValueError("truncated generated FITS payload")
                digest.update(block)
                size -= len(block)
        return digest.hexdigest()

    def compare(observed, expected, label):
        # Native arrays and division are float32. Exact nonfinite masks remain
        # mandatory; tolerance only covers finite arithmetic/serialization.
        if (
            not np.array_equal(np.isnan(observed), np.isnan(expected))
            or not np.array_equal(np.isposinf(observed), np.isposinf(expected))
            or not np.array_equal(np.isneginf(observed), np.isneginf(expected))
        ):
            raise ValueError(f"nonfinite mask differs: {label}")
        finite = np.isfinite(expected)
        if not np.allclose(observed[finite], expected[finite], rtol=2e-5, atol=1e-7):
            raise ValueError(f"native numerical proof failed: {label}")

    records, signatures, checks = {}, set(), []
    with ExitStack() as stack:
        opened = {}
        grid = None
        for key, path in products.items():
            hdus = stack.enter_context(fits.open(path, memmap=True, do_not_scale_image_data=True))
            hdu, header = hdus[0], hdus[0].header
            if (
                len(hdus) != 1
                or not isinstance(hdu, fits.PrimaryHDU)
                or header.get("BITPIX") != -32
                or header.get("NAXIS") != 4
                or hdu.data.shape[:2] != (1, 1)
                or header.get("BSCALE", 1) != 1
                or header.get("BZERO", 0) != 0
                or any(k in header for k in ("BLANK", "ZIMAGE"))
            ):
                raise ValueError(f"unsupported native FITS structure: {path}")
            if any(header.count(k) != 1 for k in header if k not in ("COMMENT", "HISTORY", "")):
                raise ValueError("duplicate native FITS metadata")
            if (
                [header.get(f"CTYPE{i}") for i in range(1, 5)]
                != ["RA---SIN", "DEC--SIN", "FREQ", "STOKES"]
                or header.get("CRPIX4") != 1
                or header.get("CDELT4") != 1
            ):
                raise ValueError(f"unsupported native WCS: {path}")
            spatial = tuple(
                header.get(k)
                for k in (
                    "NAXIS1",
                    "NAXIS2",
                    "CTYPE1",
                    "CTYPE2",
                    "CRVAL1",
                    "CRVAL2",
                    "CRPIX1",
                    "CRPIX2",
                    "CDELT1",
                    "CDELT2",
                    "CUNIT1",
                    "CUNIT2",
                    "EQUINOX",
                    "LONPOLE",
                    "LATPOLE",
                )
            )
            if grid is None:
                grid = spatial
            if spatial != grid:
                raise ValueError("native product spatial grids differ")
            if any(
                k.startswith(("CD1_", "CD2_", "PC1_", "PC2_", "PV", "A_", "B_")) for k in header
            ):
                raise ValueError("unsupported native WCS matrix/distortion")
            freq, field = key
            stokes = header.get("CRVAL4")
            if field.endswith("_pb"):
                signatures.add(stokes)
                if stokes == 4 and "CHECKSUM" in header:
                    raise ValueError(
                        "fitstoolz V-to-I operation does not support existing CHECKSUM"
                    )
                if stokes not in (1, 4):
                    raise ValueError(
                        "corrected products require uniform native I or demonstrated V"
                    )
            elif stokes != 1:
                raise ValueError("ordinary/beam product is not Stokes I")
            # Native IDG passes the restored writer even for model-pb: it
            # intentionally retains Jy/beam while ordinary model is Jy/pixel.
            unit = "JY/PIXEL" if field == "model" and freq != "mfs" else "JY/BEAM"
            if str(header.get("BUNIT", "")).upper() != unit:
                raise ValueError(f"unexpected native units: {field}")
            if (
                header.get("CUNIT3", "").upper() != "HZ"
                or header.get("CRPIX3") != 1
                or not np.isfinite(header.get("CRVAL3", np.nan))
                or not np.isfinite(header.get("CDELT3", np.nan))
                or header["CDELT3"] <= 0
            ):
                raise ValueError("invalid native frequency metadata")
            if ("CHECKSUM" in header and hdu.verify_checksum() != 1) or (
                "DATASUM" in header and hdu.verify_datasum() != 1
            ):
                raise ValueError("invalid existing FITS checksum")
            opened[key] = hdu
            info = hdu.fileinfo()
            records[key] = {
                "path": str(path),
                "stokes_in": stokes,
                "stokes_out": 1,
                "bunit": header["BUNIT"],
                "offset": info["datLoc"],
                "size": info["datSpan"],
                "payload_sha256": payload(path, info["datLoc"], info["datSpan"]),
                "source_header_sha256": payload(path, 0, info["datLoc"]),
                "source_mtime_ns": path.stat().st_mtime_ns,
                "source_bytes": path.stat().st_size,
            }
        if len(signatures) != 1:
            raise ValueError("mixed corrected Stokes signatures")
        for freq in frequencies:
            reference_field = "residual" if freq == "mfs" and "residual" in kinds else "image"
            ref = opened[(freq, reference_field)].header
            weight = ref.get("WSCIMGWG", np.nan)
            if not np.isfinite(weight) or weight <= 0:
                raise ValueError("native channel weights must be finite and positive")
            for field in [*kinds, *(k + "_pb" for k in kinds), "beam"]:
                h = opened[(freq, field)].header
                rendered_without_weight = (
                    freq == "mfs"
                    and "residual" in kinds
                    and field in ("image", "image_pb")
                    and "WSCIMGWG" not in h
                )
                if (
                    any(h[k] != ref[k] for k in ("CRVAL3", "CDELT3", "CRPIX3"))
                    or (
                        field != "beam"
                        and not rendered_without_weight
                        and h.get("WSCIMGWG") != weight
                    )
                    or (field == "beam" and "WSCIMGWG" in h and h["WSCIMGWG"] != weight)
                ):
                    raise ValueError("native frequency/weight lineage differs")
        height = grid[1]
        for freq in range(channels):
            beam = opened[(freq, "beam")].data[0, 0]
            for kind in kinds:
                for start in range(0, height, 128):
                    rows = slice(start, start + 128)
                    b = beam[rows]
                    if not np.isfinite(b).all():
                        raise ValueError("nonfinite native scalar beam")
                    apparent = opened[(freq, kind)].data[0, 0, rows]
                    if not np.isfinite(apparent).all():
                        raise ValueError("nonfinite apparent channel product")
                    expected = np.full(apparent.shape, np.nan, dtype=np.float32)
                    np.divide(apparent, b, out=expected, where=b > 1e-6)
                    compare(
                        opened[(freq, kind + "_pb")].data[0, 0, rows], expected, f"{freq}/{kind}"
                    )
                checks.append(f"channel/{freq}/{kind}: apparent/beam, cutoff=1e-6")
        if channels > 1:
            weights = [opened[(i, "image")].header["WSCIMGWG"] for i in range(channels)]
            low = min(
                opened[(i, "image")].header["CRVAL3"] - opened[(i, "image")].header["CDELT3"] / 2
                for i in range(channels)
            )
            high = max(
                opened[(i, "image")].header["CRVAL3"] + opened[(i, "image")].header["CDELT3"] / 2
                for i in range(channels)
            )
            h = opened[("mfs", "residual" if "residual" in kinds else "image")].header
            if not np.allclose(
                [h["CRVAL3"], h["CDELT3"], h["WSCIMGWG"]],
                [(low + high) / 2, high - low, sum(weights)],
                rtol=1e-10,
                atol=0,
            ):
                raise ValueError("MFS frequency/weight lineage differs")
            # MakeMFSImage accumulates into float32, divides by finite-pixel
            # weight sums. The restored MFS image is rendered, NOT divided by
            # the MFS beam. Its renderer is covered by stock/fixed native parity.
            fields = (
                ["beam", "image", "image_pb"]
                if kinds == ["image"]
                else ["beam", "model", "residual", "model_pb", "residual_pb"]
            )
            for field in fields:
                for start in range(0, height, 128):
                    rows = slice(start, start + 128)
                    shape = opened[(0, field)].data[0, 0, rows].shape
                    total, denominator = np.zeros(shape, np.float32), np.zeros(shape, np.float64)
                    for i, weight in enumerate(weights):
                        data = opened[(i, field)].data[0, 0, rows].astype(np.float64)
                        finite = np.isfinite(data)
                        total += np.where(finite, data * weight, 0)
                        denominator += np.where(finite, weight, 0)
                    with np.errstate(invalid="ignore", divide="ignore"):
                        expected = (total.astype(np.float64) / denominator).astype(np.float32)
                    compare(opened[("mfs", field)].data[0, 0, rows], expected, "mfs/" + field)
                checks.append("mfs/" + field + ": finite-pixel weighted channels")
        # All products are validated before the first card change.
    created = []
    try:
        for key, destination in destinations.items():
            source = products[key]
            record = records[key]
            destination.parent.mkdir(parents=True, exist_ok=True)
            # Fitstoolz owns the copy/header operation. Its API overwrites,
            # so reassert absence under the workflow's existing output claim.
            if destination.exists() or destination.is_symlink():
                raise ValueError("fitstoolz output must be a fresh owned path")
            created.append(destination)
            edit = ["CRVAL4=1"] if record["stokes_in"] == 4 else None
            written = header_operation(
                SimpleNamespace(
                    fname=str(source),
                    outfile=str(destination),
                    replace=False,
                    show=False,
                    edit=edit,
                    add=None,
                    remove=None,
                    log_level="INFO",
                )
            )
            if Path(written).absolute() != destination:
                raise ValueError("fitstoolz returned an unexpected output")
            with (
                fits.open(source, memmap=True) as original,
                fits.open(destination, memmap=True) as copied,
            ):
                before, after = original[0].header, copied[0].header
                if (
                    len(copied) != 1
                    or copied[0].fileinfo()["datLoc"] != record["offset"]
                    or copied[0].fileinfo()["datSpan"] != record["size"]
                    or len(before) != len(after)
                ):
                    raise ValueError("fitstoolz changed FITS structure")
                if after.get("CRVAL4") != 1 or any(
                    left.image != right.image
                    for left, right in zip(before.cards, after.cards, strict=True)
                    if left.keyword != "CRVAL4" or record["stokes_in"] == 1
                ):
                    raise ValueError("fitstoolz changed unrelated header metadata")
                if "CHECKSUM" in after and copied[0].verify_checksum() != 1:
                    raise ValueError("fitstoolz output CHECKSUM is invalid")
                if "DATASUM" in after and copied[0].verify_datasum() != 1:
                    raise ValueError("fitstoolz output DATASUM is invalid")
            record["destination"] = str(destination)
            record["operation"] = {
                "tool": "fitstoolz.apps.header.runit",
                "version": fitstoolz_version,
                "edit": edit,
                "replace": False,
            }
            if payload(destination, record["offset"], record["size"]) != record["payload_sha256"]:
                raise ValueError("copied FITS payload differs from native generated payload")
        report = {
            "schema": "dosho/wsclean-singleton-i-copies/v1",
            "input_stokes": next(iter(signatures)),
            "output_stokes": 1,
            "fitstoolz_version": fitstoolz_version,
            "checks": checks,
            "products": list(records.values()),
            "mfs_restored_validation": "native residual/model proof; independently qualified native renderer parity",
            "model_pb_units": "preserved native units: channel model JY/PIXEL; corrected and MFS model JY/BEAM",
        }
        receipt.parent.mkdir(parents=True, exist_ok=True)
        with receipt.open("x") as stream:
            created.append(receipt)
            json.dump(report, stream, indent=2, sort_keys=True)
            stream.write("\n")
        return report
    except BaseException:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        raise
    finally:
        try:
            for key, source in products.items():
                record = records[key]
                if (
                    source.stat().st_mtime_ns != record["source_mtime_ns"]
                    or source.stat().st_size != record["source_bytes"]
                    or payload(source, 0, record["offset"]) != record["source_header_sha256"]
                    or payload(source, record["offset"], record["size"]) != record["payload_sha256"]
                ):
                    raise ValueError("fitstoolz changed a native source product")
        except BaseException:
            for path in reversed(created):
                path.unlink(missing_ok=True)
            raise
