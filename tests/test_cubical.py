"""cubical is the second-highest-priority port: cult-cargo's own cubical.yml
can't be loaded at all by shinobi.loaders.cultcargo (package-scoped
_include + a dynamic_schema per-Jones-term expansion), so caracal2's
selfcal worker had to hand-build a bypass Cab with an allow_extra escape
hatch. This checks the real flattened flag names and the per-Jones-term
ParamPattern against real CubiCal CLI conventions.
"""

from shinobi.policies import build_argv

import dosho


def _cab():
    return dosho.get("cubical")


def test_registered_under_its_own_name():
    cab = _cab()
    assert cab.name == "cubical"
    assert cab.command == "gocubical"


def test_real_param_count_not_a_hand_picked_subset():
    # 135 real flattened schema.yaml params, plus 1 for the head-positional `parset` field
    assert len(_cab().inputs_model.model_fields) == 136


def test_sections_flatten_to_real_cli_flag_names():
    cab = _cab()
    assert "data_ms" in cab.inputs_model.model_fields
    assert cab.field_meta["data_ms"].nom_de_guerre == "data-ms"
    assert cab.inputs_model.model_fields["data_ms"].is_required()
    assert "sol_jones" in cab.inputs_model.model_fields
    assert cab.field_meta["sol_jones"].nom_de_guerre == "sol-jones"


def test_allow_extra_for_dynamic_jones_term_params():
    assert _cab().inputs_model.model_config.get("extra") == "allow"


def test_jones_term_pattern_matches_real_attrs_only():
    cab = _cab()
    assert cab.match_pattern("g1-solvable") is not None
    assert cab.match_pattern("g-time-int") is not None
    assert cab.match_pattern("dE-update-type") is not None
    assert cab.match_pattern("g-not-a-real-attr") is None


def test_parset_is_a_bare_head_positional_at_argv_1():
    # cubical/main.py's own main() checks sys.argv[1] literally to detect a
    # parset -- it must land immediately after "gocubical", before every
    # --flag, or CubiCal's own leftover-arg-count check rejects the run.
    cab = _cab()
    argv = build_argv(cab, {"parset": "base.parset", "data_ms": "/x.ms", "out_overwrite": True})
    assert argv[0] == "gocubical"
    assert argv[1] == "base.parset"
    assert "--parset" not in argv


def test_parset_omitted_when_not_given():
    cab = _cab()
    argv = build_argv(cab, {"data_ms": "/x.ms"})
    assert "base.parset" not in argv
    assert argv[1] == "--data-ms"


def test_build_argv_matches_real_cubical_cli_shape():
    cab = _cab()
    argv = build_argv(
        cab,
        {
            "data_ms": "/x.ms",
            "data_column": "DATA",
            "out_name": "selfcal1",
            "sol_jones": ["G"],
            "g-solvable": True,
            "g-type": "complex-2x2",
            "g-time-int": 1,
        },
    )
    assert argv[0] == "gocubical"
    assert "--data-ms" in argv
    assert "--sol-jones" in argv
    # explicit_true=True (real cubical.yml policy): a True boolean emits
    # "--flag true" (an explicit value token), never a bare "--flag" --
    # gocubical's own CLI parser doesn't tolerate a bare boolean flag.
    i = argv.index("--g-solvable")
    assert argv[i : i + 2] == ["--g-solvable", "true"]
    i = argv.index("--g-type")
    assert argv[i : i + 2] == ["--g-type", "complex-2x2"]
    i = argv.index("--g-time-int")
    assert argv[i : i + 2] == ["--g-time-int", "1"]


def test_declared_boolean_field_is_also_explicit_not_a_bare_flag():
    cab = _cab()
    argv = build_argv(cab, {"data_ms": "/x.ms", "out_overwrite": True})
    i = argv.index("--out-overwrite")
    assert argv[i : i + 2] == ["--out-overwrite", "true"]
    # explicit_false=False (real cubical.yml policy): False still just
    # omits the flag entirely, same as before this fix.
    argv = build_argv(cab, {"data_ms": "/x.ms", "out_overwrite": False})
    assert "--out-overwrite" not in argv


def test_ms_output_is_a_real_passthrough_not_a_synthetic_hack():
    """CubiCal writes corrected data back into the same input MS -- `ms`
    should resolve to whatever `data-ms` was actually given, not a
    made-up path.
    """
    from shinobi.backends.recording import RecordingBackend
    from shinobi.steps import register_step_backend
    from shinobi.steps.dispatch import _dispatch

    cab = _cab().model_copy(update={"backend": "cubical-record"})
    register_step_backend("cubical-record", RecordingBackend())
    result = _dispatch(cab, None, data_ms="/obs.ms", out_name="selfcal1")
    assert str(result.outputs.ms) == "/obs.ms"
