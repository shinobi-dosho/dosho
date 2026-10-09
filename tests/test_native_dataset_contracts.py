"""Opt-in Docker conformance for the strict MSv2 annotation example.

Set DOSHO_NATIVE_DATASET_CONTRACTS=1 and use a Python 3.11 driver with
python-casacore/numpy installed. All Measurement Sets are created here.
"""

import os
import runpy
import sys
from pathlib import Path

import pytest
from shinobi import DatasetAccess, DatasetColumns
from shinobi.dataset_access import DatasetAccessError
from shinobi.dataset_lifecycle import DatasetLifecycleStore
from shinobi.exceptions import DatasetLifecycleViolationError
from shinobi.steps.dispatch import _dispatch

import dosho

pytestmark = pytest.mark.skipif(
    os.environ.get("DOSHO_NATIVE_DATASET_CONTRACTS") != "1",
    reason="set DOSHO_NATIVE_DATASET_CONTRACTS=1 for native Docker qualification",
)


@pytest.fixture
def native_workspace(tmp_path, monkeypatch):
    if sys.version_info[:2] != (3, 11):
        pytest.fail("native container pysteps require the qualified Python 3.11 driver")
    pytest.importorskip("casacore.tables")
    pytest.importorskip("numpy")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SHINOBI_OWNERSHIP_REGISTRY", str(tmp_path / "owners.json"))
    monkeypatch.setenv("SHINOBI_SANDBOX__DIR", str(tmp_path / "sandboxes"))
    return tmp_path


def _simulate(root):
    ref = dosho.get("simms-telsim")
    scope = ref.step.model_copy(update={"backend": "docker", "cache_dir": str(root / "cache")})
    params = {
        "ms": root / "input.ms",
        "telescope": "meerkat",
        "subarray_range": ["0", "3"],
        "direction": "J2000,0h24m20s,-30d12m33s",
        "starttime": "2024-03-14T06:15:10",
        "ntime": 4,
        "nchan": 8,
        "correlations": "XX,XY,YX,YY",
        "nworkers": 1,
    }
    result = _dispatch(scope, ref.func, **params)
    assert result.success, result.stderr
    return scope, ref.func, params


def test_native_example_create_mutate_restore_read_and_image(native_workspace):
    import numpy as np
    from casacore.tables import table

    root = native_workspace
    example = Path(__file__).resolve().parents[1] / "examples" / "strict_ms_pipeline.py"
    recipe = runpy.run_path(str(example))["pipeline"].model_copy(
        update={"backend": "docker", "cache_dir": str(root / "cache")}
    )
    sky = root / "sky.txt"
    sky.write_text("#format: name ra dec stokes_i\ncentre 0h24m20s -30d12m33s 1\n")
    config = root / "flags.yaml"
    config.write_text("strategies:\n  - name: zeros\n    task: flag_nans_zeros\n")
    result = _dispatch(recipe, None, ms=root / "sim.ms", sky=sky, flag_config=config)
    assert result.success, result.stderr
    report = result.outputs.summary
    assert report["channels"] == 8 and report["correlations"] == 4
    assert report["flagged"] == 0
    with table(str(root / "sim.ms"), ack=False) as main:
        assert report["rows"] == main.nrows() > 0
        data = main.getcol("DATA")
        np.testing.assert_allclose(data[..., [0, 3]], 1, atol=1e-6)
        np.testing.assert_allclose(data[..., [1, 2]], 0, atol=1e-6)
        assert not main.getcol("FLAG").any()
    # A one-major-cycle clean emits a model FITS file without necessarily
    # creating MODEL_DATA; the production contract intentionally allows both.
    assert (root / "image-model.fits").is_file()
    assert (root / "sim.ms.flagversions" / "flags.before").is_dir()
    assert result.outputs.image.select(
        time=0, frequency=0, polarization="I", component="real"
    ).is_file()
    _assert_flag_mutation_and_restore(root)


def _assert_flag_mutation_and_restore(root):
    import numpy as np
    from casacore.tables import table

    [path] = (root / ".shinobi" / "dataset-attempts").glob("*.json")
    attempt = DatasetLifecycleStore(path).attempt()
    assert attempt.outcome == "committed"
    leaves = {leaf.step_path.rsplit(".", 1)[-1]: leaf for leaf in attempt.leaves}
    [flag] = leaves["flag"].mutations
    [restore] = leaves["restore"].mutations
    with table(str(flag.predecessor_snapshot), ack=False) as before:
        original = before.getcol("FLAG")
    with table(str(flag.successor_snapshot), ack=False) as flagged:
        assert flagged.getcol("FLAG").any()
        assert not np.array_equal(flagged.getcol("FLAG"), original)
    with table(str(restore.successor_snapshot), ack=False) as restored:
        np.testing.assert_array_equal(restored.getcol("FLAG"), original)


def test_native_simms_create_refuses_an_existing_ms(native_workspace):
    scope, func, params = _simulate(native_workspace)
    # A different invocation must not treat the existing dataset as a new target.
    with pytest.raises(DatasetAccessError, match="already exists"):
        _dispatch(scope, func, **{**params, "ntime": 5})


def test_native_incomplete_skysim_contract_fails_and_restores(native_workspace):
    import numpy as np
    from casacore.tables import table

    root = native_workspace
    _, _, params = _simulate(root)
    ms = params["ms"]
    with table(str(ms), ack=False) as main:
        original = main.getcol("DATA").copy()
    sky = root / "sky.txt"
    sky.write_text("#format: name ra dec stokes_i\ncentre 0h24m20s -30d12m33s 1\n")
    ref = dosho.get("simms-skysim")
    wrong = ref.step.model_copy(
        update={
            "backend": "docker",
            "cache_dir": str(root / "cache"),
            "dataset_accesses": [
                DatasetAccess(
                    field="ms",
                    mode="write",
                    columns=DatasetColumns(create=("PROMISED",)),
                    allow_schema_change=True,
                )
            ],
        }
    )
    with pytest.raises(DatasetLifecycleViolationError, match=r"PROMISED|DATA|undeclared"):
        _dispatch(wrong, ref.func, ms=ms, ascii_sky=sky, nworkers=1)
    with table(str(ms), ack=False) as main:
        np.testing.assert_array_equal(main.getcol("DATA"), original)
        assert "PROMISED" not in main.colnames()
