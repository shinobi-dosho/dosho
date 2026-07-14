"""The remaining mechanically-ported flat cabs (aoflagger, tricolour,
crystalball, owlcat_plotelev, shadems, ragavi-vis/gains, sofia2, simms-skysim,
simms-telsim, simms (classic), mosaic-queen, breizorro, aimfast, eidos,
smops, aegean, rmsynth1d, rmsynth3d, rmclean3d) -- no `dynamic_schema`, no
unloadable package-scoped `_include`, so porting them is a field-by-field
transcription rather than a structural fix. Most loaded cleanly via
cult-cargo's own YAML; a few of the later additions (aimfast, eidos,
rmsynth1d/3d, rmclean3d) instead needed transcription from the real tool's
own `--help` because cult-cargo's YAML for them had gone stale (missing
flags, or -- for rm-tools -- flags mapped to the wrong meaning). One
targeted test per cab: registration + a representative build_argv shape
check against the real tool's CLI.
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


def test_ragavi_vis_registered_and_prefixed():
    cab = dosho.get("ragavi-vis")
    assert cab.name == "ragavi-vis"
    assert cab.command == "ragavi-vis"
    argv = build_argv(cab, {"ms": "/x.ms"})
    assert argv[0] == "ragavi-vis"


def test_ragavi_vis_emits_htmlname_so_the_caller_controls_the_output_path():
    # htmlname is a File input (emitted on the CLI, parent dir bound) -- without
    # it ragavi-vis writes an auto-named .html into the cwd.
    cab = dosho.get("ragavi-vis")
    assert "htmlname" in cab.inputs_model.model_fields
    argv = build_argv(cab, {"ms": "/x.ms", "xaxis": "chan", "yaxis": "amp", "htmlname": "/out/plots/p-amp_chan"})
    assert "--htmlname" in argv
    assert argv[argv.index("--htmlname") + 1] == "/out/plots/p-amp_chan"


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
    assert cab.image == dosho.get("ragavi-vis").image  # same ragavi image, sibling script
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


def test_breizorro_registered_and_repeated_list_flags():
    cab = dosho.get("breizorro")
    assert cab.name == "breizorro"
    assert cab.command == "breizorro"
    # click `multiple=True` options -> flag repeated per value (repeat_list)
    assert cab.policies.repeat_list is True
    argv = build_argv(
        cab,
        {
            "restored_image": "/img.fits",
            "threshold": 7.0,
            "merge": ["/a.fits", "/b.fits"],
        },
    )
    assert argv[0] == "breizorro"
    assert "--restored-image" in argv and "/img.fits" in argv
    assert argv.count("--merge") == 2
    assert "/a.fits" in argv and "/b.fits" in argv


def test_aimfast_registered_and_nargs_flags_emit_as_bare_tokens():
    cab = dosho.get("aimfast")
    assert cab.name == "aimfast"
    assert cab.command == "aimfast"
    argv = build_argv(
        cab,
        {
            "restored_image": "/restored.fits",
            "compare_models": ["/a.lsm.html", "/b.lsm.html"],
            "centre_coord": "13:00:00,-30:00:00",
        },
    )
    assert argv[0] == "aimfast"
    assert "--restored-image" in argv
    # nargs=2 flag: one flag occurrence, then each value as a bare token
    assert argv.count("--compare-models") == 1
    assert "/a.lsm.html" in argv and "/b.lsm.html" in argv
    # real flag is literally "--centre_coord" (underscore, not hyphenated)
    assert "--centre_coord" in argv


def test_eidos_required_freq_list_and_stokes_case_preserved():
    cab = dosho.get("eidos")
    assert cab.name == "eidos"
    fields = cab.inputs_model.model_fields
    assert fields["freq"].is_required()
    assert fields["coeff"].is_required()
    argv = build_argv(cab, {"freq": [900.0, 1000.0, 1.0], "coeff": "mh", "stokes": "I"})
    assert argv[0] == "eidos"
    assert argv.count("--freq") == 1
    assert "900.0" in argv and "1000.0" in argv
    # real flag is "--Stokes" (capitalised)
    assert "--Stokes" in argv


def test_smops_required_fields_and_hyphenated_flags():
    cab = dosho.get("smops")
    assert cab.name == "smops"
    fields = cab.inputs_model.model_fields
    assert fields["ms"].is_required()
    assert fields["input_prefix"].is_required()
    argv = build_argv(
        cab,
        {"ms": "/x.ms", "input_prefix": "im", "channels_out": 4, "polynomial_order": 2},
    )
    assert argv[0] == "smops"
    assert "--ms" in argv and "/x.ms" in argv
    assert "--input-prefix" in argv
    assert "--channels-out" in argv
    assert "--polynomial-order" in argv


def test_aegean_positional_image_and_repeated_beam_triple():
    cab = dosho.get("aegean")
    assert cab.name == "aegean"
    argv = build_argv(cab, {"image": "/img.fits", "beam": [1.0, 0.5, 30.0]})
    assert argv[0] == "aegean"
    assert argv[-1] == "/img.fits"  # positional, emitted last
    assert argv.count("--beam") == 1
    assert "1.0" in argv and "0.5" in argv and "30.0" in argv


def test_rmsynth1d_positional_and_single_dash_flags():
    cab = dosho.get("rmsynth1d")
    assert cab.name == "rmsynth1d"
    assert cab.command == "rmsynth1d"
    argv = build_argv(cab, {"data_file": "/spec.dat", "fit_rmsf_gaussian": True, "nsamples": 20})
    assert argv[0] == "rmsynth1d"
    assert argv[-1] == "/spec.dat"  # positional
    assert "-t" in argv
    assert "-s" in argv and "20" in argv
    assert "--" not in "".join(argv)  # every flag is single-dash


def test_rmsynth3d_three_positionals_in_order():
    cab = dosho.get("rmsynth3d")
    assert cab.name == "rmsynth3d"
    argv = build_argv(
        cab, {"stokes_q": "/Q.fits", "stokes_u": "/U.fits", "freqs": "/freqs.dat", "verbose": True}
    )
    assert argv[0] == "rmsynth3d"
    assert "-v" in argv
    assert argv[-3:] == ["/Q.fits", "/U.fits", "/freqs.dat"]


def test_chgcentre_positionals_and_reused_wsclean_image():
    cab = dosho.get("chgcentre")
    assert cab.name == "chgcentre"
    assert cab.command == "chgcentre"
    assert cab.image == dosho.get("wsclean").image  # companion binary, same build
    argv = build_argv(cab, {"ms": "/x.ms", "ra": "00h00m00.0s", "dec": "00d00m00.0s", "force": True})
    assert argv[0] == "chgcentre"
    assert "-f" in argv
    assert argv[-3:] == ["/x.ms", "00h00m00.0s", "00d00m00.0s"]
    assert "ms" in cab.outputs_model.model_fields  # in-place edit -> passthrough


def test_flagms_reuses_owlcat_image_and_positional_ms():
    cab = dosho.get("flagms")
    assert cab.name == "flagms"
    assert cab.command == "flag-ms.py"
    assert cab.image == dosho.get("owlcat_plotelev").image
    argv = build_argv(cab, {"ms": "/x.ms", "flag": "L", "verbose": 2})
    assert argv[0] == "flag-ms.py"
    assert "--flag" in argv and "L" in argv
    assert argv[-1] == "/x.ms"  # positional


def test_pyddi_hyphenated_flags():
    cab = dosho.get("pyddi")
    assert cab.name == "pyddi"
    argv = build_argv(cab, {"image": "/img.fits", "flux_thresh": 12.0})
    assert argv[0] == "pyddi"
    assert "--image" in argv
    assert "--flux-thresh" in argv and "12.0" in argv


def test_rfinder_long_form_flags_diverge_from_short_mnemonics():
    cab = dosho.get("rfinder")
    assert cab.name == "rfinder"
    argv = build_argv(cab, {"input": "/x.ms", "telescope": "meerkat", "no_cleanup": True})
    assert argv[0] == "rfinder"
    assert "--input" in argv and "--telescope" in argv
    # the real long flag is --no_cleanup, not --no_clip (cult-cargo's own field name)
    assert "--no_cleanup" in argv


def test_spimple_binterp_repeated_ms_list_as_bare_tokens():
    cab = dosho.get("spimple-binterp")
    assert cab.name == "spimple-binterp"
    assert cab.command == "spimple-binterp"
    argv = build_argv(
        cab, {"image": "/img.fits", "output_filename": "/out", "ms": ["/a.ms", "/b.ms"]}
    )
    assert argv[0] == "spimple-binterp"
    assert argv.count("--ms") == 1  # nargs='+' -> one flag occurrence
    assert "/a.ms" in argv and "/b.ms" in argv


def test_spimple_imconv_shares_image_with_binterp():
    cab = dosho.get("spimple-imconv")
    assert cab.name == "spimple-imconv"
    assert cab.image == dosho.get("spimple-binterp").image
    argv = build_argv(cab, {"image": "/img.fits", "output_filename": "/out", "circ_psf": True})
    assert "--circ-psf" in argv


def test_spimple_spifit_model_and_residual_lists():
    cab = dosho.get("spimple-spifit")
    assert cab.name == "spimple-spifit"
    argv = build_argv(
        cab,
        {
            "model": ["/m1.fits", "/m2.fits"],
            "output_filename": "/out",
            "threshold": 5.0,
        },
    )
    assert argv.count("--model") == 1
    assert "/m1.fits" in argv and "/m2.fits" in argv
    assert "--threshold" in argv


def test_tigger_convert_positionals_and_repeated_append():
    cab = dosho.get("tigger-convert")
    assert cab.name == "tigger-convert"
    assert cab.policies.repeat_list is True
    argv = build_argv(
        cab, {"sky_model": "/in.lsm.html", "output_model": "/out.lsm.html", "append": ["/a.txt", "/b.txt"]}
    )
    assert argv[0] == "tigger-convert"
    assert argv.count("--append") == 2  # append-style optparse option, one flag per value
    assert argv[-2:] == ["/in.lsm.html", "/out.lsm.html"]


def test_tigger_restore_shares_image_with_convert():
    cab = dosho.get("tigger-restore")
    assert cab.name == "tigger-restore"
    assert cab.image == dosho.get("tigger-convert").image
    argv = build_argv(cab, {"input_image": "/img.fits", "sky_model": "/m.lsm.html", "num_sources": 10})
    assert argv[0] == "tigger-restore"
    assert "--num-sources" in argv
    assert argv[-2:] == ["/img.fits", "/m.lsm.html"]


def test_tigger_tag_variadic_positional_selectors():
    cab = dosho.get("tigger-tag")
    assert cab.name == "tigger-tag"
    argv = build_argv(
        cab, {"sky_model": "/m.lsm.html", "selectors": ["NAME_a", "+outlier"], "force": True}
    )
    assert argv[0] == "tigger-tag"
    assert "--force" in argv
    # sky_model then the free-form selector tokens, positional and in order
    assert argv[-3:] == ["/m.lsm.html", "NAME_a", "+outlier"]


def test_quartical_backup_positionals_and_plain_argparse_policy():
    cab = dosho.get("quartical-backup")
    assert cab.name == "quartical-backup"
    assert cab.command == "goquartical-backup"
    assert cab.image == dosho.get("quartical").image
    argv = build_argv(cab, {"ms_path": "/x.ms", "zarr_dir": "/backups", "column_name": "FLAG"})
    assert argv[0] == "goquartical-backup"
    assert argv[-3:] == ["/x.ms", "/backups", "FLAG"]


def test_quartical_restore_positionals_and_ms_output():
    cab = dosho.get("quartical-restore")
    assert cab.name == "quartical-restore"
    argv = build_argv(
        cab, {"zarr_path": "/backups/x.bkp.qc", "ms_path": "/x.ms", "column_name": "FLAG"}
    )
    assert argv[-3:] == ["/backups/x.bkp.qc", "/x.ms", "FLAG"]
    assert "ms_path" in cab.outputs_model.model_fields


def test_quartical_plotter_positionals_and_repeated_axes_list():
    cab = dosho.get("quartical-plotter")
    assert cab.name == "quartical-plotter"
    assert cab.command == "goquartical-plot"
    argv = build_argv(
        cab, {"input_path": "/gains/G", "output_path": "/plots", "iter_axes": ["antenna", "corr"]}
    )
    assert argv.count("--iter-axes") == 1
    assert "antenna" in argv and "corr" in argv
    assert argv[-2:] == ["/gains/G", "/plots"]


def test_rmclean3d_positionals_and_long_only_flags_get_double_dash():
    cab = dosho.get("rmclean3d")
    assert cab.name == "rmclean3d"
    argv = build_argv(
        cab, {"fdf_dirty": "/dirty.fits", "rmsf": "/rmsf.fits", "ncores": 4, "mpi": True}
    )
    assert argv[0] == "rmclean3d"
    assert argv[-2:] == ["/dirty.fits", "/rmsf.fits"]
    # long-flag-only options embed the second dash via nom_de_guerre
    assert "--ncores" in argv and "4" in argv
    assert "--mpi" in argv
    assert "-ncores" not in argv  # never single-dash
