"""Simms 3.0.2's public CLI, without importing Simms on the launcher."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import BaseModel, ValidationError
from shinobi import Cab, InputRef, MSv2, OutputRef, Recipe
from shinobi.config import AppConfig
from shinobi.dataset_backends import SharedStorageQualification
from shinobi.offload.bundle import RecipeBundle, freeze_recipe
from shinobi.offload.slurm import prepare_worker_slurm, submit_worker_slurm
from shinobi.offload.worker import ExecutionPlan
from shinobi.policies import build_argv

import dosho
from dosho import images


def _argv(name, **params):
    cab = dosho.get(f"simms-{name}")
    return build_argv(cab, cab.inputs_model(**params).model_dump())


def test_telsim_cli_parameters_and_passthrough():
    cab = dosho.get("simms-telsim")
    assert isinstance(cab, Cab)
    assert cab.image == images.SIMMS
    argv = _argv(
        "telsim",
        ms="observation.ms",
        telescope="meerkat",
        subarray_range=[0, 3],
        starttime="2024-03-14T06:15:10",
        startfreq="1284MHz",
        dfreq="1MHz",
        ntime=4,
        nchan=8,
        nworkers=1,
        rowchunks=16,
    )
    assert argv[:2] == ["simms", "telsim"]
    assert argv[-1] == "observation.ms"
    for flag, value in {
        "--telescope": "meerkat",
        "--starttime": "2024-03-14T06:15:10",
        "--startfreq": "1284MHz",
        "--dfreq": "1MHz",
        "--ntime": "4",
        "--nchan": "8",
        "--nworkers": "1",
        "--rowchunks": "16",
    }.items():
        assert argv[argv.index(flag) + 1] == value
    indices = [i for i, token in enumerate(argv) if token == "--subarray-range"]
    assert [argv[i + 1] for i in indices] == ["0", "3"]
    assert "--ms" not in argv and "--log-level" not in argv
    assert cab.inputs_model.model_fields["telescope"].is_required()
    assert cab.inputs_model.model_fields["nchan"].json_schema_extra["abbreviation"] == "nc"
    assert "ms" in cab.outputs_model.model_fields


def test_skysim_noise_controls_have_the_real_cli_spelling():
    cab = dosho.get("simms-skysim")
    assert isinstance(cab, Cab)
    assert cab.image == images.SIMMS
    argv = _argv(
        "skysim",
        ms="observation.ms",
        ascii_sky="sky.txt",
        sefd=551,
        seed=20261023,
        row_chunks=128,
        chan_chunks=4,
        nworkers=2,
        column="DATA",
        input_column="MODEL_DATA",
        mode="add",
    )
    assert argv[:2] == ["simms", "skysim"]
    assert argv[-1] == "observation.ms"
    for flag, value in {
        "--ascii-sky": "sky.txt",
        "--sefd": "551.0",
        "--seed": "20261023",
        "--row-chunks": "128",
        "--chan-chunks": "4",
        "--nworkers": "2",
        "--column": "DATA",
        "--input-column": "MODEL_DATA",
        "--mode": "add",
        "--fits-beam-mode": "aterm",
    }.items():
        assert argv[argv.index(flag) + 1] == value
    assert not {"--row_chunks", "--input_column", "--log-level"} & set(argv)
    assert "ms" in cab.outputs_model.model_fields


@pytest.mark.parametrize("field", ["no_polarisation", "no_do_wstacking"])
def test_skysim_negative_switches(field):
    flag = "--" + field.replace("_", "-")
    assert flag not in _argv("skysim", ms="x.ms")
    argv = _argv("skysim", ms="x.ms", **{field: True})
    assert flag in argv
    assert argv[argv.index(flag) + 1] != "true"
    # A recipe still using the old False value must not silently keep the
    # upstream True default. Its migration is the explicit negative switch.
    with pytest.raises(ValidationError):
        _argv("skysim", ms="x.ms", **{field.removeprefix("no_"): False})


def test_skysim_repeats_spectral_maps_and_validates_modes():
    argv = _argv("skysim", ms="x.ms", fits_spi=["alpha.fits", "beta.fits"])
    indices = [i for i, token in enumerate(argv) if token == "--fits-spi"]
    assert [argv[i + 1] for i in indices] == ["alpha.fits", "beta.fits"]
    for params in [{"mode": "bogus"}, {"fits_beam_mode": "bogus"}]:
        with pytest.raises(ValidationError):
            dosho.get("simms-skysim").inputs_model(ms="x.ms", **params)


def test_simms_file_inputs_remain_paths():
    telsim = dosho.get("simms-telsim").inputs_model(
        ms="x.ms", telescope="meerkat", subarray_file="antennas.yaml", sensitivity_file="sefd.yaml"
    )
    assert telsim.subarray_file == Path("antennas.yaml")
    assert telsim.sensitivity_file == Path("sefd.yaml")
    skysim = dosho.get("simms-skysim").inputs_model(
        ms="x.ms", ascii_sky="sky.txt", primary_beam="beams.yaml", source_schema="schema.yaml"
    )
    assert skysim.ascii_sky == Path("sky.txt")
    assert skysim.primary_beam == Path("beams.yaml")
    assert skysim.source_schema == Path("schema.yaml")


class SimulationInputs(BaseModel):
    ms: MSv2


def _recipe():
    recipe = Recipe(
        name="simulation",
        inputs_model=SimulationInputs,
        outputs_model=SimulationInputs,
        backend="docker",
    )
    recipe.add_step(
        "create", dosho.get("simms-telsim"), ms=InputRef(field="ms"), telescope="meerkat"
    )
    recipe.add_step(
        "populate",
        dosho.get("simms-skysim"),
        ms=OutputRef(step="create", field="ms"),
        sefd=551,
        seed=20261023,
        row_chunks=128,
        nworkers=1,
    )
    recipe.output_wiring["ms"] = OutputRef(step="populate", field="ms")
    return recipe


def test_simms_freezes_as_worker_cabs_without_tool_code(tmp_path, monkeypatch):
    import shinobi.offload.bundle as bundle_module

    def refuse_code(*args, **kwargs):
        pytest.fail("Simms CLI cabs must not bundle any Python wrapper")

    monkeypatch.setattr(bundle_module, "capture_code", refuse_code)
    config = AppConfig.load(config_file=tmp_path / "absent.yaml")
    bundle = freeze_recipe(
        _recipe(), {"ms": tmp_path / "sim.ms"}, config=config, workspace=tmp_path
    )
    restored = RecipeBundle.model_validate_json(bundle.model_dump_json())
    assert [step.scope.kind for step in restored.steps] == ["cab", "cab"]
    assert all(step.code is None for step in restored.steps)
    assert all(step.func is None for step in restored.declaration().steps)
    assert restored.steps[1].wiring["ms"].step == "create"
    assert (
        restored.steps[1].scope.restore().dataset_accesses
        == dosho.get("simms-skysim").dataset_accesses
    )
    assert "simms" not in sys.modules


def test_simms_worker_preparation_and_scheduler_submission(tmp_path, monkeypatch):
    """Exercise real preparation with test storage evidence and a fake sbatch.

    This validates catalogue compatibility; it does not qualify a physical
    shared filesystem or claim that jobs executed on a Slurm cluster.
    """
    monkeypatch.setenv("SHINOBI_OWNERSHIP_REGISTRY", str(tmp_path / "owners.json"))
    qualification = SharedStorageQualification(
        qualification_id=uuid4(),
        storage_root=tmp_path.resolve(),
        verified_at=time.time(),
        workers=("test-worker-a", "test-worker-b"),
        evidence="Test fixture for catalogue submission, not a physical storage qualification.",
    )
    qualification_path = tmp_path / "qualification.json"
    qualification_path.write_text(qualification.model_dump_json())
    digest = "sha256:" + "a" * 64
    monkeypatch.setattr(
        "shinobi.backends.container._pin_image",
        lambda backend, image: (image.rsplit(":", 1)[0] + "@" + digest, digest),
    )
    config = AppConfig.load(config_file=tmp_path / "absent.yaml")
    bundle = freeze_recipe(
        _recipe(), {"ms": tmp_path / "sim.ms"}, config=config, workspace=tmp_path
    )
    workflow = prepare_worker_slurm(
        bundle,
        submission_root=tmp_path / "runs",
        worker_python=Path(sys.executable),
        dataset_storage_qualification=qualification_path,
    )
    assert workflow.execution_blocked_reason is None
    assert [job.name for job in workflow.jobs] == ["create", "populate"]
    assert workflow.jobs[1].depends_on == ["create"]
    plan = ExecutionPlan.model_validate_json(
        (workflow.submission_dir / "execution.json").read_text()
    )
    assert plan.dataset_lifecycle is not None
    assert [step.accesses[0].declaration.mode.value for step in plan.dataset_lifecycle.steps] == [
        "create",
        "write",
    ]
    staged = RecipeBundle.read(workflow.submission_dir / "bundle.json")
    assert all(step.scope.kind == "cab" and step.code is None for step in staged.steps)

    scheduler_calls = []
    original_run = subprocess.run

    def scheduler(command, *args, **kwargs):
        if command[0] == "sbatch":
            scheduler_calls.append(command)
            return subprocess.CompletedProcess(command, 0, f"{1000 + len(scheduler_calls)}\n", "")
        return original_run(command, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", scheduler)
    handle = submit_worker_slurm(workflow)
    assert handle.jobs == {"create": "1001", "populate": "1002"}
    assert handle.finalizer_job == "1003"
    assert "--dependency=afterok:1001" in scheduler_calls[1]
