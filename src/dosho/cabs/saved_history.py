"""Read-only verification of an already saved CASA flag history."""

from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field

import dosho
from dosho import images
from dosho.cabs.casa_selfcal import _path_flag_digest


class VerifiedHistory(BaseModel):
    valid: bool
    version_digest: str


@dosho.pystep(
    name="verify-saved-flag-history",
    image=images.CASA_TASKS,
    cache=False,
    dataset_accesses=[{"field": "vis", "mode": "read", "exclusive": True}],
)
def verify_saved_flag_history(
    ctx,
    vis: Path,
    history: Annotated[Path, Field(json_schema_extra={"writable": False})],
    versionname: str,
    expected_digest: str,
) -> VerifiedHistory:
    """Check saved flags against the actual prior SAVE, never against live flags."""
    expected = Path(str(vis) + ".flagversions")
    if history.absolute() != expected.absolute() or history.resolve() != expected.absolute():
        raise ValueError("flag history must be the canonical selected MS sidecar")
    if not versionname or any(c in versionname for c in "/\\\x00"):
        raise ValueError("versionname must be a local nonempty CASA version")
    if len(expected_digest) != 64 or any(c not in "0123456789abcdef" for c in expected_digest):
        raise ValueError("verification requires the actual SAVE version digest")
    version = history / f"flags.{versionname}"
    if (
        not version.is_dir()
        or history.is_symlink()
        or any(p.is_symlink() for p in history.rglob("*"))
        or any(p.is_symlink() for p in expected.parents)
    ):
        raise ValueError("saved history must exist without symlinks")
    # Reject keyword-linked tables, including links escaping the physical tree.
    # CASA's fixed SAVE version contains precisely FLAG/FLAG_ROW, no table links.
    tool = ctx.import_func("table", "casatools")()
    tool.open(str(version), nomodify=True)
    try:
        if set(tool.colnames()) != {"FLAG", "FLAG_ROW"} or tool.getkeywords():
            raise ValueError("unsupported saved flag table columns or linked metadata")
        for column in tool.colnames():
            if tool.getcolkeywords(column):
                raise ValueError("unsupported saved flag column linked metadata")
    finally:
        tool.close()
    observed = _path_flag_digest(ctx, version)
    if observed != expected_digest:
        raise ValueError("saved flag version digest differs from cached SAVE")
    return VerifiedHistory(valid=True, version_digest=observed)
