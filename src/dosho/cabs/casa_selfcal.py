"""Neutral fixed CASA operations for strictly tracked self-calibration workflows.

Flag SAVE requires MS WRITE capability because CASA opens it read/write,
while its exact scientific flags must remain unchanged. It owns fresh history. Scientific MS rollback does not cover a partial
sidecar update. Manual flagging disables automatic sidecar backups only;
scientific flag selection and application are unchanged.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, Field

import dosho
from dosho import images


def _flag_digest(tool):
    """Versioned byte identity in native casatools getcol orientation/chunks."""
    import hashlib

    digest = hashlib.sha256()
    for start in range(0, tool.nrows(), 4096):
        count = min(4096, tool.nrows() - start)
        for column in ("FLAG", "FLAG_ROW"):
            values = tool.getcol(column, startrow=start, nrow=count)
            digest.update(column.encode())
            digest.update(str(values.shape).encode())
            digest.update(values.tobytes())
    return digest.hexdigest()


def _path_flag_digest(ctx, path):
    tool = ctx.import_func("table", "casatools")()
    tool.open(str(path), nomodify=True)
    try:
        return _flag_digest(tool)
    finally:
        tool.close()


class SavedFlags(BaseModel):
    vis: Path
    flagversions: Path
    flag_digest: str
    version_digest: str


@dosho.pystep(
    name="flagmanager-save",
    image=images.CASA_TASKS,
    cache=True,
    write_paths=["flagversions"],
    dataset_accesses=[
        {
            "field": "vis",
            "mode": "write",
            "columns": {"read": ["FLAG", "FLAG_ROW"], "write": ["FLAG", "FLAG_ROW"]},
        }
    ],
)
def flagmanager_save(
    ctx, vis: Path, flagversions: Path, versionname: str, merge: Literal["replace"] = "replace"
) -> SavedFlags:
    """Save flags to a preflighted fresh fixed CASA history; no retention/replay claim."""
    history = Path(flagversions)
    if history.resolve() != Path(str(vis) + ".flagversions").resolve():
        raise ValueError("flagversions must belong to the selected MS")
    if not versionname or any(c in versionname for c in "/\\\x00"):
        raise ValueError("versionname must be a local nonempty CASA version")
    if history.exists() or history.is_symlink():
        raise ValueError(
            "fresh SAVE refuses pre-existing history; preflight must precede native cleanup"
        )
    before = _path_flag_digest(ctx, vis)
    ctx.import_func("flagmanager", "casatasks")(
        vis=str(vis), mode="save", versionname=versionname, merge=merge
    )
    if _path_flag_digest(ctx, vis) != before:
        raise ValueError("CASA SAVE changed scientific FLAG/FLAG_ROW values")
    if not (history / f"flags.{versionname}").is_dir():
        raise ValueError("CASA did not produce the requested saved flag version")
    return SavedFlags(
        vis=vis,
        flagversions=history,
        flag_digest=before,
        version_digest=_path_flag_digest(ctx, history / f"flags.{versionname}"),
    )


class ModifiedMS(BaseModel):
    vis: Path


class RestoredFlags(BaseModel):
    vis: Path
    flag_digest: str


@dosho.pystep(
    name="flagversion-restore-replace",
    image=images.CASA_TASKS,
    cache=True,
    dataset_accesses=[
        {"field": "vis", "mode": "write", "columns": {"write": ["FLAG", "FLAG_ROW"]}}
    ],
)
def flagversion_restore_replace(
    ctx,
    vis: Path,
    flagversions: Annotated[Path, Field(json_schema_extra={"writable": False})],
    versionname: str,
    expected_digest: str,
    merge: Literal["replace"] = "replace",
) -> RestoredFlags:
    """Replace flags from one fixed CASA saved table using readonly casatools.

    This utility does not invoke agentflagger/flagmanager RESTORE: that native
    implementation opens its history read/write. Only fixed-shape, fully
    populated boolean FLAG/FLAG_ROW saved tables are supported here.
    """
    import numpy as np

    history = Path(flagversions)
    version = history / f"flags.{versionname}"
    if history.resolve() != Path(str(vis) + ".flagversions").resolve():
        raise ValueError("flagversions must belong to the selected MS")
    if (
        not versionname
        or any(c in versionname for c in "/\\\x00")
        or not version.is_dir()
        or history.is_symlink()
        or version.is_symlink()
        or any(p.is_symlink() for p in version.rglob("*"))
    ):
        raise ValueError("requested local nonsymlinked CASA saved flag version is absent")
    if (
        merge != "replace"
        or len(expected_digest) != 64
        or any(c not in "0123456789abcdef" for c in expected_digest)
    ):
        raise ValueError("restore requires replace and the actual SAVE version digest")
    source = ctx.import_func("table", "casatools")()
    target = ctx.import_func("table", "casatools")()
    source.open(str(version), nomodify=True)
    target_open = False
    try:
        if set(source.colnames()) != {"FLAG", "FLAG_ROW"} or source.getkeywords():
            raise ValueError("unsupported saved flag table columns or linked metadata")
        target.open(str(vis), nomodify=True)
        target_open = True
        if source.nrows() != target.nrows() or source.nrows() == 0:
            raise ValueError("saved flag table row count must match the nonempty target MS")
        for column in ("FLAG", "FLAG_ROW"):
            if source.getcoldesc(column).get("valueType") not in {
                "bool",
                "boolean",
            } or target.getcoldesc(column).get("valueType") not in {"bool", "boolean"}:
                raise ValueError("saved and target flags must be boolean columns")
        flag_shape = None
        # A complete bounded-memory validation pass precedes opening the target
        # for writing. Sparse/variable shapes are deliberately unsupported.
        for start in range(0, source.nrows(), 4096):
            for row in range(start, min(source.nrows(), start + 4096)):
                for column in ("FLAG", "FLAG_ROW"):
                    if not source.iscelldefined(column, row) or not target.iscelldefined(
                        column, row
                    ):
                        raise ValueError("sparse flag tables are unsupported")
                    saved = np.asarray(source.getcell(column, row))
                    current = np.asarray(target.getcell(column, row))
                    if (
                        saved.dtype.kind != "b"
                        or current.dtype.kind != "b"
                        or saved.shape != current.shape
                    ):
                        raise ValueError("saved flag cell type/shape must match target")
                    if column == "FLAG":
                        if saved.ndim != 2 or not all(saved.shape):
                            raise ValueError("FLAG requires a nonempty two-dimensional cell")
                        if flag_shape is None:
                            flag_shape = saved.shape
                        if saved.shape != flag_shape:
                            raise ValueError("variable flag cell shapes are unsupported")
                    elif saved.shape != ():
                        raise ValueError("FLAG_ROW requires scalar boolean cells")
        if _flag_digest(source) != expected_digest:
            raise ValueError("saved flag contents do not match the actual SAVE version digest")
        target.close()
        target_open = False
        target.open(str(vis), nomodify=False)
        target_open = True
        for start in range(0, source.nrows(), 4096):
            count = min(4096, source.nrows() - start)
            for column in ("FLAG", "FLAG_ROW"):
                target.putcol(
                    column,
                    source.getcol(column, startrow=start, nrow=count),
                    startrow=start,
                    nrow=count,
                )
        target.flush()
        target.close()
        target_open = False
    finally:
        if target_open:
            target.close()
        source.close()
    observed = _path_flag_digest(ctx, vis)
    if observed != expected_digest:
        raise ValueError("restored FLAG/FLAG_ROW do not match the saved version digest")
    return RestoredFlags(vis=vis, flag_digest=observed)


@dosho.pystep(
    name="flagdata-manual-msv2",
    image=images.CASA_TASKS,
    dataset_accesses=[
        {"field": "vis", "mode": "write", "columns": {"write": ["FLAG", "FLAG_ROW"]}},
        {"field": "vis", "mode": "write", "table": "HISTORY", "allow_row_count_change": True},
    ],
)
def flagdata_manual_msv2(
    ctx,
    vis: Path,
    mode: Literal["manual"] = "manual",
    autocorr: bool = False,
    spw: str = "",
    flagbackup: Literal[False] = False,
) -> ModifiedMS:
    ctx.import_func("flagdata", "casatasks")(
        vis=str(vis),
        mode=mode,
        autocorr=autocorr,
        spw=spw,
        flagbackup=False,
        savepars=False,
        action="apply",
    )
    return ModifiedMS(vis=vis)
