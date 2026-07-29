from typing import get_args

import pytest
from pydantic import ValidationError
from shinobi.policies import build_argv
from shinobi.steps.schema import (
    Mutability,
    ParamMeta,
    ParamPattern,
    ParamSegment,
    Policies,
    mutated_path_fields,
)

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


def test_meta_as_fourth_tuple_element_on_output():
    cab = define_cab(
        "wsclean",
        "wsclean",
        "quay.io/example/wsclean:1.0",
        {"prefix": ("str", True, None)},
        outputs={"image": ("File", False, None, ParamMeta(implicit="{prefix}-MFS-image.fits"))},
    )
    assert cab.field_meta["image"].implicit == "{prefix}-MFS-image.fits"


def test_meta_on_a_sanitised_field_keeps_its_nom_de_guerre():
    cab = define_cab(
        "tool",
        "tool",
        "quay.io/example/tool:1.0",
        {"out-name": ("str", False, "out", ParamMeta(positional=True))},
    )
    meta = cab.field_meta["out_name"]
    assert meta.positional is True
    assert meta.nom_de_guerre == "out-name"


def test_explicit_nom_de_guerre_wins_over_auto_derived():
    cab = define_cab(
        "tool",
        "tool",
        "quay.io/example/tool:1.0",
        {"prefix": ("str", True, None, ParamMeta(nom_de_guerre="name"))},
    )
    assert cab.field_meta["prefix"].nom_de_guerre == "name"


def test_hyphenated_output_names_are_sanitised_too():
    cab = define_cab(
        "tool",
        "tool",
        "quay.io/example/tool:1.0",
        {"prefix": ("str", True, None)},
        outputs={"source-list": ("File", False, None)},
    )
    assert "source_list" in cab.outputs_model.model_fields
    assert cab.field_meta["source_list"].nom_de_guerre == "source-list"


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


def test_param_meta_choices_narrow_the_model_to_a_literal():
    # A ParamMeta.choices is threaded into build_model, narrowing the field's
    # real annotation to typing.Literal so an out-of-set value fails pydantic
    # validation -- not merely documented in info text.
    cab = define_cab(
        "tool",
        "tool",
        "quay.io/example/tool:1.0",
        {"mode": ("str", True, None, ParamMeta(choices=["dirty", "clean", "predict"]))},
    )
    field = cab.inputs_model.model_fields["mode"]
    assert get_args(field.annotation) == ("dirty", "clean", "predict")
    cab.inputs_model(mode="dirty")  # in-set accepted
    with pytest.raises(ValidationError):
        cab.inputs_model(mode="bogus")  # out-of-set rejected


def test_param_meta_abbreviation_lands_in_json_schema_extra():
    # A ParamMeta.abbreviation is carried onto the field's json_schema_extra so
    # shinobi's clickutil.build_options can emit a `-<abbrev>` CLI short flag.
    cab = define_cab(
        "tool",
        "tool",
        "quay.io/example/tool:1.0",
        {
            "ascii_sky": (
                "File",
                False,
                None,
                ParamMeta(nom_de_guerre="ascii-sky", abbreviation="as"),
            )
        },
    )
    field = cab.inputs_model.model_fields["ascii_sky"]
    assert field.json_schema_extra == {"abbreviation": "as"}
    # the CLI flag itself is still driven by nom_de_guerre, unaffected
    argv = build_argv(cab, {"ascii_sky": "/m.txt"})
    assert "--ascii-sky" in argv


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


def test_input_mutability_is_rekeyed_onto_the_sanitised_field_name():
    # keyed by the raw name the author already used in `fields` -- the
    # sanitised `input_ms_path` is an artifact of the builder, not
    # something a cab author should have to predict.
    cab = define_cab(
        "tool",
        "tool",
        "quay.io/example/tool:1.0",
        {"input_ms.path": ("MS", True, None), "prefix": ("str", False, "out")},
        input_mutability={"input_ms.path": Mutability.MUTABLE},
    )
    assert cab.input_mutability == {"input_ms_path": Mutability.MUTABLE}
    assert cab.mutability_of("input_ms_path") is Mutability.MUTABLE
    assert cab.mutability_of("prefix") is Mutability.IMMUTABLE


def test_declared_mutability_reaches_mutated_path_fields_without_a_matching_output_name():
    # the point of the whole argument: an `implicit`-templated output under
    # a *different* name than the input it echoes is invisible to shinobi's
    # `input_paths & output_paths` spelling, so the cache would fingerprint
    # a path the step itself overwrites.
    outputs = {"ms": ("MS", False, None, ParamMeta(implicit="{input_ms_path}"))}
    fields = {"input_ms.path": ("MS", True, None)}
    silent = define_cab("t1", "t1", "quay.io/example/tool:1.0", fields, outputs=outputs)
    assert mutated_path_fields(silent) == set()
    declared = define_cab(
        "t2",
        "t2",
        "quay.io/example/tool:1.0",
        fields,
        outputs=outputs,
        input_mutability={"input_ms.path": Mutability.MUTABLE},
    )
    assert mutated_path_fields(declared) == {"input_ms_path"}


def test_unknown_input_mutability_name_raises_rather_than_being_dropped():
    with pytest.raises(ValueError, match="not input fields"):
        define_cab(
            "tool",
            "tool",
            "quay.io/example/tool:1.0",
            {"input_ms.path": ("MS", True, None)},
            # the sanitised name, not the raw one -- a plausible typo, and
            # silently ignoring it would restore the exact bug this fixes
            input_mutability={"input_ms_path": Mutability.MUTABLE},
        )


def test_no_input_mutability_declared_leaves_the_cab_byte_identical():
    cab = define_cab("t", "t", "quay.io/example/tool:1.0", {"prefix": ("str", True, None)})
    assert cab.input_mutability == {}
