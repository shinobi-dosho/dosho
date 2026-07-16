from shinobi.policies import build_argv
from shinobi.steps.schema import ParamMeta, ParamPattern, ParamSegment, Policies

from dosho._builder import define_cab


def test_hyphenated_names_get_sanitised_with_nom_de_guerre():
    cab = define_cab(
        "tool",
        "tool",
        "quay.io/example/tool:1.0",
        {"data-ms": ("MS", True, None), "out-name": ("str", False, "out")},
    )
    assert "data_ms" in cab.inputs_model.model_fields
    assert cab.field_meta["data_ms"].nom_de_guerre == "data-ms"
    argv = build_argv(cab, {"data_ms": "/x.ms", "out_name": "out"})
    assert "--data-ms" in argv
    assert "--out-name" in argv


def test_explicit_field_meta_merges_and_keeps_auto_nom_de_guerre():
    cab = define_cab(
        "wsclean",
        "wsclean",
        "quay.io/example/wsclean:1.0",
        {"prefix": ("str", True, None)},
        outputs={"image": ("str", False, None)},
        field_meta={"image": ParamMeta(implicit="{prefix}-MFS-image.fits")},
    )
    assert cab.field_meta["image"].implicit == "{prefix}-MFS-image.fits"


def test_field_meta_on_a_sanitised_field_keeps_its_nom_de_guerre():
    cab = define_cab(
        "tool",
        "tool",
        "quay.io/example/tool:1.0",
        {"out-name": ("str", False, "out")},
        field_meta={"out_name": ParamMeta(positional=True)},
    )
    meta = cab.field_meta["out_name"]
    assert meta.positional is True
    assert meta.nom_de_guerre == "out-name"


def test_input_patterns_allow_extra_and_are_attached():
    pattern = ParamPattern(
        separator="-",
        segments=[
            ParamSegment(regex=r".+?"),
            ParamSegment(attrs={"solvable": ParamMeta(), "type": ParamMeta()}),
        ],
    )
    cab = define_cab(
        "cubical",
        "gocubical",
        "quay.io/example/cubical:1.0",
        {"data-ms": ("MS", True, None)},
        input_patterns=[pattern],
    )
    assert cab.inputs_model.model_config.get("extra") == "allow"
    assert cab.match_pattern("g1-solvable") is not None
    assert cab.match_pattern("g-time-int") is None


def test_policies_pass_through():
    cab = define_cab(
        "quartical",
        "goquartical",
        "quay.io/example/quartical:1.0",
        {"solver.terms": ("str", False, None)},
        policies=Policies(key_value=True, repeat="[]", prefix=""),
    )
    assert cab.policies.key_value is True
    assert cab.policies.repeat == "[]"


def test_sandbox_and_harvest_pass_through():
    cab = define_cab(
        "tool",
        "tool",
        "quay.io/example/tool:1.0",
        {"prefix": ("str", True, None)},
        sandbox=True,
        harvest=["{prefix}-*"],
    )
    assert cab.sandbox is True
    assert cab.harvest == ["{prefix}-*"]
    # unset stays None (defer to recipe/config), not False
    plain = define_cab("t2", "t2", "quay.io/example/tool:1.0", {})
    assert plain.sandbox is None
    assert plain.harvest == []
