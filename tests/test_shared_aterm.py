"""Native shared-screen argv, product naming and readonly file dependencies."""

from pathlib import Path

import pytest
from shinobi.backends.container import bind_dir_modes
from shinobi.cabs import get
from shinobi.cache import compute_cache_key
from shinobi.derived import derived_reads
from shinobi.exceptions import ParameterError
from shinobi.policies import build_argv
from shinobi.products import FamilyPlan
from shinobi.sandbox import clear_stale_outputs
from shinobi.steps.dispatch import _prepare_inputs


def inputs(cab, root, **patch):
    return _prepare_inputs(
        cab,
        {
            "ms": root / "obs.ms",
            "prefix": str(root / "out/image"),
            "size": [32, 32],
            "scale": "10asec",
            "aterm_config": root / "input/beam.parset",
            "aterm_image": root / "input/beam",
            "nchan": 2,
            "niter": 10,
            **patch,
        },
    )


def test_shared_inputs_mount_readonly_fingerprint_and_survive_stale_clearing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cab = get("wsclean-idg-aterm")
    source = tmp_path / "input"
    source.mkdir()
    (tmp_path / "out").mkdir()
    screen = source / "beam"
    screen.write_bytes(b"one")
    parset = source / "beam.parset"
    parset.write_text(f"aterms=[diagonal]\ndiagonal.images=[{screen}]\n")
    prepared = inputs(cab, tmp_path)
    argv = build_argv(cab, prepared)
    assert "-aterm-config" in argv and "-aterm-image" not in argv
    assert "-gridder" in argv and argv[argv.index("-gridder") + 1] == "idg"
    reads = derived_reads(cab, prepared, tmp_path)
    assert {r.path for r in reads} == {screen, parset}
    assert all(r.required and not r.mutable for r in reads)
    modes = dict(bind_dir_modes(cab, prepared, tmp_path))
    assert modes[str(source)] is False
    first = compute_cache_key(cab, None, prepared, {})
    screen.write_bytes(b"two")
    assert compute_cache_key(cab, None, prepared, {}) != first
    before = {p: p.read_bytes() for p in (screen, parset)}
    clear_stale_outputs(cab, prepared, tmp_path, sandboxed=False)
    assert all(p.read_bytes() == data for p, data in before.items())


@pytest.mark.parametrize("niter", [0, 10])
@pytest.mark.parametrize("nchan", [1, 2])
def test_required_intrinsic_families_follow_native_channel_mfs_and_niter(niter, nchan, tmp_path):
    cab = get("wsclean-idg-aterm")
    prepared = inputs(cab, tmp_path, niter=niter, nchan=nchan)
    for field, suffix in [
        ("image_pb", "image"),
        ("residual_pb", "residual"),
        ("model_pb", "model"),
    ]:
        plan = FamilyPlan(cab.field_meta[field].family, Path, prepared, tmp_path)
        if field != "image_pb" and not niter:
            assert not plan.candidates
        else:
            names = {c.path.name for c in plan.candidates}
            expected = (
                {f"image-{suffix}-pb.fits"}
                if nchan == 1
                else {
                    f"image-0000-{suffix}-pb.fits",
                    f"image-0001-{suffix}-pb.fits",
                    f"image-MFS-{suffix}-pb.fits",
                }
            )
            assert names == expected
            assert all(c.rule.required for c in plan.candidates)


def test_native_generator_builtin_and_explicit_csv_have_real_file_contracts(tmp_path):
    builtin = get("simms-aterm-to-fits")
    csv = get("simms-aterm-to-fits-csv")
    params = {
        "ms": str(tmp_path / "obs.ms"),
        "output": str(tmp_path / "beam"),
        "npix": 32,
        "pixel_size": "60arcsec",
        "nchan": 4,
        "beam_pa_step": 1,
        "field_id": 0,
        "spw_id": 0,
    }
    argv = build_argv(builtin, _prepare_inputs(builtin, {**params, "beam_pattern": "L"}))
    assert argv[-1] == "to-fits" and argv[argv.index("--fits-format") + 1] == "wsclean"
    assert csv.field_meta["beam_pattern"].writable is False
    assert csv.inputs_model.model_fields["beam_pattern"].annotation is Path
    with pytest.raises(ParameterError):
        _prepare_inputs(builtin, {**params, "beam_pattern": "guessed"})
