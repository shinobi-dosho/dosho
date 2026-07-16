"""dosho.cabs.casatasks -- @shinobi.pystep wrappers for CASA tasks.

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
from dosho.cabs.casatasks import (
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
    """Full real listobs() signature per casadocs, not just vis/listfile --
    see the module docstring's audit note."""
    fields = listobs.step.inputs_model.model_fields
    assert fields["vis"].is_required()
    assert fields["listfile"].is_required()
    assert not fields["overwrite"].is_required()
    assert fields["overwrite"].default is False  # CASA's own default, not this file's old True
    assert "spw" in fields and "antenna" in fields and "cachesize" in fields


def test_mstransform_has_real_defaults_for_optional_regridding_kwargs():
    fields = mstransform.step.inputs_model.model_fields
    assert fields["vis"].is_required()
    assert not fields["field"].is_required()  # CASA's own default ('') is now exposed, not hardcoded
    assert not fields["regridms"].is_required()
    assert fields["regridms"].default is False
    assert fields["datacolumn"].default == "corrected"
    assert fields["realmodelcol"].default is False  # the gap oxkat's split scripts needed
    assert fields["keepflags"].default is True  # was silently hardcoded, now a real param


def test_gaincal_gaintype_defaults_to_casas_own_default():
    """Deliberately matches CASA's own default ('G') rather than requiring
    a caller to always specify it -- consistency with casadocs wins over
    guarding against a silently-wrong solve type.
    """
    fields = gaincal.step.inputs_model.model_fields
    assert not fields["gaintype"].is_required()
    assert fields["gaintype"].default == "G"
    assert not fields["calmode"].is_required()


def test_flagdata_mode_defaults_to_casas_own_default():
    fields = flagdata.step.inputs_model.model_fields
    assert not fields["mode"].is_required()
    assert fields["mode"].default == "manual"
    assert not fields["field"].is_required()


def test_applycal_gaintable_is_required_list():
    fields = applycal.step.inputs_model.model_fields
    assert fields["gaintable"].is_required()
    assert fields["gaintable"].annotation == list[Path]
    assert "spw" in fields  # was missing entirely -- every other selection param had it


def test_gaincal_and_bandpass_have_the_params_oxkats_1gc_ladder_needs():
    """oxkat's 1GC_casa_refcal.py passes these explicitly on every call;
    a caller using this cab without them can't reproduce that ladder.
    """
    gaincal_fields = gaincal.step.inputs_model.model_fields
    assert gaincal_fields["append"].default is False
    assert gaincal_fields["minblperant"].default == 4

    bandpass_fields = bandpass.step.inputs_model.model_fields
    assert bandpass_fields["bandtype"].default == "B"
    assert bandpass_fields["minblperant"].default == 4
    assert bandpass_fields["append"].default is False


def test_fluxscale_has_append_and_real_list_typed_reference_transfer():
    """oxkat's F3 call passes transfer=pcals, a list of every secondary
    calibrator -- this only round-trips if transfer is a real list, not
    a string (CASA's own `stringVec` type).
    """
    fields = fluxscale.step.inputs_model.model_fields
    assert fields["append"].default is False
    assert fields["reference"].is_required()
    assert fields["reference"].annotation == list[str]
    assert fields["transfer"].annotation == list[str] | None


def test_flagmanager_generic_shape_not_caracal_specific_bookkeeping():
    """Only the raw CASA task shape belongs here -- caracal2's own "before
    this worker ran" marker convention is pipeline-specific orchestration,
    not part of this wrapper. `oldname`/`comment` (mode='rename'/'save')
    are real CASA parameters this file was missing, not caracal2-specific
    additions.
    """
    fields = flagmanager.step.inputs_model.model_fields
    assert set(fields) == {"vis", "mode", "versionname", "oldname", "comment", "merge"}
    assert not fields["mode"].is_required()
    assert fields["mode"].default == "list"
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


def test_every_pystep_body_quiets_casa_logging_before_importing_casatasks():
    """Output hygiene: each pystep must call `_quiet_casa(ctx)` *before* its
    `ctx.import_func(..., "casatasks")` -- the casa-*.log is created as an
    import side effect, so ordering is the whole point (see the module
    docstring). Checked over every StepRef in the module, not just the
    handful imported at the top of this file.
    """
    import inspect

    from shinobi.steps.schema import StepRef

    from dosho.cabs import casatasks as module

    refs = [v for v in vars(module).values() if isinstance(v, StepRef)]
    assert len(refs) >= 50  # the full audited task set, not a subset
    for ref in refs:
        src = inspect.getsource(ref.func.__wrapped__)
        assert "_quiet_casa(ctx)" in src, ref.name
        assert src.index("_quiet_casa(ctx)") < src.index("ctx.import_func("), ref.name


def test_quiet_casa_writes_site_config_and_redirects_casalog():
    import os

    from dosho.cabs.casatasks import _quiet_casa

    class FakeLog:
        def __init__(self):
            self.logfile = None

        def setlogfile(self, path):
            self.logfile = path

    class FakeCtx:
        def __init__(self):
            self.log = FakeLog()

        def import_func(self, name, module):
            assert (name, module) == ("casalog", "casatasks")
            return self.log

    had = os.environ.pop("CASASITECONFIG", None)
    config = None
    try:
        ctx = FakeCtx()
        _quiet_casa(ctx)
        config = os.environ["CASASITECONFIG"]
        with open(config) as f:
            content = f.read()
        assert "nologfile = True" in content
        assert "telemetry_enabled = False" in content
        assert ctx.log.logfile == os.devnull
        # idempotent: a second call must not clobber an existing config
        _quiet_casa(FakeCtx())
        assert os.environ["CASASITECONFIG"] == config
    finally:
        os.environ.pop("CASASITECONFIG", None)
        if config is not None:
            try:
                os.remove(config)
            except FileNotFoundError:
                pass
        if had is not None:
            os.environ["CASASITECONFIG"] = had
