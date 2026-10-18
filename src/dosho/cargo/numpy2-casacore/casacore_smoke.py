"""Exercise NumPy 2 through python-casacore's complex array conversion."""

import tempfile
from pathlib import Path

import numpy as np
from casacore.tables import makearrcoldesc, maketabdesc, table

assert int(np.__version__.split(".", 1)[0]) >= 2, np.__version__
with tempfile.TemporaryDirectory() as root:
    path = str(Path(root) / "abi.tab")
    desc = maketabdesc([makearrcoldesc("DATA", 0j, ndim=1, shape=[2])])
    with table(path, desc, nrow=2, readonly=False, ack=False) as tab:
        tab.putcol(
            "DATA",
            np.array([[1 + 2j, 3 + 4j], [5 + 6j, 7 + 8j]], dtype=np.complex64),
        )
    with table(path, readonly=True, ack=False) as tab:
        data = tab.getcol("DATA")
    assert data.shape == (2, 2) and data[1, 1] == 7 + 8j, data
