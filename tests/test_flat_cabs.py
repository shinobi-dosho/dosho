"""The remaining mechanically-ported flat cabs (aoflagger, tricolour,
crystalball, owlcat_plotelev, shadems, ragavi-vis/gains, sofia2, simms
(classic), mosaic-queen, breizorro, aimfast, eidos, smops, aegean,
rmsynth1d, rmsynth3d, rmclean3d) -- no `dynamic_schema`, no unloadable
package-scoped `_include`, so porting them is a field-by-field
transcription rather than a structural fix. Most loaded cleanly via
cult-cargo's own YAML; a few of the later additions (aimfast, eidos,
rmsynth1d/3d, rmclean3d) instead needed transcription from the real tool's
own `--help` because cult-cargo's YAML for them had gone stale (missing
flags, or -- for rm-tools -- flags mapped to the wrong meaning). One
targeted test per cab: registration + a representative build_argv shape
check against the real tool's CLI.

`simms`'s 3.0 sub-commands (`simms-skysim`/`simms-telsim`/
`simms-primary-beam`) are no longer binary cabs -- as of simms 3.0 they are
`@shinobi.pystep` functions (`simms.apps.*`) that dosho wraps (see
`dosho/cabs/simms.py`), so their tests check the pystep's `inputs_model`
schema shape (Literal choices, `json_schema_extra` abbreviations) and that
they wire into a `Recipe`, not a `build_argv` shape. `simms` (classic) is
still a real binary and keeps its binary-cab test below.
"""

import re

import pytest
from pydantic import ValidationError
from shinobi import StepRef
from shinobi.backends.recording import RecordingBackend
from shinobi.policies import build_argv
from shinobi.steps import register_step_backend
from shinobi.steps.dispatch import _dispatch

import dosho
from dosho import images


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


def test_owlcat_plotelev_output_name_is_a_file_input_emitted_on_the_cli():
    # `output_name` must be an *input* (File-typed, so containers bind its
    # parent dir) as well as a passthrough output -- output-only fields are
    # never emitted, and the script then writes lst-elev.png into the cwd.
    cab = dosho.get("owlcat_plotelev")
    assert "output_name" in cab.inputs_model.model_fields
    argv = build_argv(cab, {"msname": "/x.ms", "output_name": "/plots/elev.png"})
    assert "--output-name" in argv
    assert "/plots/elev.png" in argv
    # omitted: not emitted at all (script falls back to its own default)
    argv_default = build_argv(cab, {"msname": "/x.ms"})
    assert "--output-name" not in argv_default


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
    argv = build_argv(
        cab, {"ms": "/x.ms", "xaxis": "chan", "yaxis": "amp", "htmlname": "/out/plots/p-amp_chan"}
    )
    assert "--htmlname" in argv
    assert argv[argv.index("--htmlname") + 1] == "/out/plots/p-amp_chan"


def test_sofia2_real_param_count():
    cab = dosho.get("sofia2")
    assert cab.name == "sofia2"
    assert len(cab.inputs_model.model_fields) == 100


def test_sofia2_renders_settings_not_flags():
    # SoFiA-2 has no flags at all: `sofia <parfile>|<setting> ...`, where a
    # setting is a bare `module.parameter=value` token. Under shinobi's
    # default `--` policies SoFiA reads the first token as the name of a
    # parameter file and dies with error code 5 before reading a voxel.
    cab = dosho.get("sofia2")
    argv = build_argv(cab, cab.inputs_model(input_data="/x/cube.fits").model_dump())
    assert argv[0] == "sofia"
    settings = argv[1:]
    assert all(re.fullmatch(r"[a-zA-Z]+\.[a-zA-Z0-9]+=.*", token) for token in settings)
    assert "input.data=/x/cube.fits" in settings


def test_sofia2_parameter_names_are_the_ones_sofia_27_knows():
    # A cab renders *every* defaulted field, and `pipeline.pedantic` (SoFiA's
    # own default, true) makes an unknown setting fatal -- error code 7. So a
    # name cult-cargo's schema carried from before the 2.6.38/2.6.54 renames
    # is not inert here, it stops the run. See the module docstring for the
    # mapping; these are the five that moved.
    cab = dosho.get("sofia2")
    argv = build_argv(cab, cab.inputs_model(input_data="/x/cube.fits").model_dump())
    names = {token.split("=", 1)[0] for token in argv[1:]}
    assert not {n for n in names if n.startswith("rippleFilter.")}
    assert "background.enable" in names and "background.windowZ" in names
    assert {"filter.minPixels", "filter.minSNR", "filter.discardNegative"} <= names
    assert not {"reliability.minPixels", "reliability.minSNR", "linker.keepNegative"} & names
    assert {"output.marginCubeletsXY", "output.marginCubeletsZ"} <= names
    assert "output.marginCubelets" not in names
    # ...and `port2tigger` was never a SoFiA parameter at all -- a
    # stimela-classic wrapper option that reaches a plain binary as the bare
    # token `port2tigger=false`, which SoFiA rejects.
    assert "port2tigger" not in cab.inputs_model.model_fields


def test_simms_skysim_is_a_pystep_with_choices_and_abbreviations():
    from typing import get_args

    step = dosho.get("simms-skysim")
    assert isinstance(step, StepRef)
    assert step.name == "simms-skysim"
    assert step.step.image == images.SIMMS
    fields = step.step.inputs_model.model_fields
    assert fields["ms"].is_required()  # the MS is the one required input
    # `choices` reach real pydantic validation as a Literal, not just info text
    assert get_args(fields["mode"].annotation) == ("sim", "add", "subtract")
    step.step.inputs_model(ms="/x.ms", mode="add")  # in-set value accepted
    with pytest.raises(ValidationError):
        step.step.inputs_model(ms="/x.ms", mode="bogus")  # out-of-set rejected
    # `abbreviation` is carried onto json_schema_extra for `ninja run`'s short flag
    assert fields["ascii_sky"].json_schema_extra == {"abbreviation": "as"}
    assert "ms" in step.step.outputs_model.model_fields  # passthrough MS output
    # simms 3.0.2's image-domain a-term beam knobs. `aterm` is upstream's default,
    # so a stale transcription here would silently pin every FITS-image predict to
    # the legacy PA-averaged power beam
    assert get_args(fields["fits_beam_mode"].annotation) == ("aterm", "average")
    assert fields["fits_beam_mode"].default == "aterm"
    assert fields["fits_beam_mode"].json_schema_extra == {"abbreviation": "fbm"}
    assert fields["aterm_freq_tol"].json_schema_extra == {"abbreviation": "aft"}


def test_simms_telsim_is_a_pystep_sharing_the_skysim_image():
    step = dosho.get("simms-telsim")
    assert isinstance(step, StepRef)
    assert step.name == "simms-telsim"
    assert step.step.image == dosho.get("simms-skysim").step.image  # same simms 3.0 image
    fields = step.step.inputs_model.model_fields
    assert fields["ms"].is_required()
    assert fields["telescope"].is_required()
    assert fields["telescope"].json_schema_extra == {"abbreviation": "tel"}
    assert fields["nchan"].json_schema_extra == {"abbreviation": "nc"}
    assert "ms" in step.step.outputs_model.model_fields  # passthrough MS output
    # `subarray_range` must keep simms' `list[str | int]`, str first: shinobi picks
    # the click type from the first scalar leaf, so a plain list[int] renders as
    # INTEGER and click rejects the documented comma form before simms sees it
    assert step.step.inputs_model(
        ms="/x.ms", telescope="meerkat", subarray_range=["0,64"]
    ).subarray_range == ["0,64"]
    assert step.step.inputs_model(
        ms="/x.ms", telescope="meerkat", subarray_range=[0, 64]
    ).subarray_range == [0, 64]


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
    # ...and must be File-typed (Path), not str: only path-typed fields get
    # absolutized back to the workspace + their parent dir pre-created under a
    # sandbox, so a str type makes ragavi-gains crash writing a relative path
    # into the empty scratch cwd (same reason ragavi-vis' htmlname is File).
    from pathlib import Path
    from typing import get_args

    for field in ("htmlname", "plotname"):
        assert Path in get_args(cab.inputs_model.model_fields[field].annotation)
        assert Path in get_args(cab.outputs_model.model_fields[field].annotation)


def test_simms_primary_beam_is_a_pystep_with_mode_choices():
    from typing import get_args

    step = dosho.get("simms-primary-beam")
    assert isinstance(step, StepRef)
    assert step.name == "simms-primary-beam"
    assert step.step.image == dosho.get("simms-skysim").step.image  # same simms 3.0 image
    fields = step.step.inputs_model.model_fields
    # the operation selector is a required Literal choice field
    assert get_args(fields["mode"].annotation) == ("to-fits", "tag-ms", "apply", "correct")
    assert fields["mode"].is_required()
    with pytest.raises(ValidationError):
        step.step.inputs_model(mode="bogus")  # out-of-set rejected
    assert fields["beam_pattern"].json_schema_extra == {"abbreviation": "bp"}
    # the cattery/DDFacet to-fits knobs (simms' heterogeneous-beam support):
    # these transcribe simms field-for-field, so drift here silently makes a
    # whole simms mode unreachable from dosho
    assert get_args(fields["fits_format"].annotation) == ("simms", "cattery")
    assert get_args(fields["beam_l_axis"].annotation) == ("-X", "X")
    assert get_args(fields["beam_m_axis"].annotation) == ("Y", "-Y")
    beam_axes = dosho.get("simms-skysim").step.inputs_model.model_fields
    assert "beam_l_axis" in beam_axes and "beam_m_axis" in beam_axes
    # path-valued fields must be Path-typed, not str: only path-typed fields
    # are absolutized into the workspace and have their parents bound into the
    # container (same rule as the ragavi cabs). A str `ms`/`label_map` makes
    # the step fail pydantic validation the moment a caller passes a real Path.
    from pathlib import Path

    for field in ("ms", "label_map", "output", "ascii_sky", "fits_sky", "source_schema"):
        assert Path in get_args(fields[field].annotation), field
    for field in ("ms", "ascii_sky", "primary_beam", "source_schema"):
        assert (
            Path in get_args(beam_axes[field].annotation) or beam_axes[field].annotation is Path
        ), field
    # ...but NOT beam_pattern: it takes a built-in model NAME or a band
    # shorthand as well as a path, and absolutizing a name would corrupt it
    assert fields["beam_pattern"].annotation == (str | None)
    # both passthrough outputs: `output` for to-fits/apply/correct, and `ms`
    # for tag-ms, which mutates the MS in place and is otherwise unwireable
    assert "output" in step.step.outputs_model.model_fields
    assert "ms" in step.step.outputs_model.model_fields


def test_simms_pysteps_wire_into_a_recipe():
    import shinobi
    from pydantic import create_model

    recipe = shinobi.Recipe(
        name="sim", inputs_model=create_model("I"), outputs_model=create_model("O")
    )
    recipe.add_step("mk", dosho.get("simms-telsim"), ms="out.ms", telescope="meerkat")
    recipe.add_step("sky", dosho.get("simms-skysim"), ms="out.ms", ascii_sky="sky.txt", mode="sim")
    assert [s.name for s in recipe.steps] == ["mk", "sky"]
    # the StepRef carries its pystep orchestration func into the recipe step
    assert recipe.steps[1].func is not None


def test_simms_classic_is_a_genuinely_different_tool_and_image():
    cab = dosho.get("simms")
    assert cab.name == "simms"
    assert cab.command == "simms"
    assert cab.image != dosho.get("simms-skysim").step.image
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
    argv = build_argv(
        cab, {"ms": "/x.ms", "ra": "00h00m00.0s", "dec": "00d00m00.0s", "force": True}
    )
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


def test_flagms_declares_the_ms_and_export_file_it_writes():
    # flag-ms.py's whole purpose is rewriting flags in the MS it is handed,
    # and --export writes the named flag file. Both are re-declared as
    # same-named outputs, which makes the write wirable by a downstream step
    # *and* satisfies `mutated_path_fields`' input/output name intersection
    # -- so `compute_cache_key` stops fingerprinting an MS the step itself
    # rewrote. `import_` is read-only and must stay out of the mutated set.
    from shinobi.steps.schema import mutated_path_fields

    cab = dosho.get("flagms")
    assert set(cab.outputs_model.model_fields) == {"ms", "export"}
    assert mutated_path_fields(cab) == {"ms", "export"}
    assert "import_" not in mutated_path_fields(cab)


def test_flagms_outputs_do_not_clobber_their_inputs_field_meta():
    # The hazard casatasks.py's docstring warns about: `field_meta` is
    # `{**input_meta, **output_meta}`, so an output-side ParamMeta on a
    # name that is also a real input silently replaces the input's. `ms`
    # would stop being positional and the argv would break. Neither output
    # carries a 4th spec element, so both metas survive intact.
    cab = dosho.get("flagms")
    assert cab.field_meta["ms"].positional is True
    assert cab.field_meta["export"].positional is False
    argv = build_argv(cab, {"ms": "/x.ms", "flag": "+L", "export": "flags.gz"})
    assert argv[-1] == "/x.ms"  # still the trailing positional
    assert "--export" in argv and "flags.gz" in argv


def test_flagms_mutated_ms_is_dropped_from_the_cache_key(tmp_path):
    # `invalidate_path_hashes` is load-bearing: `_hash_path` is memoized, so
    # without it this would pass for a stale-cache reason and hold against a
    # cab declaring nothing at all.
    from shinobi.cache import compute_cache_key, invalidate_path_hashes

    cab = dosho.get("flagms")
    (ms := tmp_path / "obs.ms").mkdir()
    params = {"ms": str(ms), "flag": "+L"}
    before = compute_cache_key(cab, None, params, None)
    (ms / "BITFLAG").write_text("flags raised by the step itself")
    invalidate_path_hashes()
    assert compute_cache_key(cab, None, params, None) == before

    # the control: the same cab as it was before this fix -- no outputs at
    # all, so nothing for the name intersection to find
    from shinobi.loaders import build_model

    naive = cab.model_copy(update={"outputs_model": build_model("flagms_NoOutputs", {})})
    stale = compute_cache_key(naive, None, params, None)
    (ms / "BITFLAG").write_text("and again")
    invalidate_path_hashes()
    assert compute_cache_key(naive, None, params, None) != stale


def test_write_targets_are_declared_outputs_so_a_recipe_can_wire_them():
    # These five had a path-typed *input* naming where the tool writes and no
    # outputs model at all: nothing for `mutated_path_fields`' name
    # intersection to find (so the step's own write moved its cache key), and
    # no OutputRef for a downstream step to depend on.
    from shinobi.steps.schema import mutated_path_fields

    for name, field in (
        ("tigger-convert", "output_model"),
        ("tigger-restore", "output_image"),
        ("tigger-tag", "output"),
        ("rfinder", "output_dir"),
        ("quartical-backup", "zarr_dir"),
    ):
        cab = dosho.get(name)
        assert field in cab.outputs_model.model_fields, name
        assert field in mutated_path_fields(cab), name


def test_new_outputs_do_not_clobber_their_inputs_field_meta():
    # `field_meta` is `{**input_meta, **output_meta}`, so an output-side
    # ParamMeta on a name that is also a real input silently replaces the
    # input's -- the positionals below would stop being positional. None of
    # the new output specs carries a 4th element; these argv shapes are the
    # proof, not the intent.
    assert build_argv(
        dosho.get("tigger-convert"),
        {"sky_model": "in.lsm.html", "output_model": "out.lsm.html", "force": True},
    ) == ["tigger-convert", "--force", "in.lsm.html", "out.lsm.html"]
    assert build_argv(
        dosho.get("quartical-backup"),
        {"ms_path": "/x.ms", "zarr_dir": "/bk", "column_name": "FLAG"},
    ) == ["goquartical-backup", "/x.ms", "/bk", "FLAG"]
    assert build_argv(dosho.get("rfinder"), {"output_dir": "/out"}) == [
        "rfinder",
        "--output_dir",
        "/out",
    ]


def test_tigger_tag_saves_in_place_by_default_so_its_model_is_mutable():
    # --output's own help: "Save changes to a different output model
    # [default: save in place]" -- with no --output the input model *is* the
    # output. The sibling commands read their model and write elsewhere, so
    # theirs stays immutable.
    from shinobi.steps.schema import Mutability

    assert dosho.get("tigger-tag").mutability_of("sky_model") is Mutability.MUTABLE
    for sibling in ("tigger-convert", "tigger-restore"):
        assert dosho.get(sibling).mutability_of("sky_model") is Mutability.IMMUTABLE


def test_quartical_backup_reads_its_ms_rather_than_writing_it():
    # unlike the `quartical` cab, goquartical-backup only reads the MS -- it
    # copies a column out to zarr. The MS must keep its content hash.
    from shinobi.steps.schema import Mutability

    assert dosho.get("quartical-backup").mutability_of("ms_path") is Mutability.IMMUTABLE


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


def test_spimple_output_filename_is_a_prefix_not_a_directory():
    """Every spimple `--help` calls it "Path to output directory"; all three
    commands use it as a filename stem. Source-verified against v0.0.5 (the
    pinned image): binterp writes `save_fits(opts.output_filename, ...)`
    verbatim, imconv/spifit do `outfile = opts.output_filename` then
    concatenate a per-product suffix. Declaring it as the directory would put
    every product one level too high.
    """
    binterp = dosho.get("spimple-binterp")
    # binterp: the value *is* the file -- a same-named passthrough output
    assert "output_filename" in binterp.outputs_model.model_fields
    assert binterp.field_meta["output_filename"].implicit is None
    # and the input keeps its flag: `field_meta` merges output over input, so a
    # ParamMeta on the output spec would have dropped this
    assert binterp.field_meta["output_filename"].nom_de_guerre == "output-filename"
    argv = build_argv(binterp, {"image": "/img.fits", "output_filename": "/out/beam.fits"})
    assert "--output-filename" in argv and "/out/beam.fits" in argv


def test_spimple_binterp_output_passes_the_input_value_through():
    cab = dosho.get("spimple-binterp").model_copy(update={"backend": "spimple-record"})
    register_step_backend("spimple-record", RecordingBackend())
    result = _dispatch(cab, None, image="/img.fits", output_filename="/out/beam.fits")
    assert str(result.outputs.output_filename) == "/out/beam.fits"


def test_spimple_imconv_products_resolve_to_the_suffixes_the_tool_writes():
    # image_convolver.py: outfile + '.clean_psf.fits' / '.convolved.fits' /
    # '.power_beam.fits' / '.spatial_weight.fits', one per `products` letter.
    cab = dosho.get("spimple-imconv").model_copy(update={"backend": "spimple-record"})
    register_step_backend("spimple-record", RecordingBackend())
    result = _dispatch(cab, None, image="/img.fits", output_filename="out/img")
    assert str(result.outputs.clean_psf) == "out/img.clean_psf.fits"
    assert str(result.outputs.convolved) == "out/img.convolved.fits"
    assert str(result.outputs.power_beam) == "out/img.power_beam.fits"
    assert str(result.outputs.spatial_weight) == "out/img.spatial_weight.fits"
    assert cab.harvest == ["{output_filename}.*"]


def test_spimple_spifit_products_resolve_to_the_suffixes_the_tool_writes():
    # spi_fitter.py, letter for letter from the `products` help text.
    cab = dosho.get("spimple-spifit").model_copy(update={"backend": "spimple-record"})
    register_step_backend("spimple-record", RecordingBackend())
    result = _dispatch(cab, None, output_filename="out/spi")
    expected = {
        "alpha": "out/spi.alpha.fits",
        "alpha_err": "out/spi.alpha_err.fits",
        "i0": "out/spi.I0.fits",
        "i0_err": "out/spi.I0_err.fits",
        "irec_cube": "out/spi.Irec_cube.fits",
        "clean_psf": "out/spi.clean_psf.fits",
        "convolved_model": "out/spi.convolved_model.fits",
        "convolved_residual": "out/spi.convolved_residual.fits",
        "power_beam": "out/spi.power_beam.fits",
        "fit_diff": "out/spi.fit_diff.fits",
    }
    for field, path in expected.items():
        assert str(getattr(result.outputs, field)) == path
    assert cab.harvest == ["{output_filename}.*"]
    # the output names must not shadow the model/residual *inputs*, which would
    # turn them into passthroughs of the wrong value
    assert "model" not in cab.outputs_model.model_fields
    assert "residual" not in cab.outputs_model.model_fields


def test_sofia2_every_moment_map_resolves_not_just_mom2():
    # One `output.writeMoments` toggle writes four files; mom0/mom1 used to be
    # declared without a template, so they validated but never resolved.
    cab = dosho.get("sofia2").model_copy(update={"backend": "sofia-record"})
    register_step_backend("sofia-record", RecordingBackend())
    result = _dispatch(
        cab, None, input_data="/cube.fits", output_directory="/out", output_filename="run1"
    )
    assert str(result.outputs.mom0) == "/out/run1_mom0.fits"
    assert str(result.outputs.mom1) == "/out/run1_mom1.fits"
    assert str(result.outputs.mom2) == "/out/run1_mom2.fits"
    assert str(result.outputs.chan_map) == "/out/run1_chan.fits"


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
        cab,
        {
            "sky_model": "/in.lsm.html",
            "output_model": "/out.lsm.html",
            "append": ["/a.txt", "/b.txt"],
        },
    )
    assert argv[0] == "tigger-convert"
    assert argv.count("--append") == 2  # append-style optparse option, one flag per value
    assert argv[-2:] == ["/in.lsm.html", "/out.lsm.html"]


def test_tigger_restore_shares_image_with_convert():
    cab = dosho.get("tigger-restore")
    assert cab.name == "tigger-restore"
    assert cab.image == dosho.get("tigger-convert").image
    argv = build_argv(
        cab, {"input_image": "/img.fits", "sky_model": "/m.lsm.html", "num_sources": 10}
    )
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


def test_vis_mowjsub_positional_ms_and_hyphenated_flags():
    cab = dosho.get("vis-mowjsub")
    assert cab.name == "vis-mowjsub"
    assert cab.command == "vis-mowjsub"
    assert cab.image == images.MOWJSUB
    argv = build_argv(
        cab,
        {
            "ms": "/x.ms",
            "output_ms": "/out.ms",
            "input_column": "CORRECTED_DATA",
            "output_column": "DATA",
            "vel_width": 250.0,
        },
    )
    assert argv[0] == "vis-mowjsub"
    assert argv[-1] == "/x.ms"  # positional, and last
    # every other name is hyphenated on the CLI but underscored as a field
    assert "--input-column" in argv and "--output-ms" in argv and "--vel-width" in argv
    assert "--input_column" not in argv


def test_vis_mowjsub_defaults_match_the_tools_own_parser_yaml():
    cab = dosho.get("vis-mowjsub")
    fields = cab.inputs_model.model_fields
    assert fields["ms"].is_required()
    assert fields["input_column"].default == "DATA"
    assert fields["output_column"].default == "LINE_DATA"
    assert fields["fit_model"].default == "b-spline"
    assert fields["doppler_interpolation"].default == "nearest"
    assert fields["nworkers"].default == 4
    # no fitspw equivalent: the continuum is fitted across the whole band
    assert not [f for f in fields if "fitspw" in f or "spw_sel" in f]


def test_vis_mowjsub_declares_its_in_place_write():
    """Without --output-ms the tool adds `output-column` to the INPUT MS, so
    `ms` is a mutator. Undeclared, Tier 1 could roll that write away under a
    later cache hit (stimela-ninja#52)."""
    from shinobi.steps.schema import mutated_path_fields

    cab = dosho.get("vis-mowjsub")
    assert "ms" in mutated_path_fields(cab)


def test_vis_mowjsub_output_ms_is_wireable():
    cab = dosho.get("vis-mowjsub")
    assert "output_ms" in cab.outputs_model.model_fields
