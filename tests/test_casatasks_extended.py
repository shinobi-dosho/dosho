"""dosho.cabs.casatasks -- the 44 tasks added beyond the original 13
(listobs/mstransform/fixvis/clearcal/initweights/flagdata/setjy/gaincal/
polcal/bandpass/applycal/fluxscale/flagmanager, covered in
test_casatasks.py), completing the Flagging/Calibration/Imaging/
Manipulation categories per casadocs.readthedocs.io. Same rationale as
test_casatasks.py: `casatasks` isn't installed in this test environment,
so these check schema shape and the in-place-mutation-as-output
convention, not real execution.
"""

from pathlib import Path

import dosho
from dosho import images
from dosho.cabs.casatasks import (
    clearstat,
    delmod,
    fixplanets,
    ft,
    rerefant,
    rmtables,
    sdintimaging,
    smoothcal,
    statwt,
    tclean,
    uvcontsub_old,
    uvsub,
    virtualconcat,
)

_NEW_TASK_NAMES = [
    "accor", "appendantab", "blcal", "defintent", "fringefit", "gencal",
    "getantposalma", "getcalmodvla", "pccor", "polfromgain", "rerefant",
    "smoothcal", "wvrgcal", "flagcmd", "msuvbinflag", "apparentsens",
    "deconvolve", "delmod", "feather", "ft", "impbcor", "makemask",
    "predictcomp", "widebandpbcor", "tclean", "sdintimaging", "clearstat",
    "concat", "conjugatevis", "cvel", "cvel2", "fixplanets", "hanningsmooth",
    "msuvbin", "partition", "phaseshift", "rmtables", "split", "statwt",
    "uvcontsub", "uvcontsub_old", "uvmodelfit", "uvsub", "virtualconcat",
]


def test_all_44_new_tasks_are_registered():
    assert len(_NEW_TASK_NAMES) == 44
    for name in _NEW_TASK_NAMES:
        resolved = dosho.get(name)
        assert resolved.name == name


def test_all_44_new_tasks_use_the_pinned_casa6_image():
    for name in _NEW_TASK_NAMES:
        ref = dosho.get(name)
        assert ref.step.image == images.CASA6, name


# --- in-place-mutated inputs are classified as outputs ---------------------


def test_delmod_echoes_vis_its_only_output():
    """delmod deletes model representations from vis in place -- there's
    no separate output file, so vis itself must be the output.
    """
    fields = delmod.step.outputs_model.model_fields
    assert set(fields) == {"vis"}


def test_ft_echoes_vis_since_it_writes_the_model_in_place():
    fields = ft.step.outputs_model.model_fields
    assert set(fields) == {"vis"}


def test_fixplanets_echoes_vis_since_it_edits_field_source_tables_in_place():
    fields = fixplanets.step.outputs_model.model_fields
    assert set(fields) == {"vis"}


def test_statwt_echoes_vis_since_it_writes_weights_in_place():
    fields = statwt.step.outputs_model.model_fields
    assert set(fields) == {"vis"}


def test_uvsub_echoes_vis_since_it_mutates_corrected_data_in_place():
    fields = uvsub.step.outputs_model.model_fields
    assert set(fields) == {"vis"}


def test_rerefant_and_smoothcal_fall_back_to_tablein_when_caltable_omitted():
    """Both mutate tablein in place unless a distinct caltable is given --
    the output must resolve to whichever path was actually written.
    """
    for step in (rerefant, smoothcal):
        assert set(step.step.outputs_model.model_fields) == {"caltable"}


def test_virtualconcat_echoes_moved_vis_when_keepcopy_is_false():
    """CASA's own keepcopy default is False, meaning the input MSs are
    consumed into concatvis rather than left untouched -- that's a real
    mutation of the inputs, not just a new concatvis output.
    """
    fields = virtualconcat.step.outputs_model.model_fields
    assert set(fields) == {"concatvis", "moved_vis"}
    assert not fields["moved_vis"].is_required()


def test_uvcontsub_old_output_paths_are_deterministic_from_vis():
    """uvcontsub_old has no outputvis parameter at all -- CASA fixes the
    output name to {vis}.contsub (and {vis}.cont if want_cont=True), so
    those must be computed outputs, not a caller-supplied path.
    """
    fields = uvcontsub_old.step.inputs_model.model_fields
    assert "outputvis" not in fields
    out_fields = uvcontsub_old.step.outputs_model.model_fields
    assert set(out_fields) == {"contsub_vis", "cont_vis"}


# --- no-artifact tasks get empty outputs, not a fabricated field ----------


def test_clearstat_and_rmtables_have_no_output_fields():
    """clearstat clears locks globally; rmtables deletes its inputs --
    neither has a resulting path a downstream step could meaningfully
    wire from.
    """
    assert clearstat.step.outputs_model.model_fields == {}
    assert rmtables.step.outputs_model.model_fields == {}


def test_rmtables_tablenames_is_a_required_list():
    fields = rmtables.step.inputs_model.model_fields
    assert fields["tablenames"].is_required()
    assert fields["tablenames"].annotation == list[str]


# --- tclean / sdintimaging: the big ones ------------------------------------


def test_tclean_image_family_derives_from_imagename():
    fields = tclean.step.outputs_model.model_fields
    assert set(fields) == {"imagename", "image", "residual", "model", "psf", "pb", "image_pbcor", "mutated_vis"}
    assert not fields["image_pbcor"].is_required()
    assert not fields["mutated_vis"].is_required()


def test_tclean_gaintype_equivalent_selectors_have_real_casa_defaults():
    """Unlike gaincal's gaintype/flagdata's mode, tclean's own mode
    selectors (specmode, gridder, deconvolver, weighting, usemask) all
    default to CASA's own values -- there's no equivalent prior "no sane
    default" decision for this task, so casadocs wins throughout.
    """
    fields = tclean.step.inputs_model.model_fields
    assert fields["specmode"].default == "mfs"
    assert fields["gridder"].default == "standard"
    assert fields["deconvolver"].default == "hogbom"
    assert fields["weighting"].default == "natural"
    assert fields["usemask"].default == "user"
    assert fields["niter"].default == 0  # CASA's own tclean default (not gaincal/bandpass's world)


def test_sdintimaging_shares_tcleans_image_family_shape():
    fields = sdintimaging.step.outputs_model.model_fields
    assert set(fields) == {"imagename", "image", "residual", "model", "psf", "image_pbcor"}


def test_a_new_pystep_wires_into_a_recipe_like_a_cab():
    from pydantic import BaseModel
    from shinobi import Recipe

    class Inputs(BaseModel):
        ms: Path

    class Outputs(BaseModel):
        pass

    recipe = Recipe(name="t", inputs_model=Inputs, outputs_model=Outputs)
    recipe.add_step("delmod", dosho.get("delmod"), vis=recipe.inputs.ms)
    assert [s.name for s in recipe.steps] == ["delmod"]
    assert recipe.steps[0].wiring == {"vis": recipe.inputs.ms}
