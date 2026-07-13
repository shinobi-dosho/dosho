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
    # the MS is positional (`plot-elevation-tracks.py [options] MS`), not --msname
    assert "--msname" not in argv
    assert "/x.ms" in argv


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


def test_simms_skysim_multiword_flags_are_hyphenated():
    # every multi-word skysim flag must be hyphenated (e.g. --source-schema,
    # not --source_schema, which simms rejects)
    cab = dosho.get("simms-skysim")
    argv = build_argv(
        cab, {"ms": "/x.ms", "ascii_sky": "/m.txt", "source_schema": "/s.yaml", "field_id": 0}
    )
    assert not [a for a in argv if a.startswith("--") and "_" in a]
    assert "--source-schema" in argv
    assert "--ascii-sky" in argv


def test_simms_telsim_sibling_subcommand_of_skysim():
    cab = dosho.get("simms-telsim")
    assert cab.name == "simms-telsim"
    assert cab.command == "simms telsim"
    assert cab.image == dosho.get("simms-skysim").image  # same simms binary
    argv = build_argv(cab, {"ms": "/x.ms", "telescope": "meerkat"})
    assert argv[:2] == ["simms", "telsim"]
    assert "--telescope" in argv
    assert argv[-1] == "/x.ms"  # positional


def test_ragavi_gains_registered_and_passes_gain_flags():
    cab = dosho.get("ragavi-gains")
    assert cab.name == "ragavi-gains"
    assert cab.command == "ragavi-gains"
    assert cab.image == dosho.get("ragavi").image  # same ragavi image, sibling script
    argv = build_argv(
        cab, {"table": ["/x.G0"], "gaintype": ["G"], "htmlname": "x.G0", "plotname": "x.G0.png"}
    )
    assert argv[0] == "ragavi-gains"
    assert "--table" in argv
    assert "--gaintype" in argv
    assert "--htmlname" in argv  # output filename passed on the CLI
    assert "--plotname" in argv
    # htmlname/plotname are also same-named passthrough outputs
    assert "htmlname" in cab.outputs_model.model_fields
    assert "plotname" in cab.outputs_model.model_fields


def test_simms_primary_beam_tag_ms_flags_and_passthrough_output():
    cab = dosho.get("simms-primary-beam")
    assert cab.name == "simms-primary-beam"
    # `simms` is a chained multicommand: the action ("tag-ms") is a trailing
    # positional emitted AFTER primary-beam's options, so it is NOT part of the
    # command string (see the cab's own comment).
    assert cab.command == "simms primary-beam"
    assert cab.image == dosho.get("simms-skysim").image  # same simms 3.0 binary
    # model_dump() fills the `action` default ("tag-ms"), mirroring dispatch's
    # _prepare_inputs (which build_argv actually receives at runtime).
    prepared = cab.inputs_model(
        ms="/x.ms", telescope_name_column="TEL", from_layout="meerkat"
    ).model_dump()
    argv = build_argv(cab, prepared)
    assert argv[:2] == ["simms", "primary-beam"]
    assert argv[-1] == "tag-ms"  # action positional, after the options
    assert "--ms" in argv  # tag-ms takes --ms, not a positional
    assert "--telescope-name-column" in argv
    assert "--from-layout" in argv
    assert argv.index("--from-layout") < argv.index("tag-ms")  # options precede the action
    assert "ms" in cab.outputs_model.model_fields  # passthrough output


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


def test_msutils_summary_positional_ms_and_json_flag():
    cab = dosho.get("msutils-summary")
    assert cab.name == "msutils-summary"
    assert cab.command == "msutils summary"
    argv = build_argv(cab, {"ms": "/x.ms", "json_out": "s.json", "quiet": True})
    assert argv[:2] == ["msutils", "summary"]
    # `json_out` renames the field off pydantic's `BaseModel.json`, but the
    # tool's real `--json` flag is preserved via nom_de_guerre.
    assert "--json" in argv and "json_out" not in argv
    assert "--quiet" in argv  # bare bool flag
    assert argv[-1] == "/x.ms"  # positional, emitted last
    assert "json_out" in cab.outputs_model.model_fields  # user path is also an output


def test_msutils_addcol_two_positionals_in_order_and_ms_output():
    cab = dosho.get("msutils-addcol")
    assert cab.name == "msutils-addcol"
    assert cab.command == "msutils addcol"
    argv = build_argv(cab, {"ms": "/x.ms", "colname": "CORRECTED_DATA", "init_with": 0.0})
    assert argv[:2] == ["msutils", "addcol"]
    assert "--init-with" in argv  # hyphenated flag from sanitised field name
    # ms then colname, both positional, emitted last in declaration order
    assert argv[-2:] == ["/x.ms", "CORRECTED_DATA"]
    assert "ms" in cab.outputs_model.model_fields  # in-place edit -> passthrough


def test_msutils_copycol_three_positionals():
    cab = dosho.get("msutils-copycol")
    assert cab.name == "msutils-copycol"
    argv = build_argv(cab, {"ms": "/x.ms", "fromcol": "DATA", "tocol": "CORRECTED_DATA"})
    assert argv == ["msutils", "copycol", "/x.ms", "DATA", "CORRECTED_DATA"]


def test_msutils_sumcols_variadic_positional_cols_as_separate_tokens():
    cab = dosho.get("msutils-sumcols")
    assert cab.name == "msutils-sumcols"
    assert cab.inputs_model.model_fields["cols"].is_required()
    argv = build_argv(
        cab, {"ms": "/x.ms", "cols": ["MODEL_DATA", "DATA"], "out": "SUM", "subtract": True}
    )
    assert "--out" in argv and "--subtract" in argv
    # cols are bare positional tokens (repeat_as_tokens), after ms
    assert argv[-3:] == ["/x.ms", "MODEL_DATA", "DATA"]


def test_msutils_addnoise_defaults_and_ms_output():
    cab = dosho.get("msutils-addnoise")
    assert cab.name == "msutils-addnoise"
    fields = cab.inputs_model.model_fields
    assert fields["sefd"].default == 551.0
    assert fields["column"].default == "MODEL_DATA"
    argv = build_argv(cab, {"ms": "/x.ms", "column": "MODEL_DATA", "sefd": 551.0, "add_to": "DATA"})
    assert "--add-to" in argv  # hyphenated flag
    assert argv[-1] == "/x.ms"  # positional
    assert "ms" in cab.outputs_model.model_fields


def test_msutils_flagstats_repeated_flags_and_file_outputs():
    cab = dosho.get("msutils-flagstats")
    assert cab.name == "msutils-flagstats"
    # click `multiple=True` options -> flag repeated per value (repeat_list)
    assert cab.policies.repeat_list is True
    argv = build_argv(
        cab, {"ms": "/x.ms", "plot": "f.png", "json_out": "f.json", "field": ["0", "1"]}
    )
    assert argv.count("--field") == 2  # one occurrence per value
    assert "--plot" in argv and "--json" in argv
    assert argv[-1] == "/x.ms"  # positional
    assert {"plot", "json_out"} <= set(cab.outputs_model.model_fields)
