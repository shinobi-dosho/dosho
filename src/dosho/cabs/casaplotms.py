"""`@shinobi.pystep` wrapper for CASA's `plotms` task
(`casaplotms.plotms`, a sibling package to `casatasks`, not part of it --
same `ctx.import_func`-inside-container mechanism as
`dosho.cabs.casatasks`, see that module's own docstring for the full
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
    """Outputs of the `plotms` step."""

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
    """Render a CASA `plotms` diagnostic plot.

    Args:
        ctx: The pystep execution context.
        vis: Path to the measurement set to plot.
        xaxis: Column/quantity to plot on the x-axis.
        yaxis: Column/quantity to plot on the y-axis.
        plotfile: Path to write the rendered plot to.
        xdatacolumn: Data column for `xaxis`, if applicable.
        ydatacolumn: Data column for `yaxis`, if applicable.
        coloraxis: Quantity to color points by.
        field: Field selection string.
        correlation: Correlation selection string.
        iteraxis: Axis to iterate multi-panel plots over (e.g. per
            correlation), for the fuller diagnostic-plot shape.
        expformat: Output image format.
        exprange: Which iteration panels to export (`"all"` or a range).
        overwrite: Whether to overwrite an existing `plotfile`.
        showgui: Whether to show the interactive GUI while plotting.

    Returns:
        `PlotmsOutputs` with the written `plotfile`.
    """
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
