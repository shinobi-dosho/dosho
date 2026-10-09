"""A contracted Python MSv2 reader, imported inside the running container."""

from __future__ import annotations

from pydantic import BaseModel
from shinobi import DatasetAccess, DatasetColumns, MSv2, pystep


class SummaryOutputs(BaseModel):
    summary: dict[str, int | list[int]]


@pystep(
    dataset_accesses=[
        DatasetAccess(field="ms", mode="read", columns=DatasetColumns(read=("UVW", "DATA", "FLAG")))
    ],
)
def summarize(ctx, ms: MSv2) -> SummaryOutputs:
    """Read dimensions and flag counts without changing the Measurement Set."""
    table = ctx.import_func("table", "casacore.tables")
    with table(str(ms), ack=False) as main:
        data = main.getcol("DATA")
        flags = main.getcol("FLAG")
        uvw = main.getcol("UVW")
        values = {
            "rows": main.nrows(),
            "channels": data.shape[1],
            "correlations": data.shape[2],
            "flagged": int(flags.sum()),
            "uvw_shape": list(uvw.shape),
        }
    return SummaryOutputs(summary=values)
