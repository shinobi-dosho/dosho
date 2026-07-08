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
    assert len(_cab().inputs_model.model_fields) == 50


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


def test_ms_and_gain_directory_outputs_are_real_passthroughs():
    from shinobi.backends.recording import RecordingBackend
    from shinobi.steps import register_step_backend
    from shinobi.steps.dispatch import _dispatch

    cab = _cab().model_copy(update={"backend": "quartical-record"})
    register_step_backend("quartical-record", RecordingBackend())
    result = _dispatch(cab, None, input_ms_path="/obs.ms", output_gain_directory="gains.qc")
    assert str(result.outputs.ms) == "/obs.ms"
    assert str(result.outputs.gain_directory) == "gains.qc"
