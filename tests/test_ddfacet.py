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
