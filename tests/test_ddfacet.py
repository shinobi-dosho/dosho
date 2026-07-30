"""dosho.cabs.ddfacet -- ported from DDFacet's own DefaultParset.cfg (see
that module's docstring for the sourcing/parsing methodology). Checks
registration, field-count sanity, and real `--Section-OptionName` argv
shape (case-preserved, comma-joined list values) -- not exhaustive
per-field coverage, given the scale (273 fields).
"""

from shinobi.policies import build_argv

import dosho


def test_ddfacet_registered_and_uses_pinned_image():
    cab = dosho.get("ddfacet")
    assert cab.name == "ddfacet"
    assert cab.command == "DDF.py"
    from dosho import images

    assert cab.image == images.DDFACET


def test_ddfacet_full_field_count():
    # 274 real DefaultParset.cfg options, minus 1 #no_cmdline:1 (Misc.ParsetVersion),
    # plus 1 for the positional `parset` field (not a DefaultParset.cfg option itself)
    assert len(dosho.get("ddfacet").inputs_model.model_fields) == 274


def test_ddfacet_case_preserved_flags_and_comma_joined_ms_list():
    cab = dosho.get("ddfacet")
    argv = build_argv(
        cab,
        {
            "data_ms": ["a.MS", "b.MS"],
            "image_n_pix": 6000,
            "image_cell": 1.5,
            "output_name": "myimage",
            "deconv_mode": "HMP",
        },
    )
    assert argv[0] == "DDF.py"
    # real flags are case-sensitive: --Data-MS, --Image-NPix, not lowercase
    assert "--Data-MS" in argv
    assert "a.MS,b.MS" in argv  # comma-joined, not repeated flags
    assert "--Image-NPix" in argv and "6000" in argv
    assert "--Output-Name" in argv and "myimage" in argv
    assert "--Deconv-Mode" in argv and "HMP" in argv


def test_ddfacet_no_cmdline_only_field_is_excluded():
    # Misc.ParsetVersion is #no_cmdline:1 in the real .cfg -- can't be set via CLI
    assert "misc_parset_version" not in dosho.get("ddfacet").inputs_model.model_fields


def test_ddfacet_parset_is_a_bare_head_positional():
    cab = dosho.get("ddfacet")
    argv = build_argv(cab, {"parset": "base.parset", "image_n_pix": 6000})
    # DDF.py [parset file] <options> -- bare value before every --flag, no --Parset flag
    assert argv == ["DDF.py", "base.parset", "--Image-NPix", "6000"]


def test_ddfacet_parset_omitted_when_not_given():
    cab = dosho.get("ddfacet")
    argv = build_argv(cab, {"image_n_pix": 6000})
    assert "base.parset" not in argv
    assert argv == ["DDF.py", "--Image-NPix", "6000"]


def test_ddfacet_read_side_paths_are_path_dtypes_not_str():
    # DDFacet's .cfg does carry `#type:` tags, but `str` there means "a
    # string on the command line", not "not a path" -- so every filename
    # option arrived invisible to `path_fields`, hence never bind-mounted and
    # never workspace-anchored. Classified from each option's own .cfg help.
    from shinobi.steps.schema import path_fields

    assert path_fields(dosho.get("ddfacet").inputs_model) == {
        "parset",
        "data_ms",
        "predict_from_image",
        "predict_init_dico_model",
        "output_shift_facets_file",
        "image_multi_field_file",
        "facets_flux_padding_app_model",
        "beam_fits_file",
        "mask_external",
        "hmp_peak_weight_image",
        "pointing_solutions_pointing_sols_csv",
        "dde_solutions_sols_dir",
    }


def test_ddfacet_write_targets_and_column_names_stay_str():
    # Cache-Dir/DirWisdomFFTW/Montblanc-LogFile/Output-Name are DDFacet
    # *write* targets: a string-typed write target stays relative under a
    # sandbox on purpose (same call as killms' Solutions-SolsDir). Staying
    # `str` is the dtype half; the declaration half is the `harvest` glob
    # asserted below -- dtype and declaration are separate axes, and only
    # Output-Name gets both. The *ColName fields are MS column names, and
    # DDESolutions-DDSols is a name resolved against SolsDir, not a path.
    from shinobi.steps.schema import path_fields

    paths = path_fields(dosho.get("ddfacet").inputs_model)
    for field in (
        "cache_dir",
        "cache_dir_wisdom_fftw",
        "montblanc_log_file",
        "output_name",
        "data_col_name",
        "predict_col_name",
        "weight_out_col_name",
        "dde_solutions_dd_sols",
    ):
        assert field not in paths


def test_ddfacet_ms_is_declared_mutable():
    # DDF.py writes into the MS it images: --Predict-ColName,
    # --Weight-OutColName, and by default its cache "next to the MS". No
    # outputs model, so nothing for the name intersection to find.
    from shinobi.steps.schema import Mutability, mutated_path_fields

    cab = dosho.get("ddfacet")
    assert cab.mutability_of("data_ms") is Mutability.MUTABLE
    assert mutated_path_fields(cab) == {"data_ms"}
    # a read-side path keeps its content hash -- swapping the mask really is
    # a different step
    assert cab.mutability_of("mask_external") is Mutability.IMMUTABLE


def test_ddfacet_dtype_changes_do_not_touch_argv_shape():
    argv = build_argv(
        dosho.get("ddfacet"),
        {"data_ms": ["/x.ms"], "mask_external": "/m.fits", "dde_solutions_sols_dir": "/sols"},
    )
    assert "--Data-MS" in argv and "/x.ms" in argv
    assert "--Mask-External" in argv and "/m.fits" in argv
    assert "--DDESolutions-SolsDir" in argv and "/sols" in argv


def test_ddfacet_is_marked_experimental_with_its_unsupported_modes():
    """DDFacet is a rogue sibling upstream: its `.cfg` carries no usable
    `#type:` tags and `Output-Images` names the image family by letter code at
    run time. dosho does not patch around that indefinitely -- it marks the cab
    experimental and states which modes are not covered.
    """
    from dosho._builder import EXPERIMENTAL_CABS

    reason = EXPERIMENTAL_CABS["ddfacet"]
    assert "Output-Name" in reason
    assert "sandboxed" in reason and "containerised" in reason
    assert dosho.get("ddfacet").info.startswith("EXPERIMENTAL:")


def test_ddfacet_get_warns_once():
    import warnings

    from dosho import registry

    registry._warned_experimental.discard("ddfacet")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        dosho.get("ddfacet")
        dosho.get("ddfacet")
    assert len(caught) == 1
    assert "EXPERIMENTAL" in str(caught[0].message)


def test_ddfacet_write_targets_stay_undeclared():
    # The deliberate consequence of the marker above: no output fields, no
    # harvest globs. A declaration here would be the patch the experimental tag
    # exists instead of.
    cab = dosho.get("ddfacet")
    assert cab.outputs_model.model_fields == {}
    assert cab.harvest == []
    assert cab.sandbox is None
