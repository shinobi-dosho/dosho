"""dosho.cabs.killms -- ported from killMS's own DefaultParset.cfg, the
same ReadCFG.py-based format DDFacet uses (see ddfacet.py's docstring).
Checks registration, field-count sanity, real argv shape, and that killms
builds on top of dosho's own DDFACET image.
"""

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
    assert "--VisData-MSName" in argv and "obs.MS" in argv
    assert "--SkyModel-SkyModel" in argv and "model.lsm.html" in argv
    assert "--Solvers-SolverType" in argv and "CohJones" in argv


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
    assert argv[1] == "--VisData-MSName"


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
    # the dtype change must not touch the argv shape: still --VisData-MSName
    argv = build_argv(cab, {"vis_data_ms_name": "obs.MS"})
    assert argv == ["kMS.py", "--VisData-MSName", "obs.MS"]


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


def test_killms_declares_the_solutions_directory_it_writes():
    """The `.sols.npz` filename is built internally (`reformat(MSName)`), so the
    *directory* is what gets declared -- and it is what a pipeline wires, since
    DDFacet consumes SolsDir plus a solution name, never the file.
    """
    from shinobi.steps.schema import path_fields

    cab = dosho.get("killms")
    assert "solutions_sols_dir" in cab.outputs_model.model_fields
    # input stays `str` (relative under a sandbox); the output side is path-typed
    assert "solutions_sols_dir" not in path_fields(cab.inputs_model)
    assert "solutions_sols_dir" in path_fields(cab.outputs_model)
    # the flag still renders: field_meta merges output over input, so an
    # output-side ParamMeta would have dropped the nom_de_guerre
    assert cab.field_meta["solutions_sols_dir"].nom_de_guerre == "Solutions-SolsDir"
    argv = build_argv(cab, {"vis_data_ms_name": "/obs.ms", "solutions_sols_dir": "/sols"})
    assert "--Solutions-SolsDir" in argv and "/sols" in argv


def test_killms_solsdir_passthrough_resolves_and_stays_none_when_unset():
    from shinobi.backends.recording import RecordingBackend
    from shinobi.steps import register_step_backend
    from shinobi.steps.dispatch import _dispatch

    register_step_backend("killms-record", RecordingBackend())
    cab = dosho.get("killms").model_copy(update={"backend": "killms-record"})

    result = _dispatch(cab, None, vis_data_ms_name="/obs.ms", solutions_sols_dir="/sols")
    assert str(result.outputs.solutions_sols_dir) == "/sols"

    # unset declares nothing, which is right: the solutions then land inside the
    # MS directory, already mounted as an input
    result = _dispatch(cab, None, vis_data_ms_name="/obs.ms")
    assert result.outputs.solutions_sols_dir is None


def test_killms_experimental_marker_names_only_the_residual():
    from dosho._builder import EXPERIMENTAL_CABS

    reason = EXPERIMENTAL_CABS["killms"]
    assert "DDFCacheDir" in reason
    assert "sols.npz" in reason  # the unnameable file, wired as dir + name instead
    assert dosho.get("killms").info.startswith("EXPERIMENTAL:")


def test_killms_cache_dir_stays_undeclared():
    cab = dosho.get("killms")
    assert "image_sky_model_ddf_cache_dir" not in cab.outputs_model.model_fields
    assert cab.harvest == []
