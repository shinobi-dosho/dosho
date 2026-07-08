"""dosho.psteps.casatasks -- @shinobi.pystep wrappers for CASA tasks.

CASA tasks are Python-package calls (casatasks.<task>), never real
standalone binaries, so they can't be represented as a dosho.Cab at all
(shinobi only executes flavour="binary" cabs) -- StepRef is the only
correct shape here. `casatasks` itself isn't installed in this test
environment (same as caracal2's own tests, which never actually dispatch
these either), so these tests check schema shape and Recipe wiring, not
real execution.
"""

from pathlib import Path

from pydantic import BaseModel
from shinobi import Recipe

import dosho
from dosho import images
from dosho.psteps.casatasks import (
    applycal,
    bandpass,
    clearcal,
    fixvis,
    flagdata,
    flagmanager,
    fluxscale,
    gaincal,
    initweights,
    listobs,
    mstransform,
    polcal,
    setjy,
)


def _all_pysteps():
    return {
        "listobs": listobs,
        "mstransform": mstransform,
        "fixvis": fixvis,
        "clearcal": clearcal,
        "initweights": initweights,
        "flagdata": flagdata,
        "setjy": setjy,
        "gaincal": gaincal,
        "polcal": polcal,
        "bandpass": bandpass,
        "applycal": applycal,
        "fluxscale": fluxscale,
        "flagmanager": flagmanager,
    }


def test_every_casatask_pystep_uses_the_pinned_casa6_image():
    for name, ref in _all_pysteps().items():
        assert ref.step.image == images.CASA6, name


def test_every_casatask_pystep_resolves_through_the_registry():
    for name in _all_pysteps():
        resolved = dosho.get(name)
        assert resolved.name == name


def test_listobs_schema_shape():
    fields = listobs.step.inputs_model.model_fields
    assert set(fields) == {"vis", "listfile"}
    assert fields["vis"].is_required()
    assert fields["listfile"].is_required()


def test_mstransform_has_real_defaults_for_optional_regridding_kwargs():
    fields = mstransform.step.inputs_model.model_fields
    assert fields["vis"].is_required()
    assert fields["field"].is_required()
    assert not fields["regridms"].is_required()
    assert fields["regridms"].default is False
    assert fields["datacolumn"].default == "corrected"


def test_gaincal_gaintype_is_required_not_defaulted():
    """gaintype disambiguates K/G/F/KCROSS -- there's no sane default."""
    fields = gaincal.step.inputs_model.model_fields
    assert fields["gaintype"].is_required()
    assert not fields["calmode"].is_required()


def test_flagdata_mode_required_others_optional():
    fields = flagdata.step.inputs_model.model_fields
    assert fields["mode"].is_required()
    assert not fields["field"].is_required()


def test_applycal_gaintable_is_required_list():
    fields = applycal.step.inputs_model.model_fields
    assert fields["gaintable"].is_required()
    assert fields["gaintable"].annotation == list[Path]


def test_flagmanager_generic_shape_not_caracal_specific_bookkeeping():
    """Only the raw CASA task shape (mode/versionname/merge) belongs here
    -- caracal2's own "before this worker ran" marker convention is
    pipeline-specific orchestration, not part of this wrapper.
    """
    fields = flagmanager.step.inputs_model.model_fields
    assert set(fields) == {"vis", "mode", "versionname", "merge"}
    assert fields["mode"].is_required()
    assert not fields["versionname"].is_required()


def test_a_pystep_wires_into_a_recipe_like_a_cab():
    class Inputs(BaseModel):
        ms: Path

    class Outputs(BaseModel):
        pass

    recipe = Recipe(name="t", inputs_model=Inputs, outputs_model=Outputs)
    recipe.add_step("listobs", dosho.get("listobs"), vis=recipe.inputs.ms, listfile=Path("obs.txt"))
    assert [s.name for s in recipe.steps] == ["listobs"]
    assert recipe.steps[0].wiring == {"vis": recipe.inputs.ms}
