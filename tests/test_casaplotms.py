"""dosho.cabs.casaplotms -- @shinobi.pystep wrapper for CASA's plotms
task (casaplotms.plotms, a sibling package to casatasks). Not installed
in this test environment -- checks schema shape and Recipe wiring only,
same convention as test_casatasks.py.
"""

from pathlib import Path

from pydantic import BaseModel
from shinobi import Recipe

import dosho
from dosho import images
from dosho.cabs.casaplotms import plotms


def test_uses_the_pinned_casa6_image():
    assert plotms.step.image == images.CASA6


def test_resolves_through_the_registry():
    resolved = dosho.get("plotms")
    assert resolved.name == "plotms"


def test_schema_covers_both_minimal_and_full_call_shapes():
    fields = plotms.step.inputs_model.model_fields
    # required for any plot at all
    for required in ("vis", "xaxis", "yaxis", "plotfile"):
        assert fields[required].is_required(), required
    # optional, real CASA plotms defaults
    for optional, default in (
        ("xdatacolumn", ""),
        ("ydatacolumn", ""),
        ("coloraxis", ""),
        ("field", ""),
        ("correlation", ""),
        ("iteraxis", ""),
        ("expformat", "png"),
        ("exprange", "all"),
        ("overwrite", True),
        ("showgui", False),
    ):
        assert not fields[optional].is_required(), optional
        assert fields[optional].default == default, optional


def test_minimal_elevation_track_shape_wires_into_a_recipe():
    """Mirrors the minimal call shape (vis/xaxis/yaxis/coloraxis/plotfile/
    overwrite) an elevation-track plot uses -- no per-correlation axes.
    """

    class Inputs(BaseModel):
        ms: Path

    class Outputs(BaseModel):
        pass

    recipe = Recipe(name="t", inputs_model=Inputs, outputs_model=Outputs)
    recipe.add_step(
        "plotelev",
        dosho.get("plotms"),
        vis=recipe.inputs.ms,
        xaxis="hourangle",
        yaxis="elevation",
        coloraxis="field",
        plotfile=Path("elevation_tracks.png"),
        overwrite=True,
    )
    assert [s.name for s in recipe.steps] == ["plotelev"]
