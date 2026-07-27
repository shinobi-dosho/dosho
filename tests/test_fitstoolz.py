"""fitstoolz's six wrapped apps (`dosho/cabs/fitstoolz.py`).

fitstoolz authors its apps as `@shinobi.pystep` functions inside the tool
itself (like simms 3.0), so dosho wraps them as pysteps rather than binary
cabs -- these check the pystep's `inputs_model`/`outputs_model` schema
shape and that they wire into a `Recipe`, not a `build_argv` token shape.
"""

from pathlib import Path

import pytest
import shinobi
from pydantic import ValidationError, create_model
from shinobi import StepRef

import dosho
from dosho import images

_APPS = [
    "fitstoolz-header",
    "fitstoolz-stats",
    "fitstoolz-slice",
    "fitstoolz-add-axis",
    "fitstoolz-remove-axis",
    "fitstoolz-stack",
]


@pytest.mark.parametrize("name", _APPS)
def test_every_app_is_a_registered_pystep_on_the_fitstoolz_image(name):
    step = dosho.get(name)
    assert isinstance(step, StepRef)
    assert step.name == name
    assert step.step.image == images.FITSTOOLZ
    # every app takes the image to operate on, and it is the one required input
    # they all share (`fname`, positional on fitstoolz's own CLI)
    assert step.step.inputs_model.model_fields["fname"].is_required()


def test_apps_are_also_importable_directly_under_prefixed_names():
    from dosho.cabs import fitstoolz_header, fitstoolz_slice

    # the module's own attribute is `slice_` (fitstoolz avoids shadowing the
    # builtin); the package re-export is prefixed, so `from dosho.cabs import
    # slice` can never shadow it either
    assert fitstoolz_slice.name == "fitstoolz-slice"
    assert fitstoolz_header is dosho.get("fitstoolz-header")


def test_header_edit_add_remove_are_repeatable_and_output_is_optional():
    step = dosho.get("fitstoolz-header")
    fields = step.step.inputs_model.model_fields
    for name in ("edit", "remove", "add"):
        assert step.step.inputs_model(fname="/x.fits", **{name: ["FOO=1", "BAR=2"]})
    assert fields["show"].default is False
    assert fields["replace"].default is False
    # `--show` writes nothing, so the output path must be allowed to come back
    # unset rather than being a required output
    assert step.step.outputs_model().outfile is None


def test_stats_returns_real_statistics_not_just_a_path():
    step = dosho.get("fitstoolz-stats")
    outputs = step.step.outputs_model.model_fields
    assert set(outputs) == {"min", "max", "mean", "std"}
    # a downstream step can wire to any of them
    assert step.step.outputs_model(min=-1.0, max=2.0, mean=0.1, std=0.5).std == 0.5
    fields = step.step.inputs_model.model_fields
    # `slice`/`clip_*` keep fitstoolz's own names, since `runit` reads them off
    # the namespace this wrapper builds
    assert step.step.inputs_model(fname="/x.fits", slice=["FREQ,0,64"]).slice == ["FREQ,0,64"]
    assert fields["blank_value"].default is None


def test_slice_axis_is_a_repeatable_ctype_start_end_spec():
    step = dosho.get("fitstoolz-slice")
    inputs = step.step.inputs_model(fname="/x.fits", axis=["FREQ,0,64", "STOKES,0,1"])
    assert inputs.axis == ["FREQ,0,64", "STOKES,0,1"]
    assert step.step.inputs_model.model_fields["memmap"].default is True


def test_add_axis_requires_the_axis_it_is_adding():
    step = dosho.get("fitstoolz-add-axis")
    fields = step.step.inputs_model.model_fields
    assert fields["ctype"].is_required() and fields["index"].is_required()
    with pytest.raises(ValidationError):
        step.step.inputs_model(fname="/x.fits")  # no ctype/index
    inputs = step.step.inputs_model(fname="/x.fits", ctype="FREQ", index=0)
    # WCS defaults match fitstoolz's own, so an omitted knob means the same thing
    assert (inputs.crpix, inputs.crval, inputs.cdelt, inputs.cunit) == (0, 0.0, 1.0, "")


def test_remove_axis_carries_its_cli_short_flags():
    step = dosho.get("fitstoolz-remove-axis")
    fields = step.step.inputs_model.model_fields
    assert fields["ctype"].json_schema_extra == {"abbreviation": "ct"}
    assert fields["select_index"].json_schema_extra == {"abbreviation": "si"}
    assert fields["select_index"].default == 0


def test_stack_takes_extra_files_and_names_its_own_output():
    step = dosho.get("fitstoolz-stack")
    fields = step.step.inputs_model.model_fields
    # unlike the other apps, the stacked output path is a required *input*
    assert fields["stacked_fits"].is_required() and fields["axis"].is_required()
    inputs = step.step.inputs_model(
        fname="/a.fits", axis="FREQ", extra_files=["/b.fits", "/c.fits"], stacked_fits="/out.fits"
    )
    # path-typed so shinobi absolutizes them and binds their parents into the
    # container -- fitstoolz's own signature says plain str
    assert inputs.extra_files == [Path("/b.fits"), Path("/c.fits")]
    assert "stacked_fits" in step.step.outputs_model.model_fields


def test_opts_renders_paths_back_to_the_strings_runit_expects():
    from dosho.cabs.fitstoolz import _opts

    opts = _opts(
        {"ctx": object(), "fname": Path("/a.fits"), "extra": [Path("/b.fits")], "replace": True}
    )
    assert not hasattr(opts, "ctx")  # the ctx is dosho's, not fitstoolz's
    assert opts.fname == "/a.fits"
    assert opts.extra == ["/b.fits"]
    assert opts.replace is True


def test_fitstoolz_pysteps_wire_into_a_recipe():
    recipe = shinobi.Recipe(
        name="cube", inputs_model=create_model("I"), outputs_model=create_model("O")
    )
    recipe.add_step(
        "sub", dosho.get("fitstoolz-slice"), fname="cube.fits", axis=["FREQ,0,64"], outfile="s.fits"
    )
    recipe.add_step("rms", dosho.get("fitstoolz-stats"), fname="s.fits", show=True)
    assert [s.name for s in recipe.steps] == ["sub", "rms"]
    # the StepRef carries its pystep orchestration func into the recipe step
    assert recipe.steps[1].func is not None
