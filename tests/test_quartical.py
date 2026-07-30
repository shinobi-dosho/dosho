"""quartical rounds out the three dynamic_schema cabs cult-cargo can't
give shinobi a real schema for. It also exercises the key_value/repeat
cab-level policies (stimela-ninja commit 6cb1238, added specifically to
fix quartical's hydra-style argv shape) end to end against a real port.
"""

from shinobi.policies import build_argv

import dosho


def _cab():
    return dosho.get("quartical")


def test_registered_under_its_own_name():
    cab = _cab()
    assert cab.name == "quartical"
    assert cab.command == "goquartical"


def test_real_param_count_not_a_hand_picked_subset():
    # 50 real flattened argument_schema.yaml params, plus 1 for the
    # head-positional `parset` field
    assert len(_cab().inputs_model.model_fields) == 51


def test_sections_flatten_to_real_dotted_cli_names():
    cab = _cab()
    assert "input_ms_path" in cab.inputs_model.model_fields
    assert cab.field_meta["input_ms_path"].nom_de_guerre == "input_ms.path"
    assert cab.inputs_model.model_fields["input_ms_path"].is_required()
    assert cab.field_meta["solver_terms"].nom_de_guerre == "solver.terms"


def test_key_value_and_bracket_repeat_policies():
    cab = _cab()
    assert cab.policies.key_value is True
    assert cab.policies.repeat == "[]"
    assert cab.policies.prefix == ""


def test_gain_term_pattern_matches_real_attrs_only():
    cab = _cab()
    assert cab.match_pattern("G.time_interval") is not None
    assert cab.match_pattern("K.type") is not None
    assert cab.match_pattern("dE.solve_per") is not None
    assert cab.match_pattern("G.not-a-real-attr") is None


def test_load_from_is_a_path_dtype_so_it_gets_bound_and_anchored():
    # `<term>.load_from` names a directory on disk (a previous run's gain
    # output plus the per-term zarr group). Shinobi decides whether a
    # pattern-matched param needs a bind mount / workspace anchoring from
    # its dtype alone, so a `str` here means the gain store is never mounted
    # into the container and a relative path is left resolving against the
    # sandbox instead of the workspace. Every other attr stays non-path.
    from shinobi.loaders._modelgen import is_file_dtype

    cab = _cab()
    assert is_file_dtype(cab.match_pattern("G.load_from").dtype)
    for attr in ("type", "solve_per", "time_interval", "freq_interval", "interp_method"):
        assert not is_file_dtype(cab.match_pattern(f"G.{attr}").dtype)


def test_load_from_still_emits_as_one_hydra_token():
    # the dtype change is about bind-mounting, not argv shape
    cab = _cab()
    argv = build_argv(cab, {"input_ms_path": "/x.ms", "G.load_from": "gains.qc/G"})
    assert "G.load_from=gains.qc/G" in argv


def test_build_argv_matches_real_quartical_hydra_style_cli():
    cab = _cab()
    argv = build_argv(
        cab,
        {
            "input_ms_path": "/x.ms",
            "input_ms_data_column": "DATA",
            "solver_terms": ["G"],
            "G.time_interval": "1",
            "G.type": "complex",
        },
    )
    assert argv[0] == "goquartical"
    assert "input_ms.path=/x.ms" in argv
    assert "input_ms.data_column=DATA" in argv
    assert "solver.terms=[G]" in argv
    assert "G.time_interval=1" in argv
    assert "G.type=complex" in argv
    # never the two-token --flag value shape
    assert not any(a.startswith("--") for a in argv)


def test_parset_is_a_bare_positional_not_a_key_value_token():
    # goquartical's own parser.py scans the whole argv for a bare
    # *.yaml/*.yml token -- never a "parset=..." hydra-style token, unlike
    # every other field on this cab (key_value=True).
    cab = _cab()
    argv = build_argv(cab, {"parset": "base.yaml", "input_ms_path": "/x.ms"})
    assert argv == ["goquartical", "base.yaml", "input_ms.path=/x.ms"]


def test_parset_omitted_when_not_given():
    cab = _cab()
    argv = build_argv(cab, {"input_ms_path": "/x.ms"})
    assert "base.yaml" not in argv
    assert argv == ["goquartical", "input_ms.path=/x.ms"]


def test_ms_and_gain_directory_outputs_are_real_passthroughs():
    from shinobi.backends.recording import RecordingBackend
    from shinobi.steps import register_step_backend
    from shinobi.steps.dispatch import _dispatch

    cab = _cab().model_copy(update={"backend": "quartical-record"})
    register_step_backend("quartical-record", RecordingBackend())
    result = _dispatch(cab, None, input_ms_path="/obs.ms", output_gain_directory="gains.qc")
    assert str(result.outputs.ms) == "/obs.ms"
    assert str(result.outputs.gain_directory) == "gains.qc"


def test_in_place_ms_write_is_declared_mutable_not_just_echoed_as_an_output():
    # The `ms` output is an `implicit` passthrough of `input_ms.path`, so
    # shinobi's name-intersection spelling of "mutated in place" sees
    # nothing (`ms` != `input_ms_path`). Without the explicit declaration,
    # `compute_cache_key` hashes the MS goquartical is about to rewrite --
    # a standalone re-run of an unchanged step can never hit its own cache
    # entry -- and `snapshots.eligible_fields` protects nothing.
    from shinobi.steps.schema import Mutability, mutated_path_fields

    cab = _cab()
    assert cab.mutability_of("input_ms_path") is Mutability.MUTABLE
    assert mutated_path_fields(cab) == {
        "input_ms_path",
        "output_gain_directory",
        "output_log_directory",
    }


def test_mutated_ms_is_dropped_from_the_cache_key_so_a_rerun_can_hit(tmp_path):
    # the behavioural half of the declaration: two keys computed over the
    # same params must agree even when the MS's own content has changed
    # underneath (which it has -- the step is what changed it).
    # `invalidate_path_hashes` is not ceremony: `_hash_path` is memoized, so
    # without it the second key would match for a stale-cache reason rather
    # than the declared-mutable one, and the same assertion would pass
    # against a cab that never declared anything.
    from shinobi.cache import compute_cache_key, invalidate_path_hashes

    cab = _cab()
    ms = tmp_path / "obs.ms"
    ms.mkdir()
    params = {"input_ms_path": str(ms), "output_gain_directory": "gains.qc"}
    before = compute_cache_key(cab, None, params, None)
    (ms / "CORRECTED_DATA").write_text("rewritten by the step itself")
    invalidate_path_hashes()
    assert compute_cache_key(cab, None, params, None) == before
    # ... and the undeclared cab is what that guards against: same rewrite,
    # different key, so the step re-runs forever
    naive = cab.model_copy(update={"input_mutability": {}})
    stale = compute_cache_key(naive, None, params, None)
    (ms / "CORRECTED_DATA").write_text("rewritten again")
    invalidate_path_hashes()
    assert compute_cache_key(naive, None, params, None) != stale
    # a different MS path is still a different step, though
    assert (
        compute_cache_key(cab, None, {**params, "input_ms_path": str(tmp_path / "other.ms")}, None)
        != before
    )


def test_every_write_target_is_declared_and_the_one_read_path_is_not():
    # goquartical has exactly four path-typed inputs. Three of them name a
    # location it writes (the MS it rewrites, the gain store it solves into,
    # the log dir it fills); `parset` is the only one it purely reads, and
    # it must keep its content hash -- editing the parset really is a
    # different step.
    from shinobi.steps.schema import path_fields

    cab = _cab()
    assert path_fields(cab.inputs_model) == {
        "input_ms_path",
        "output_gain_directory",
        "output_log_directory",
        "parset",
    }
    assert "parset" not in cab.input_mutability


def test_an_undeclared_write_target_would_move_the_key_on_its_own(tmp_path):
    # why all three are declared together rather than one per PR: any single
    # undeclared write target is enough to move the key on every run, so a
    # partial fix measures as no fix at all. Declare only the first two and
    # the log dir alone still breaks it.
    from shinobi.cache import compute_cache_key, invalidate_path_hashes
    from shinobi.steps.schema import Mutability

    partial = _cab().model_copy(
        update={
            "input_mutability": {
                "input_ms_path": Mutability.MUTABLE,
                "output_gain_directory": Mutability.MUTABLE,
            }
        }
    )
    (ms := tmp_path / "obs.ms").mkdir()
    logs = tmp_path / "logs.qc"
    params = {
        "input_ms_path": str(ms),
        "output_gain_directory": str(tmp_path / "gains.qc"),
        "output_log_directory": str(logs),
    }
    before = compute_cache_key(partial, None, params, None)
    logs.mkdir()
    (logs / "quartical.log").write_text("the run's own log")
    invalidate_path_hashes()
    assert compute_cache_key(partial, None, params, None) != before
    # the real cab declares all three, so the same run keys stably
    cab = _cab()
    invalidate_path_hashes()
    stable = compute_cache_key(cab, None, params, None)
    (logs / "quartical.log").write_text("a second run's log")
    invalidate_path_hashes()
    assert compute_cache_key(cab, None, params, None) == stable


def test_quartical_plotter_output_path_is_declared_as_a_write_target():
    # Same shape as quartical-backup's zarr_dir: the input stays `str` (a
    # positional "desired output location"), the path-typed output side is what
    # gets the directory bind-mounted.
    from shinobi.steps.schema import path_fields

    cab = dosho.get("quartical-plotter")
    assert "output_path" in cab.outputs_model.model_fields
    assert "output_path" not in path_fields(cab.inputs_model)
    assert "output_path" in path_fields(cab.outputs_model)
    # positional-ness survives the field_meta merge
    assert cab.field_meta["output_path"].positional is True
    argv = build_argv(cab, {"input_path": "/gains/G", "output_path": "/plots"})
    assert argv[0] == "goquartical-plot"
    assert "/plots" in argv and "--output-path" not in argv
