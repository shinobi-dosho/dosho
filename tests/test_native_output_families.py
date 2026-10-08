"""Opt-in native product and cache qualification with disposable fixture copies."""

import os
import shutil
from pathlib import Path

import pytest
from shinobi.steps.dispatch import _dispatch

import dosho

_MS = os.environ.get("DOSHO_OUTPUT_FAMILY_TEST_MS")
_CUBE = os.environ.get("DOSHO_SOFIA_TEST_CUBE")
_SKY = os.environ.get("DOSHO_KILLMS_TEST_SKY_MODEL")


@pytest.mark.parametrize(
    "name,mode",
    [
        ("quartical", None),
        ("killms", None),
        ("sofia2", None),
        ("ddfacet", "Dirty"),
        ("ddfacet", "Clean"),
    ],
)
def test_native_product_capture_and_cache(tmp_path, monkeypatch, name, mode):
    if name == "sofia2":
        if not _CUBE:
            pytest.skip("set DOSHO_SOFIA_TEST_CUBE to a tiny FITS source cube")
    elif not _MS or (name == "killms" and not _SKY):
        pytest.skip("set DOSHO_OUTPUT_FAMILY_TEST_MS and DOSHO_KILLMS_TEST_SKY_MODEL")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SHINOBI_OWNERSHIP_REGISTRY", str(tmp_path / "ownership.json"))
    cab = dosho.get(name).model_copy(
        update={
            "backend": "docker",
            "cache": True,
            "cache_dir": str(tmp_path / "cache"),
            "sandbox": False,
        }
    )
    ms = tmp_path / "input.ms"
    if name != "sofia2":
        shutil.copytree(Path(_MS).resolve(), ms)
    if name == "quartical":
        params = {
            "input_ms_path": ms,
            "input_model_recipe": "MODEL_DATA",
            "input_ms_weight_column": "WEIGHT",
            "solver_iter_recipe": [1],
            "solver_threads": 1,
            "dask_threads": 1,
            "output_flags": False,
            "output_overwrite": True,
            "G.time_interval": "0",
            "G.freq_interval": "0",
        }
        field = "gain_directory"
    elif name == "killms":
        params = {
            "vis_data_ms_name": ms,
            "vis_data_in_col": "DATA",
            "sky_model_sky_model": Path(_SKY).resolve(),
            "solutions_sols_dir": "solutions",
            "actions_update_weights": 0,
            "actions_ncpu": 1,
            "actions_debug_pdb": 0,
            "solutions_skip_existing_sols": 0,
        }
        field = "solutions"
    elif name == "ddfacet":
        params = {
            "data_ms": [ms],
            "data_col_name": "DATA",
            "weight_col_name": "WEIGHT",
            "output_name": "native",
            "output_mode": mode,
            "image_n_pix": 32,
            "image_cell": 60.0,
            "parallel_ncpu": 1,
            "facets_n_facets": 1,
            "deconv_mode": "HMP",
            "hmp_scales": [0],
            "deconv_max_major_iter": 1,
            "deconv_max_minor_iter": 1,
            "output_images": "dDpPMmRrIi",
            "output_cubes": "dDpPMmRrIi",
            "cache_dir": "ddfcache",
            "cache_dirty": "off",
            "cache_psf": "off",
            "output_clobber": True,
        }
        field = "dirty" if mode == "Dirty" else "restored"
    else:
        params = {
            "input_data": Path(_CUBE).resolve(),
            "pipeline_threads": 1,
            "reliability_enable": False,
            "scfind_enable": False,
            "threshold_enable": True,
            "threshold_threshold": 5.0,
            "output_writeCubelets": True,
            "output_writeMoments": True,
            "output_writeMask": True,
            "output_writeMask2d": True,
            "output_writePV": True,
            "output_writeDiagnosticPlot": False,
            "output_overwrite": True,
        }
        field = "cubelets"
    first = _dispatch(cab, None, **params)
    assert first.returncode == 0, first.stderr
    family = getattr(first.outputs, field)
    assert family.resolved and family.members
    if name in {"quartical", "killms"}:
        bundle = family.select()
        assert bundle.path.is_dir()
        if name == "killms":
            assert not bundle.path.is_relative_to(ms)
            victim = next(bundle.path.rglob("*.npz"))
            assert list(bundle.path.rglob("*.parset"))
        else:
            victim = next(path for path in bundle.path.rglob("*") if path.is_file())
    else:
        assert all(member.value.is_file() for member in family.members)
        if name == "ddfacet" and mode == "Dirty":
            victim = family.select(representation="mean", flux_scale="apparent")
        elif name == "ddfacet":
            victim = family.select(representation="mean", flux_scale="apparent")
            assert (
                first.outputs.model.members
                and first.outputs.residual.members
                and first.outputs.psf.members
            )
        else:
            victim = family.members[-1].value
            assert (
                first.outputs.catalogue.members
                and first.outputs.mask.members
                and first.outputs.moments.members
            )
    hit = _dispatch(cab, None, **params)
    assert hit.cached and hit.outputs == first.outputs
    victim.unlink()
    repaired = _dispatch(cab, None, **params)
    assert repaired.returncode == 0 and not repaired.cached and victim.exists(), repaired.stderr
