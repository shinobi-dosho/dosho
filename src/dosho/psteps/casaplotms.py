"""`@shinobi.pystep` wrapper for CASA's `plotms` task
(`casaplotms.plotms`, a sibling package to `casatasks`, not part of it --
same `ctx.import_func`-inside-container mechanism as
`dosho.psteps.casatasks`, see that module's own docstring for the full
rationale).

One general wrapper covers both a minimal single-axis-pair plot (e.g. an
elevation-vs-hourangle track) and the fuller per-datacolumn/per-correlation
diagnostic-plot shape (iterating over correlations via `iteraxis`) --
callers omit whatever they don't need; the real task's own defaults apply.
"""

from __future__ import annotations

from pathlib import Path

import shinobi
from pydantic import BaseModel

from dosho import images


class PlotmsOutputs(BaseModel):
    plotfile: Path


@shinobi.pystep(image=images.CASA6)
def plotms(
    ctx,
    vis: Path,
    xaxis: str,
    yaxis: str,
    plotfile: Path,
    xdatacolumn: str = "",
    ydatacolumn: str = "",
    coloraxis: str = "",
    field: str = "",
    correlation: str = "",
    iteraxis: str = "",
    expformat: str = "png",
    exprange: str = "all",
    overwrite: bool = True,
    showgui: bool = False,
) -> PlotmsOutputs:
    plotms_fn = ctx.import_func("plotms", "casaplotms")
    plotms_fn(
        vis=str(vis),
        xaxis=xaxis,
        yaxis=yaxis,
        xdatacolumn=xdatacolumn,
        ydatacolumn=ydatacolumn,
        coloraxis=coloraxis,
        field=field,
        correlation=correlation,
        iteraxis=iteraxis,
        plotfile=str(plotfile),
        expformat=expformat,
        exprange=exprange,
        overwrite=overwrite,
        showgui=showgui,
    )
    return PlotmsOutputs(plotfile=plotfile)
