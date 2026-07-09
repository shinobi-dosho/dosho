"""`@shinobi.pystep` wrappers for CASA tasks (the `casatasks` Python
package, run in-container via `ctx.import_func`).

CASA tasks are Python-package function calls, not standalone binaries --
cult-cargo's own `casa/*.yml` cabs declare `flavour: python`/`python-code`
for exactly this reason, and shinobi's `build_argv` refuses to execute any
cab whose `flavour != "binary"` (a deliberate security boundary: never
treat cab-supplied command content as code to run). A `@shinobi.pystep` is
architecturally different and safe here: `ctx.import_func("<task>",
"casatasks")` runs *inside the running container*, at step-execution
time, calling a real Python function the pystep author wrote directly
into trusted source -- not shinobi interpreting untrusted cab data. See
`shinobi.steps.pyfunc`'s own docstring for the full mechanism.

Each wrapper here is a thin, generic pass-through to one real CASA task
with its own real keyword names -- no pipeline-specific orchestration
logic (flag-version bookkeeping, per-worker config translation, etc.)
belongs here; that stays in whatever pipeline calls these.
"""

from __future__ import annotations

from pathlib import Path

import shinobi
from pydantic import BaseModel

from dosho import images


def _normalize_caltables(
    gaintable: list[Path] | None,
    gainfield: list[str] | None,
    interp: list[str] | None,
) -> tuple[list[str], list[str], list[str]]:
    """Coerce the optional, previously-solved-table triple shared by
    `gaincal`/`polcal`/`bandpass` into the plain-string lists CASA tasks
    expect, defaulting `None` to an empty list.
    """
    return [str(g) for g in (gaintable or [])], gainfield or [], interp or []


class ListobsOutputs(BaseModel):
    listfile: Path


@shinobi.pystep(image=images.CASA6)
def listobs(ctx, vis: Path, listfile: Path) -> ListobsOutputs:
    listobs_fn = ctx.import_func("listobs", "casatasks")
    listobs_fn(vis=str(vis), listfile=str(listfile), overwrite=True)
    return ListobsOutputs(listfile=listfile)


class MstransformOutputs(BaseModel):
    outputvis: Path


@shinobi.pystep(image=images.CASA6)
def mstransform(
    ctx,
    vis: Path,
    outputvis: Path,
    field: str,
    datacolumn: str = "corrected",
    timeaverage: bool = False,
    timebin: str = "0s",
    chanaverage: bool = False,
    chanbin: int = 1,
    spw: str = "",
    antenna: str = "",
    correlation: str = "",
    scan: str = "",
    usewtspectrum: bool = True,
    nthreads: int = 1,
    regridms: bool = False,
    mode: str = "channel",
    nchan: int = -1,
    start: str = "0",
    width: str = "1",
    interpolation: str = "linear",
    restfreq: str = "",
    outframe: str = "",
    veltype: str = "radio",
    douvcontsub: bool = False,
    fitspw: str = "",
    fitorder: int = 0,
) -> MstransformOutputs:
    """`regridms`/`mode`/`nchan`/`start`/`width`/`interpolation`/
    `restfreq`/`outframe`/`veltype` are Doppler regridding;
    `douvcontsub`/`fitspw`/`fitorder` are uv-plane continuum subtraction --
    both left at the real task's own defaults unless a caller passes them.
    """
    mstransform_fn = ctx.import_func("mstransform", "casatasks")
    mstransform_fn(
        vis=str(vis),
        outputvis=str(outputvis),
        field=field,
        datacolumn=datacolumn,
        timeaverage=timeaverage,
        timebin=timebin,
        chanaverage=chanaverage,
        chanbin=chanbin,
        spw=spw,
        antenna=antenna,
        correlation=correlation,
        scan=scan,
        usewtspectrum=usewtspectrum,
        nthreads=nthreads,
        regridms=regridms,
        mode=mode,
        nchan=nchan,
        start=start,
        width=width,
        interpolation=interpolation,
        restfreq=restfreq,
        outframe=outframe,
        veltype=veltype,
        douvcontsub=douvcontsub,
        fitspw=fitspw,
        fitorder=fitorder,
        keepflags=True,
    )
    return MstransformOutputs(outputvis=outputvis)


class FixvisOutputs(BaseModel):
    outputvis: Path


@shinobi.pystep(image=images.CASA6)
def fixvis(
    ctx,
    vis: Path,
    outputvis: Path,
    phasecenter: str = "",
    field: str = "",
    reuse: bool = True,
) -> FixvisOutputs:
    """`phasecenter=""` (the real CASA default) fixes UVW coordinates
    without changing the phase centre.
    """
    fixvis_fn = ctx.import_func("fixvis", "casatasks")
    fixvis_fn(vis=str(vis), outputvis=str(outputvis), phasecenter=phasecenter, field=field, reuse=reuse)
    return FixvisOutputs(outputvis=outputvis)


class ClearcalOutputs(BaseModel):
    vis: Path


@shinobi.pystep(image=images.CASA6)
def clearcal(ctx, vis: Path, field: str = "", addmodel: bool = False) -> ClearcalOutputs:
    """Resets MODEL_DATA (and optionally adds scratch columns if they
    don't exist yet, `addmodel`). Operates in place -- `vis` is echoed
    back as the output so callers can chain a real dependency edge onto
    the next in-place-modifying step.
    """
    clearcal_fn = ctx.import_func("clearcal", "casatasks")
    clearcal_fn(vis=str(vis), field=field, addmodel=addmodel)
    return ClearcalOutputs(vis=vis)


class InitweightsOutputs(BaseModel):
    vis: Path


@shinobi.pystep(image=images.CASA6)
def initweights(ctx, vis: Path, wtmode: str = "ones", dowtsp: bool = True) -> InitweightsOutputs:
    """Sets uniform (all-ones) spectral weights."""
    initweights_fn = ctx.import_func("initweights", "casatasks")
    initweights_fn(vis=str(vis), wtmode=wtmode, dowtsp=dowtsp)
    return InitweightsOutputs(vis=vis)


class FlagdataOutputs(BaseModel):
    vis: Path
    summary: dict | None = None


@shinobi.pystep(image=images.CASA6)
def flagdata(
    ctx,
    vis: Path,
    mode: str,
    field: str = "",
    spw: str = "",
    antenna: str = "",
    scan: str = "",
    timerange: str = "",
    correlation: str = "",
    autocorr: bool = False,
    quackinterval: float = 0.0,
    quackmode: str = "beg",
    lowerlimit: float = 0.0,
    upperlimit: float = 90.0,
    tolerance: float = 0.0,
    ntime: str = "0s",
    combinescans: bool = False,
    datacolumn: str = "DATA",
    usewindowstats: str = "none",
    flagdimension: str = "freqtime",
    timecutoff: float = 4.0,
    freqcutoff: float = 3.0,
    clipminmax: list[float] | None = None,
    flagbackup: bool = False,
) -> FlagdataOutputs:
    """One generic wrapper covers every `mode` (`unflag`/`clip`/
    `quack`/`elevation`/`shadow`/`spw`/`time`/`scan`/`antennas`/`summary`/
    `tfcrop`/...) -- `mode="summary"` returns the flag-count breakdown via
    `FlagdataOutputs.summary`, matching the real task's own return value.
    """
    flagdata_fn = ctx.import_func("flagdata", "casatasks")
    result = flagdata_fn(
        vis=str(vis),
        mode=mode,
        field=field,
        spw=spw,
        antenna=antenna,
        scan=scan,
        timerange=timerange,
        correlation=correlation,
        autocorr=autocorr,
        quackinterval=quackinterval,
        quackmode=quackmode,
        lowerlimit=lowerlimit,
        upperlimit=upperlimit,
        tolerance=tolerance,
        ntime=ntime,
        combinescans=combinescans,
        datacolumn=datacolumn,
        usewindowstats=usewindowstats,
        flagdimension=flagdimension,
        timecutoff=timecutoff,
        freqcutoff=freqcutoff,
        clipminmax=clipminmax or [0.0, 0.0],
        flagbackup=flagbackup,
    )
    return FlagdataOutputs(vis=vis, summary=result if mode == "summary" else None)


class SetjyOutputs(BaseModel):
    vis: Path


@shinobi.pystep(image=images.CASA6)
def setjy(
    ctx,
    vis: Path,
    field: str = "",
    standard: str = "Perley-Butler 2010",
    fluxdensity: list[float] | None = None,
    model: str | None = None,
    spix: list[float] | None = None,
    reffreq: str = "",
    polindex: list[float] | None = None,
    polangle: list[float] | None = None,
    rotmeas: float = 0.0,
    scalebychan: bool = True,
    usescratch: bool = True,
) -> SetjyOutputs:
    """`fluxdensity=[-1.0]` (the real CASA default) uses the standard's
    own flux model; `spix`/`reffreq`/`polindex`/`polangle`/`rotmeas` are
    for a manual polarized-calibrator model, defaulting to the real
    task's own no-op values.
    """
    setjy_fn = ctx.import_func("setjy", "casatasks")
    setjy_fn(
        vis=str(vis),
        field=field,
        standard=standard,
        fluxdensity=fluxdensity or [-1.0],
        spix=spix or [0.0],
        reffreq=reffreq,
        polindex=polindex or [],
        polangle=polangle or [],
        rotmeas=rotmeas,
        model=model or "",
        scalebychan=scalebychan,
        usescratch=usescratch,
    )
    return SetjyOutputs(vis=vis)


class GaincalOutputs(BaseModel):
    caltable: Path


@shinobi.pystep(image=images.CASA6)
def gaincal(
    ctx,
    vis: Path,
    caltable: Path,
    gaintype: str,
    calmode: str = "ap",
    solint: str = "inf",
    combine: str = "",
    field: str = "",
    spw: str = "",
    uvrange: str = "",
    refant: str = "",
    minsnr: float = 3.0,
    solnorm: bool = False,
    gaintable: list[Path] | None = None,
    gainfield: list[str] | None = None,
    interp: list[str] | None = None,
    parang: bool = False,
) -> GaincalOutputs:
    """`gaintype` disambiguates the real task's own solve mode (`"K"`
    delay, `"G"`/`"F"` gain, `"KCROSS"` crosshand delay, ...) --
    `gaintable`/`gainfield`/`interp` are previously-solved tables applied
    on the fly while solving this one.
    """
    gaincal_fn = ctx.import_func("gaincal", "casatasks")
    gaintable, gainfield, interp = _normalize_caltables(gaintable, gainfield, interp)
    gaincal_fn(
        vis=str(vis),
        caltable=str(caltable),
        gaintype=gaintype,
        calmode=calmode,
        solint=solint,
        combine=combine,
        field=field,
        spw=spw,
        uvrange=uvrange,
        refant=refant,
        minsnr=minsnr,
        solnorm=solnorm,
        gaintable=gaintable,
        gainfield=gainfield,
        interp=interp,
        parang=parang,
    )
    return GaincalOutputs(caltable=caltable)


class PolcalOutputs(BaseModel):
    caltable: Path


@shinobi.pystep(image=images.CASA6)
def polcal(
    ctx,
    vis: Path,
    caltable: Path,
    poltype: str,
    field: str = "",
    spw: str = "",
    uvrange: str = "",
    solint: str = "inf",
    combine: str = "",
    refant: str = "",
    gaintable: list[Path] | None = None,
    gainfield: list[str] | None = None,
    interp: list[str] | None = None,
) -> PolcalOutputs:
    """A genuinely different CASA task from `gaincal` (disambiguated by
    `poltype`, e.g. `"Xf"` crosshand phase, `"Df"` leakage -- not a
    variation on the `gaincal` wrapper above).
    """
    polcal_fn = ctx.import_func("polcal", "casatasks")
    gaintable, gainfield, interp = _normalize_caltables(gaintable, gainfield, interp)
    polcal_fn(
        vis=str(vis),
        caltable=str(caltable),
        poltype=poltype,
        field=field,
        spw=spw,
        uvrange=uvrange,
        solint=solint,
        combine=combine,
        refant=refant,
        gaintable=gaintable,
        gainfield=gainfield,
        interp=interp,
    )
    return PolcalOutputs(caltable=caltable)


class BandpassOutputs(BaseModel):
    caltable: Path


@shinobi.pystep(image=images.CASA6)
def bandpass(
    ctx,
    vis: Path,
    caltable: Path,
    solint: str = "inf",
    combine: str = "scan",
    field: str = "",
    spw: str = "",
    refant: str = "",
    minsnr: float = 3.0,
    solnorm: bool = False,
    fillgaps: int = 0,
    gaintable: list[Path] | None = None,
    gainfield: list[str] | None = None,
    interp: list[str] | None = None,
    parang: bool = False,
) -> BandpassOutputs:
    bandpass_fn = ctx.import_func("bandpass", "casatasks")
    gaintable, gainfield, interp = _normalize_caltables(gaintable, gainfield, interp)
    bandpass_fn(
        vis=str(vis),
        caltable=str(caltable),
        solint=solint,
        combine=combine,
        field=field,
        spw=spw,
        refant=refant,
        minsnr=minsnr,
        solnorm=solnorm,
        fillgaps=fillgaps,
        gaintable=gaintable,
        gainfield=gainfield,
        interp=interp,
        parang=parang,
    )
    return BandpassOutputs(caltable=caltable)


class ApplycalOutputs(BaseModel):
    vis: Path


@shinobi.pystep(image=images.CASA6)
def applycal(
    ctx,
    vis: Path,
    gaintable: list[Path],
    field: str = "",
    gainfield: list[str] | None = None,
    interp: list[str] | None = None,
    calwt: list[bool] | None = None,
    parang: bool = False,
    applymode: str = "calflag",
    flagbackup: bool = True,
) -> ApplycalOutputs:
    """Applies an accumulated list of calibration tables to `vis`."""
    applycal_fn = ctx.import_func("applycal", "casatasks")
    tables = [str(g) for g in gaintable]
    applycal_fn(
        vis=str(vis),
        field=field,
        gaintable=tables,
        gainfield=gainfield or [""] * len(tables),
        interp=interp or ["linear"] * len(tables),
        calwt=calwt or [False] * len(tables),
        parang=parang,
        applymode=applymode,
        flagbackup=flagbackup,
    )
    return ApplycalOutputs(vis=vis)


class FluxscaleOutputs(BaseModel):
    fluxtable: Path


@shinobi.pystep(image=images.CASA6)
def fluxscale(ctx, vis: Path, caltable: Path, fluxtable: Path, reference: str, transfer: str = "") -> FluxscaleOutputs:
    """Transfers a reference (flux) calibrator's absolute flux scale onto
    a gain table solved against a secondary/gain calibrator.
    """
    fluxscale_fn = ctx.import_func("fluxscale", "casatasks")
    fluxscale_fn(
        vis=str(vis), caltable=str(caltable), fluxtable=str(fluxtable), reference=reference, transfer=transfer
    )
    return FluxscaleOutputs(fluxtable=fluxtable)


class FlagmanagerOutputs(BaseModel):
    vis: Path
    versionlist: list[str] | None = None


@shinobi.pystep(image=images.CASA6)
def flagmanager(
    ctx, vis: Path, mode: str, versionname: str = "", merge: str = "replace"
) -> FlagmanagerOutputs:
    """Real CASA flag-version management (`mode="save"/"restore"/
    "delete"/"list"`). `mode="list"` returns the version list via
    `FlagmanagerOutputs.versionlist`, matching the real task's own return
    value for that mode; other modes echo `vis` only. Flag-version
    bookkeeping conventions (e.g. a "before this worker ran" marker) are
    pipeline-specific orchestration, not part of this generic wrapper.
    """
    flagmanager_fn = ctx.import_func("flagmanager", "casatasks")
    result = flagmanager_fn(vis=str(vis), mode=mode, versionname=versionname, merge=merge)
    return FlagmanagerOutputs(vis=vis, versionlist=result if mode == "list" else None)
