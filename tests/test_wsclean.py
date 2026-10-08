"""WSClean 3.6 argv and coordinate families, including product/cache evidence."""

import itertools
import os
import shutil
from pathlib import Path

import pytest
import yaml
from shinobi.backends.recording import RecordingBackend
from shinobi.loaders import yaml_cab
from shinobi.policies import build_argv
from shinobi.products import FamilyPlan
from shinobi.sandbox import clear_stale_outputs
from shinobi.steps import register_step_backend
from shinobi.steps.dispatch import _dispatch

import dosho
from dosho import registry


def _cab():
    return dosho.get("wsclean")


def test_registered_under_its_own_name():
    cab = _cab()
    assert cab.name == "wsclean"
    assert cab.command == "wsclean"


def test_real_param_count_not_a_hand_picked_subset():
    # The full imaging schema, including source-verified 3.6 additions.
    assert len(_cab().inputs_model.model_fields) == 170


def test_tuple_and_union_dtypes_resolve_to_real_python_types():
    fields = _cab().inputs_model.model_fields
    assert fields["size"].annotation == tuple[int, int]
    assert fields["scale"].annotation == str | float
    assert fields["weight"].annotation == str | tuple[str, float] | None
    assert fields["channel_range"].annotation == tuple[int, int] | None


def test_build_argv_matches_real_wsclean_cli_shape():
    cab = _cab()
    argv = build_argv(
        cab,
        {
            "ms": ["obs.ms"],
            "prefix": "deep",
            "size": (4096, 4096),
            "scale": "1.3asec",
            "weight": ("briggs", 0.5),
            "channel_range": (10, 20),
            "niter": 400000,
        },
    )
    assert argv[0] == "wsclean"
    assert "-name" in argv and "deep" in argv  # prefix's real nom_de_guerre
    # -size/-weight/-channel-range are each emitted as a flag followed by
    # separate bare tokens, not one comma-joined token.
    i = argv.index("-size")
    assert argv[i : i + 3] == ["-size", "4096", "4096"]
    i = argv.index("-weight")
    assert argv[i : i + 3] == ["-weight", "briggs", "0.5"]
    i = argv.index("-channel-range")
    assert argv[i : i + 3] == ["-channel-range", "10", "20"]
    # "ms" is positional, emitted last, no flag.
    assert argv[-1] == "obs.ms"
    assert "--ms" not in argv and "-ms" not in argv


def test_data_column_default_column_flag_is_data_column_not_column():
    cab = _cab()
    assert cab.field_meta["column"].nom_de_guerre == "data-column"


def _path_only_cab():
    """Exercise product handling without claiming a strict-MS backend contract."""
    _, text = registry.get_document("wsclean")
    document = yaml.safe_load(text)
    body = document["cabs"]["wsclean"]
    body.pop("dataset_accesses")
    body["inputs"]["ms"].update(dtype="List[MS]", mutable=True)
    return yaml_cab.loads(yaml.safe_dump(document), **registry.loader_options())["wsclean"]


def _inputs(**kwargs):
    return (
        _cab()
        .inputs_model(
            **{"ms": ["obs.ms"], "prefix": "deep", "size": (32, 32), "scale": "1amin", **kwargs}
        )
        .model_dump()
    )


def _plan(kind, cwd, **kwargs):
    return FamilyPlan(_cab().field_meta[kind].family, Path, _inputs(**kwargs), cwd)


@pytest.mark.parametrize("nchan", [1, 2])
@pytest.mark.parametrize("intervals", [1, 2])
@pytest.mark.parametrize("pol", ["Q", "iq", "I,Q", ["I", "Q"]])
def test_dimensions_match_36_filename_rules(tmp_path, nchan, intervals, pol):
    plan = _plan("image", tmp_path, nchan=nchan, intervals_out=intervals, pol=pol)
    polarizations = ["Q"] if pol == "Q" else ["I", "Q"]
    expected = {}
    for time in range(intervals):
        time_part = f"-t{time:04d}" if intervals > 1 else ""
        for frequency in [*range(nchan), *(["mfs"] if nchan > 1 else [])]:
            frequency_part = (
                "-MFS" if frequency == "mfs" else (f"-{frequency:04d}" if nchan > 1 else "")
            )
            for polarization in polarizations:
                pol_part = f"-{polarization}" if len(polarizations) > 1 else ""
                name = f"deep{time_part}{frequency_part}{pol_part}-image.fits"
                expected[name] = {
                    "time": time,
                    "frequency": frequency,
                    "polarization": polarization,
                    "component": "real",
                }
    assert {c.path.name: c.coordinates for c in plan.candidates} == expected


def test_xy_and_yx_are_combined_into_xy_real_and_imaginary(tmp_path):
    plan = _plan("image", tmp_path, pol="xxxyyxyy")
    assert {c.path.name: c.coordinates["component"] for c in plan.candidates} == {
        "deep-XX-image.fits": "real",
        "deep-XY-image.fits": "real",
        "deep-YY-image.fits": "real",
        "deep-XYi-image.fits": "imaginary",
    }
    assert {c.coordinates["polarization"] for c in plan.candidates} == {"XX", "XY", "YY"}


def test_psf_has_no_polarization_axis(tmp_path):
    plan = _plan("psf", tmp_path, pol="IQUV", nchan=2, intervals_out=2)
    assert len(plan.candidates) == 6
    assert plan.candidates[0].path.name == "deep-t0000-0000-psf.fits"
    assert all(set(c.coordinates) == {"time", "frequency"} for c in plan.candidates)


@pytest.mark.parametrize("mode", [{"predict": True}, {"dry_run": True}])
def test_predict_and_dry_run_reserve_no_products(tmp_path, mode):
    for kind in ("image", "dirty", "residual", "model", "psf", "source_list"):
        assert not _plan(kind, tmp_path, **mode).candidates


def test_psf_only_and_no_dirty_do_not_reserve_unavailable_images(tmp_path):
    for kind in ("image", "dirty", "model", "residual"):
        assert not _plan(kind, tmp_path, make_psf_only=True).candidates
    assert _plan("psf", tmp_path, make_psf_only=True).candidates
    assert not _plan("dirty", tmp_path, no_dirty=True).candidates


def test_source_list_is_an_optional_undecorated_product(tmp_path):
    assert not _plan("source_list", tmp_path).candidates
    plan = _plan("source_list", tmp_path, save_source_list=True, nchan=2, intervals_out=2)
    assert [(c.path.name, c.coordinates) for c in plan.candidates] == [("deep-sources.txt", {})]


class _EmittingBackend(RecordingBackend):
    def __init__(self, filenames):
        super().__init__()
        self.filenames = filenames

    def run(self, cab, argv, inputs, **kwargs):
        result = super().run(cab, argv, inputs, **kwargs)
        root = Path(kwargs.get("cwd") or Path.cwd())
        for filename in self.filenames:
            (root / filename).write_text(f"emission {len(self.calls)}")
        return result


def _dispatch_fixture(tmp_path, monkeypatch, filenames, *, cache=False, sandbox=False, **kwargs):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SHINOBI_OWNERSHIP_REGISTRY", str(tmp_path / "ownership.json"))
    monkeypatch.setenv("SHINOBI_SANDBOX__DIR", str(tmp_path / "sandboxes"))
    (tmp_path / "obs.ms").mkdir(exist_ok=True)
    backend = _EmittingBackend(filenames)
    register_step_backend("wsclean-products", backend)
    cab = _path_only_cab().model_copy(
        update={
            "backend": "wsclean-products",
            "cache": cache,
            "cache_dir": str(tmp_path / "cache"),
            "sandbox": sandbox,
        }
    )
    inputs = {"ms": ["obs.ms"], "prefix": "deep", "size": (32, 32), "scale": "1amin", **kwargs}
    return cab, backend, inputs, _dispatch(cab, None, **inputs)


def test_empty_execution_does_not_fabricate_any_product(tmp_path, monkeypatch):
    _, _, _, result = _dispatch_fixture(tmp_path, monkeypatch, [])
    for kind in ("image", "dirty", "residual", "model", "psf", "source_list"):
        family = getattr(result.outputs, kind)
        assert family.resolved and family.members == ()
    assert "image_mfs" not in type(result.outputs).model_fields


@pytest.mark.parametrize("sandbox", [False, True])
def test_actual_members_select_and_missing_member_invalidates_cache(tmp_path, monkeypatch, sandbox):
    filenames = ["deep-0000-Q-image.fits", "deep-MFS-Q-image.fits", "deep-MFS-psf.fits"]
    cab, backend, inputs, first = _dispatch_fixture(
        tmp_path, monkeypatch, filenames, cache=True, sandbox=sandbox, nchan=2, pol=["I", "Q"]
    )
    assert len(first.outputs.image.members) == 2
    assert first.outputs.residual.members == ()
    selected = first.outputs.image.select(
        time=0, frequency="mfs", polarization="Q", component="real"
    )
    assert selected.resolve() == tmp_path / "deep-MFS-Q-image.fits"
    assert selected.is_file()
    hit = _dispatch(cab, None, **inputs)
    assert hit.cached and hit.outputs == first.outputs
    selected.unlink()
    repaired = _dispatch(cab, None, **inputs)
    assert not repaired.cached and selected.exists()
    assert len(backend.calls) == 2


def test_unchanged_previous_files_are_not_published(tmp_path, monkeypatch):
    (tmp_path / "deep-image.fits").write_text("old image")
    _, _, _, result = _dispatch_fixture(tmp_path, monkeypatch, [])
    assert result.outputs.image.members == ()


def test_prediction_stale_clearing_preserves_model_inputs(tmp_path, monkeypatch):
    model = tmp_path / "deep-model.fits"
    model.write_text("prediction input")
    cab, _, inputs, _ = _dispatch_fixture(tmp_path, monkeypatch, [], predict=True)
    prepared = cab.inputs_model(**inputs).model_dump()
    clear_stale_outputs(cab, prepared, tmp_path, sandboxed=False)
    _dispatch(cab, None, **inputs)
    assert model.read_text() == "prediction input"


def test_continuation_preserves_existing_model_and_updates_its_family(tmp_path, monkeypatch):
    model = tmp_path / "deep-model.fits"
    model.write_text("previous model")
    cab, _, inputs, result = _dispatch_fixture(tmp_path, monkeypatch, [], continue_=True)
    prepared = cab.inputs_model(**inputs).model_dump()
    clear_stale_outputs(cab, prepared, tmp_path, sandboxed=False)
    assert model.read_text() == "previous model"
    assert (
        result.outputs.model.select(
            time=0, frequency=0, polarization="I", component="real"
        ).resolve()
        == model
    )


def test_changed_family_declaration_invalidates_cached_result(tmp_path, monkeypatch):
    cab, backend, inputs, first = _dispatch_fixture(
        tmp_path, monkeypatch, ["deep-image.fits"], cache=True
    )
    assert first.outputs.image.members
    assert _dispatch(cab, None, **inputs).cached
    metadata = dict(cab.field_meta)
    family = metadata["image"].family
    real_rule = family.rules[0].model_copy(update={"coordinates": {"component": "restored"}})
    metadata["image"] = metadata["image"].model_copy(
        update={"family": family.model_copy(update={"rules": (real_rule, *family.rules[1:])})}
    )
    changed = cab.model_copy(update={"field_meta": metadata})
    result = _dispatch(changed, None, **inputs)
    assert not result.cached and len(backend.calls) == 2
    assert result.outputs.image.members[0].coordinates["component"] == "restored"


def test_polarization_list_builds_one_comma_separated_cli_argument():
    argv = build_argv(_cab(), _inputs(pol=["I", "Q"]))
    index = argv.index("-pol")
    assert argv[index : index + 2] == ["-pol", "I,Q"]


def test_output_patterns_validate_combinatorial_names_without_resolving_them():
    cab = _cab()
    assert cab.match_output_pattern("dirty.per-band") is not None
    assert cab.match_output_pattern("restored.i.per-interval.mfs") is not None
    assert cab.match_output_pattern("totally-unknown-shape") is None


def test_harvest_declares_the_full_prefix_family():
    # Supplementary products (weights, UV, beams) remain harvested even when
    # they have no coordinate family. Sandboxing remains a caller choice.
    cab = _cab()
    assert cab.harvest == ["{prefix}-*"]
    assert cab.sandbox is None


_NATIVE_MS = os.environ.get("DOSHO_WSCLEAN_TEST_MS")
_NATIVE_CASES = [
    {"nchan": bands, "intervals_out": times, "pol": pol}
    for bands, times, pol in itertools.product((1, 2), (1, 2), (["Q"], ["I", "Q"]))
] + [
    {"nchan": 2, "pol": ["XX", "XY", "YX", "YY"], "gridder": "wstacking"},
    {"make_psf_only": True},
    {"no_dirty": True},
    {"niter": 1, "beam_size": 60.0, "save_source_list": True},
]


@pytest.mark.skipif(not _NATIVE_MS, reason="set DOSHO_WSCLEAN_TEST_MS to a tiny native MS fixture")
@pytest.mark.parametrize("options", _NATIVE_CASES)
def test_native_36_members_and_cache(tmp_path, monkeypatch, options):
    """Opt-in Docker conformance for products; the strict-MS contract is tested separately.

    The caller's fixture is copied before execution. It needs four linear
    correlations, at least two channels and two timesteps, and a DATA column.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SHINOBI_OWNERSHIP_REGISTRY", str(tmp_path / "ownership.json"))
    source = tmp_path / "input.ms"
    shutil.copytree(Path(_NATIVE_MS).resolve(), source)
    cab = _path_only_cab().model_copy(
        update={
            "backend": "docker",
            "cache": True,
            "cache_dir": str(tmp_path / "cache"),
            "sandbox": False,
        }
    )
    inputs = {
        "ms": [source],
        "prefix": "native",
        "size": (32, 32),
        "scale": "1amin",
        "threads": 1,
        "make_psf": True,
        **options,
    }
    first = _dispatch(cab, None, **inputs)
    assert first.returncode == 0, first.stderr
    for field, suffix in (
        ("image", "image.fits"),
        ("dirty", "dirty.fits"),
        ("model", "model.fits"),
        ("residual", "residual.fits"),
        ("psf", "psf.fits"),
        ("source_list", "sources.txt"),
    ):
        actual = {p.name for p in tmp_path.glob("native-*" + suffix)}
        captured = {m.value.name for m in getattr(first.outputs, field).members}
        assert captured == actual, (field, captured, actual)
    assert first.outputs.psf.members
    if options.get("make_psf_only"):
        assert not first.outputs.image.members
    else:
        assert first.outputs.image.members
    if options.get("gridder") == "wstacking":
        assert any(m.coordinates["component"] == "imaginary" for m in first.outputs.image.members)
    if options.get("niter"):
        assert (
            first.outputs.model.members
            and first.outputs.residual.members
            and first.outputs.source_list.members
        )
    hit = _dispatch(cab, None, **inputs)
    assert hit.cached and hit.outputs == first.outputs
    victim = first.outputs.psf.members[-1].value
    victim.unlink()
    repaired = _dispatch(cab, None, **inputs)
    assert not repaired.cached and victim.exists()


@pytest.mark.parametrize(
    "field,value",
    [
        ("size", (32,)),
        ("shift", ("1deg",)),
        ("dd_psf_grid", (2, 2, 2)),
        ("wstack_nwlayers_for_size", (32,)),
        ("spectral_correction", (150e6, "1,-0.7", "extra")),
        ("beam_shape", (60.0, 60.0)),
    ],
)
def test_fixed_arity_arguments_reject_malformed_lengths(field, value):
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        _cab().inputs_model(**_inputs(**{field: value}))


def test_source_verified_floats_units_and_csv_parameters():
    inputs = _cab().inputs_model(
        **_inputs(
            mem=50.5,
            abs_mem=0.5,
            local_rms_window=2.5,
            beam_aterm_update=0.5,
            facet_beam_update=0.5,
            abs_threshold="1mJy",
            abs_auto_mask="1mJy",
            beam_size="1amin",
            channel_division_frequencies=[1400e6, 1410e6],
            spectral_correction=(150e6, "83.084,-0.699,-0.110"),
        )
    )
    argv = build_argv(_cab(), inputs.model_dump())
    assert argv[argv.index("-channel-division-frequencies") + 1] == "1400000000.0,1410000000.0"
    assert argv[
        argv.index("-spectral-correction") + 1 : argv.index("-spectral-correction") + 3
    ] == ["150000000.0", "83.084,-0.699,-0.110"]
    assert all(token in argv for token in ("50.5", "0.5", "2.5", "1mJy", "1amin"))


def test_temp_dir_is_an_input_scratch_destination():
    cab = _cab()
    assert cab.field_meta["temp_dir"].write_path
    assert "temp_dir" not in cab.outputs_model.model_fields
    assert cab.scratch == ["{temp_dir}/*"]
    assert build_argv(cab, {"temp_dir": "scratch"}) == ["wsclean", "-temp-dir", "scratch"]
    assert "scalar_beam" not in cab.inputs_model.model_fields
    assert "local_rms_image" in cab.inputs_model.model_fields
    assert (
        cab.inputs_model(**_inputs(direct_ft_precision="ldouble")).direct_ft_precision == "ldouble"
    )
