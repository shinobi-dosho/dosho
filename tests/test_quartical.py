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
    assert mutated_path_fields(cab) == {"input_ms_path"}


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


def test_gain_directory_output_is_not_swept_up_as_mutable():
    # only the MS is declared mutable; the gain store is a real new artifact
    # and must keep its content hash in the key
    assert "output_gain_directory" not in _cab().input_mutability
