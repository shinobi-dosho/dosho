"""Real tiny tables with a casatools-shaped adapter; native oracle is separate."""

from pathlib import Path

import numpy as np
import pytest

from dosho.cabs.casa_selfcal import _path_flag_digest, flagversion_restore_replace


class _Tool:
    def __init__(self, state):
        self.state = state

    def open(self, path, nomodify=True):
        from casacore.tables import table

        self.table = table(path, readonly=nomodify, ack=False)
        self.writable = not nomodify
        if self.writable:
            self.state["write_opens"] += 1

    def close(self):
        self.table.close()

    def flush(self):
        self.table.flush()

    def nrows(self):
        return self.table.nrows()

    def colnames(self):
        return self.table.colnames()

    def getkeywords(self):
        return self.table.getkeywords()

    def getcoldesc(self, name):
        return self.table.getcoldesc(name)

    def iscelldefined(self, name, row):
        return self.table.iscelldefined(name, row)

    def getcell(self, name, row):
        value = self.table.getcell(name, row)
        return value.T if name == "FLAG" else value

    def getcol(self, name, **kwargs):
        value = self.table.getcol(name, **kwargs)
        return value.transpose(2, 1, 0) if name == "FLAG" else value

    def putcol(self, name, value, **kwargs):
        self.state["writes"] += 1
        assert self.writable
        if name == "FLAG":
            value = value.transpose(2, 1, 0)
        self.table.putcol(name, value, **kwargs)


class _Context:
    def __init__(self):
        self.state = {"writes": 0, "write_opens": 0}

    def import_func(self, name, package):
        assert (name, package) == ("table", "casatools")
        return lambda: _Tool(self.state)


def _fixture(root):
    from casacore.tables import default_ms, makearrcoldesc, makescacoldesc, maketabdesc, table

    vis = root / "fixture.ms"
    flags = np.array(
        [
            [[True, False], [False, False], [False, True]],
            [[False, False], [False, False], [False, False]],
            [[True, True], [True, True], [True, True]],
        ],
        dtype=bool,
    )
    rowflags = np.array([False, True, False])  # deliberately inconsistent patterns
    with default_ms(str(vis)) as ms:
        ms.addrows(3)
        ms.putcol("FLAG", np.zeros_like(flags))
        ms.putcol("FLAG_ROW", ~rowflags)
        ms.putcol("SCAN_NUMBER", np.array([9, 10, 11], dtype="int32"))
    history = Path(str(vis) + ".flagversions")
    history.mkdir()
    version = history / "flags.legacy"
    with table(
        str(version),
        maketabdesc([makearrcoldesc("FLAG", False, ndim=2), makescacoldesc("FLAG_ROW", False)]),
        nrow=3,
        readonly=False,
        ack=False,
    ) as saved:
        saved.putcol("FLAG", flags)
        saved.putcol("FLAG_ROW", rowflags)
    return vis, history, version, flags, rowflags


def test_readonly_fixed_restore_copies_columns_independently_and_verifies_digest(tmp_path):
    from casacore.tables import table

    ctx = _Context()
    vis, history, version, flags, rowflags = _fixture(tmp_path)
    digest = _path_flag_digest(ctx, version)
    before = {
        str(p.relative_to(history)): p.read_bytes()
        for p in history.rglob("*")
        if p.is_file() and p.name != "table.lock"
    }
    result = flagversion_restore_replace(ctx, vis, history, "legacy", digest)
    assert result.vis == vis and result.flag_digest == digest
    with table(str(vis), ack=False) as ms:
        assert np.array_equal(ms.getcol("FLAG"), flags)
        assert np.array_equal(ms.getcol("FLAG_ROW"), rowflags)
        assert ms.getcol("SCAN_NUMBER").tolist() == [9, 10, 11]
    assert ctx.state == {"writes": 2, "write_opens": 1}
    assert before == {
        str(p.relative_to(history)): p.read_bytes()
        for p in history.rglob("*")
        if p.is_file() and p.name != "table.lock"
    }


@pytest.mark.parametrize("malformed", ["columns", "rows", "shape", "variable", "dtype", "digest"])
def test_invalid_history_refuses_before_any_write_open(tmp_path, malformed):
    from casacore.tables import makescacoldesc, maketabdesc, table

    ctx = _Context()
    vis, history, version, _, _ = _fixture(tmp_path)
    expected = _path_flag_digest(ctx, version)
    with table(str(version), readonly=False, ack=False) as saved:
        if malformed == "columns":
            saved.addcols(maketabdesc(makescacoldesc("EXTRA", 0)))
        elif malformed == "rows":
            saved.removerows([2])
        elif malformed == "shape":
            saved.putcell("FLAG", 2, np.zeros((2, 2), dtype=bool))
        elif malformed == "variable":
            saved.putcell("FLAG", 1, np.zeros((2, 3), dtype=bool))
        elif malformed == "dtype":
            saved.removecols("FLAG_ROW")
            saved.addcols(maketabdesc(makescacoldesc("FLAG_ROW", 0)))
        elif malformed == "digest":
            saved.putcell("FLAG_ROW", 0, True)
    before = _path_flag_digest(ctx, vis)
    with pytest.raises(ValueError):
        flagversion_restore_replace(ctx, vis, history, "legacy", expected)
    assert ctx.state == {"writes": 0, "write_opens": 0}
    assert _path_flag_digest(ctx, vis) == before


def test_saved_digest_is_required_and_merge_is_replace_only(tmp_path):
    ctx = _Context()
    vis, history, version, _, _ = _fixture(tmp_path)
    digest = _path_flag_digest(ctx, version)
    for expected, merge in [("", "replace"), (digest, "or")]:
        with pytest.raises(ValueError, match="requires replace"):
            flagversion_restore_replace(ctx, vis, history, "legacy", expected, merge)
    assert ctx.state["writes"] == 0
