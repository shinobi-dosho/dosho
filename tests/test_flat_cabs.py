"""The remaining mechanically-ported flat cabs (aoflagger, tricolour,
crystalball, owlcat_plotelev, shadems, ragavi, sofia2, simms-skysim,
simms-telsim, simms (classic), mosaic-queen) -- each already loaded cleanly
via cult-cargo's own YAML
(no dynamic_schema, no unloadable package-scoped _include), so porting
them is a field-by-field transcription rather than a structural fix.
One targeted test per cab: registration + a representative build_argv
shape check against the real tool's CLI.
"""

import dosho
from shinobi.policies import build_argv


def test_aoflagger_single_dash_cli():
    cab = dosho.get("aoflagger")
    assert cab.name == "aoflagger"
    argv = build_argv(cab, {"msname": "/x.ms", "verbose": True, "threads": 4})
    assert argv[0] == "aoflagger"
    assert "-v" in argv
    assert "-j" in argv and "4" in argv


def test_tricolour_positional_ms_and_double_dash_flags():
    cab = dosho.get("tricolour")
    assert cab.name == "tricolour"
    argv = build_argv(cab, {"ms": "/x.ms", "data_column": "DATA"})
    assert argv[0] == "tricolour"
    assert argv[-1] == "/x.ms"  # positional
    assert "--data-column" in argv


def test_crystalball_required_fields_and_argv():
    cab = dosho.get("crystalball")
    assert cab.name == "crystalball"
    fields = cab.inputs_model.model_fields
    assert fields["output_column"].is_required()
    assert fields["sky_model"].is_required()
    argv = build_argv(cab, {"ms": "/x.ms", "output_column": "MODEL_DATA", "sky_model": "sky.txt"})
    assert "--output-column" in argv
    assert "--sky-model" in argv
    assert argv[-1] == "/x.ms"


def test_owlcat_plotelev_output_field_has_real_default():
    cab = dosho.get("owlcat_plotelev")
    assert cab.name == "owlcat_plotelev"
    assert cab.outputs_model.model_fields["output_name"].default == "lst-elev.png"
    argv = build_argv(cab, {"msname": "/x.ms"})
    assert argv[0] == "plot-elevation-tracks.py"
    assert "--msname" in argv


def test_shadems_union_dtypes_resolve_to_real_python_types():
    cab = dosho.get("shadems")
    assert cab.name == "shadems"
    fields = cab.inputs_model.model_fields
    assert fields["field"].annotation == int | str | list[str] | list[int] | None
    argv = build_argv(cab, {"ms": "/x.ms", "xaxis": "CHAN", "yaxis": "amp"})
    assert argv[0] == "shadems"
    assert argv[-1] == "/x.ms"  # positional


def test_ragavi_registered_and_prefixed():
    cab = dosho.get("ragavi")
    assert cab.name == "ragavi"
    assert cab.command == "ragavi-vis"
    argv = build_argv(cab, {"ms": "/x.ms"})
    assert argv[0] == "ragavi-vis"


def test_sofia2_real_param_count():
    cab = dosho.get("sofia2")
    assert cab.name == "sofia2"
    assert len(cab.inputs_model.model_fields) == 100


def test_simms_skysim_registered_under_hyphenated_name():
    cab = dosho.get("simms-skysim")
    assert cab.name == "simms-skysim"
    assert cab.command == "simms skysim"
    argv = build_argv(cab, {})
    assert argv[:2] == ["simms", "skysim"]


def test_simms_telsim_sibling_subcommand_of_skysim():
    cab = dosho.get("simms-telsim")
    assert cab.name == "simms-telsim"
    assert cab.command == "simms telsim"
    assert cab.image == dosho.get("simms-skysim").image  # same simms binary
    argv = build_argv(cab, {"ms": "/x.ms", "telescope": "meerkat"})
    assert argv[:2] == ["simms", "telsim"]
    assert "--telescope" in argv
    assert argv[-1] == "/x.ms"  # positional


def test_simms_classic_is_a_genuinely_different_tool_and_image():
    cab = dosho.get("simms")
    assert cab.name == "simms"
    assert cab.command == "simms"
    assert cab.image != dosho.get("simms-skysim").image
    assert cab.field_meta["msname"].nom_de_guerre == "name"
    argv = build_argv(cab, {"msname": "/x.ms", "telescope": "meerkat"})
    assert argv[0] == "simms"
    assert "--name" in argv
    assert "--tel" in argv


def test_mosaic_queen_replace_policy_and_output():
    cab = dosho.get("mosaic-queen")
    assert cab.name == "mosaic-queen"
    assert cab.policies.replace == {"_": "-"}
    assert "output" in cab.outputs_model.model_fields
