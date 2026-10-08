"""dosho.cabs.killms -- ported from killMS's own DefaultParset.cfg, the
same ReadCFG.py-based format DDFacet uses (see ddfacet.py's docstring).
Checks registration, field-count sanity, real argv shape, and that killms
builds on top of dosho's own DDFACET image.
"""

import pytest
from shinobi.policies import build_argv

import dosho


def test_killms_registered_and_uses_pinned_image():
    cab = dosho.get("killms")
    assert cab.name == "killms"
    assert cab.command == "kMS.py"
    from dosho import images

    assert cab.image == images.KILLMS
    # KILLMS's own manifest entry builds FROM the DDFACET image (see images.yaml)
    assert images.manifest["images"]["KILLMS"]["build"]["base"] == "DDFACET"


def test_killms_full_field_count():
    # 94 real DefaultParset.cfg options, plus 1 for the head-positional `parset` field
    assert len(dosho.get("killms").inputs_model.model_fields) == 95


def test_killms_case_preserved_flags():
    cab = dosho.get("killms")
    argv = build_argv(
        cab,
        {
            "vis_data_ms_name": "obs.MS",
            "sky_model_sky_model": "model.lsm.html",
            "solvers_solver_type": "CohJones",
        },
    )
    assert argv[0] == "kMS.py"
    assert "--MSName" in argv and "obs.MS" in argv
    assert "--SkyModel" in argv and "model.lsm.html" in argv
    assert "--SolverType" in argv and "CohJones" in argv


def test_killms_parset_is_a_bare_head_positional_at_argv_1():
    # kMS.py's own driver() reads sys.argv[1] as the parset unconditionally
    # (no leftover-arg validation) -- it must land immediately after
    # "kMS.py", or it's silently never read as a parset at all.
    cab = dosho.get("killms")
    argv = build_argv(cab, {"parset": "base.parset", "vis_data_ms_name": "obs.MS"})
    assert argv[0] == "kMS.py"
    assert argv[1] == "base.parset"
    assert "--parset" not in argv


def test_killms_parset_omitted_when_not_given():
    cab = dosho.get("killms")
    argv = build_argv(cab, {"vis_data_ms_name": "obs.MS"})
    assert "base.parset" not in argv
    assert argv[1] == "--MSName"


def test_every_real_path_option_is_a_path_dtype_not_a_str():
    # DefaultParset.cfg tags almost nothing with `#type:`, so the parser
    # fallback lands every path on `str` -- and a `str` is invisible to
    # `path_fields`, hence never bind-mounted into the container and never
    # workspace-anchored under a sandbox. The dtypes come from each option's
    # role in kMS.py's own option table instead; this pins the whole set, so
    # a future field naming a location on disk can't be added as `str`
    # without this test being looked at.
    from shinobi.steps.schema import path_fields

    assert path_fields(dosho.get("killms").inputs_model) == {
        "parset",
        "vis_data_ms_name",
        "sky_model_sky_model",
        "beam_fits_file",
        "image_sky_model_base_image_name",
        "image_sky_model_dico_model",
        "image_sky_model_nodes_file",
        "image_sky_model_image_predict_parset",
        "image_sky_model_mask_image",
        "solutions_ext_sols",
        "compression_compression_dir_file",
        "kafca_evolution_sol_file",
    }


def test_ms_is_typed_so_it_gets_bound_and_anchored():
    from shinobi.loaders._modelgen import is_file_dtype

    cab = dosho.get("killms")
    assert is_file_dtype("MS")
    assert "vis_data_ms_name" in cab.inputs_model.model_fields
    # the dtype change must not touch the argv shape: still --MSName
    argv = build_argv(cab, {"vis_data_ms_name": "obs.MS"})
    assert argv == ["kMS.py", "--MSName", "obs.MS"]


def test_write_targets_and_name_components_stay_str():
    # SolsDir/DDFCacheDir are killMS *write* targets: a string-typed write
    # target stays relative under a sandbox on purpose, so the tool writes
    # inside the sandbox for harvest to collect. OutSolsName is a name
    # component, not a path (kMS.py builds "<ms>/killMS.<name>.sols.npz"
    # from it). *Col fields are MS column names.
    from shinobi.steps.schema import path_fields

    paths = path_fields(dosho.get("killms").inputs_model)
    for field in (
        "solutions_sols_dir",
        "image_sky_model_ddf_cache_dir",
        "solutions_out_sols_name",
        "sky_model_kills",
        "vis_data_in_col",
        "vis_data_out_col",
    ):
        assert field not in paths


def test_ms_is_declared_mutable_since_killms_writes_into_it():
    # kMS.py opens the MS for writing (solved column, full predicted data,
    # imaging weights) and, with no SolsDir, drops the .sols.npz inside the
    # MS directory itself. This cab models no outputs, so the
    # name-intersection spelling has nothing to intersect -- the plain
    # flag/gaincal shape Mutability.MUTABLE exists for.
    from shinobi.steps.schema import Mutability, mutated_path_fields

    cab = dosho.get("killms")
    assert cab.mutability_of("vis_data_ms_name") is Mutability.MUTABLE
    assert mutated_path_fields(cab) == {"vis_data_ms_name"}
    # read-side paths keep their content hash -- swapping the sky model
    # really is a different step
    assert cab.mutability_of("sky_model_sky_model") is Mutability.IMMUTABLE


def test_mutated_ms_is_dropped_from_the_cache_key(tmp_path):
    from shinobi.cache import compute_cache_key, invalidate_path_hashes

    cab = dosho.get("killms")
    (ms := tmp_path / "obs.MS").mkdir()
    params = {"vis_data_ms_name": str(ms)}
    before = compute_cache_key(cab, None, params, None)
    (ms / "CORRECTED_DATA").write_text("written by kMS.py itself")
    invalidate_path_hashes()
    assert compute_cache_key(cab, None, params, None) == before

    naive = cab.model_copy(update={"input_mutability": {}})
    stale = compute_cache_key(naive, None, params, None)
    (ms / "CORRECTED_DATA").write_text("and again")
    invalidate_path_hashes()
    assert compute_cache_key(naive, None, params, None) != stale


def test_killms_solution_bundle_has_a_separate_owned_root():
    from pathlib import Path

    from shinobi.products import DirectoryBundle, FamilyPlan

    cab = dosho.get("killms")
    inputs = cab.inputs_model(vis_data_ms_name="obs.ms", solutions_sols_dir="sols").model_dump()
    assert inputs["solutions_sols_dir"] == "sols"
    plan = FamilyPlan(cab.field_meta["solutions"].family, DirectoryBundle, inputs, Path.cwd())
    assert plan.root == Path.cwd() / "sols"
    argv = build_argv(cab, {"vis_data_ms_name": "/obs.ms", "solutions_sols_dir": "/sols"})
    assert "--SolsDir" in argv and "/sols" in argv


def test_killms_unproduced_solutions_are_an_empty_family(tmp_path, monkeypatch):
    from shinobi.backends.recording import RecordingBackend
    from shinobi.steps import register_step_backend
    from shinobi.steps.dispatch import _dispatch

    monkeypatch.chdir(tmp_path)
    register_step_backend("killms-record", RecordingBackend())
    cab = dosho.get("killms").model_copy(update={"backend": "killms-record"})
    result = _dispatch(cab, None, vis_data_ms_name="obs.ms", solutions_sols_dir="sols")
    assert result.outputs.solutions.resolved and result.outputs.solutions.members == ()


def test_killms_experimental_marker_names_only_the_residual():
    from dosho.registry import _index

    reason = _index()["killms"]["experimental"]
    assert "inventoried" in reason
    assert "batch" in reason.lower()
    assert dosho.get("killms").info.startswith("EXPERIMENTAL:")


def test_killms_cache_dir_is_scratch_not_an_output():
    cab = dosho.get("killms")
    assert cab.scratch == ["{image_sky_model_ddf_cache_dir}/*"]
    # declaring it as an output would mount it *and* drag the cache into the
    # caller's workspace on every sandboxed run
    assert "image_sky_model_ddf_cache_dir" not in cab.outputs_model.model_fields
    assert cab.harvest == []


def test_killms_scratch_declares_nothing_when_the_cache_is_unset():
    from pathlib import Path

    from shinobi.steps.schema import declared_output_dirs

    cab = dosho.get("killms")
    dirs = [str(d) for d, _ in declared_output_dirs(cab, {"solutions_sols_dir": "sols/r1"})]
    assert "None" not in dirs
    assert any(Path(d).name in {"sols", "r1"} for d in dirs)


def test_empty_preapply_lists_preserve_native_list_shape():
    argv = build_argv(
        dosho.get("killms"), {"pre_apply_pre_apply_sols": [], "pre_apply_pre_apply_mode": []}
    )
    assert argv == ["kMS.py", "--PreApplySols", "[]", "--PreApplyMode", "[]"]


@pytest.mark.parametrize(
    "field,flag",
    [
        ("beam_fits_par_angle_inc_deg", "FITSParAngleIncDeg"),
        ("beam_feed_angle", "FeedAngle"),
        ("weighting_wtuv", "WTUV"),
        ("solvers_dt", "dt"),
        ("coh_jones_lambda_lm", "LambdaLM"),
        ("kafca_init_l_mdt", "InitLMdt"),
    ],
)
def test_native_float_options_preserve_fractional_values(field, flag):
    """These flags are float options in killMS 3.3.0's read_options table."""
    cab = dosho.get("killms")
    inputs = cab.inputs_model(vis_data_ms_name="obs.ms", solutions_sols_dir="sols", **{field: 2.5})
    assert getattr(inputs, field) == 2.5
    assert build_argv(cab, {field: getattr(inputs, field)}) == ["kMS.py", f"--{flag}", "2.5"]
