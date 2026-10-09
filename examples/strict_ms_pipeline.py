"""A small strict MSv2 simulation, flagging and imaging recipe.

Run with a Python 3.11 driver and the pinned Docker images. Every MS port,
including the custom Python reader, carries an MSv2 access contract.
"""

from __future__ import annotations

import runpy
from pathlib import Path

from pydantic import BaseModel
from shinobi import MSv2, ProductFamily, Recipe
from shinobi.steps.schema import InputRef, OutputRef, StepRef

import dosho
from dosho import images

# Keep the container-executed reader in a separate source module: the runner
# loads its entire file, so it must not also construct the host-side recipe.
summarize = runpy.run_path(str(Path(__file__).with_name("strict_ms_summary.py")))["summarize"]
summarize = summarize.model_copy(
    update={"step": summarize.step.model_copy(update={"image": images.MSUTILS})}
)


class Inputs(BaseModel):
    ms: MSv2
    sky: Path
    flag_config: Path
    prefix: str = "image"


class Outputs(BaseModel):
    ms: MSv2
    summary: dict[str, int | list[int]]
    image: ProductFamily[Path]


pipeline = Recipe(name="strict-ms-pipeline", inputs_model=Inputs, outputs_model=Outputs)
pipeline.add_step(
    "simulate",
    dosho.get("simms-telsim"),
    ms=InputRef(field="ms"),
    telescope="meerkat",
    subarray_range=["0", "3"],
    direction="J2000,0h24m20s,-30d12m33s",
    starttime="2024-03-14T06:15:10",
    ntime=4,
    nchan=8,
    correlations="XX,XY,YX,YY",
    nworkers=1,
)
pipeline.add_step(
    "populate",
    dosho.get("simms-skysim"),
    ms=OutputRef(step="simulate", field="ms"),
    ascii_sky=InputRef(field="sky"),
    nworkers=1,
)
populated = OutputRef(step="populate", field="ms")
pipeline.add_step(
    "backup",
    StepRef(name="backup", step=dosho.get("msutils-flags-backup"), params={"name": "before"}),
    ms=populated,
)
pipeline.add_step(
    "flag",
    dosho.get("tricolour"),
    ms=populated,
    config=InputRef(field="flag_config"),
    nworkers=2,
    scan_numbers="1",
)
pipeline.add_step(
    "restore",
    StepRef(name="restore", step=dosho.get("msutils-flags-restore"), params={"name": "before"}),
    ms=OutputRef(step="flag", field="ms"),
)
restored = OutputRef(step="restore", field="ms")
pipeline.add_step("summary", summarize, ms=restored)
pipeline.add_step(
    "image",
    dosho.get("wsclean"),
    ms=[restored],
    prefix=InputRef(field="prefix"),
    size=(32, 32),
    scale="1amin",
    threads=1,
    niter=1,
    make_psf=True,
)
pipeline.set_output("ms", restored)
pipeline.set_output("summary", OutputRef(step="summary", field="summary"))
pipeline.set_output("image", OutputRef(step="image", field="image"))
