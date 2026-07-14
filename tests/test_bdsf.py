"""dosho.cabs.bdsf -- @shinobi.pystep wrapper for PyBDSF's process_image +
write_catalog.

`bdsf` itself isn't installed in this test environment (same rationale as
`test_casatasks.py`: PyBDSF is a heavy scientific package meant to run
inside the BDSF image, not on the test host) -- these tests check schema
shape, registration, and the "at least one output file" guard (called
directly against the undecorated function, bypassing `ctx`/PyBDSF), not a
real `process_image` run.
"""

from pathlib import Path

import pytest
from pydantic import BaseModel
from shinobi import Recipe

import dosho
from dosho import images
from dosho.cabs.bdsf import catalog


def test_bdsf_catalog_uses_the_pinned_bdsf_image():
    assert catalog.step.image == images.BDSF


def test_bdsf_catalog_resolves_through_the_registry():
    resolved = dosho.get("bdsf-catalog")
    assert resolved.name == "bdsf-catalog"


def test_bdsf_catalog_schema_shape():
    fields = catalog.step.inputs_model.model_fields
    assert fields["image"].is_required()
    assert not fields["outfile_gaul"].is_required()
    assert not fields["outfile_srl"].is_required()
    assert fields["catalog_format"].default == "bbs"
    assert fields["thresh_isl"].default == 3.0
    assert fields["thresh_pix"].default == 5.0
    assert fields["adaptive_rms_box"].default is False
    # rms_map is a real tri-state True/False/None option, not a plain bool
    assert fields["rms_map"].annotation == bool | None


def test_bdsf_catalog_requires_at_least_one_output_file():
    real_func = catalog.func.__wrapped__
    with pytest.raises(ValueError, match="outfile_gaul/outfile_srl"):
        real_func(ctx=None, image=Path("/x.fits"))


def test_bdsf_catalog_wires_into_a_recipe_like_a_cab():
    class Inputs(BaseModel):
        image: Path

    class Outputs(BaseModel):
        pass

    recipe = Recipe(name="t", inputs_model=Inputs, outputs_model=Outputs)
    recipe.add_step(
        "catalog", dosho.get("bdsf-catalog"), image=recipe.inputs.image, outfile_srl=Path("out.srl")
    )
    assert [s.name for s in recipe.steps] == ["catalog"]
    assert recipe.steps[0].wiring == {"image": recipe.inputs.image}
