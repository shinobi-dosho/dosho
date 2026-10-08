"""Shared capture and cache contracts for the migrated scientific cabs."""

from pathlib import Path

import pytest
from shinobi.backends.recording import RecordingBackend
from shinobi.exceptions import ParameterError
from shinobi.steps import register_step_backend
from shinobi.steps.dispatch import _dispatch

import dosho


class _Products(RecordingBackend):
    def __init__(self, files):
        super().__init__()
        self.files = files

    def run(self, cab, argv, inputs, **kwargs):
        result = super().run(cab, argv, inputs, **kwargs)
        root = Path(kwargs.get("cwd") or Path.cwd())
        for name in self.files:
            path = root / name
            if cab.name == "quartical":
                if name.startswith("gains.qc/"):
                    path = root / inputs["output_gain_directory"] / name.removeprefix("gains.qc/")
                elif name.startswith("logs.qc/"):
                    path = root / inputs["output_log_directory"] / name.removeprefix("logs.qc/")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"produced {len(self.calls)}")
        return result


CASES = [
    (
        "quartical",
        {"input_ms_path": "obs.ms"},
        ["logs.qc/log", "gains.qc/.zgroup", "gains.qc/G/.zattrs", "gains.qc/G/gains/0.0"],
        "gain_directory",
    ),
    (
        "killms",
        {"vis_data_ms_name": "obs.ms", "solutions_sols_dir": "sols"},
        ["sols/obs.ms/killMS.CohJones.sols.npz", "sols/obs.ms/killMS.CohJones.sols.parset"],
        "solutions",
    ),
    (
        "ddfacet",
        {"data_ms": ["obs.ms"], "output_name": "image"},
        [
            "image.app.restored.fits",
            "image.cube.int.restored.fits",
            "image.residual02.fits",
            "image.02.DicoModel",
        ],
        "restored",
    ),
    (
        "sofia2",
        {"input_data": "cube.fits", "output_writeCubelets": True, "output_writeMoments": True},
        ["sofia_cubelets/sofia_4_cube.fits", "sofia_cubelets/sofia_4_spec.txt", "sofia_mom0.fits"],
        "cubelets",
    ),
]


@pytest.mark.parametrize("name,params,files,field", CASES, ids=[case[0] for case in CASES])
@pytest.mark.parametrize("sandbox", [False, True])
def test_capture_cache_and_missing_member(
    tmp_path, monkeypatch, name, params, files, field, sandbox
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SHINOBI_OWNERSHIP_REGISTRY", str(tmp_path / "ownership.json"))
    monkeypatch.setenv("SHINOBI_SANDBOX__DIR", str(tmp_path / "sandboxes"))
    (tmp_path / "obs.ms").mkdir()
    (tmp_path / "cube.fits").write_text("input fixture")
    backend = _Products(files)
    register_step_backend("family-products", backend)
    cab = dosho.get(name).model_copy(
        update={
            "backend": "family-products",
            "cache": True,
            "cache_dir": str(tmp_path / "cache"),
            "sandbox": sandbox,
        }
    )
    first = _dispatch(cab, None, **params)
    family = getattr(first.outputs, field)
    assert family.resolved and family.members
    if name in {"quartical", "killms"}:
        bundle = family.select()
        assert bundle.path.is_dir()
        victim = tmp_path / files[-1]
    else:
        victim = family.members[0].value
    assert all((tmp_path / filename).exists() for filename in files)
    hit = _dispatch(cab, None, **params)
    assert hit.cached and hit.outputs == first.outputs
    victim.unlink()
    repaired = _dispatch(cab, None, **params)
    assert not repaired.cached and victim.exists()
    assert len(backend.calls) == 2
    if name == "ddfacet":
        assert repaired.outputs.residual.select(
            cycle=2, representation="mean", flux_scale="apparent"
        ).is_file()
        assert repaired.outputs.dico_model.select(cycle=2).is_file()
    if name == "sofia2":
        assert repaired.outputs.cubelets.select(source=4, product="cube", format="fits").is_file()
        assert repaired.outputs.moments.select(product="mom0", format="fits").is_file()


def test_quartical_bundle_rejects_remote_store_as_a_local_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    backend = _Products([])
    register_step_backend("remote-gains", backend)
    cab = dosho.get("quartical").model_copy(update={"backend": "remote-gains"})
    with pytest.raises(ValueError, match="remote stores"):
        _dispatch(cab, None, input_ms_path="obs.ms", output_gain_directory="s3://bucket/gains.qc")
    assert not backend.calls


def test_killms_requires_an_owned_solutions_root():
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="solutions_sols_dir"):
        dosho.get("killms").inputs_model(vis_data_ms_name="obs.ms")


@pytest.mark.parametrize("sandbox", [False, True])
@pytest.mark.parametrize(
    "destination",
    [
        "obs.ms",
        "obs.ms/solutions",
        "./obs.ms/sub/../solutions",
        "alias/solutions",
        ".",
        "absolute_nested",
    ],
)
def test_killms_solutions_cannot_overlap_ms(tmp_path, monkeypatch, sandbox, destination):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SHINOBI_OWNERSHIP_REGISTRY", str(tmp_path / "ownership.json"))
    monkeypatch.setenv("SHINOBI_SANDBOX__DIR", str(tmp_path / "sandboxes"))
    ms = tmp_path / "obs.ms"
    ms.mkdir()
    (ms / "sentinel").write_text("preserve")
    (tmp_path / "alias").symlink_to(ms, target_is_directory=True)
    if destination == "absolute_nested":
        destination = str(ms / "solutions")
    backend = _Products([])
    register_step_backend("forbidden-gains", backend)
    cab = dosho.get("killms").model_copy(update={"backend": "forbidden-gains", "sandbox": sandbox})
    with pytest.raises(ParameterError, match="overlaps input tree"):
        _dispatch(cab, None, vis_data_ms_name=ms, solutions_sols_dir=destination)
    assert not backend.calls
    assert (ms / "sentinel").read_text() == "preserve"
    assert not (ms / "solutions").exists()


@pytest.mark.parametrize(
    "destination",
    [
        "",
        "None",
        "solsNone",
        "input.ms#outside",
        "input.ms /solutions",
        "[sols]",
        "sols,other",
        "True",
        "False",
    ],
)
def test_killms_rejects_native_parser_path_reinterpretation(tmp_path, monkeypatch, destination):
    monkeypatch.chdir(tmp_path)
    backend = _Products([])
    register_step_backend("parser-gains", backend)
    cab = dosho.get("killms").model_copy(update={"backend": "parser-gains"})
    with pytest.raises(ParameterError, match="pattern"):
        _dispatch(cab, None, vis_data_ms_name="input.ms", solutions_sols_dir=destination)
    assert not backend.calls


def test_killms_parser_constraint_is_loaded_into_the_model():
    cab = dosho.get("killms")
    assert "pattern" in cab.inputs_model.model_json_schema()["properties"]["solutions_sols_dir"]
