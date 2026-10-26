import pytest

from dosho.cabs.casa_selfcal import _path_flag_digest
from dosho.cabs.saved_history import verify_saved_flag_history
from tests.test_flagversion_restore import _Context, _fixture, _Tool


def test_saved_history_is_readonly_and_ignores_later_live_flags(tmp_path, monkeypatch):
    monkeypatch.setattr(
        _Tool, "getcolkeywords", lambda self, name: self.table.getcolkeywords(name), raising=False
    )
    vis, history, version, _flags, _rows = _fixture(tmp_path)
    ctx = _Context()
    expected = _path_flag_digest(ctx, version)
    from casacore.tables import table

    with table(str(vis), readonly=False, ack=False) as live:
        live.putcol("FLAG", ~live.getcol("FLAG"))
    assert verify_saved_flag_history(ctx, vis, history, "legacy", expected).valid
    assert ctx.state == {"writes": 0, "write_opens": 0}
    with pytest.raises(ValueError, match="digest differs"):
        verify_saved_flag_history(ctx, vis, history, "legacy", "0" * 64)
    (version / "nested-link").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError, match="without symlinks"):
        verify_saved_flag_history(ctx, vis, history, "legacy", expected)


def test_saved_history_rejects_keyword_link_closure(tmp_path, monkeypatch):
    monkeypatch.setattr(
        _Tool, "getcolkeywords", lambda self, name: self.table.getcolkeywords(name), raising=False
    )
    vis, history, version, _flags, _rows = _fixture(tmp_path)
    ctx = _Context()
    expected = _path_flag_digest(ctx, version)
    from casacore.tables import table

    with table(str(version), readonly=False, ack=False) as saved:
        saved.putkeyword("NESTED", "Table: /outside")
    with pytest.raises(ValueError, match="linked metadata"):
        verify_saved_flag_history(ctx, vis, history, "legacy", expected)
