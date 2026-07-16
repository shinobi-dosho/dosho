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

Every task below is audited field-by-field against CASA's own docs
(casadocs.readthedocs.io/en/stable/api/casatasks.html), not against
cult-cargo -- cult-cargo's `casa/*.yml` cabs are known to be incomplete
for exactly the same reasons dosho exists (see wsclean.py/cubical.py's own
docstrings), so cross-checking against another possibly-gapped source
would just propagate the same gaps. Two consequences of that audit worth
flagging: (1) several parameter *defaults* below now match CASA's real
default rather than a value this file previously hardcoded (e.g.
`applycal`'s `calwt` now defaults to `[True]` per gaintable, not
`[False]`; `initweights`'s `wtmode` now defaults to `'nyq'`, not
`'ones'`) -- a deliberate correctness fix, not preserved for
compatibility; (2) truly internal-only CASA parameters explicitly marked
"Hidden parameter for internal use only" in the docs (`mstransform`'s
`disableparallel`/`ddistart`/`reindex`/`monolithic_processing`) are not
exposed here, since they're not meaningful for a pipeline to control.

"variant"-typed CASA parameters (can be several different Python types
depending on context) are typed here as whichever concrete type real
pipeline usage actually needs (usually `str` for a selection string, or a
`list[...]`) rather than a full `Union` -- consistent with how this file
already handled `uvrange`/`solint` before this audit.

Covers every task in CASA's own Flagging/Calibration/Imaging/Manipulation
categories (casadocs' own grouping), excluding Single Dish, Visualization,
and Simulation. A handful of `mode`/`gaintype`-shaped solve-type selectors
(`gaincal.gaintype`, `flagdata.mode`) still default to CASA's own values
after an earlier attempt to make them required-with-no-default was
reverted -- consistency with casadocs won out over guarding against a
silently-wrong solve type; every other task's own mode selectors
(`tclean.specmode`/`gridder`/`deconvolver`/`usemask`, etc.) follow the
same casadocs-first rule and always have.

**Every output model classifies an in-place-mutated input as an output,
not just newly-created files.** A task that writes into its own `vis`
(`clearcal`/`initweights`/`flagdata`/`setjy`/`applycal`/`delmod`/`ft`/
`fixplanets`/`statwt`/`uvsub`/...) echoes `vis` back; a task that mutates
`tablein` unless a distinct output path is given (`rerefant`/`smoothcal`)
resolves to whichever path was actually written; a task with no
resulting artifact at all (`clearstat`, which clears locks globally;
`rmtables`, which deletes its own inputs) gets an empty outputs model
rather than a fabricated field. This is what lets a downstream recipe
step wire a real `OutputRef` dependency on "this MS has actually been
mutated," instead of silently missing it.

Here that's straightforward: every task in this file is a `@shinobi.pystep`,
which builds its own return value directly in Python, so echoing `vis`
back is just returning it. The same rule applies to a `Cab` (a real-binary
wrapper via `define_cab`) too, but the mechanism is different --
`dosho/src/dosho/cabs/tricolour.py` is the reference example: declare the
in-place-mutated field under `outputs=` with the *same name* it already
has as an input (`outputs={"ms": ...}`) and no `ParamMeta.implicit`.
`shinobi.steps.dispatch._fill_outputs` fills a `Cab`'s outputs by
priority -- wrangler value, then *same-named final input value*, then a
reserved field, then `implicit`, then the field's own default -- so the
same-named-input tier does the echoing automatically, no extra
`field_meta` entry needed.

`shinobi.policies.build_argv` only ever consults `field_meta[name]` for
names in `cab.inputs_model.model_fields`, so a field that exists *only* in
`outputs_model` (a distinct name like `flagged_ms`, never declared as an
input) could safely carry its own `implicit` template too -- same
mechanism `wsclean.py`'s `image_mfs`/`cubical.py`'s `ms` output already
use, and `build_argv` would never see it, since it only walks input
fields. The actual hazard is narrower and easy to trip over: `implicit`
set on an entry keyed by a name that's *also* a real input field makes
`build_argv` use that literal value unconditionally for the input too,
discarding whatever the caller passed -- which is exactly what happens if
`ms`'s own `field_meta` entry (the real positional input) picks up an
`implicit`, whether or not a same-named or different-named output field
also references it.

**Output hygiene**: every pystep body starts with `_quiet_casa(ctx)` (see
its docstring), so CASA's `casa-<timestamp>.log` cwd junk is prevented at
the source rather than mopped up after. Every parameter naming a file a
task *writes* has been audited against sandboxed execution
(`shinobi.sandbox`, where only declared outputs survive): the side-output
files are declared optional output fields (`flagdata`/`flagcmd`'s
`outfile`, `flagcmd`'s `plotfile`, `fluxscale`'s `listfile`,
`predictcomp`'s `savefig`), and the imaging product families that can't
be enumerated statically carry a `harvest` keep-glob (`tclean`/
`sdintimaging`, `"{imagename}.*"` -- see each decorator's comment).
Reviewed and left alone: `deconvolve`/`widebandpbcor` *mutate* an
existing `{imagename}.*` family in place, so a sandboxed run with a
relative prefix fails loudly at read time (nothing is silently lost),
and `flagdata`'s `timedev`/`freqdev` are variant-typed (number/array/
"write the deviations here" filename in `action='calculate'`) -- too
ambiguous to declare as outputs. No pystep sets `sandbox=True` on its
own scope: a cab declares what must survive, not execution policy.
"""

from __future__ import annotations

import shutil
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


def _quiet_casa(ctx) -> None:
    """Stop CASA littering the working directory with `casa-<timestamp>.log`
    (stdout/stderr are captured on the `StepResult` anyway, so the file is
    pure junk). Called as the first statement of every pystep body here,
    *before* its `ctx.import_func(..., "casatasks")` -- the log file is
    created as an import side effect, so redirecting after the fact can only
    silence it, not prevent it.

    Two layers, both best-effort:

    * a `casaconfig` site-config file (`nologfile = True`, plus telemetry/
      crashreporter off -- more `~/.casa` droppings) pointed at via
      `$CASASITECONFIG` before the first `casatasks` import, so no log file
      is ever created (CASA >= 6.5; the pinned CASA6 image is 6.7);
    * `casalog.setlogfile(os.devnull)` after import, for any CASA that
      ignored the site config -- the stray file then still appears but stays
      empty.

    Runs inside the container (the runner loads only this source file, with
    the `dosho` package stubbed -- see `shinobi.steps.pyfunc`), so it uses
    nothing but the stdlib and `ctx`: local imports, no dosho helpers.
    `casaplotms.py` carries its own copy for exactly that reason -- a
    cross-module import of this function would silently resolve to the
    in-container stub and do nothing.
    """
    import os
    import tempfile

    if "CASASITECONFIG" not in os.environ:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix="_casasiteconfig.py", delete=False
        ) as config:
            config.write(
                "nologfile = True\n"
                "telemetry_enabled = False\n"
                "crashreporter_enabled = False\n"
            )
        os.environ["CASASITECONFIG"] = config.name
    casalog = ctx.import_func("casalog", "casatasks")
    casalog.setlogfile(os.devnull)


class ListobsOutputs(BaseModel):
    """Outputs of the `listobs` step."""

    listfile: Path


@shinobi.pystep(image=images.CASA6)
def listobs(
    ctx,
    vis: Path,
    listfile: Path,
    selectdata: bool = True,
    spw: str = "",
    field: str = "",
    antenna: str = "",
    uvrange: str = "",
    timerange: str = "",
    correlation: str = "",
    scan: str = "",
    intent: str = "",
    feed: str = "",
    array: str = "",
    observation: str = "",
    verbose: bool = True,
    listunfl: bool = False,
    cachesize: float = 50.0,
    overwrite: bool = False,
) -> ListobsOutputs:
    """Write a CASA `listobs` text summary of a measurement set.

    Args:
        ctx: The pystep execution context.
        vis: Path to the measurement set to summarize.
        listfile: Path to write the summary to.
        selectdata: Whether the selection parameters below apply.
        spw: Spectral window/channel selection.
        field: Field selection.
        antenna: Antenna/baseline selection.
        uvrange: uv-range selection (default units meters).
        timerange: Time-range selection.
        correlation: Correlation selection.
        scan: Scan-number selection.
        intent: Observation-intent selection.
        feed: Multi-feed selection (not yet implemented by CASA itself).
        array: (Sub)array selection.
        observation: Observation-ID selection.
        verbose: More (True) or less (False) detail in the report.
        listunfl: Also list unflagged row counts (can be slow).
        cachesize: Max size in MB of the data-structure cache (experimental).
        overwrite: Overwrite `listfile` if it already exists. CASA's own
            default is `False`; this wrapper matches it rather than the
            `True` this file previously hardcoded -- pass it explicitly if
            you want the old always-overwrite behaviour.

    Returns:
        `ListobsOutputs` with the written `listfile`.
    """
    _quiet_casa(ctx)
    listobs_fn = ctx.import_func("listobs", "casatasks")
    listobs_fn(
        vis=str(vis),
        selectdata=selectdata,
        spw=spw,
        field=field,
        antenna=antenna,
        uvrange=uvrange,
        timerange=timerange,
        correlation=correlation,
        scan=scan,
        intent=intent,
        feed=feed,
        array=array,
        observation=observation,
        verbose=verbose,
        listfile=str(listfile),
        listunfl=listunfl,
        cachesize=cachesize,
        overwrite=overwrite,
    )
    return ListobsOutputs(listfile=listfile)


def _remove_existing_output(outputvis: Path | str) -> None:
    """Delete a pre-existing output MS -- and its `.flagversions` twin,
    which would otherwise pair stale flag versions with the fresh MS --
    so the calling task can rewrite it (see the `overwrite` convenience
    parameter on `mstransform`/`fixvis`)."""
    for stale in (Path(outputvis), Path(f"{outputvis}.flagversions")):
        if stale.exists():
            shutil.rmtree(stale)


class MstransformOutputs(BaseModel):
    """Outputs of the `mstransform` step."""

    outputvis: Path


@shinobi.pystep(image=images.CASA6)
def mstransform(
    ctx,
    vis: Path,
    outputvis: Path,
    field: str = "",
    spw: str = "",
    scan: str = "",
    antenna: str = "",
    correlation: str = "",
    timerange: str = "",
    intent: str = "",
    array: str = "",
    uvrange: str = "",
    observation: str = "",
    feed: str = "",
    datacolumn: str = "corrected",
    realmodelcol: bool = False,
    keepflags: bool = True,
    usewtspectrum: bool = False,
    createmms: bool = False,
    tileshape: list[int] | None = None,
    separationaxis: str = "auto",
    numsubms: str = "auto",
    taql: str = "",
    combinespws: bool = False,
    chanaverage: bool = False,
    chanbin: int = 1,
    hanning: bool = False,
    regridms: bool = False,
    mode: str = "channel",
    nchan: int = -1,
    start: str = "0",
    width: str = "1",
    nspw: int = 1,
    interpolation: str = "linear",
    phasecenter: str = "",
    restfreq: str = "",
    outframe: str = "",
    veltype: str = "radio",
    preaverage: bool = False,
    timeaverage: bool = False,
    timebin: str = "0s",
    timespan: str = "",
    maxuvwdistance: float = 0.0,
    docallib: bool = False,
    callib: str = "",
    douvcontsub: bool = False,
    fitspw: str = "",
    fitorder: int = 0,
    want_cont: bool = False,
    denoising_lib: bool = True,
    nthreads: int = 1,
    niter: int = 1,
    overwrite: bool = False,
) -> MstransformOutputs:
    """Split/combine/regrid an MS and optionally average in channel/time.

    Grouped below by the real task's own conditional sections (each
    sub-group only matters when its own gate parameter is set):
    `createmms` (`separationaxis`/`numsubms`/`taql`), `combinespws`,
    `chanaverage` (`chanbin`), `hanning`, `regridms`
    (`mode`/`nchan`/`start`/`width`/`nspw`/`interpolation`/`phasecenter`/
    `restfreq`/`outframe`/`veltype`/`preaverage`), `timeaverage`
    (`timebin`/`timespan`/`maxuvwdistance`), `docallib` (`callib`),
    `douvcontsub` (`fitspw`/`fitorder`/`want_cont`/`denoising_lib`/
    `nthreads`/`niter` -- note `nthreads`/`niter` are `douvcontsub`
    sub-parameters in real CASA, not general-purpose, though this file
    previously exposed `nthreads` as if it were).

    `realmodelcol` and `keepflags` are the two gaps that mattered most for
    porting oxkat's `PRE_casa_average_to_1k_add_wtspec.py` /
    `1GC_06_casa_split_calibrators.py` / `1GC_09_casa_split_targets.py`:
    both scripts pass `realmodelcol=True` explicitly, and this file didn't
    expose it at all before (only silently hardcoded `keepflags=True`).

    Args:
        ctx: The pystep execution context.
        vis: Input MS or multi-MS.
        outputvis: Output MS or multi-MS path.
        field: Field selection.
        spw: Spectral window/channel selection.
        scan: Scan-number selection.
        antenna: Antenna/baseline selection.
        correlation: Correlation selection (e.g. `"XX,YY"`).
        timerange: Time-range selection.
        intent: Observation-intent selection.
        array: (Sub)array selection.
        uvrange: uv-range selection.
        observation: Observation-ID selection.
        feed: Multi-feed selection (not yet implemented by CASA itself).
        datacolumn: Which data column(s) to process.
        realmodelcol: Materialize a virtual MODEL column as a real one.
        keepflags: Keep fully-flagged rows instead of dropping them.
        usewtspectrum: Force-create WEIGHT_SPECTRUM/SIGMA_SPECTRUM.
        createmms: Produce a multi-MS output.
        tileshape: Disk tile shape, 1 or 3 ints.
        separationaxis: `createmms` parallelization axis.
        numsubms: `createmms` sub-MS count (`"auto"` or an int-as-string).
        taql: Table-query string for nested selections.
        combinespws: Combine input spws into one output spw.
        chanaverage: Average data across channels.
        chanbin: Input-channel bin width for `chanaverage`.
        hanning: Hanning-smooth to remove Gibbs ringing.
        regridms: Transform channel labels/visibilities to a new frame.
        mode: Regridding mode (`channel`/`velocity`/`frequency`/`channel_b`).
        nchan: Output channel count (`-1` = all).
        start: Regridding start (units depend on `mode`).
        width: Regridding channel width (units depend on `mode`).
        nspw: Number of output spws to create.
        interpolation: Spectral interpolation method.
        phasecenter: Phase-center direction for spectral-frame transforms.
        restfreq: Rest frequency for the output.
        outframe: Output reference frame (`""` keeps the input frame).
        veltype: Velocity definition.
        preaverage: Pre-average channels before regridding when ratio > 2.
        timeaverage: Average data across time.
        timebin: Time-averaging bin width.
        timespan: Span the time bin across `scan`, `state`, or both.
        maxuvwdistance: Max start-to-end baseline separation, in metres.
        docallib: Enable on-the-fly calibration (as in `applycal`).
        callib: Path to a calibration-library file (needs `docallib=True`).
        douvcontsub: Enable uv-plane continuum subtraction (deprecated
            upstream in favour of `uvcontsub`, kept here for parity).
        fitspw: spw:channel selection for the continuum fit.
        fitorder: Polynomial order for the continuum fit.
        want_cont: Produce the continuum estimate instead of the
            subtracted data.
        denoising_lib: Use the GSL denoising library instead of casacore.
        nthreads: OMP thread count for `douvcontsub`.
        niter: Re-weighted-linear-fit iteration count for `douvcontsub`.
        overwrite: Delete a pre-existing `outputvis` (and its
            `.flagversions` twin) before running. NOT a real CASA
            parameter -- the real task has no overwrite option and
            unconditionally fails on an existing output; this
            wrapper-level convenience is what lets a pipeline rerun be
            idempotent. Default `False` keeps CASA's own
            refuse-to-clobber behaviour.

    Returns:
        `MstransformOutputs` with the written `outputvis`.
    """
    _quiet_casa(ctx)
    if overwrite:
        _remove_existing_output(outputvis)
    mstransform_fn = ctx.import_func("mstransform", "casatasks")
    mstransform_fn(
        vis=str(vis),
        outputvis=str(outputvis),
        field=field,
        spw=spw,
        scan=scan,
        antenna=antenna,
        correlation=correlation,
        timerange=timerange,
        intent=intent,
        array=array,
        uvrange=uvrange,
        observation=observation,
        feed=feed,
        datacolumn=datacolumn,
        realmodelcol=realmodelcol,
        keepflags=keepflags,
        usewtspectrum=usewtspectrum,
        createmms=createmms,
        tileshape=tileshape or [0],
        separationaxis=separationaxis,
        numsubms=numsubms,
        taql=taql,
        combinespws=combinespws,
        chanaverage=chanaverage,
        chanbin=chanbin,
        hanning=hanning,
        regridms=regridms,
        mode=mode,
        nchan=nchan,
        start=start,
        width=width,
        nspw=nspw,
        interpolation=interpolation,
        phasecenter=phasecenter,
        restfreq=restfreq,
        outframe=outframe,
        veltype=veltype,
        preaverage=preaverage,
        timeaverage=timeaverage,
        timebin=timebin,
        timespan=timespan,
        maxuvwdistance=maxuvwdistance,
        docallib=docallib,
        callib=callib,
        douvcontsub=douvcontsub,
        fitspw=fitspw,
        fitorder=fitorder,
        want_cont=want_cont,
        denoising_lib=denoising_lib,
        nthreads=nthreads,
        niter=niter,
    )
    return MstransformOutputs(outputvis=outputvis)


class FixvisOutputs(BaseModel):
    """Outputs of the `fixvis` step."""

    outputvis: Path


@shinobi.pystep(image=images.CASA6)
def fixvis(
    ctx,
    vis: Path,
    outputvis: Path,
    field: str = "",
    refcode: str = "",
    reuse: bool = True,
    phasecenter: str = "",
    distances: str = "",
    datacolumn: str = "all",
    overwrite: bool = False,
) -> FixvisOutputs:
    """Recompute (u, v, w) and/or change the phase center.

    Args:
        ctx: The pystep execution context.
        vis: Input MS.
        outputvis: Output MS path (defaults to `vis` in real CASA if left
            empty; this wrapper always passes it explicitly).
        field: Field selection.
        refcode: Reference frame to convert UVW into; defaults to the
            FIELD table's own `PHASE_DIR` frame if left empty.
        reuse: Base the UVW calculation on existing values (ignored if
            `phasecenter` is set).
        phasecenter: New phase-center direction, or an RA/DEC offset from
            the current one.
        distances: Experimental per-field distances (as quanta) for
            refocusing.
        datacolumn: Which visibility column(s) a phase-center shift
            modifies.
        overwrite: Delete a pre-existing `outputvis` (and its
            `.flagversions` twin) before running. NOT a real CASA
            parameter -- same wrapper-level rerun-idempotency convenience
            as `mstransform`'s own `overwrite`.

    Returns:
        `FixvisOutputs` with the written `outputvis`.
    """
    _quiet_casa(ctx)
    if overwrite:
        _remove_existing_output(outputvis)
    fixvis_fn = ctx.import_func("fixvis", "casatasks")
    fixvis_fn(
        vis=str(vis),
        outputvis=str(outputvis),
        field=field,
        refcode=refcode,
        reuse=reuse,
        phasecenter=phasecenter,
        distances=distances,
        datacolumn=datacolumn,
    )
    return FixvisOutputs(outputvis=outputvis)


class ClearcalOutputs(BaseModel):
    """Outputs of the `clearcal` step."""

    vis: Path


@shinobi.pystep(image=images.CASA6)
def clearcal(
    ctx, vis: Path, field: str = "", spw: str = "", intent: str = "", addmodel: bool = False
) -> ClearcalOutputs:
    """Resets MODEL_DATA (and optionally adds scratch columns if they
    don't exist yet, `addmodel`). Operates in place -- `vis` is echoed
    back as the output so callers can chain a real dependency edge onto
    the next in-place-modifying step.

    Args:
        ctx: The pystep execution context.
        vis: MS to reset calibration on.
        field: Field selection.
        spw: Spectral window selection.
        intent: Observation-intent selection.
        addmodel: Also add a MODEL_DATA column alongside CORRECTED_DATA.

    Returns:
        `ClearcalOutputs` echoing `vis`.
    """
    _quiet_casa(ctx)
    clearcal_fn = ctx.import_func("clearcal", "casatasks")
    clearcal_fn(vis=str(vis), field=field, spw=spw, intent=intent, addmodel=addmodel)
    return ClearcalOutputs(vis=vis)


class InitweightsOutputs(BaseModel):
    """Outputs of the `initweights` step."""

    vis: Path


@shinobi.pystep(image=images.CASA6)
def initweights(
    ctx,
    vis: Path,
    wtmode: str = "nyq",
    tsystable: Path | None = None,
    gainfield: str = "",
    interp: str = "linear,linear",
    spwmap: list[int] | None = None,
    dowtsp: bool = False,
) -> InitweightsOutputs:
    """Initialize weight-related columns in the MS.

    Args:
        ctx: The pystep execution context.
        vis: MS to initialize weights on.
        wtmode: Initialization mode (`nyq`/`sigma`/`weight`/`ones`/`tsys`/
            `tinttsys`/`delwtsp`/`delsigsp`). CASA's own default is
            `'nyq'`; this wrapper previously hardcoded `'ones'`.
        tsystable: Tsys caltable to apply on the fly (`tsys`/`tinttsys` modes).
        gainfield: Calibrator subset from `tsystable` (`tsys`/`tinttsys` modes).
        interp: Time[,freq] interpolation for `tsystable` (`tsys`/`tinttsys` modes).
        spwmap: Spw combinations to form for `tsystable` (`tsys`/`tinttsys` modes).
        dowtsp: Also initialize the WEIGHT_SPECTRUM column.

    Returns:
        `InitweightsOutputs` echoing `vis`.
    """
    _quiet_casa(ctx)
    initweights_fn = ctx.import_func("initweights", "casatasks")
    initweights_fn(
        vis=str(vis),
        wtmode=wtmode,
        tsystable=str(tsystable) if tsystable else "",
        gainfield=gainfield,
        interp=interp,
        spwmap=spwmap or [],
        dowtsp=dowtsp,
    )
    return InitweightsOutputs(vis=vis)


class FlagdataOutputs(BaseModel):
    """Outputs of the `flagdata` step.

    Attributes:
        vis: The (in-place-flagged) measurement set.
        summary: Flag-count breakdown, populated only when `mode="summary"`.
        outfile: The saved flag-commands file, populated only when
            `savepars=True` wrote to a real file (an empty `outfile`
            saves to the MS's own FLAG_CMD table instead).
    """

    vis: Path
    summary: dict | None = None
    outfile: Path | None = None


@shinobi.pystep(image=images.CASA6)
def flagdata(
    ctx,
    vis: Path,
    mode: str = "manual",
    action: str = "apply",
    savepars: bool = False,
    field: str = "",
    spw: str = "",
    antenna: str = "",
    timerange: str = "",
    correlation: str = "",
    scan: str = "",
    intent: str = "",
    array: str = "",
    uvrange: str = "",
    observation: str = "",
    feed: str = "",
    # mode='manual'/'manualflag'
    autocorr: bool = False,
    # mode='list'
    inpfile: list[str] | None = None,
    reason: str = "any",
    tbuff: float = 0.0,
    # mode='clip'
    clipminmax: list[float] | None = None,
    clipoutside: bool = True,
    clipzeros: bool = False,
    # shared by clip/tfcrop/rflag/antint pre-averaging + the column they read
    datacolumn: str = "DATA",
    channelavg: bool = False,
    chanbin: int = 1,
    timeavg: bool = False,
    timebin: str = "0s",
    # mode='quack'
    quackinterval: float = 1.0,
    quackmode: str = "beg",
    quackincrement: bool = False,
    # mode='shadow'
    tolerance: float = 0.0,
    addantenna: str = "",
    # mode='elevation'
    lowerlimit: float = 0.0,
    upperlimit: float = 90.0,
    # shared chunking for mode='tfcrop'/'rflag'/'extend'
    ntime: str = "scan",
    combinescans: bool = False,
    # mode='tfcrop'
    timecutoff: float = 4.0,
    freqcutoff: float = 3.0,
    timefit: str = "line",
    freqfit: str = "poly",
    maxnpieces: int = 7,
    flagdimension: str = "freqtime",
    usewindowstats: str = "none",
    halfwin: int = 1,
    extendflags: bool = True,
    # mode='rflag'
    winsize: int = 3,
    timedev: str = "",
    freqdev: str = "",
    timedevscale: float = 5.0,
    freqdevscale: float = 5.0,
    spectralmax: float = 1e6,
    spectralmin: float = 0.0,
    # mode='antint'
    antint_ref_antenna: str = "",
    minchanfrac: float = 0.6,
    verbose: bool = False,
    # mode='extend'
    extendpols: bool = True,
    growtime: float = 50.0,
    growfreq: float = 50.0,
    growaround: bool = False,
    flagneartime: bool = False,
    flagnearfreq: bool = False,
    # mode='summary'
    minrel: float = 0.0,
    maxrel: float = 1.0,
    minabs: int = 0,
    maxabs: int = -1,
    spwchan: bool = False,
    spwcorr: bool = False,
    basecnt: bool = False,
    fieldcnt: bool = False,
    name: str = "Summary",
    # action='apply'/'calculate'
    display: str = "",
    # action='apply'
    flagbackup: bool = True,
    # savepars=True
    cmdreason: str = "",
    outfile: str = "",
    overwrite: bool = True,
    writeflags: bool = True,
) -> FlagdataOutputs:
    """One generic wrapper covers every `mode` (`manual`/`list`/`clip`/
    `quack`/`shadow`/`elevation`/`tfcrop`/`rflag`/`antint`/`extend`/
    `unflag`/`summary`) -- `mode="summary"` returns the flag-count
    breakdown via `FlagdataOutputs.summary`, matching the real task's own
    return value. `rflag`'s own tunables (`winsize`/`timedev`/`freqdev`/
    `timedevscale`/`freqdevscale`/`spectralmax`/`spectralmin`) and the
    whole `antint`/`extend` modes were missing entirely before this audit,
    even though oxkat's own `1GC_casa_refcal.py` drives `rflag` throughout
    its residual-reflagging steps.

    `mode` defaults to `'manual'`, matching CASA's own default.

    Args:
        ctx: The pystep execution context.
        vis: MS or caltable to flag.
        mode: Flagging mode.
        action: `none`/`apply`/`calculate`.
        savepars: Save the current parameters to FLAG_CMD or a file.
        field: Field selection (all modes but `list`).
        spw: Spectral window/channel selection.
        antenna: Antenna/baseline selection.
        timerange: Time-range selection.
        correlation: Correlation selection.
        scan: Scan-number selection.
        intent: Observation-intent selection.
        array: (Sub)array selection.
        uvrange: uv-range selection.
        observation: Observation-ID selection.
        feed: Multi-feed selection (not yet implemented by CASA itself).
        autocorr: Flag only auto-correlations (`mode='manual'`).
        inpfile: Flag-command file(s)/list (`mode='list'`).
        reason: REASON-type filter for flag commands (`mode='list'`).
        tbuff: Time-range padding in seconds (`mode='list'`).
        clipminmax: [min, max] Jy range that will NOT be clipped (`mode='clip'`).
        clipoutside: Clip outside the range instead of within it (`mode='clip'`).
        clipzeros: Also clip exactly-zero data (`mode='clip'`).
        datacolumn: Data column to operate on (`clip`/`tfcrop`/`rflag`/`antint`).
        channelavg: Pre-average across channels before analysis.
        chanbin: Channel bin width for `channelavg`.
        timeavg: Pre-average across time before analysis.
        timebin: Time bin width for `timeavg`.
        quackinterval: Seconds to quack from scan start/end (`mode='quack'`).
        quackmode: `beg`/`endb`/`tail`/`end` (`mode='quack'`).
        quackincrement: Increment quacking to account for already-flagged data.
        tolerance: Allowed shadow amount in metres (`mode='shadow'`).
        addantenna: Antenna-position file/dict for shadow calc (`mode='shadow'`).
        lowerlimit: Lower elevation limit in degrees (`mode='elevation'`).
        upperlimit: Upper elevation limit in degrees (`mode='elevation'`).
        ntime: Time-range per chunk (`tfcrop`/`rflag`/`extend`).
        combinescans: Accumulate data across scans (`tfcrop`/`rflag`/`extend`).
        timecutoff: Time-direction deviation threshold (`mode='tfcrop'`).
        freqcutoff: Frequency-direction deviation threshold (`mode='tfcrop'`).
        timefit: `poly`/`line` fit in time (`mode='tfcrop'`).
        freqfit: `poly`/`line` fit in frequency (`mode='tfcrop'`).
        maxnpieces: Polynomial-fit piece count, 1-9 (`mode='tfcrop'`).
        flagdimension: `freq`/`time`/`freqtime`/`timefreq` (`mode='tfcrop'`).
        usewindowstats: `none`/`sum`/`std`/`both` (`mode='tfcrop'`).
        halfwin: Sliding-window half-width, 1/2/3 (`mode='tfcrop'`).
        extendflags: Extend flags along time/freq/correlation (`tfcrop`/`rflag`).
        winsize: Sliding time-window size in timesteps (`mode='rflag'`).
        timedev: Time-series noise estimate (`mode='rflag'`).
        freqdev: Spectral noise estimate (`mode='rflag'`).
        timedevscale: Threshold scaling for `timedev` (`mode='rflag'`).
        freqdevscale: Threshold scaling for `freqdev` (`mode='rflag'`).
        spectralmax: Flag the whole spectrum above this `freqdev` (`mode='rflag'`).
        spectralmin: Flag the whole spectrum below this `freqdev` (`mode='rflag'`).
        antint_ref_antenna: Reference antenna to check (`mode='antint'`).
        minchanfrac: Minimum flagged-channel fraction, 0-1 (`mode='antint'`).
        verbose: Print flagged-integration timestamps (`mode='antint'`).
        extendpols: Extend flags to all selected correlations (`mode='extend'`).
        growtime: Flag a timerange if this % already flagged (`mode='extend'`).
        growfreq: Flag channels if this % already flagged (`mode='extend'`).
        growaround: Flag based on surrounding flags (`mode='extend'`).
        flagneartime: Flag one timestep before/after a flagged one (`mode='extend'`).
        flagnearfreq: Flag one channel before/after a flagged one (`mode='extend'`).
        minrel: Minimum relative flag fraction to report (`mode='summary'`).
        maxrel: Maximum relative flag fraction to report (`mode='summary'`).
        minabs: Minimum absolute flag count to report (`mode='summary'`).
        maxabs: Maximum absolute flag count to report, `-1` = infinity (`mode='summary'`).
        spwchan: Per-channel-per-spw breakdown (`mode='summary'`).
        spwcorr: Per-correlation-per-spw breakdown (`mode='summary'`).
        basecnt: Per-baseline breakdown (`mode='summary'`).
        fieldcnt: Per-field breakdown (`mode='summary'`).
        name: Summary report name (`mode='summary'`).
        display: `none`/`data`/`report`/`both` (`action='apply'/'calculate'`).
        flagbackup: Back up flags before running (`action='apply'`).
        cmdreason: Reason to save (`savepars=True`).
        outfile: Output file for saved parameters (`savepars=True`).
        overwrite: Overwrite an existing `outfile` (`savepars=True`).
        writeflags: Write flags to the MS (`savepars=True`).

    Returns:
        `FlagdataOutputs` echoing `vis`, plus `summary` when `mode="summary"`
        and `outfile` when `savepars=True` wrote to a real file.
    """
    _quiet_casa(ctx)
    flagdata_fn = ctx.import_func("flagdata", "casatasks")
    result = flagdata_fn(
        vis=str(vis),
        mode=mode,
        action=action,
        savepars=savepars,
        field=field,
        spw=spw,
        antenna=antenna,
        timerange=timerange,
        correlation=correlation,
        scan=scan,
        intent=intent,
        array=array,
        uvrange=uvrange,
        observation=observation,
        feed=feed,
        autocorr=autocorr,
        inpfile=inpfile or "",
        reason=reason,
        tbuff=tbuff,
        clipminmax=clipminmax or [],
        clipoutside=clipoutside,
        clipzeros=clipzeros,
        datacolumn=datacolumn,
        channelavg=channelavg,
        chanbin=chanbin,
        timeavg=timeavg,
        timebin=timebin,
        quackinterval=quackinterval,
        quackmode=quackmode,
        quackincrement=quackincrement,
        tolerance=tolerance,
        addantenna=addantenna,
        lowerlimit=lowerlimit,
        upperlimit=upperlimit,
        ntime=ntime,
        combinescans=combinescans,
        timecutoff=timecutoff,
        freqcutoff=freqcutoff,
        timefit=timefit,
        freqfit=freqfit,
        maxnpieces=maxnpieces,
        flagdimension=flagdimension,
        usewindowstats=usewindowstats,
        halfwin=halfwin,
        extendflags=extendflags,
        winsize=winsize,
        timedev=timedev,
        freqdev=freqdev,
        timedevscale=timedevscale,
        freqdevscale=freqdevscale,
        spectralmax=spectralmax,
        spectralmin=spectralmin,
        antint_ref_antenna=antint_ref_antenna,
        minchanfrac=minchanfrac,
        verbose=verbose,
        extendpols=extendpols,
        growtime=growtime,
        growfreq=growfreq,
        growaround=growaround,
        flagneartime=flagneartime,
        flagnearfreq=flagnearfreq,
        minrel=minrel,
        maxrel=maxrel,
        minabs=minabs,
        maxabs=maxabs,
        spwchan=spwchan,
        spwcorr=spwcorr,
        basecnt=basecnt,
        fieldcnt=fieldcnt,
        name=name,
        display=display,
        flagbackup=flagbackup,
        cmdreason=cmdreason,
        outfile=outfile,
        overwrite=overwrite,
        writeflags=writeflags,
    )
    return FlagdataOutputs(
        vis=vis,
        summary=result if mode == "summary" else None,
        outfile=Path(outfile) if savepars and outfile else None,
    )


class SetjyOutputs(BaseModel):
    """Outputs of the `setjy` step."""

    vis: Path


@shinobi.pystep(image=images.CASA6)
def setjy(
    ctx,
    vis: Path,
    field: str = "",
    spw: str = "",
    selectdata: bool = False,
    timerange: str = "",
    scan: str = "",
    intent: str = "",
    observation: str = "",
    scalebychan: bool = True,
    standard: str = "Perley-Butler 2017",
    model: str = "",
    listmodels: bool = False,
    interpolation: str = "nearest",
    fluxdensity: list[float] | None = None,
    spix: list[float] | None = None,
    reffreq: str = "1GHz",
    polindex: list[float] | None = None,
    polangle: list[float] | None = None,
    rotmeas: float = 0.0,
    fluxdict: dict | None = None,
    useephemdir: bool = False,
    usescratch: bool = True,
    ismms: bool = False,
) -> SetjyOutputs:
    """Fill MODEL_DATA (or the model representation) for a calibrator.

    Args:
        ctx: The pystep execution context.
        vis: MS to set the model on.
        field: Field selection.
        spw: Spectral window selection.
        selectdata: Whether `timerange`/`scan`/`intent`/`observation` apply.
        timerange: Time-range selection (`selectdata=True`).
        scan: Scan-number selection (`selectdata=True`).
        intent: Observation-intent selection (`selectdata=True`).
        observation: Observation-ID selection (`selectdata=True`).
        scalebychan: Scale flux density per channel rather than per spw.
        standard: Flux-density standard, e.g. `"Perley-Butler 2017"`,
            `"Stevens-Reynolds 2016"`, `"manual"`, `"fluxscale"`.
        model: Field-model file location (Perley-Butler standards).
        listmodels: List available VLA/solar-system models instead of running.
        interpolation: Time-interpolation method for variable sources.
        fluxdensity: `[I, Q, U, V]` in Jy (`standard='manual'`).
        spix: Spectral index of the I flux density (`standard='manual'`).
        reffreq: Reference frequency for `spix` (`standard='manual'`).
        polindex: Frequency-dependent polarization-fraction coefficients
            (`standard='manual'`).
        polangle: Frequency-dependent polarization-angle coefficients, in
            radians (`standard='manual'`).
        rotmeas: Rotation measure in rad/m^2 (`standard='manual'`).
        fluxdict: Output dict from `fluxscale` (`standard='fluxscale'`).
        useephemdir: Use ephemeris-table directions for solar-system objects.
        usescratch: Create/use the MODEL_DATA column if needed.
        ismms: Internal flag for multi-MS use.

    Returns:
        `SetjyOutputs` echoing `vis`.
    """
    _quiet_casa(ctx)
    setjy_fn = ctx.import_func("setjy", "casatasks")
    setjy_fn(
        vis=str(vis),
        field=field,
        spw=spw,
        selectdata=selectdata,
        timerange=timerange,
        scan=scan,
        intent=intent,
        observation=observation,
        scalebychan=scalebychan,
        standard=standard,
        model=model,
        listmodels=listmodels,
        interpolation=interpolation,
        fluxdensity=fluxdensity if fluxdensity is not None else [-1],
        spix=spix or [0.0],
        reffreq=reffreq,
        polindex=polindex or [],
        polangle=polangle or [],
        rotmeas=rotmeas,
        fluxdict=fluxdict or {},
        useephemdir=useephemdir,
        usescratch=usescratch,
        ismms=ismms,
    )
    return SetjyOutputs(vis=vis)


class GaincalOutputs(BaseModel):
    """Outputs of the `gaincal` step."""

    caltable: Path


@shinobi.pystep(image=images.CASA6)
def gaincal(
    ctx,
    vis: Path,
    caltable: Path,
    gaintype: str = "G",
    field: str = "",
    spw: str = "",
    intent: str = "",
    selectdata: bool = True,
    timerange: str = "",
    uvrange: str = "",
    antenna: str = "",
    scan: str = "",
    observation: str = "",
    msselect: str = "",
    solint: str = "inf",
    combine: str = "",
    preavg: float = -1.0,
    refant: str = "",
    refantmode: str = "flex",
    minblperant: int = 4,
    minsnr: float = 3.0,
    solnorm: bool = False,
    normtype: str = "mean",
    splinetime: float = 3600.0,
    npointaver: int = 3,
    phasewrap: float = 180.0,
    smodel: list[float] | None = None,
    calmode: str = "ap",
    solmode: str = "",
    rmsthresh: list[float] | None = None,
    corrdepflags: bool = False,
    append: bool = False,
    docallib: bool = False,
    callib: str = "",
    gaintable: list[Path] | None = None,
    gainfield: list[str] | None = None,
    interp: list[str] | None = None,
    spwmap: list[int] | None = None,
    parang: bool = False,
) -> GaincalOutputs:
    """Solve for temporal gains from calibrator observations.

    `append` and `minblperant` were both missing before this audit --
    oxkat's own `1GC_casa_refcal.py` needs `append=True` for its
    per-secondary G2/K2 and G3/K3 accumulation (see
    `docs/MIGRATION_PLAN.md` §10/§7 risk 1) and `minblperant=4` throughout.

    `gaintype` defaults to `'G'`, matching CASA's own default.

    Args:
        ctx: The pystep execution context.
        vis: MS to solve against.
        caltable: Output gain-calibration table.
        field: Field selection.
        spw: Spectral window/channel selection.
        intent: Observation-intent selection.
        selectdata: Whether the selection parameters below apply.
        timerange: Time-range selection.
        uvrange: uv-range selection.
        antenna: Antenna/baseline selection.
        scan: Scan-number selection.
        observation: Observation-ID selection.
        msselect: Raw TaQL data selection.
        solint: Solution interval.
        combine: Data axes to combine over (`obs`/`scan`/`spw`/`field`).
        preavg: Pre-averaging interval in seconds (rarely needed).
        refant: Reference antenna name(s); a prioritized list is allowed.
        refantmode: `flex`/`strict` reference-antenna behaviour.
        minblperant: Minimum baselines per antenna required to solve.
        minsnr: Reject solutions below this SNR.
        solnorm: Normalize (squared) solution amplitudes (`G`/`T` only).
        normtype: `mean`/`median` normalization calc (`solnorm=True`).
        gaintype: Solution type (`G`/`T`/`GSPLINE`/`K`/`KCROSS`).
        splinetime: Spline timescale in seconds (`gaintype='GSPLINE'`).
        npointaver: Phase-unwrapping window (`gaintype='GSPLINE'`).
        phasewrap: Phase-jump wrap threshold in degrees (`gaintype='GSPLINE'`).
        smodel: Point-source Stokes parameters for the source model.
        calmode: Solution type (`ap`/`p`/`a`).
        solmode: Robust solving mode (`''`/`L1`/`R`/`L1R`).
        rmsthresh: RMS threshold sequence (`solmode='R'` or `'L1R'`).
        corrdepflags: Respect correlation-dependent flags.
        append: Append this solve's solutions to an existing `caltable`
            instead of overwriting it.
        docallib: Use a cal-library file instead of `gaintable`/`gainfield`/
            `interp`/`spwmap`.
        callib: Cal-library filename (`docallib=True`).
        gaintable: Previously-solved tables to pre-apply (`docallib=False`).
        gainfield: Calibrator subset per `gaintable` entry (`docallib=False`).
        interp: Interpolation mode per `gaintable` entry (`docallib=False`).
        spwmap: Spw combinations to form for `gaintable` (`docallib=False`).
        parang: Apply the parallactic-angle correction.

    Returns:
        `GaincalOutputs` with the solved `caltable`.
    """
    _quiet_casa(ctx)
    gaincal_fn = ctx.import_func("gaincal", "casatasks")
    gaintable_s, gainfield_s, interp_s = _normalize_caltables(gaintable, gainfield, interp)
    gaincal_fn(
        vis=str(vis),
        caltable=str(caltable),
        field=field,
        spw=spw,
        intent=intent,
        selectdata=selectdata,
        timerange=timerange,
        uvrange=uvrange,
        antenna=antenna,
        scan=scan,
        observation=observation,
        msselect=msselect,
        solint=solint,
        combine=combine,
        preavg=preavg,
        refant=refant,
        refantmode=refantmode,
        minblperant=minblperant,
        minsnr=minsnr,
        solnorm=solnorm,
        normtype=normtype,
        gaintype=gaintype,
        splinetime=splinetime,
        npointaver=npointaver,
        phasewrap=phasewrap,
        smodel=smodel or [],
        calmode=calmode,
        solmode=solmode,
        rmsthresh=rmsthresh or [],
        corrdepflags=corrdepflags,
        append=append,
        docallib=docallib,
        callib=callib,
        gaintable=gaintable_s,
        gainfield=gainfield_s,
        interp=interp_s,
        spwmap=spwmap or [],
        parang=parang,
    )
    return GaincalOutputs(caltable=caltable)


class PolcalOutputs(BaseModel):
    """Outputs of the `polcal` step."""

    caltable: Path


@shinobi.pystep(image=images.CASA6)
def polcal(
    ctx,
    vis: Path,
    caltable: Path,
    poltype: str,
    field: str = "",
    spw: str = "",
    intent: str = "",
    selectdata: bool = True,
    timerange: str = "",
    uvrange: str = "",
    antenna: str = "",
    scan: str = "",
    observation: str = "",
    msselect: str = "",
    solint: str = "inf",
    combine: str = "obs,scan",
    preavg: float = 300.0,
    refant: str = "",
    minblperant: int = 4,
    minsnr: float = 3.0,
    smodel: list[float] | None = None,
    append: bool = False,
    docallib: bool = False,
    callib: str = "",
    gaintable: list[Path] | None = None,
    gainfield: list[str] | None = None,
    interp: list[str] | None = None,
    spwmap: list[int] | None = None,
) -> PolcalOutputs:
    """Determine instrumental polarization calibration. A genuinely
    different CASA task from `gaincal` (disambiguated by `poltype`, e.g.
    `"Xf"` crosshand phase, `"Df"` leakage -- not a variation on the
    `gaincal` wrapper above).

    Args:
        ctx: The pystep execution context.
        vis: MS to solve against.
        caltable: Output calibration table.
        poltype: Instrumental-polarization solution type.
        field: Field selection.
        spw: Spectral window/channel selection.
        intent: Observation-intent selection.
        selectdata: Whether the selection parameters below apply.
        timerange: Time-range selection.
        uvrange: uv-range selection.
        antenna: Antenna/baseline selection.
        scan: Scan-number selection.
        observation: Observation-ID selection.
        msselect: Raw TaQL data selection.
        solint: Solution interval.
        combine: Data axes to combine over.
        preavg: Pre-averaging interval in seconds.
        refant: Reference antenna name(s).
        minblperant: Minimum baselines per antenna required to solve.
        minsnr: Reject solutions below this SNR.
        smodel: Point-source Stokes parameters for the source model.
        append: Append to an existing `caltable` instead of overwriting it.
        docallib: Use a cal-library file instead of `gaintable`/`gainfield`/
            `interp`/`spwmap`.
        callib: Cal-library filename (`docallib=True`).
        gaintable: Previously-solved tables to pre-apply.
        gainfield: Calibrator subset per `gaintable` entry.
        interp: Interpolation mode per `gaintable` entry.
        spwmap: Spw combinations to form for `gaintable`.

    Returns:
        `PolcalOutputs` with the solved `caltable`.
    """
    _quiet_casa(ctx)
    polcal_fn = ctx.import_func("polcal", "casatasks")
    gaintable_s, gainfield_s, interp_s = _normalize_caltables(gaintable, gainfield, interp)
    polcal_fn(
        vis=str(vis),
        caltable=str(caltable),
        poltype=poltype,
        field=field,
        spw=spw,
        intent=intent,
        selectdata=selectdata,
        timerange=timerange,
        uvrange=uvrange,
        antenna=antenna,
        scan=scan,
        observation=observation,
        msselect=msselect,
        solint=solint,
        combine=combine,
        preavg=preavg,
        refant=refant,
        minblperant=minblperant,
        minsnr=minsnr,
        smodel=smodel or [],
        append=append,
        docallib=docallib,
        callib=callib,
        gaintable=gaintable_s,
        gainfield=gainfield_s,
        interp=interp_s,
        spwmap=spwmap or [],
    )
    return PolcalOutputs(caltable=caltable)


class BandpassOutputs(BaseModel):
    """Outputs of the `bandpass` step."""

    caltable: Path


@shinobi.pystep(image=images.CASA6)
def bandpass(
    ctx,
    vis: Path,
    caltable: Path,
    field: str = "",
    spw: str = "",
    intent: str = "",
    selectdata: bool = True,
    timerange: str = "",
    uvrange: str = "",
    antenna: str = "",
    scan: str = "",
    observation: str = "",
    msselect: str = "",
    solint: str = "inf",
    combine: str = "scan",
    refant: str = "",
    minblperant: int = 4,
    minsnr: float = 3.0,
    solnorm: bool = False,
    bandtype: str = "B",
    smodel: list[float] | None = None,
    corrdepflags: bool = False,
    append: bool = False,
    fillgaps: int = 0,
    degamp: int = 3,
    degphase: int = 3,
    visnorm: bool = False,
    maskcenter: int = 0,
    maskedge: int = 5,
    docallib: bool = False,
    callib: str = "",
    gaintable: list[Path] | None = None,
    gainfield: list[str] | None = None,
    interp: list[str] | None = None,
    spwmap: list[int] | None = None,
    parang: bool = False,
) -> BandpassOutputs:
    """Solve for a bandpass (per-channel gain) calibration table.

    `bandtype` and `minblperant` were both missing before this audit --
    oxkat's own `1GC_casa_refcal.py` passes `bandtype='B'` and
    `minblperant=4` explicitly on every bandpass call (see
    `docs/MIGRATION_PLAN.md` §10).

    Args:
        ctx: The pystep execution context.
        vis: MS to solve against.
        caltable: Output bandpass-calibration table.
        field: Field selection (typically the bandpass calibrator).
        spw: Spectral window selection.
        intent: Observation-intent selection.
        selectdata: Whether the selection parameters below apply.
        timerange: Time-range selection.
        uvrange: uv-range selection.
        antenna: Antenna/baseline selection.
        scan: Scan-number selection.
        observation: Observation-ID selection.
        msselect: Raw TaQL data selection.
        solint: Solution interval, time[,freq].
        combine: Data axes to combine over (e.g. `"scan"`).
        refant: Reference antenna.
        minblperant: Minimum baselines per antenna required to solve.
        minsnr: Minimum SNR for an accepted solution (`bandtype='B'` only).
        solnorm: Normalize amplitude/phase per spw, pol, ant, timestamp.
        bandtype: `B` (standard bandpass) or `BPOLY` (polynomial bandpass).
        smodel: Point-source Stokes parameters for the source model.
        corrdepflags: Respect correlation-dependent flags.
        append: Append this solve's solutions to an existing `caltable`
            instead of overwriting it.
        fillgaps: Channels to interpolate over flagged gaps (`bandtype='B'`).
        degamp: BPOLY amplitude polynomial degree (`bandtype='BPOLY'`).
        degphase: BPOLY phase polynomial degree (`bandtype='BPOLY'`).
        visnorm: Normalize data before the BPOLY solve (`bandtype='BPOLY'`).
        maskcenter: Channels to avoid at band center (`bandtype='BPOLY'`).
        maskedge: Percent of channels to avoid at each band edge
            (`bandtype='BPOLY'`).
        docallib: Use a cal-library file instead of `gaintable`/`gainfield`/
            `interp`/`spwmap`.
        callib: Cal-library filename (`docallib=True`).
        gaintable: Previously-solved tables to pre-apply (`docallib=False`).
        gainfield: Calibrator subset per `gaintable` entry (`docallib=False`).
        interp: Interpolation mode per `gaintable` entry (`docallib=False`).
        spwmap: Spw combinations to form for `gaintable` (`docallib=False`).
        parang: Apply the parallactic-angle correction.

    Returns:
        `BandpassOutputs` with the solved `caltable`.
    """
    _quiet_casa(ctx)
    bandpass_fn = ctx.import_func("bandpass", "casatasks")
    gaintable_s, gainfield_s, interp_s = _normalize_caltables(gaintable, gainfield, interp)
    bandpass_fn(
        vis=str(vis),
        caltable=str(caltable),
        field=field,
        spw=spw,
        intent=intent,
        selectdata=selectdata,
        timerange=timerange,
        uvrange=uvrange,
        antenna=antenna,
        scan=scan,
        observation=observation,
        msselect=msselect,
        solint=solint,
        combine=combine,
        refant=refant,
        minblperant=minblperant,
        minsnr=minsnr,
        solnorm=solnorm,
        bandtype=bandtype,
        smodel=smodel or [],
        corrdepflags=corrdepflags,
        append=append,
        fillgaps=fillgaps,
        degamp=degamp,
        degphase=degphase,
        visnorm=visnorm,
        maskcenter=maskcenter,
        maskedge=maskedge,
        docallib=docallib,
        callib=callib,
        gaintable=gaintable_s,
        gainfield=gainfield_s,
        interp=interp_s,
        spwmap=spwmap or [],
        parang=parang,
    )
    return BandpassOutputs(caltable=caltable)


class ApplycalOutputs(BaseModel):
    """Outputs of the `applycal` step."""

    vis: Path


@shinobi.pystep(image=images.CASA6)
def applycal(
    ctx,
    vis: Path,
    gaintable: list[Path],
    field: str = "",
    spw: str = "",
    intent: str = "",
    selectdata: bool = True,
    timerange: str = "",
    uvrange: str = "",
    antenna: str = "",
    scan: str = "",
    observation: str = "",
    msselect: str = "",
    docallib: bool = False,
    callib: str = "",
    gainfield: list[str] | None = None,
    interp: list[str] | None = None,
    spwmap: list[int] | None = None,
    calwt: list[bool] | None = None,
    parang: bool = False,
    applymode: str = "",
    flagbackup: bool = True,
) -> ApplycalOutputs:
    """Apply an accumulated list of calibration tables to `vis`.

    `spw` was missing before this audit (every other selection parameter
    was already present). `calwt`'s default now matches CASA's own
    (`[True]` per gaintable, applied per-table below); this file
    previously hardcoded `[False]`.

    Args:
        ctx: The pystep execution context.
        vis: MS to apply calibration to.
        gaintable: Calibration tables to apply, in order.
        field: Field selection.
        spw: Spectral window/channel selection.
        intent: Observation-intent selection.
        selectdata: Whether the selection parameters below apply.
        timerange: Time-range selection.
        uvrange: uv-range selection.
        antenna: Antenna/baseline selection.
        scan: Scan-number selection.
        observation: Observation-ID selection.
        msselect: Raw TaQL data selection.
        docallib: Use a cal-library file instead of `gaintable`/`gainfield`/
            `interp`/`spwmap`.
        callib: Cal-library filename (`docallib=True`).
        gainfield: Calibrator subset per `gaintable` entry (`docallib=False`).
        interp: Interpolation mode per `gaintable` entry (`docallib=False`).
        spwmap: Spw combinations to form for `gaintable` (`docallib=False`).
        calwt: Whether to calibrate data weights, per `gaintable` entry.
        parang: Apply the parallactic-angle correction.
        applymode: `calflag`/`trial`/`flagonly`/`calonly`/`''` (CASA's own
            default, meaning `calflag`).
        flagbackup: Back up flags before applying.

    Returns:
        `ApplycalOutputs` echoing `vis`.
    """
    _quiet_casa(ctx)
    applycal_fn = ctx.import_func("applycal", "casatasks")
    tables = [str(g) for g in gaintable]
    applycal_fn(
        vis=str(vis),
        field=field,
        spw=spw,
        intent=intent,
        selectdata=selectdata,
        timerange=timerange,
        uvrange=uvrange,
        antenna=antenna,
        scan=scan,
        observation=observation,
        msselect=msselect,
        docallib=docallib,
        callib=callib,
        gaintable=tables,
        gainfield=gainfield or [""] * len(tables),
        interp=interp or ["linear"] * len(tables),
        spwmap=spwmap or [],
        calwt=calwt or [True] * len(tables),
        parang=parang,
        applymode=applymode,
        flagbackup=flagbackup,
    )
    return ApplycalOutputs(vis=vis)


class FluxscaleOutputs(BaseModel):
    """Outputs of the `fluxscale` step.

    Attributes:
        fluxtable: The written flux-scaled calibration table.
        listfile: The written fit/flux-density results file, populated
            only when a `listfile` was requested.
    """

    fluxtable: Path
    listfile: Path | None = None


@shinobi.pystep(image=images.CASA6)
def fluxscale(
    ctx,
    vis: Path,
    caltable: Path,
    fluxtable: Path,
    reference: list[str],
    transfer: list[str] | None = None,
    listfile: str = "",
    append: bool = False,
    refspwmap: list[int] | None = None,
    gainthreshold: float = -1.0,
    antenna: str = "",
    timerange: str = "",
    scan: str = "",
    incremental: bool = False,
    fitorder: int = 1,
    display: bool = False,
) -> FluxscaleOutputs:
    """Bootstrap the flux-density scale from standard calibrators.

    `append` was missing entirely before this audit, even though oxkat's
    own `1GC_casa_refcal.py` passes it explicitly (`append=False`) on
    every call. `reference`/`transfer` are now real lists, matching CASA's
    own `stringVec` type -- this file previously typed them as plain
    `str`, which is why oxkat's own F3 call (`transfer=pcals`, a list of
    every secondary calibrator) couldn't be ported faithfully; see
    `recipes/ref_1gc.py`'s `f3` step in the shinobi-oxkat repo, which
    worked around this with a comma-joined string and should switch to a
    real list once this lands.

    Args:
        ctx: The pystep execution context.
        vis: MS the calibration tables were solved against.
        caltable: Input gain-calibration table (from `gaincal`).
        fluxtable: Output flux-scaled calibration table.
        reference: Reference-calibrator field name(s) with known flux.
        transfer: Field name(s) to transfer the flux scale onto; defaults
            to every source not in `reference`.
        listfile: File to write the fit/flux-density results to.
        append: Append to an existing `fluxtable` instead of overwriting it.
        refspwmap: Spw-boundary mapping for scaling across spws.
        gainthreshold: Fractional-deviation-from-median threshold on gain
            amplitudes used in the flux calculation.
        antenna: Antenna/baseline selection.
        timerange: Time-range selection.
        scan: Scan-number selection.
        incremental: Write an incremental caltable (correction factors only).
        fitorder: Spectral-fit order across multiple spectral windows.
        display: Show flux-scaling statistics/histograms.

    Returns:
        `FluxscaleOutputs` with the written `fluxtable`, plus `listfile`
        when one was requested.
    """
    _quiet_casa(ctx)
    fluxscale_fn = ctx.import_func("fluxscale", "casatasks")
    fluxscale_fn(
        vis=str(vis),
        caltable=str(caltable),
        fluxtable=str(fluxtable),
        reference=reference,
        transfer=transfer or [],
        listfile=listfile,
        append=append,
        refspwmap=refspwmap or [-1],
        gainthreshold=gainthreshold,
        antenna=antenna,
        timerange=timerange,
        scan=scan,
        incremental=incremental,
        fitorder=fitorder,
        display=display,
    )
    return FluxscaleOutputs(
        fluxtable=fluxtable, listfile=Path(listfile) if listfile else None
    )


class FlagmanagerOutputs(BaseModel):
    """Outputs of the `flagmanager` step.

    Attributes:
        vis: The measurement set the flag version operation ran against.
        versionlist: Flag version names, populated only when `mode="list"`.
    """

    vis: Path
    versionlist: list[str] | None = None


@shinobi.pystep(image=images.CASA6)
def flagmanager(
    ctx,
    vis: Path,
    mode: str = "list",
    versionname: str = "",
    oldname: str = "",
    comment: str = "",
    merge: str = "replace",
) -> FlagmanagerOutputs:
    """Real CASA flag-version management (`mode="list"/"save"/"restore"/
    "delete"/"rename"`). `mode="list"` returns the version list via
    `FlagmanagerOutputs.versionlist`, matching the real task's own return
    value for that mode; other modes echo `vis` only. `oldname`/`comment`
    (for `mode="rename"`/`"save"`) were missing before this audit. Flag-
    version bookkeeping conventions (e.g. a "before this worker ran"
    marker) are pipeline-specific orchestration, not part of this generic
    wrapper.

    Args:
        ctx: The pystep execution context.
        vis: MS to manage flag versions for.
        mode: `list`/`save`/`restore`/`delete`/`rename`.
        versionname: Flag-version name (`save`/`restore`/`delete`/`rename`).
        oldname: Flag version to rename (`mode='rename'`).
        comment: Short description of `versionname` (`save`/`rename`).
        merge: `replace` (overwrite) merge behaviour (`save`/`restore`).

    Returns:
        `FlagmanagerOutputs` echoing `vis`, plus `versionlist` when
        `mode="list"`.
    """
    _quiet_casa(ctx)
    flagmanager_fn = ctx.import_func("flagmanager", "casatasks")
    result = flagmanager_fn(
        vis=str(vis), mode=mode, versionname=versionname, oldname=oldname, comment=comment, merge=merge
    )
    return FlagmanagerOutputs(vis=vis, versionlist=result if mode == "list" else None)


# ============================================================================
# Flagging (remainder of the category, beyond flagdata/flagmanager above)
# ============================================================================


class FlagcmdOutputs(BaseModel):
    """Outputs of the `flagcmd` step.

    Attributes:
        vis: The (in-place-flagged) MS or caltable.
        outfile: The saved flag-commands file, populated only when
            `savepars=True` wrote to a real file (an empty `outfile`
            saves to the MS's own FLAG_CMD table instead).
        plotfile: The written plot, populated only when `action="plot"`
            was given a `plotfile` to write.
    """

    vis: Path
    outfile: Path | None = None
    plotfile: Path | None = None


@shinobi.pystep(image=images.CASA6)
def flagcmd(
    ctx,
    vis: Path,
    inpmode: str = "table",
    inpfile: list[str] | None = None,
    tablerows: list[int] | None = None,
    reason: str = "any",
    useapplied: bool = False,
    tbuff: float = 0.0,
    ants: str = "",
    action: str = "apply",
    flagbackup: bool = True,
    clearall: bool = False,
    rowlist: list[int] | None = None,
    plotfile: str = "",
    savepars: bool = False,
    outfile: str = "",
    overwrite: bool = True,
) -> FlagcmdOutputs:
    """Flagging based on batches of flag-commands, from a table, a file, or
    an SDM Flag.xml (`inpmode='table'/'list'/'xml'`).

    Args:
        ctx: The pystep execution context.
        vis: MS or caltable to flag.
        inpmode: Where flag commands come from (`table`/`list`/`xml`).
        inpfile: Source of flag commands (`inpmode='list'`): MS/file path(s)
            or an inline command list.
        tablerows: FLAG_CMD rows to read (`inpmode='table'`).
        reason: REASON-type filter for flag commands.
        useapplied: Only select rows whose APPLIED column is True.
        tbuff: Time-range padding in seconds (`inpmode='xml'`).
        ants: Allowed antenna names to select by (`inpmode='xml'`).
        action: `apply`/`unapply`/`list`/`plot`/`clear`/`extract`.
        flagbackup: Back up FLAG before running (`action='apply'/'unapply'`).
        clearall: Delete all FLAG_CMD rows (`action='clear'`).
        rowlist: FLAG_CMD rows to clear (`action='clear'`).
        plotfile: Output plot file (`action='plot'`).
        savepars: Save flag commands to the MS or a file.
        outfile: Output file for saved commands (`savepars=True`).
        overwrite: Overwrite an existing `outfile` (`savepars=True`).

    Returns:
        `FlagcmdOutputs` echoing `vis`, plus `outfile` when `savepars=True`
        wrote to a real file and `plotfile` when `action="plot"` wrote one.
    """
    _quiet_casa(ctx)
    flagcmd_fn = ctx.import_func("flagcmd", "casatasks")
    flagcmd_fn(
        vis=str(vis),
        inpmode=inpmode,
        inpfile=inpfile or "",
        tablerows=tablerows or [],
        reason=reason,
        useapplied=useapplied,
        tbuff=tbuff,
        ants=ants,
        action=action,
        flagbackup=flagbackup,
        clearall=clearall,
        rowlist=rowlist or [],
        plotfile=plotfile,
        savepars=savepars,
        outfile=outfile,
        overwrite=overwrite,
    )
    return FlagcmdOutputs(
        vis=vis,
        outfile=Path(outfile) if savepars and outfile else None,
        plotfile=Path(plotfile) if action == "plot" and plotfile else None,
    )


class MsuvbinflagOutputs(BaseModel):
    """Outputs of the `msuvbinflag` step."""

    binnedvis: Path


@shinobi.pystep(image=images.CASA6)
def msuvbinflag(
    ctx,
    binnedvis: Path,
    method: str = "radial_per_plane",
    nsigma: float = 5.0,
    doplot: bool = False,
) -> MsuvbinflagOutputs:
    """Identify UV-plane outliers in a `msuvbin`-binned MS and flag them.

    Args:
        ctx: The pystep execution context.
        binnedvis: Binned visibility MS (the output of `msuvbin`).
        method: Outlier-detection algorithm (`radial_per_plane`/
            `radial_mean_annular`).
        nsigma: Flagging threshold, in sigma.
        doplot: Plot the radial profiles computed before flagging (can be
            slow).

    Returns:
        `MsuvbinflagOutputs` echoing `binnedvis`.
    """
    _quiet_casa(ctx)
    msuvbinflag_fn = ctx.import_func("msuvbinflag", "casatasks")
    msuvbinflag_fn(binnedvis=str(binnedvis), method=method, nsigma=nsigma, doplot=doplot)
    return MsuvbinflagOutputs(binnedvis=binnedvis)


# ============================================================================
# Calibration (remainder of the category, beyond clearcal/initweights/
# gaincal/polcal/bandpass/applycal/fluxscale above)
# ============================================================================


class AccorOutputs(BaseModel):
    """Outputs of the `accor` step."""

    caltable: Path


@shinobi.pystep(image=images.CASA6)
def accor(
    ctx,
    vis: Path,
    caltable: Path,
    field: str = "",
    spw: str = "",
    intent: str = "",
    selectdata: bool = True,
    timerange: str = "",
    antenna: str = "",
    scan: str = "",
    observation: str = "",
    msselect: str = "",
    solint: str = "inf",
    combine: str = "",
    corrdepflags: bool = False,
    append: bool = False,
    docallib: bool = False,
    callib: str = "",
    gaintable: list[Path] | None = None,
    gainfield: list[str] | None = None,
    interp: list[str] | None = None,
    spwmap: list[int] | None = None,
) -> AccorOutputs:
    """Normalize visibilities based on auto-correlations (VLA/EVLA-era
    normalization for non-VLA-corrected data).

    Args:
        ctx: The pystep execution context.
        vis: MS to solve against.
        caltable: Output calibration table.
        field: Field selection.
        spw: Spectral window/channel selection.
        intent: Observation-intent selection.
        selectdata: Whether the selection parameters below apply.
        timerange: Time-range selection.
        antenna: Antenna/baseline selection.
        scan: Scan-number selection.
        observation: Observation-ID selection.
        msselect: Raw TaQL data selection.
        solint: Solution interval.
        combine: Data axes to combine over.
        corrdepflags: Respect correlation-dependent flags.
        append: Append to an existing `caltable` instead of overwriting it.
        docallib: Use a cal-library file instead of `gaintable`/`gainfield`/
            `interp`/`spwmap`.
        callib: Cal-library filename (`docallib=True`).
        gaintable: Previously-solved tables to pre-apply (`docallib=False`).
        gainfield: Calibrator subset per `gaintable` entry (`docallib=False`).
        interp: Interpolation mode per `gaintable` entry (`docallib=False`).
        spwmap: Spw combinations to form for `gaintable` (`docallib=False`).

    Returns:
        `AccorOutputs` with the solved `caltable`.
    """
    _quiet_casa(ctx)
    accor_fn = ctx.import_func("accor", "casatasks")
    gaintable_s, gainfield_s, interp_s = _normalize_caltables(gaintable, gainfield, interp)
    accor_fn(
        vis=str(vis),
        caltable=str(caltable),
        field=field,
        spw=spw,
        intent=intent,
        selectdata=selectdata,
        timerange=timerange,
        antenna=antenna,
        scan=scan,
        observation=observation,
        msselect=msselect,
        solint=solint,
        combine=combine,
        corrdepflags=corrdepflags,
        append=append,
        docallib=docallib,
        callib=callib,
        gaintable=gaintable_s,
        gainfield=gainfield_s,
        interp=interp_s,
        spwmap=spwmap or [],
    )
    return AccorOutputs(caltable=caltable)


class AppendantabOutputs(BaseModel):
    """Outputs of the `appendantab` step."""

    outvis: Path


@shinobi.pystep(image=images.CASA6)
def appendantab(
    ctx,
    vis: Path,
    outvis: Path,
    antab: Path,
    overwrite: bool = False,
    append_tsys: bool = True,
    append_gc: bool = True,
) -> AppendantabOutputs:
    """Append Tsys/gain-curve data from a VLBI antab file into an MS's
    SYSCAL/GAIN_CURVE subtables.

    Args:
        ctx: The pystep execution context.
        vis: Input MS.
        outvis: Output MS (replaced if it already exists and `overwrite`).
        antab: antab file to read Tsys/gain-curve info from.
        overwrite: Allow `outvis` to be overwritten.
        append_tsys: Fill the SYSCAL subtable from the antab file.
        append_gc: Fill the GAIN_CURVE subtable from the antab file.

    Returns:
        `AppendantabOutputs` with the written `outvis`.
    """
    _quiet_casa(ctx)
    appendantab_fn = ctx.import_func("appendantab", "casatasks")
    appendantab_fn(
        vis=str(vis),
        outvis=str(outvis),
        antab=str(antab),
        overwrite=overwrite,
        append_tsys=append_tsys,
        append_gc=append_gc,
    )
    return AppendantabOutputs(outvis=outvis)


class BlcalOutputs(BaseModel):
    """Outputs of the `blcal` step."""

    caltable: Path


@shinobi.pystep(image=images.CASA6)
def blcal(
    ctx,
    vis: Path,
    caltable: Path,
    field: str = "",
    spw: str = "",
    intent: str = "",
    selectdata: bool = True,
    timerange: str = "",
    uvrange: str = "",
    antenna: str = "",
    scan: str = "",
    observation: str = "",
    msselect: str = "",
    solint: str = "inf",
    combine: str = "scan",
    freqdep: bool = False,
    calmode: str = "ap",
    solnorm: bool = False,
    gaintable: list[Path] | None = None,
    gainfield: list[str] | None = None,
    interp: list[str] | None = None,
    spwmap: list[int] | None = None,
    parang: bool = False,
) -> BlcalOutputs:
    """Calculate a baseline-based (non-antenna-based) calibration solution.

    Args:
        ctx: The pystep execution context.
        vis: MS to solve against.
        caltable: Output calibration table.
        field: Field selection.
        spw: Spectral window/channel selection.
        intent: Observation-intent selection.
        selectdata: Whether the selection parameters below apply.
        timerange: Time-range selection.
        uvrange: uv-range selection.
        antenna: Antenna/baseline selection.
        scan: Scan-number selection.
        observation: Observation-ID selection.
        msselect: Raw TaQL data selection.
        solint: Solution interval.
        combine: Data axes to combine over.
        freqdep: Solve frequency-dependent solutions.
        calmode: Solution type (`ap`/`p`/`a`).
        solnorm: Normalize average solution amplitudes to 1.0.
        gaintable: Previously-solved tables to pre-apply.
        gainfield: Calibrator subset per `gaintable` entry.
        interp: Interpolation mode per `gaintable` entry.
        spwmap: Spw combinations to form for `gaintable`.
        parang: Apply the parallactic-angle correction.

    Returns:
        `BlcalOutputs` with the solved `caltable`.
    """
    _quiet_casa(ctx)
    blcal_fn = ctx.import_func("blcal", "casatasks")
    gaintable_s, gainfield_s, interp_s = _normalize_caltables(gaintable, gainfield, interp)
    blcal_fn(
        vis=str(vis),
        caltable=str(caltable),
        field=field,
        spw=spw,
        intent=intent,
        selectdata=selectdata,
        timerange=timerange,
        uvrange=uvrange,
        antenna=antenna,
        scan=scan,
        observation=observation,
        msselect=msselect,
        solint=solint,
        combine=combine,
        freqdep=freqdep,
        calmode=calmode,
        solnorm=solnorm,
        gaintable=gaintable_s,
        gainfield=gainfield_s,
        interp=interp_s,
        spwmap=spwmap or [],
        parang=parang,
    )
    return BlcalOutputs(caltable=caltable)


class DefintentOutputs(BaseModel):
    """Outputs of the `defintent` step."""

    vis: Path


@shinobi.pystep(image=images.CASA6)
def defintent(
    ctx,
    vis: Path,
    intent: str = "",
    mode: str = "",
    outputvis: str = "",
    scan: str = "",
    field: str = "",
    obsid: str = "",
) -> DefintentOutputs:
    """Manually set (or append to) scan intents.

    Args:
        ctx: The pystep execution context.
        vis: MS to edit.
        intent: Intent string(s) to add.
        mode: `set` (replace intents) or `append` (add to existing ones).
        outputvis: Write a copy here instead of editing `vis` in place.
        scan: Scan selection.
        field: Field selection.
        obsid: Observation-ID selection.

    Returns:
        `DefintentOutputs` with `outputvis` if given, else `vis`.
    """
    _quiet_casa(ctx)
    defintent_fn = ctx.import_func("defintent", "casatasks")
    defintent_fn(
        vis=str(vis), intent=intent, mode=mode, outputvis=outputvis, scan=scan, field=field, obsid=obsid
    )
    return DefintentOutputs(vis=Path(outputvis) if outputvis else vis)


class FringefitOutputs(BaseModel):
    """Outputs of the `fringefit` step."""

    caltable: Path


@shinobi.pystep(image=images.CASA6)
def fringefit(
    ctx,
    vis: Path,
    caltable: Path,
    field: str = "",
    spw: str = "",
    intent: str = "",
    selectdata: bool = True,
    timerange: str = "",
    uvrange: str = "",
    antenna: str = "",
    scan: str = "",
    observation: str = "",
    msselect: str = "",
    solint: str = "inf",
    combine: str = "",
    refant: str = "",
    minsnr: float = 3.0,
    zerorates: bool = False,
    globalsolve: bool = True,
    niter: int = 100,
    delaywindow: list[float] | None = None,
    ratewindow: list[float] | None = None,
    append: bool = False,
    corrdepflags: bool = False,
    corrcomb: str = "none",
    docallib: bool = False,
    callib: str = "",
    gaintable: list[Path] | None = None,
    gainfield: list[str] | None = None,
    interp: list[str] | None = None,
    spwmap: list[int] | None = None,
    paramactive: list[bool] | None = None,
    concatspws: bool = True,
    parang: bool = False,
) -> FringefitOutputs:
    """Fringe-fit delay and rate (VLBI-style global fringe fitting).

    Args:
        ctx: The pystep execution context.
        vis: MS to solve against.
        caltable: Output calibration table.
        field: Field selection.
        spw: Spectral window/channel selection.
        intent: Observation-intent selection.
        selectdata: Whether the selection parameters below apply.
        timerange: Time-range selection.
        uvrange: uv-range selection.
        antenna: Antenna/baseline selection.
        scan: Scan-number selection.
        observation: Observation-ID selection.
        msselect: Raw TaQL data selection.
        solint: Solution interval.
        combine: Data axes to combine over.
        refant: Reference antenna name(s).
        minsnr: Reject solutions below this SNR.
        zerorates: Zero delay-rates in the solution table.
        globalsolve: Refine estimates with a global least-squares solver.
        niter: Max least-squares solver iterations.
        delaywindow: FFT delay search-window constraint, in ns.
        ratewindow: FFT rate search-window constraint, in sec/sec.
        append: Append to an existing `caltable` instead of overwriting it.
        corrdepflags: Respect correlation-dependent flags.
        corrcomb: Correlation-combination strategy.
        docallib: Use a cal-library file instead of `gaintable`/`gainfield`/
            `interp`/`spwmap`.
        callib: Cal-library filename (`docallib=True`).
        gaintable: Previously-solved tables to pre-apply (`docallib=False`).
        gainfield: Calibrator subset per `gaintable` entry (`docallib=False`).
        interp: Interpolation mode per `gaintable` entry (`docallib=False`).
        spwmap: Spw combinations to form for `gaintable` (`docallib=False`).
        paramactive: Which parameters to solve for.
        concatspws: Multi-band FFT combination strategy.
        parang: Apply the parallactic-angle correction.

    Returns:
        `FringefitOutputs` with the solved `caltable`.
    """
    _quiet_casa(ctx)
    fringefit_fn = ctx.import_func("fringefit", "casatasks")
    gaintable_s, gainfield_s, interp_s = _normalize_caltables(gaintable, gainfield, interp)
    fringefit_fn(
        vis=str(vis),
        caltable=str(caltable),
        field=field,
        spw=spw,
        intent=intent,
        selectdata=selectdata,
        timerange=timerange,
        uvrange=uvrange,
        antenna=antenna,
        scan=scan,
        observation=observation,
        msselect=msselect,
        solint=solint,
        combine=combine,
        refant=refant,
        minsnr=minsnr,
        zerorates=zerorates,
        globalsolve=globalsolve,
        niter=niter,
        delaywindow=delaywindow or [],
        ratewindow=ratewindow or [],
        append=append,
        corrdepflags=corrdepflags,
        corrcomb=corrcomb,
        docallib=docallib,
        callib=callib,
        gaintable=gaintable_s,
        gainfield=gainfield_s,
        interp=interp_s,
        spwmap=spwmap or [],
        paramactive=paramactive or [],
        concatspws=concatspws,
        parang=parang,
    )
    return FringefitOutputs(caltable=caltable)


class GencalOutputs(BaseModel):
    """Outputs of the `gencal` step."""

    caltable: Path


@shinobi.pystep(image=images.CASA6)
def gencal(
    ctx,
    vis: Path,
    caltable: Path,
    caltype: str,
    infile: str = "",
    endpoint: str = "asdm",
    timeout: int = 180,
    retry: int = 3,
    retry_wait_time: int = 5,
    ant_pos_time_limit: int = 0,
    spw: str = "",
    antenna: str = "",
    pol: str = "",
    parameter: list[float] | None = None,
    uniform: bool = True,
) -> GencalOutputs:
    """Generate a calibration table of manually-specified values, for
    types without a data-driven solve (`amp`/`ph`/`sbd`/`mbd`/`antpos`/
    `antposvla`/`tsys`/`evlagain`/`opac`/`gc`/`gceff`/`eff`/`tecim`/
    `jyperk`/`eop`).

    Args:
        ctx: The pystep execution context.
        vis: MS to generate the table for.
        caltable: Output/input calibration table (created if it doesn't
            exist yet).
        caltype: The calibration type.
        infile: Input auxiliary file (`antpos`/`gc`/`gceff`/`tecim`/`jyperk`).
        endpoint: Jy/K web-API endpoint (`caltype='jyperk'`).
        timeout: Max web-API wait time in seconds (`caltype='jyperk'`).
        retry: Web-API retry count (`caltype='jyperk'`).
        retry_wait_time: Seconds between retries (`caltype='jyperk'`).
        ant_pos_time_limit: Days post-observation to include an offset
            correction (`caltype='antpos'`).
        spw: Spectral window/channel selection.
        antenna: Antenna/baseline selection.
        pol: Polarization selection.
        parameter: The calibration value(s) for the selection above.
        uniform: Assume uniform values across the array (`caltype='tsys'`).

    Returns:
        `GencalOutputs` with the written `caltable`.
    """
    _quiet_casa(ctx)
    gencal_fn = ctx.import_func("gencal", "casatasks")
    gencal_fn(
        vis=str(vis),
        caltable=str(caltable),
        caltype=caltype,
        infile=infile,
        endpoint=endpoint,
        timeout=timeout,
        retry=retry,
        retry_wait_time=retry_wait_time,
        ant_pos_time_limit=ant_pos_time_limit,
        spw=spw,
        antenna=antenna,
        pol=pol,
        parameter=parameter or [],
        uniform=uniform,
    )
    return GencalOutputs(caltable=caltable)


class GetantposalmaOutputs(BaseModel):
    """Outputs of the `getantposalma` step."""

    outfile: Path


@shinobi.pystep(image=images.CASA6)
def getantposalma(
    ctx,
    outfile: Path,
    overwrite: bool = False,
    asdm: str = "",
    tw: str = "",
    snr: str = "default",
    search: str = "both_latest",
    hosts: list[str] | None = None,
    firstintegration: bool = True,
    nretry: int = 0,
    rdelay: float = 3.0,
) -> GetantposalmaOutputs:
    """Query ALMA's web service for antenna-position corrections and write
    them to a JSON file (for `gencal caltype='antpos'`).

    Args:
        ctx: The pystep execution context.
        outfile: Output JSON file for the antenna positions.
        overwrite: Overwrite `outfile` if it already exists.
        asdm: The associated ASDM UID (queried by name, need not exist
            on the local filesystem).
        tw: Optional time window, `"begin_time,end_time"` (UTC ISO format).
        snr: `"default"` or a non-negative minimum correction S/N.
        search: `both_latest` or `both_closest` measurement-search strategy.
        hosts: Priority-ordered list of web-service hosts to query.
        firstintegration: Exclude first-integration-flagged calibrations.
        nretry: Retry count after failure (every host retried each attempt).
        rdelay: Delay between retries, in seconds (min 0.5).

    Returns:
        `GetantposalmaOutputs` with the written `outfile`.
    """
    _quiet_casa(ctx)
    getantposalma_fn = ctx.import_func("getantposalma", "casatasks")
    getantposalma_fn(
        outfile=str(outfile),
        overwrite=overwrite,
        asdm=asdm,
        tw=tw,
        snr=snr,
        search=search,
        hosts=hosts or ["https://asa.alma.cl/uncertainties-service/uncertainties/versions/last/measurements/casa/"],
        firstintegration=firstintegration,
        nretry=nretry,
        rdelay=rdelay,
    )
    return GetantposalmaOutputs(outfile=outfile)


class GetcalmodvlaOutputs(BaseModel):
    """Outputs of the `getcalmodvla` step."""

    outfile: Path


@shinobi.pystep(image=images.CASA6)
def getcalmodvla(
    ctx,
    outfile: Path,
    overwrite: bool = False,
    source: str = "",
    direction: str = "",
    band: str = "",
    obsdate: str = "0",
    refdate: str = "0",
    hosts: list[str] | None = None,
) -> GetcalmodvlaOutputs:
    """Query a VLA web service for a calibrator's brightness-distribution
    component list (for `setjy standard='fluxscale'`-style use).

    Args:
        ctx: The pystep execution context.
        outfile: Output component-list path.
        overwrite: Overwrite `outfile` if it already exists.
        source: Calibrator name (`"3C48"`/`"3C286"`/`"3C138"`/`"3C147"`).
        direction: Calibrator position instead of `source`,
            `"EPOCH LONGITUDE LATITUDE"`.
        band: VLA receiver band (`P`/`L`/`S`/`C`/`X`/`U`/`K`/`A`/`Q`).
        obsdate: Observation date (MJD, or `"YYYY-MM-DD"`).
        refdate: Reference date after which new DB entries are ignored.
        hosts: Web-service hostnames to query, in order.

    Returns:
        `GetcalmodvlaOutputs` with the written `outfile`.
    """
    _quiet_casa(ctx)
    getcalmodvla_fn = ctx.import_func("getcalmodvla", "casatasks")
    getcalmodvla_fn(
        outfile=str(outfile),
        overwrite=overwrite,
        source=source,
        direction=direction,
        band=band,
        obsdate=obsdate,
        refdate=refdate,
        hosts=hosts or ["http://obs.vla.nrao.edu/calmodvla"],
    )
    return GetcalmodvlaOutputs(outfile=outfile)


class PccorOutputs(BaseModel):
    """Outputs of the `pccor` step."""

    caltable: Path


@shinobi.pystep(image=images.CASA6)
def pccor(
    ctx,
    vis: Path,
    pccor_caltable: Path,
    refant: str,
    timerange: str = "none",
    scan: str = "none",
    spw: str = "none",
    antenna: str = "none",
    cablecal_correction: bool = False,
    ff_table: str = "none",
) -> PccorOutputs:
    """Generate Pulse-Cal corrections for VLBA data.

    Args:
        ctx: The pystep execution context.
        vis: MS to solve against.
        pccor_caltable: Output calibration table.
        refant: Reference antenna name.
        timerange: Time range for comparing fringe-fit and pulse-cal
            delays (needs a bright, high-SNR, coherent source).
        scan: Scan selection for the same comparison.
        spw: Spectral windows to compute solutions for.
        antenna: Antennas to compute solutions for.
        cablecal_correction: Add cable delay to the pulse-cal delays.
        ff_table: Optional reference fringe-fit table for manual control
            of cycle-ambiguity resolution.

    Returns:
        `PccorOutputs` with the solved `pccor_caltable`.
    """
    _quiet_casa(ctx)
    pccor_fn = ctx.import_func("pccor", "casatasks")
    pccor_fn(
        vis=str(vis),
        pccor_caltable=str(pccor_caltable),
        refant=refant,
        timerange=timerange,
        scan=scan,
        spw=spw,
        antenna=antenna,
        cablecal_correction=cablecal_correction,
        ff_table=ff_table,
    )
    return PccorOutputs(caltable=pccor_caltable)


class PolfromgainOutputs(BaseModel):
    """Outputs of the `polfromgain` step."""

    caltable: Path | None = None


@shinobi.pystep(image=images.CASA6)
def polfromgain(
    ctx,
    vis: Path,
    tablein: Path,
    caltable: str = "",
    paoffset: float = 0.0,
    minpacov: float = 30.0,
) -> PolfromgainOutputs:
    """Derive linear polarization (Q, U) from the ratio of a gain table's
    parallel-hand amplitudes across parallactic-angle coverage.

    Args:
        ctx: The pystep execution context.
        vis: MS the gain table was solved against.
        tablein: Input gain-calibration table.
        caltable: Optional output, polarization-corrected caltable.
        paoffset: Manual feed position-angle offset, clockwise, in degrees.
        minpacov: Minimum parallactic-angle coverage (degrees) required
            for Q/U estimation.

    Returns:
        `PolfromgainOutputs` with `caltable` if one was written.
    """
    _quiet_casa(ctx)
    polfromgain_fn = ctx.import_func("polfromgain", "casatasks")
    polfromgain_fn(vis=str(vis), tablein=str(tablein), caltable=caltable, paoffset=paoffset, minpacov=minpacov)
    return PolfromgainOutputs(caltable=Path(caltable) if caltable else None)


class RerefantOutputs(BaseModel):
    """Outputs of the `rerefant` step."""

    caltable: Path


@shinobi.pystep(image=images.CASA6)
def rerefant(
    ctx,
    vis: Path,
    tablein: Path,
    caltable: str = "",
    refantmode: str = "flex",
    refant: str = "",
) -> RerefantOutputs:
    """Re-reference an existing gain table to a different reference
    antenna, without re-solving.

    Args:
        ctx: The pystep execution context.
        vis: MS the input table was solved against.
        tablein: Input calibration table.
        caltable: Output table (overwrites `tablein` if left empty).
        refantmode: Reference-antenna algorithm (`flex`/`strict`).
        refant: Reference antenna name(s).

    Returns:
        `RerefantOutputs` with the written `caltable` (or `tablein`, if
        `caltable` was left empty).
    """
    _quiet_casa(ctx)
    rerefant_fn = ctx.import_func("rerefant", "casatasks")
    rerefant_fn(vis=str(vis), tablein=str(tablein), caltable=caltable, refantmode=refantmode, refant=refant)
    return RerefantOutputs(caltable=Path(caltable) if caltable else tablein)


class SmoothcalOutputs(BaseModel):
    """Outputs of the `smoothcal` step."""

    caltable: Path


@shinobi.pystep(image=images.CASA6)
def smoothcal(
    ctx,
    vis: Path,
    tablein: Path,
    caltable: str = "",
    field: list[str] | None = None,
    smoothtype: str = "median",
    smoothtime: float = 60.0,
    ratesmooth: bool = False,
) -> SmoothcalOutputs:
    """Smooth an existing calibration table in time.

    Args:
        ctx: The pystep execution context.
        vis: MS the input table was solved against.
        tablein: Input calibration table.
        caltable: Output table (overwrites `tablein` if left empty).
        field: Field-name selection to smooth.
        smoothtype: Smoothing filter.
        smoothtime: Smoothing time, in seconds.
        ratesmooth: Use experimental rate-aware smoothing.

    Returns:
        `SmoothcalOutputs` with the written `caltable` (or `tablein`, if
        `caltable` was left empty).
    """
    _quiet_casa(ctx)
    smoothcal_fn = ctx.import_func("smoothcal", "casatasks")
    smoothcal_fn(
        vis=str(vis),
        tablein=str(tablein),
        caltable=caltable,
        field=field or [],
        smoothtype=smoothtype,
        smoothtime=smoothtime,
        ratesmooth=ratesmooth,
    )
    return SmoothcalOutputs(caltable=Path(caltable) if caltable else tablein)


class WvrgcalOutputs(BaseModel):
    """Outputs of the `wvrgcal` step."""

    caltable: Path


@shinobi.pystep(image=images.CASA6)
def wvrgcal(
    ctx,
    vis: Path,
    caltable: Path,
    toffset: float = 0.0,
    segsource: bool = True,
    sourceflag: list[str] | None = None,
    tie: list[str] | None = None,
    nsol: int = 1,
    disperse: bool = False,
    wvrflag: list[str] | None = None,
    statfield: str = "",
    statsource: str = "",
    smooth: str = "",
    scale: float = 1.0,
    spw: list[int] | None = None,
    wvrspw: list[int] | None = None,
    reversespw: str = "",
    cont: bool = False,
    maxdistm: float = 500.0,
    minnumants: int = 2,
    mingoodfrac: float = 0.8,
    usefieldtab: bool = False,
    refant: list[str] | None = None,
    offsetstable: str = "",
    rseed: int = 0,
) -> WvrgcalOutputs:
    """Generate a gain table from ALMA Water Vapour Radiometer data.

    Args:
        ctx: The pystep execution context.
        vis: MS with WVR data to solve against.
        caltable: Output calibration table.
        toffset: Time offset, in seconds, between interferometric and WVR data.
        segsource: Recalculate coefficients separately for each source.
        sourceflag: Source(s) whose WVR data is bad, no correction produced.
        tie: Source(s) to prioritize tying phase together for.
        nsol: Number of phase-correction-coefficient solutions.
        disperse: Apply a dispersion correction.
        wvrflag: Antenna(s) whose WVR data is bad, replaced by interpolation.
        statfield: Compute statistics on this field only.
        statsource: Compute statistics on this source only.
        smooth: Timescale to smooth the calibration solution over.
        scale: Scale the whole phase correction by this factor.
        spw: Spectral windows to save solutions for.
        wvrspw: Spectral windows to take WVR data from.
        reversespw: Spectral windows to reverse the correction sign for.
        cont: Estimate the continuum (e.g. from clouds).
        maxdistm: Max antenna distance, in metres, used for flagged-antenna
            interpolation.
        minnumants: Minimum nearby-antenna count required for interpolation.
        mingoodfrac: Fraction threshold below which an antenna is flagged.
        usefieldtab: Derive antenna AZ/EL from the FIELD table instead of
            POINTING.
        refant: Antenna(s) whose WVR data to use for dT/dL parameters.
        offsetstable: Table of temperature offsets to subtract from WVR data.
        rseed: Random seed for the fitting routine.

    Returns:
        `WvrgcalOutputs` with the written `caltable`.
    """
    _quiet_casa(ctx)
    wvrgcal_fn = ctx.import_func("wvrgcal", "casatasks")
    wvrgcal_fn(
        vis=str(vis),
        caltable=str(caltable),
        toffset=toffset,
        segsource=segsource,
        sourceflag=sourceflag or [],
        tie=tie or [],
        nsol=nsol,
        disperse=disperse,
        wvrflag=wvrflag or [],
        statfield=statfield,
        statsource=statsource,
        smooth=smooth,
        scale=scale,
        spw=spw or [],
        wvrspw=wvrspw or [],
        reversespw=reversespw,
        cont=cont,
        maxdistm=maxdistm,
        minnumants=minnumants,
        mingoodfrac=mingoodfrac,
        usefieldtab=usefieldtab,
        refant=refant or [],
        offsetstable=offsetstable,
        rseed=rseed,
    )
    return WvrgcalOutputs(caltable=caltable)


# ============================================================================
# Imaging (remainder of the category, beyond setjy above)
# ============================================================================


class ApparentsensOutputs(BaseModel):
    """Outputs of the `apparentsens` step."""

    sensitivity: dict | None = None


@shinobi.pystep(image=images.CASA6)
def apparentsens(
    ctx,
    vis: list[str],
    selectdata: bool = True,
    field: list[str] | None = None,
    spw: list[str] | None = None,
    intent: list[str] | None = None,
    timerange: list[str] | None = None,
    uvrange: list[str] | None = None,
    antenna: list[str] | None = None,
    scan: list[str] | None = None,
    observation: str = "",
    imsize: list[int] | None = None,
    cell: str = "1arcsec",
    stokes: str = "I",
    specmode: str = "mfs",
    weighting: str = "natural",
    robust: float = 0.5,
    npixels: int = 0,
    uvtaper: list[str] | None = None,
) -> ApparentsensOutputs:
    """Estimate imaging sensitivity for a proposed weighting/selection,
    without actually imaging. Read-only: neither `vis` nor any image is
    touched. The real task's own return value (a sensitivity dict) is
    exposed via `ApparentsensOutputs.sensitivity`.

    Args:
        ctx: The pystep execution context.
        vis: Input MS(es).
        selectdata: Whether the selection parameters below apply.
        field: Field selection.
        spw: Spectral window/channel selection.
        intent: Observation-intent selection.
        timerange: Time-range selection.
        uvrange: uv-range selection.
        antenna: Antenna/baseline selection.
        scan: Scan-number selection.
        observation: Observation-ID selection.
        imsize: Pixel count, `[nx, ny]`.
        cell: Pixel cell size.
        stokes: Stokes planes (`I` only, currently).
        specmode: Spectral mode (`mfs` only, currently).
        weighting: Weighting scheme (`natural`/`uniform`/`briggs`).
        robust: Briggs robustness parameter (`weighting='briggs'`).
        npixels: uv-cell-size pixel count (`0` = auto).
        uvtaper: uv-plane taper on outer baselines.

    Returns:
        `ApparentsensOutputs` with the computed `sensitivity` dict.
    """
    _quiet_casa(ctx)
    apparentsens_fn = ctx.import_func("apparentsens", "casatasks")
    result = apparentsens_fn(
        vis=vis,
        selectdata=selectdata,
        field=field or [],
        spw=spw or [],
        intent=intent or [],
        timerange=timerange or [],
        uvrange=uvrange or [],
        antenna=antenna or [],
        scan=scan or [],
        observation=observation,
        imsize=imsize or [100],
        cell=cell,
        stokes=stokes,
        specmode=specmode,
        weighting=weighting,
        robust=robust,
        npixels=npixels,
        uvtaper=uvtaper or [""],
    )
    return ApparentsensOutputs(sensitivity=result if isinstance(result, dict) else None)


class DeconvolveOutputs(BaseModel):
    """Outputs of the `deconvolve` step.

    Attributes:
        imagename: The image-name prefix, echoed back -- `deconvolve`
            mutates the `.model`/`.residual`/(if `restoration`)
            `.image`/`.psf` images already on disk under this prefix
            in place; it does not create a new prefix.
    """

    imagename: str


@shinobi.pystep(image=images.CASA6)
def deconvolve(
    ctx,
    imagename: str,
    startmodel: str = "",
    deconvolver: str = "hogbom",
    scales: list[int] | None = None,
    smallscalebias: float = 0.0,
    nterms: int = 2,
    fusedthreshold: float = 0.0,
    largestscale: int = -1,
    restoration: bool = True,
    restoringbeam: list[str] | None = None,
    niter: int = 100,
    gain: float = 0.1,
    threshold: float = 0.0,
    nsigma: float = 0.0,
    interactive: bool = False,
    fullsummary: bool = False,
    fastnoise: bool = True,
    usemask: str = "user",
    mask: list[str] | None = None,
    pbmask: float = 0.0,
    sidelobethreshold: float = 3.0,
    noisethreshold: float = 5.0,
    lownoisethreshold: float = 1.5,
    negativethreshold: float = 0.0,
    smoothfactor: float = 1.0,
    minbeamfrac: float = 0.3,
    cutthreshold: float = 0.01,
    growiterations: int = 75,
    dogrowprune: bool = True,
    verbose: bool = False,
) -> DeconvolveOutputs:
    """Image-domain-only minor-cycle deconvolution (no major cycle, no
    visibility gridding) against existing PSF/residual images.

    Args:
        ctx: The pystep execution context.
        imagename: Pre-name (prefix) of the input and output images.
        startmodel: Starting model image name.
        deconvolver: Minor-cycle algorithm (`hogbom`/`clark`/`multiscale`/
            `mtmfs`/`mem`/`clarkstokes`/`asp`).
        scales: Scale sizes in pixels (`multiscale`/`mtmfs`).
        smallscalebias: Scale-selection bias (`multiscale`/`mtmfs`).
        nterms: Taylor-term count in the spectral model (`mtmfs`).
        fusedthreshold: Hogbom-clean trigger threshold (`asp`).
        largestscale: Largest allowed scale (`asp`).
        restoration: Perform the restoration step.
        restoringbeam: Restoring-beam shape (default: the PSF main lobe).
        niter: Maximum iteration count.
        gain: Loop gain.
        threshold: Stopping threshold.
        nsigma: Multiplicative rms-based stopping-threshold factor.
        interactive: Modify masks/parameters at runtime.
        fullsummary: Return the full convergence-history dict.
        fastnoise: Use the faster (older) noise calculation.
        usemask: Mask type (`user`/`pb`/`auto-multithresh`).
        mask: Mask image name(s)/region file(s)/region string(s) (`usemask='user'`).
        pbmask: Primary-beam mask threshold.
        sidelobethreshold: Sidelobe-based mask threshold (`auto-multithresh`).
        noisethreshold: Noise-based mask threshold (`auto-multithresh`).
        lownoisethreshold: Mask-growth threshold (`auto-multithresh`).
        negativethreshold: Negative-feature mask threshold (`auto-multithresh`).
        smoothfactor: Mask-smoothing factor, in beams (`auto-multithresh`).
        minbeamfrac: Minimum beam fraction for pruning (`auto-multithresh`).
        cutthreshold: Smoothed-mask cut threshold (`auto-multithresh`).
        growiterations: Binary-dilation iteration count (`auto-multithresh`).
        dogrowprune: Prune the grown mask (`auto-multithresh`).
        verbose: Print detailed automasking info.

    Returns:
        `DeconvolveOutputs` echoing `imagename`.
    """
    _quiet_casa(ctx)
    deconvolve_fn = ctx.import_func("deconvolve", "casatasks")
    deconvolve_fn(
        imagename=imagename,
        startmodel=startmodel,
        deconvolver=deconvolver,
        scales=scales or [],
        smallscalebias=smallscalebias,
        nterms=nterms,
        fusedthreshold=fusedthreshold,
        largestscale=largestscale,
        restoration=restoration,
        restoringbeam=restoringbeam or [""],
        niter=niter,
        gain=gain,
        threshold=threshold,
        nsigma=nsigma,
        interactive=interactive,
        fullsummary=fullsummary,
        fastnoise=fastnoise,
        usemask=usemask,
        mask=mask or [""],
        pbmask=pbmask,
        sidelobethreshold=sidelobethreshold,
        noisethreshold=noisethreshold,
        lownoisethreshold=lownoisethreshold,
        negativethreshold=negativethreshold,
        smoothfactor=smoothfactor,
        minbeamfrac=minbeamfrac,
        cutthreshold=cutthreshold,
        growiterations=growiterations,
        dogrowprune=dogrowprune,
        verbose=verbose,
    )
    return DeconvolveOutputs(imagename=imagename)


class DelmodOutputs(BaseModel):
    """Outputs of the `delmod` step."""

    vis: Path


@shinobi.pystep(image=images.CASA6)
def delmod(ctx, vis: Path, otf: bool = True, field: str = "", scr: bool = False) -> DelmodOutputs:
    """Delete model representations from an MS, in place.

    Args:
        ctx: The pystep execution context.
        vis: MS to delete model representations from.
        otf: Delete the on-the-fly (virtual) model keywords.
        field: Field selection (`otf=True` only -- `scr` always applies to
            the whole MODEL_DATA column).
        scr: Also delete the scratch MODEL_DATA column, if it exists.

    Returns:
        `DelmodOutputs` echoing `vis`.
    """
    _quiet_casa(ctx)
    delmod_fn = ctx.import_func("delmod", "casatasks")
    delmod_fn(vis=str(vis), otf=otf, field=field, scr=scr)
    return DelmodOutputs(vis=vis)


class FeatherOutputs(BaseModel):
    """Outputs of the `feather` step."""

    imagename: Path


@shinobi.pystep(image=images.CASA6)
def feather(
    ctx,
    highres: Path,
    lowres: Path,
    imagename: Path,
    sdfactor: float = 1.0,
    effdishdiam: float = -1.0,
    lowpassfiltersd: bool = False,
) -> FeatherOutputs:
    """Combine a high-resolution (interferometric) and low-resolution
    (single-dish) image via their Fourier transforms.

    Args:
        ctx: The pystep execution context.
        highres: High-resolution (interferometer) image.
        lowres: Low-resolution (single-dish) image.
        imagename: Output feathered-image path.
        sdfactor: Scale factor for the single-dish image.
        effdishdiam: New effective single-dish diameter, in metres (can
            only shrink it).
        lowpassfiltersd: Reject high spatial frequencies in the SD image.

    Returns:
        `FeatherOutputs` with the written `imagename`.
    """
    _quiet_casa(ctx)
    feather_fn = ctx.import_func("feather", "casatasks")
    feather_fn(
        highres=str(highres),
        lowres=str(lowres),
        imagename=str(imagename),
        sdfactor=sdfactor,
        effdishdiam=effdishdiam,
        lowpassfiltersd=lowpassfiltersd,
    )
    return FeatherOutputs(imagename=imagename)


class FtOutputs(BaseModel):
    """Outputs of the `ft` step."""

    vis: Path


@shinobi.pystep(image=images.CASA6)
def ft(
    ctx,
    vis: Path,
    field: str = "",
    spw: str = "",
    timerange: str = "",
    uvrange: str = "",
    antenna: str = "",
    scan: str = "",
    observation: str = "",
    intent: str = "",
    model: list[str] | None = None,
    nterms: int = 1,
    reffreq: str = "",
    complist: str = "",
    incremental: bool = False,
    usescratch: bool = False,
) -> FtOutputs:
    """Fourier-transform a model image or component list into the MS's
    model representation, in place (either the virtual/OTF keywords, or
    the MODEL_DATA column when `usescratch=True`).

    Args:
        ctx: The pystep execution context.
        vis: MS to write the model into.
        field: Field selection.
        spw: Spectral window/channel selection.
        timerange: Time-range selection.
        uvrange: uv-range selection.
        antenna: Antenna/baseline selection.
        scan: Scan-number selection.
        observation: Observation-ID selection.
        intent: Observation-intent selection.
        model: Input model image(s).
        nterms: Taylor-term count for the sky's frequency dependence.
        reffreq: Reference frequency, e.g. `"1.5GHz"`.
        complist: Component-list name.
        incremental: Add to the existing model visibility instead of
            replacing it.
        usescratch: Store the predicted visibilities in MODEL_DATA.

    Returns:
        `FtOutputs` echoing `vis`.
    """
    _quiet_casa(ctx)
    ft_fn = ctx.import_func("ft", "casatasks")
    ft_fn(
        vis=str(vis),
        field=field,
        spw=spw,
        timerange=timerange,
        uvrange=uvrange,
        antenna=antenna,
        scan=scan,
        observation=observation,
        intent=intent,
        model=model or "",
        nterms=nterms,
        reffreq=reffreq,
        complist=complist,
        incremental=incremental,
        usescratch=usescratch,
    )
    return FtOutputs(vis=vis)


class ImpbcorOutputs(BaseModel):
    """Outputs of the `impbcor` step."""

    outfile: Path


@shinobi.pystep(image=images.CASA6)
def impbcor(
    ctx,
    imagename: Path,
    pbimage: str,
    outfile: Path,
    overwrite: bool = False,
    box: str = "",
    region: str = "",
    chans: str = "",
    stokes: str = "",
    mask: str = "",
    mode: str = "divide",
    cutoff: float = -1.0,
    stretch: bool = False,
) -> ImpbcorOutputs:
    """Construct a primary-beam-corrected image from an image and a PB
    pattern image.

    Args:
        ctx: The pystep execution context.
        imagename: Input image (CASA/FITS/MIRIAD).
        pbimage: Primary-beam-pattern image (CASA/FITS/MIRIAD), or an
            array of pixel values.
        outfile: Output CASA image path.
        overwrite: Overwrite `outfile` if it already exists.
        box: Rectangular region in the direction plane (`''` = whole plane).
        region: Region selection (`''` = whole image).
        chans: Channels to use (`''` = all).
        stokes: Stokes planes to use (`''` = all).
        mask: Mask to use.
        mode: `divide` or `multiply` by the PB image.
        cutoff: PB cutoff; below this, values are masked (`mode='divide'`).
        stretch: Stretch the mask if necessary/possible.

    Returns:
        `ImpbcorOutputs` with the written `outfile`.
    """
    _quiet_casa(ctx)
    impbcor_fn = ctx.import_func("impbcor", "casatasks")
    impbcor_fn(
        imagename=str(imagename),
        pbimage=pbimage,
        outfile=str(outfile),
        overwrite=overwrite,
        box=box,
        region=region,
        chans=chans,
        stokes=stokes,
        mask=mask,
        mode=mode,
        cutoff=cutoff,
        stretch=stretch,
    )
    return ImpbcorOutputs(outfile=outfile)


class MakemaskOutputs(BaseModel):
    """Outputs of the `makemask` step."""

    output: str


@shinobi.pystep(image=images.CASA6)
def makemask(
    ctx,
    mode: str = "list",
    inpimage: list[str] | None = None,
    inpmask: list[str] | None = None,
    output: str = "",
    overwrite: bool = False,
    inpfreqs: list[int] | None = None,
    outfreqs: list[int] | None = None,
) -> MakemaskOutputs:
    """Make and manipulate image masks (`mode='list'/'copy'/'expand'/
    'delete'/'setdefaultmask'`). For `mode='copy'`/`'expand'`, `output`
    (an image name, or `imagename:internal_maskname`) is the real output
    product -- it may point back into `inpimage` itself for an internal
    T/F mask, which is exactly why it's classified as this step's output
    rather than treated as a side effect.

    Args:
        ctx: The pystep execution context.
        mode: `list`/`copy`/`expand`/`delete`/`setdefaultmask`.
        inpimage: Input image(s) (`copy`/`expand`/`list` modes).
        inpmask: Mask(s) to process: image masks, T/F internal masks
            (include the parent image name), or regions (`copy` mode).
        output: Output mask name (`imagename` or `imagename:internal_maskname`).
        overwrite: Overwrite `output` if it already exists.
        inpfreqs: Channels/frequencies in `inpmask` to read masks from
            (`mode='expand'`).
        outfreqs: Channels/frequencies in `output` to expand the mask onto
            (`mode='expand'`).

    Returns:
        `MakemaskOutputs` echoing `output`.
    """
    _quiet_casa(ctx)
    makemask_fn = ctx.import_func("makemask", "casatasks")
    makemask_fn(
        mode=mode,
        inpimage=inpimage or "",
        inpmask=inpmask or "",
        output=output,
        overwrite=overwrite,
        inpfreqs=inpfreqs or "",
        outfreqs=outfreqs or "",
    )
    return MakemaskOutputs(output=output)


class PredictcompOutputs(BaseModel):
    """Outputs of the `predictcomp` step.

    Attributes:
        prefix: Echoed prefix the component-list directory was written under.
        savefig: The written amplitude-vs-uv-distance plot, populated only
            when a `savefig` was requested.
    """

    prefix: Path
    savefig: Path | None = None


@shinobi.pystep(image=images.CASA6)
def predictcomp(
    ctx,
    objname: str,
    prefix: Path,
    standard: str = "Butler-JPL-Horizons 2010",
    epoch: str = "",
    minfreq: str = "",
    maxfreq: str = "",
    nfreqs: int = 2,
    antennalist: str = "",
    showplot: bool = False,
    savefig: str = "",
    symb: str = ".",
    include0amp: bool = False,
    include0bl: bool = False,
    blunit: str = "",
    showbl0flux: bool = False,
) -> PredictcompOutputs:
    """Build a component list for a known calibrator (e.g. a solar-system
    object via a flux-density standard).

    Args:
        ctx: The pystep execution context.
        objname: Object name, as recognized by `setjy`.
        prefix: Prefix for the component-list directory this writes.
        standard: Flux-density-model standard (as in `setjy`).
        epoch: Prediction time (relevant for solar-system-object standards).
        minfreq: Minimum predicted frequency, with units, e.g. `"230GHz"`.
        maxfreq: Maximum predicted frequency, with units.
        nfreqs: Number of frequencies to predict visibilities at.
        antennalist: Array-configuration file, for visibility prediction
            and plotting.
        showplot: Display the amplitude-vs-uv-distance plot on screen.
        savefig: File to save that plot to.
        symb: Matplotlib plot symbol.
        include0amp: Force the amplitude axis to start at 0.
        include0bl: Force the baseline axis to start at 0.
        blunit: Baseline-axis unit (`''` or `'klambda'`).
        showbl0flux: Print the zero-baseline flux.

    Returns:
        `PredictcompOutputs` echoing `prefix`, plus `savefig` when a plot
        file was requested.
    """
    _quiet_casa(ctx)
    predictcomp_fn = ctx.import_func("predictcomp", "casatasks")
    predictcomp_fn(
        objname=objname,
        standard=standard,
        epoch=epoch,
        minfreq=minfreq,
        maxfreq=maxfreq,
        nfreqs=nfreqs,
        prefix=str(prefix),
        antennalist=antennalist,
        showplot=showplot,
        savefig=savefig,
        symb=symb,
        include0amp=include0amp,
        include0bl=include0bl,
        blunit=blunit,
        showbl0flux=showbl0flux,
    )
    return PredictcompOutputs(prefix=prefix, savefig=Path(savefig) if savefig else None)


class WidebandpbcorOutputs(BaseModel):
    """Outputs of the `widebandpbcor` step.

    Attributes:
        imagename: Echoed back -- `widebandpbcor` writes/updates
            `.pbcor.workdirectory`/spectral-index images under this
            prefix in place, same shape as `deconvolve`'s `imagename`.
    """

    imagename: str


@shinobi.pystep(image=images.CASA6)
def widebandpbcor(
    ctx,
    vis: Path,
    imagename: str,
    nterms: int = 2,
    threshold: str = "",
    action: str = "pbcor",
    reffreq: str = "",
    pbmin: float = 0.2,
    field: str = "",
    spwlist: list[int] | None = None,
    chanlist: list[int] | None = None,
    weightlist: list[float] | None = None,
) -> WidebandpbcorOutputs:
    """Wideband primary-beam correction on the output of MS-MFS (`tclean`
    with `deconvolver='mtmfs'`) imaging.

    Args:
        ctx: The pystep execution context.
        vis: MS the images were made from (for PB geometry).
        imagename: Prefix of the multi-term images to operate on.
        nterms: Number of Taylor terms to use.
        threshold: Intensity above which to recompute the spectral index.
        action: `pbcor` (PB-correct) or `calcalpha` (spectral-index only).
        reffreq: Reference frequency, if set during `tclean`.
        pbmin: PB threshold below which not to correct.
        field: Fields to include in the PB calculation.
        spwlist: Spectral-window IDs, N entries.
        chanlist: Channel IDs, N entries.
        weightlist: Relative weights, N entries.

    Returns:
        `WidebandpbcorOutputs` echoing `imagename`.
    """
    _quiet_casa(ctx)
    widebandpbcor_fn = ctx.import_func("widebandpbcor", "casatasks")
    widebandpbcor_fn(
        vis=str(vis),
        imagename=imagename,
        nterms=nterms,
        threshold=threshold,
        action=action,
        reffreq=reffreq,
        pbmin=pbmin,
        field=field,
        spwlist=spwlist or [],
        chanlist=chanlist or [],
        weightlist=weightlist or [],
    )
    return WidebandpbcorOutputs(imagename=imagename)


class TcleanOutputs(BaseModel):
    """Outputs of the `tclean` step.

    Attributes:
        imagename: Echoed image-name prefix.
        image: `{imagename}.image` -- the restored image.
        residual: `{imagename}.residual`.
        model: `{imagename}.model`.
        psf: `{imagename}.psf`.
        pb: `{imagename}.pb` -- the primary-beam image.
        image_pbcor: `{imagename}.image.pbcor`, present only when
            `pbcor=True`.
        mutated_vis: The input MS(es), echoed back only when
            `savemodel != 'none'` -- that's the one case `tclean` also
            writes into `vis` itself (virtual model keywords or a real
            MODEL_DATA column), not just into `imagename`'s image family.
    """

    imagename: str
    image: Path
    residual: Path
    model: Path
    psf: Path
    pb: Path
    image_pbcor: Path | None = None
    mutated_vis: list[Path] | None = None


# harvest: tclean's product family is `{imagename}.<suffix>` and only its
# common members are declared output fields above -- `.sumwt` (always),
# `.mask`, `.weight`, and the whole mtmfs shape (`.image.tt0`/`.alpha`/...,
# where the declared `.image` doesn't even exist) can't be enumerated
# statically. One keep-glob covers every mode, same pattern as wsclean's
# `{prefix}-*` (see shinobi.sandbox; inert unless the step runs sandboxed).
@shinobi.pystep(image=images.CASA6, harvest=["{imagename}.*"])
def tclean(
    ctx,
    vis: list[str],
    imagename: str,
    selectdata: bool = True,
    field: list[str] | None = None,
    spw: list[str] | None = None,
    timerange: list[str] | None = None,
    uvrange: list[str] | None = None,
    antenna: list[str] | None = None,
    scan: list[str] | None = None,
    observation: str = "",
    intent: list[str] | None = None,
    datacolumn: str = "corrected",
    imsize: list[int] | None = None,
    cell: str = "1arcsec",
    phasecenter: str = "",
    stokes: str = "I",
    projection: str = "SIN",
    startmodel: str = "",
    specmode: str = "mfs",
    reffreq: str = "",
    nchan: int = -1,
    start: str = "",
    width: str = "",
    outframe: str = "LSRK",
    veltype: str = "radio",
    restfreq: list[str] | None = None,
    interpolation: str = "linear",
    perchanweightdensity: bool = True,
    gridder: str = "standard",
    pblimit: float = 0.2,
    vptable: str = "",
    wprojplanes: int = 1,
    facets: int = 1,
    normtype: str = "flatnoise",
    usepointing: bool = False,
    mosweight: bool = True,
    conjbeams: bool = False,
    psfphasecenter: str = "",
    psterm: bool = False,
    aterm: bool = True,
    cfcache: str = "",
    computepastep: float = 360.0,
    rotatepastep: float = 360.0,
    pointingoffsetsigdev: list[float] | None = None,
    wbawp: bool = True,
    deconvolver: str = "hogbom",
    scales: list[int] | None = None,
    smallscalebias: float = 0.0,
    nterms: int = 2,
    fusedthreshold: float = 0.0,
    largestscale: int = -1,
    restoration: bool = True,
    restoringbeam: list[str] | None = None,
    pbcor: bool = False,
    outlierfile: str = "",
    weighting: str = "natural",
    robust: float = 0.5,
    noise: str = "1.0Jy",
    npixels: int = 0,
    uvtaper: list[str] | None = None,
    niter: int = 0,
    gain: float = 0.1,
    threshold: float = 0.0,
    nsigma: float = 0.0,
    cycleniter: int = -1,
    cyclefactor: float = 1.0,
    minpsffraction: float = 0.05,
    maxpsffraction: float = 0.8,
    interactive: bool = False,
    nmajor: int = -1,
    fullsummary: bool = False,
    usemask: str = "user",
    mask: list[str] | None = None,
    pbmask: float = 0.0,
    sidelobethreshold: float = 3.0,
    noisethreshold: float = 5.0,
    lownoisethreshold: float = 1.5,
    negativethreshold: float = 0.0,
    smoothfactor: float = 1.0,
    minbeamfrac: float = 0.3,
    cutthreshold: float = 0.01,
    growiterations: int = 75,
    dogrowprune: bool = True,
    minpercentchange: float = -1.0,
    verbose: bool = False,
    fastnoise: bool = True,
    restart: bool = True,
    savemodel: str = "none",
    calcres: bool = True,
    calcpsf: bool = True,
    psfcutoff: float = 0.35,
    parallel: bool = False,
) -> TcleanOutputs:
    """Radio-interferometric image reconstruction (CLEAN with major/minor
    cycles) -- CASA's flagship imager. One flat wrapper covers every
    `specmode`/`gridder`/`deconvolver`/`weighting`/`usemask` combination,
    same convention as `flagdata`'s modes; see the `Args` groupings below
    for which parameters are conditional on which selector.

    Args:
        ctx: The pystep execution context.
        vis: Input MS(es).
        imagename: Prefix of the output images.
        selectdata: Whether the data-selection parameters below apply.
        field: Field selection.
        spw: Spectral window/channel selection.
        timerange: Time-range selection.
        uvrange: uv-range selection.
        antenna: Antenna/baseline selection.
        scan: Scan-number selection.
        observation: Observation-ID selection.
        intent: Observation-intent selection.
        datacolumn: Data column to image (`data`/`corrected`).
        imsize: Pixel count, `[nx, ny]`.
        cell: Pixel cell size.
        phasecenter: Image phase center.
        stokes: Stokes planes to make.
        projection: Coordinate projection.
        startmodel: Starting model image.
        specmode: Spectral mode (`mfs`/`cube`/`cubedata`/`cubesource`/`mvc`).
        reffreq: Reference frequency (`specmode='mfs'/'mvc'`).
        nchan: Output channel count (`specmode='cube*'`).
        start: First output channel (`specmode='cube*'`).
        width: Output channel width (`specmode='cube*'`).
        outframe: Spectral reference frame for `start`/`width`
            (`specmode='cube'/'cubesource'`).
        veltype: Velocity definition (`specmode='cube*'`).
        restfreq: Rest frequencies (`specmode='cube*'`).
        interpolation: Spectral interpolation (`specmode='cube*'`).
        perchanweightdensity: Per-channel Briggs weight density
            (`specmode='cube*'`).
        gridder: Gridding convolution function (`standard`/`wproject`/
            `widefield`/`mosaic`/`awproject`/`awp2`).
        pblimit: PB gain cutoff for normalization.
        vptable: Voltage-pattern table (`gridder='standard'/'widefield'/
            'wproject'`).
        wprojplanes: Distinct w-values for the convolution function
            (`gridder='widefield'/'wproject'/'awproject'/'awp2'`).
        facets: Facets per side (`gridder='widefield'`).
        normtype: Normalization type (`gridder='mosaic'/'awproject'/'awp2'`).
        usepointing: Use POINTING-table phase directions
            (`gridder='mosaic'/'awproject'/'awp2'`).
        mosweight: Independently weight each mosaic field
            (`gridder='mosaic'/'awproject'/'awp2'`).
        conjbeams: Use the conjugate frequency for wideband A-terms
            (`gridder='mosaic'/'awproject'`).
        psfphasecenter: Alternate PSF phase center (`gridder='mosaic'`).
        psterm: Use the prolate-spheroidal anti-aliasing term
            (`gridder='awproject'`).
        aterm: Use aperture-illumination functions (`gridder='awproject'`).
        cfcache: Convolution-function cache directory (`gridder='awproject'`).
        computepastep: Parallactic-angle recompute interval, in degrees
            (`gridder='awproject'/'awp2'`).
        rotatepastep: Parallactic-angle rotate interval, in degrees
            (`gridder='awproject'`).
        pointingoffsetsigdev: Pointing-offset threshold for heterogeneous
            arrays (`gridder='awproject'`).
        wbawp: Use wideband A-terms (`gridder='awproject'`).
        deconvolver: Minor-cycle algorithm (`hogbom`/`clark`/`multiscale`/
            `mtmfs`/`mem`/`clarkstokes`/`asp`).
        scales: Scale sizes in pixels (`deconvolver='multiscale'/'mtmfs'`).
        smallscalebias: Scale-selection bias (`deconvolver='multiscale'/'mtmfs'`).
        nterms: Taylor-term count (`deconvolver='mtmfs'`).
        fusedthreshold: Hogbom-clean trigger threshold (`deconvolver='asp'`).
        largestscale: Largest allowed scale (`deconvolver='asp'`).
        restoration: Perform the restoration step.
        restoringbeam: Restoring-beam shape.
        pbcor: PB-correct the restored image.
        outlierfile: Outlier-field image-definitions file.
        weighting: Weighting scheme (`natural`/`uniform`/`briggs`/
            `superuniform`/`radial`/`briggsabs`/`briggsbwtaper`).
        robust: Briggs robustness parameter (`weighting='briggs*'`).
        noise: Noise parameter (`weighting='briggsabs'`).
        npixels: uv-cell-size pixel count (`weighting='briggs*'/'superuniform'`).
        uvtaper: uv-plane taper on outer baselines.
        niter: Maximum total iteration count.
        gain: CLEAN loop-gain fraction.
        threshold: Stopping threshold, in Jy.
        nsigma: N-sigma stopping-threshold multiplier.
        cycleniter: Max minor-cycle iterations per major cycle.
        cyclefactor: PSF-sidelobe scaling for the minor-cycle threshold.
        minpsffraction: Minimum cleaning-depth PSF fraction.
        maxpsffraction: Maximum cleaning-depth PSF fraction.
        interactive: Enable the interactive GUI at major-cycle boundaries.
        nmajor: Maximum major-cycle count (`-1` = unlimited).
        fullsummary: Return the full convergence-history dict.
        usemask: Mask type (`user`/`pb`/`auto-multithresh`).
        mask: Mask image(s)/region file(s)/CRTF expression(s) (`usemask='user'`).
        pbmask: Primary-beam mask threshold.
        sidelobethreshold: Sidelobe-based mask threshold (`usemask='auto-multithresh'`).
        noisethreshold: Noise-based mask threshold (`usemask='auto-multithresh'`).
        lownoisethreshold: Mask-growth threshold (`usemask='auto-multithresh'`).
        negativethreshold: Negative-feature mask threshold (`usemask='auto-multithresh'`).
        smoothfactor: Mask-smoothing factor, in beams (`usemask='auto-multithresh'`).
        minbeamfrac: Minimum beam fraction for pruning (`usemask='auto-multithresh'`).
        cutthreshold: Smoothed-mask cut threshold (`usemask='auto-multithresh'`).
        growiterations: Binary-dilation iteration count (`usemask='auto-multithresh'`).
        dogrowprune: Prune the grown mask (`usemask='auto-multithresh'`).
        minpercentchange: Minimum mask-size change to trigger an automask
            update (`usemask='auto-multithresh'`).
        verbose: Print detailed automasking info (`usemask='auto-multithresh'`).
        fastnoise: Use the faster (older) noise calculation.
        restart: Reuse existing images, or increment `imagename` if not.
        savemodel: Save model visibilities (`none`/`virtual`/`modelcolumn`)
            -- the only case `tclean` also mutates `vis` itself.
        calcres: Calculate the initial residual image.
        calcpsf: Calculate the PSF.
        psfcutoff: PSF pixel threshold for the restoring-beam Gaussian fit.
        parallel: Run major cycles in parallel.

    Returns:
        `TcleanOutputs` with the image family under `imagename`, plus
        `mutated_vis` when `savemodel != 'none'`.
    """
    _quiet_casa(ctx)
    tclean_fn = ctx.import_func("tclean", "casatasks")
    tclean_fn(
        vis=vis,
        imagename=imagename,
        selectdata=selectdata,
        field=field or [],
        spw=spw or [],
        timerange=timerange or [],
        uvrange=uvrange or [],
        antenna=antenna or [],
        scan=scan or [],
        observation=observation,
        intent=intent or [],
        datacolumn=datacolumn,
        imsize=imsize or [100],
        cell=cell,
        phasecenter=phasecenter,
        stokes=stokes,
        projection=projection,
        startmodel=startmodel,
        specmode=specmode,
        reffreq=reffreq,
        nchan=nchan,
        start=start,
        width=width,
        outframe=outframe,
        veltype=veltype,
        restfreq=restfreq or [],
        interpolation=interpolation,
        perchanweightdensity=perchanweightdensity,
        gridder=gridder,
        pblimit=pblimit,
        vptable=vptable,
        wprojplanes=wprojplanes,
        facets=facets,
        normtype=normtype,
        usepointing=usepointing,
        mosweight=mosweight,
        conjbeams=conjbeams,
        psfphasecenter=psfphasecenter,
        psterm=psterm,
        aterm=aterm,
        cfcache=cfcache,
        computepastep=computepastep,
        rotatepastep=rotatepastep,
        pointingoffsetsigdev=pointingoffsetsigdev or [],
        wbawp=wbawp,
        deconvolver=deconvolver,
        scales=scales or [],
        smallscalebias=smallscalebias,
        nterms=nterms,
        fusedthreshold=fusedthreshold,
        largestscale=largestscale,
        restoration=restoration,
        restoringbeam=restoringbeam or [""],
        pbcor=pbcor,
        outlierfile=outlierfile,
        weighting=weighting,
        robust=robust,
        noise=noise,
        npixels=npixels,
        uvtaper=uvtaper or [""],
        niter=niter,
        gain=gain,
        threshold=threshold,
        nsigma=nsigma,
        cycleniter=cycleniter,
        cyclefactor=cyclefactor,
        minpsffraction=minpsffraction,
        maxpsffraction=maxpsffraction,
        interactive=interactive,
        nmajor=nmajor,
        fullsummary=fullsummary,
        usemask=usemask,
        mask=mask or [""],
        pbmask=pbmask,
        sidelobethreshold=sidelobethreshold,
        noisethreshold=noisethreshold,
        lownoisethreshold=lownoisethreshold,
        negativethreshold=negativethreshold,
        smoothfactor=smoothfactor,
        minbeamfrac=minbeamfrac,
        cutthreshold=cutthreshold,
        growiterations=growiterations,
        dogrowprune=dogrowprune,
        minpercentchange=minpercentchange,
        verbose=verbose,
        fastnoise=fastnoise,
        restart=restart,
        savemodel=savemodel,
        calcres=calcres,
        calcpsf=calcpsf,
        psfcutoff=psfcutoff,
        parallel=parallel,
    )
    return TcleanOutputs(
        imagename=imagename,
        image=Path(f"{imagename}.image"),
        residual=Path(f"{imagename}.residual"),
        model=Path(f"{imagename}.model"),
        psf=Path(f"{imagename}.psf"),
        pb=Path(f"{imagename}.pb"),
        image_pbcor=Path(f"{imagename}.image.pbcor") if pbcor else None,
        mutated_vis=[Path(v) for v in vis] if savemodel != "none" else None,
    )


class SdintimagingOutputs(BaseModel):
    """Outputs of the `sdintimaging` step. Same shape as `TcleanOutputs`
    -- `sdintimaging` is `tclean` plus a single-dish joint-deconvolution
    term, and shares its image-family output convention.
    """

    imagename: str
    image: Path
    residual: Path
    model: Path
    psf: Path
    image_pbcor: Path | None = None


# harvest: same reasoning as tclean's, and stronger -- sdintimaging writes
# its products under `{imagename}.joint.*`/`.int.*`/`.sd.*` sub-prefixes,
# so the declared fields cover even less of the real on-disk family.
@shinobi.pystep(image=images.CASA6, harvest=["{imagename}.*"])
def sdintimaging(
    ctx,
    vis: list[str],
    imagename: str,
    usedata: str = "sdint",
    sdimage: str = "",
    sdpsf: str = "",
    sdgain: float = 1.0,
    dishdia: str = "",
    selectdata: bool = True,
    field: list[str] | None = None,
    spw: list[str] | None = None,
    timerange: list[str] | None = None,
    uvrange: list[str] | None = None,
    antenna: list[str] | None = None,
    scan: list[str] | None = None,
    observation: str = "",
    intent: list[str] | None = None,
    datacolumn: str = "corrected",
    imsize: list[int] | None = None,
    cell: str = "1arcsec",
    phasecenter: str = "",
    stokes: str = "I",
    projection: str = "SIN",
    startmodel: str = "",
    specmode: str = "mfs",
    reffreq: str = "",
    nchan: int = -1,
    start: str = "",
    width: str = "",
    outframe: str = "LSRK",
    veltype: str = "radio",
    restfreq: list[str] | None = None,
    interpolation: str = "linear",
    perchanweightdensity: bool = True,
    gridder: str = "standard",
    facets: int = 1,
    psfphasecenter: str = "",
    wprojplanes: int = 1,
    vptable: str = "",
    mosweight: bool = True,
    aterm: bool = True,
    psterm: bool = False,
    wbawp: bool = True,
    cfcache: str = "",
    usepointing: bool = False,
    computepastep: float = 360.0,
    rotatepastep: float = 360.0,
    pointingoffsetsigdev: list[float] | None = None,
    pblimit: float = 0.2,
    deconvolver: str = "hogbom",
    scales: list[int] | None = None,
    nterms: int = 2,
    smallscalebias: float = 0.0,
    restoration: bool = True,
    restoringbeam: list[str] | None = None,
    pbcor: bool = False,
    weighting: str = "natural",
    robust: float = 0.5,
    noise: str = "1.0Jy",
    npixels: int = 0,
    uvtaper: list[str] | None = None,
    niter: int = 0,
    gain: float = 0.1,
    threshold: float = 0.0,
    nsigma: float = 0.0,
    cycleniter: int = -1,
    cyclefactor: float = 1.0,
    minpsffraction: float = 0.05,
    maxpsffraction: float = 0.8,
    nmajor: int = -1,
    interactive: bool = False,
    fullsummary: bool = False,
    usemask: str = "user",
    mask: list[str] | None = None,
    pbmask: float = 0.0,
    sidelobethreshold: float = 3.0,
    noisethreshold: float = 5.0,
    lownoisethreshold: float = 1.5,
    negativethreshold: float = 0.0,
    smoothfactor: float = 1.0,
    minbeamfrac: float = 0.3,
    cutthreshold: float = 0.01,
    growiterations: int = 75,
    dogrowprune: bool = True,
    minpercentchange: float = -1.0,
    verbose: bool = False,
    fastnoise: bool = True,
    restart: bool = True,
    calcres: bool = True,
    calcpsf: bool = True,
) -> SdintimagingOutputs:
    """Joint deconvolution of interferometric visibilities and a
    single-dish image cube into one sky model (`tclean` plus an SD term;
    see `TcleanOutputs`/`tclean`'s own docstring for the shared parameter
    groups' conditional structure).

    Args:
        ctx: The pystep execution context.
        vis: Input interferometric MS(es).
        imagename: Prefix of the output images.
        usedata: Output image type (`int`/`sd`/`sdint`).
        sdimage: Input single-dish image cube.
        sdpsf: Input single-dish PSF image, or auto-calculated if blank.
        sdgain: Single-dish flux-scale gain factor.
        dishdia: Effective single-dish diameter, in metres.
        selectdata: Whether the data-selection parameters below apply.
        field: Field selection.
        spw: Spectral window/channel selection.
        timerange: Time-range selection.
        uvrange: uv-range selection.
        antenna: Antenna/baseline selection.
        scan: Scan-number selection.
        observation: Observation-ID selection.
        intent: Observation-intent selection.
        datacolumn: Data column to image (`data`/`corrected`).
        imsize: Pixel count, `[nx, ny]`.
        cell: Pixel cell size.
        phasecenter: Image phase center.
        stokes: Stokes planes to make.
        projection: Coordinate projection.
        startmodel: Starting model image (for regridding).
        specmode: Spectral mode (`mfs`/`cube`/`cubedata`/`cubesource`).
        reffreq: Reference frequency for the spectral coordinate system.
        nchan: Output channel count (`-1` = auto).
        start: First output channel.
        width: Output channel width.
        outframe: Spectral reference frame.
        veltype: Velocity definition.
        restfreq: Rest frequencies, for velocity conversions.
        interpolation: Spectral interpolation.
        perchanweightdensity: Per-channel Briggs weight density.
        gridder: Gridding convolution function.
        facets: Facets per side.
        psfphasecenter: Alternate PSF phase center (`gridder='mosaic'`).
        wprojplanes: Distinct w-values for the convolution function.
        vptable: Voltage-pattern table.
        mosweight: Independently weight each mosaic field.
        aterm: Use aperture-illumination functions during gridding.
        psterm: Use the prolate-spheroidal anti-aliasing term.
        wbawp: Use frequency-dependent A-terms.
        cfcache: Convolution-function cache directory.
        usepointing: Use POINTING-table phase directions.
        computepastep: Parallactic-angle recompute interval, in degrees.
        rotatepastep: Parallactic-angle rotate interval, in degrees.
        pointingoffsetsigdev: Pointing-offset thresholds for heterogeneous
            arrays, in arcsec.
        pblimit: Primary-beam gain cutoff for normalization.
        deconvolver: Minor-cycle algorithm.
        scales: Scale sizes in pixels (`deconvolver='multiscale'/'mtmfs'`).
        nterms: Taylor-term count for spectral modeling (`deconvolver='mtmfs'`).
        smallscalebias: Scale-bias factor.
        restoration: Perform the restoration step.
        restoringbeam: Restoring-beam spec, or `'common'` for automatic.
        pbcor: PB-correct the restored image.
        weighting: Weighting scheme.
        robust: Briggs robustness parameter.
        noise: Noise parameter (`weighting='briggsabs'`).
        npixels: uv-cell box size (`weighting='superuniform'`).
        uvtaper: Gaussian uv-plane taper.
        niter: Maximum total iteration count.
        gain: CLEAN loop-gain fraction.
        threshold: Stopping threshold, in Jy.
        nsigma: N-sigma stopping-threshold multiplier.
        cycleniter: Max minor-cycle iterations per major cycle.
        cyclefactor: PSF-sidelobe scaling for the minor-cycle threshold.
        minpsffraction: Minimum cleaning-depth PSF fraction.
        maxpsffraction: Maximum cleaning-depth PSF fraction.
        nmajor: Maximum major-cycle count (`-1` = unlimited).
        interactive: Enable the interactive GUI at major-cycle boundaries.
        fullsummary: Return the full convergence-history dict.
        usemask: Mask type.
        mask: Mask image(s)/region file(s)/CRTF expression(s).
        pbmask: Primary-beam mask threshold.
        sidelobethreshold: Sidelobe-based mask threshold (`auto-multithresh`).
        noisethreshold: Noise-based mask threshold (`auto-multithresh`).
        lownoisethreshold: Mask-growth threshold (`auto-multithresh`).
        negativethreshold: Negative-feature mask threshold (`auto-multithresh`).
        smoothfactor: Mask-smoothing factor, in beams (`auto-multithresh`).
        minbeamfrac: Minimum beam fraction for pruning (`auto-multithresh`).
        cutthreshold: Smoothed-mask cut threshold (`auto-multithresh`).
        growiterations: Binary-dilation iteration count (`auto-multithresh`).
        dogrowprune: Prune the grown mask (`auto-multithresh`).
        minpercentchange: Minimum mask-size change to trigger an automask
            update per channel (`auto-multithresh`).
        verbose: Print detailed automasking info (`auto-multithresh`).
        fastnoise: Use the faster (older) noise calculation.
        restart: Reuse existing images/model, or increment `imagename`.
        calcres: Calculate the initial residual image.
        calcpsf: Calculate the PSF.

    Returns:
        `SdintimagingOutputs` with the image family under `imagename`.
    """
    _quiet_casa(ctx)
    sdintimaging_fn = ctx.import_func("sdintimaging", "casatasks")
    sdintimaging_fn(
        vis=vis,
        imagename=imagename,
        usedata=usedata,
        sdimage=sdimage,
        sdpsf=sdpsf,
        sdgain=sdgain,
        dishdia=dishdia,
        selectdata=selectdata,
        field=field or [],
        spw=spw or [],
        timerange=timerange or [],
        uvrange=uvrange or [],
        antenna=antenna or [],
        scan=scan or [],
        observation=observation,
        intent=intent or [],
        datacolumn=datacolumn,
        imsize=imsize or [100],
        cell=cell,
        phasecenter=phasecenter,
        stokes=stokes,
        projection=projection,
        startmodel=startmodel,
        specmode=specmode,
        reffreq=reffreq,
        nchan=nchan,
        start=start,
        width=width,
        outframe=outframe,
        veltype=veltype,
        restfreq=restfreq or [],
        interpolation=interpolation,
        perchanweightdensity=perchanweightdensity,
        gridder=gridder,
        facets=facets,
        psfphasecenter=psfphasecenter,
        wprojplanes=wprojplanes,
        vptable=vptable,
        mosweight=mosweight,
        aterm=aterm,
        psterm=psterm,
        wbawp=wbawp,
        cfcache=cfcache,
        usepointing=usepointing,
        computepastep=computepastep,
        rotatepastep=rotatepastep,
        pointingoffsetsigdev=pointingoffsetsigdev or [],
        pblimit=pblimit,
        deconvolver=deconvolver,
        scales=scales or [],
        nterms=nterms,
        smallscalebias=smallscalebias,
        restoration=restoration,
        restoringbeam=restoringbeam or [""],
        pbcor=pbcor,
        weighting=weighting,
        robust=robust,
        noise=noise,
        npixels=npixels,
        uvtaper=uvtaper or [""],
        niter=niter,
        gain=gain,
        threshold=threshold,
        nsigma=nsigma,
        cycleniter=cycleniter,
        cyclefactor=cyclefactor,
        minpsffraction=minpsffraction,
        maxpsffraction=maxpsffraction,
        nmajor=nmajor,
        interactive=interactive,
        fullsummary=fullsummary,
        usemask=usemask,
        mask=mask or [""],
        pbmask=pbmask,
        sidelobethreshold=sidelobethreshold,
        noisethreshold=noisethreshold,
        lownoisethreshold=lownoisethreshold,
        negativethreshold=negativethreshold,
        smoothfactor=smoothfactor,
        minbeamfrac=minbeamfrac,
        cutthreshold=cutthreshold,
        growiterations=growiterations,
        dogrowprune=dogrowprune,
        minpercentchange=minpercentchange,
        verbose=verbose,
        fastnoise=fastnoise,
        restart=restart,
        calcres=calcres,
        calcpsf=calcpsf,
    )
    return SdintimagingOutputs(
        imagename=imagename,
        image=Path(f"{imagename}.image"),
        residual=Path(f"{imagename}.residual"),
        model=Path(f"{imagename}.model"),
        psf=Path(f"{imagename}.psf"),
        image_pbcor=Path(f"{imagename}.image.pbcor") if pbcor else None,
    )


# ============================================================================
# Manipulation (remainder of the category, beyond mstransform/fixvis above)
# ============================================================================


class ClearstatOutputs(BaseModel):
    """Outputs of the `clearstat` step. No parameters, no artifact -- it
    clears table autolocks globally, not tied to any specific input.
    """


@shinobi.pystep(image=images.CASA6)
def clearstat(ctx) -> ClearstatOutputs:
    """Clear all autolock file locks that might block other tasks from
    running on the same table/file.

    Args:
        ctx: The pystep execution context.

    Returns:
        `ClearstatOutputs` (no fields).
    """
    _quiet_casa(ctx)
    clearstat_fn = ctx.import_func("clearstat", "casatasks")
    clearstat_fn()
    return ClearstatOutputs()


class ConcatOutputs(BaseModel):
    """Outputs of the `concat` step."""

    concatvis: Path


@shinobi.pystep(image=images.CASA6)
def concat(
    ctx,
    vis: list[Path],
    concatvis: Path,
    freqtol: str = "",
    dirtol: str = "",
    respectname: bool = False,
    timesort: bool = False,
    copypointing: bool = True,
    visweightscale: list[float] | None = None,
    forcesingleephemfield: str = "",
) -> ConcatOutputs:
    """Concatenate several MSs into one (additive: appends if `concatvis`
    already exists).

    Args:
        ctx: The pystep execution context.
        vis: Input MSs to concatenate.
        concatvis: Output (or existing, to append to) MS.
        freqtol: Frequency-shift tolerance for merging spws (default 1 Hz
            when left empty).
        dirtol: Direction-shift tolerance for merging fields (default
            1 milliarcsec when left empty).
        respectname: Don't merge same-direction fields with different names.
        timesort: Sort the output by TIME, ascending.
        copypointing: Copy the POINTING subtable.
        visweightscale: Per-input-MS weight-scaling factors.
        forcesingleephemfield: Force a single merged ephemeris for the
            given field(s), overriding the default non-overlap check.

    Returns:
        `ConcatOutputs` with the written `concatvis`.
    """
    _quiet_casa(ctx)
    concat_fn = ctx.import_func("concat", "casatasks")
    concat_fn(
        vis=[str(v) for v in vis],
        concatvis=str(concatvis),
        freqtol=freqtol,
        dirtol=dirtol,
        respectname=respectname,
        timesort=timesort,
        copypointing=copypointing,
        visweightscale=visweightscale or [],
        forcesingleephemfield=forcesingleephemfield,
    )
    return ConcatOutputs(concatvis=concatvis)


class ConjugatevisOutputs(BaseModel):
    """Outputs of the `conjugatevis` step."""

    outputvis: Path


@shinobi.pystep(image=images.CASA6)
def conjugatevis(
    ctx, vis: Path, outputvis: Path, spwlist: list[int] | None = None, overwrite: bool = False
) -> ConjugatevisOutputs:
    """Change the sign of the phases in every visibility column.

    Args:
        ctx: The pystep execution context.
        vis: Input MS.
        outputvis: Output MS path.
        spwlist: Spectral window(s) to conjugate (default: all).
        overwrite: Overwrite `outputvis` if it already exists.

    Returns:
        `ConjugatevisOutputs` with the written `outputvis`.
    """
    _quiet_casa(ctx)
    conjugatevis_fn = ctx.import_func("conjugatevis", "casatasks")
    conjugatevis_fn(vis=str(vis), spwlist=spwlist or "", outputvis=str(outputvis), overwrite=overwrite)
    return ConjugatevisOutputs(outputvis=outputvis)


class CvelOutputs(BaseModel):
    """Outputs of the `cvel` step."""

    outputvis: Path


@shinobi.pystep(image=images.CASA6)
def cvel(
    ctx,
    vis: Path,
    outputvis: Path,
    passall: bool = False,
    field: str = "",
    spw: str = "",
    selectdata: bool = True,
    antenna: str = "",
    timerange: str = "",
    scan: str = "",
    array: str = "",
    mode: str = "channel",
    nchan: int = -1,
    start: str = "0",
    width: str = "1",
    interpolation: str = "linear",
    phasecenter: str = "",
    restfreq: str = "",
    outframe: str = "",
    veltype: str = "radio",
    hanning: bool = False,
) -> CvelOutputs:
    """Regrid an MS to a new spectral window/channel structure or frame
    (the original, non-multi-MS-aware regridder; see `cvel2` for the
    modern replacement).

    Args:
        ctx: The pystep execution context.
        vis: Input MS.
        outputvis: Output MS path.
        passall: Pass non-selected data through unchanged.
        field: Field selection.
        spw: Spectral window/channel selection.
        selectdata: Whether `antenna`/`timerange`/`scan`/`array` apply.
        antenna: Antenna/baseline selection.
        timerange: Time-range selection.
        scan: Scan-number selection.
        array: (Sub)array selection.
        mode: Regridding mode (`channel`/`velocity`/`frequency`).
        nchan: Output channel count (`-1` = all).
        start: Regridding start (units depend on `mode`).
        width: Regridding channel width (units depend on `mode`).
        interpolation: Spectral interpolation method.
        phasecenter: Phase center for the spectral-coordinate transform.
        restfreq: Rest frequency for the output.
        outframe: Output reference frame (`''` keeps the input frame).
        veltype: Velocity definition.
        hanning: Hanning-smooth before regridding, to remove Gibbs ringing.

    Returns:
        `CvelOutputs` with the written `outputvis`.
    """
    _quiet_casa(ctx)
    cvel_fn = ctx.import_func("cvel", "casatasks")
    cvel_fn(
        vis=str(vis),
        outputvis=str(outputvis),
        passall=passall,
        field=field,
        spw=spw,
        selectdata=selectdata,
        antenna=antenna,
        timerange=timerange,
        scan=scan,
        array=array,
        mode=mode,
        nchan=nchan,
        start=start,
        width=width,
        interpolation=interpolation,
        phasecenter=phasecenter,
        restfreq=restfreq,
        outframe=outframe,
        veltype=veltype,
        hanning=hanning,
    )
    return CvelOutputs(outputvis=outputvis)


class Cvel2Outputs(BaseModel):
    """Outputs of the `cvel2` step."""

    outputvis: Path


@shinobi.pystep(image=images.CASA6)
def cvel2(
    ctx,
    vis: Path,
    outputvis: Path,
    keepmms: bool = True,
    field: str = "",
    spw: str = "",
    scan: str = "",
    antenna: str = "",
    correlation: str = "",
    timerange: str = "",
    intent: str = "",
    array: str = "",
    uvrange: str = "",
    observation: str = "",
    feed: str = "",
    datacolumn: str = "all",
    mode: str = "channel",
    nchan: int = -1,
    start: str = "0",
    width: str = "1",
    interpolation: str = "linear",
    phasecenter: str = "",
    restfreq: str = "",
    outframe: str = "",
    veltype: str = "radio",
    hanning: bool = False,
) -> Cvel2Outputs:
    """Regrid an MS or multi-MS to a new spectral window/channel structure
    or frame (the modern, multi-MS-aware replacement for `cvel`).

    Args:
        ctx: The pystep execution context.
        vis: Input MS or multi-MS.
        outputvis: Output MS (or multi-MS) path.
        keepmms: Keep multi-MS output if the input is a multi-MS.
        field: Field selection.
        spw: Spectral window/channel selection.
        scan: Scan-number selection.
        antenna: Antenna/baseline selection.
        correlation: Correlation selection.
        timerange: Time-range selection.
        intent: Observation-intent selection.
        array: (Sub)array selection.
        uvrange: uv-range selection.
        observation: Observation-ID selection.
        feed: Multi-feed selection (not yet implemented by CASA itself).
        datacolumn: Which data column(s) to process.
        mode: Regridding mode (`channel`/`velocity`/`frequency`/`channel_b`).
        nchan: Output channel count (`-1` = all).
        start: Start input channel (sign of `width` decides direction).
        width: Output channel width.
        interpolation: Spectral interpolation method.
        phasecenter: Phase center for the spectral-coordinate transform.
        restfreq: Rest frequency for the output.
        outframe: Output reference frame (LSRK/LSRD/BARY/GALACTO/...).
        veltype: Velocity definition.
        hanning: Hanning-smooth to remove Gibbs ringing.

    Returns:
        `Cvel2Outputs` with the written `outputvis`.
    """
    _quiet_casa(ctx)
    cvel2_fn = ctx.import_func("cvel2", "casatasks")
    cvel2_fn(
        vis=str(vis),
        outputvis=str(outputvis),
        keepmms=keepmms,
        field=field,
        spw=spw,
        scan=scan,
        antenna=antenna,
        correlation=correlation,
        timerange=timerange,
        intent=intent,
        array=array,
        uvrange=uvrange,
        observation=observation,
        feed=feed,
        datacolumn=datacolumn,
        mode=mode,
        nchan=nchan,
        start=start,
        width=width,
        interpolation=interpolation,
        phasecenter=phasecenter,
        restfreq=restfreq,
        outframe=outframe,
        veltype=veltype,
        hanning=hanning,
    )
    return Cvel2Outputs(outputvis=outputvis)


class FixplanetsOutputs(BaseModel):
    """Outputs of the `fixplanets` step."""

    vis: Path


@shinobi.pystep(image=images.CASA6)
def fixplanets(
    ctx,
    vis: Path,
    field: str = "",
    fixuvw: bool = False,
    direction: str = "",
    refant: str = "0",
    reftime: str = "first",
) -> FixplanetsOutputs:
    """Change FIELD/SOURCE table entries based on a user-provided
    direction or the POINTING table, in place, optionally fixing UVW too.

    Args:
        ctx: The pystep execution context.
        vis: MS to edit.
        field: Field selection.
        fixuvw: Also recalculate UVW coordinates.
        direction: Explicit direction to use instead of the POINTING table
            (a coordinate, or an ephemeris-table path).
        refant: Antenna to read POINTING-table info from (ID or name).
        reftime: Timestamp to read POINTING-table info from (or `'median'`).

    Returns:
        `FixplanetsOutputs` echoing `vis`.
    """
    _quiet_casa(ctx)
    fixplanets_fn = ctx.import_func("fixplanets", "casatasks")
    fixplanets_fn(vis=str(vis), field=field, fixuvw=fixuvw, direction=direction, refant=refant, reftime=reftime)
    return FixplanetsOutputs(vis=vis)


class HanningsmoothOutputs(BaseModel):
    """Outputs of the `hanningsmooth` step."""

    outputvis: Path


@shinobi.pystep(image=images.CASA6)
def hanningsmooth(
    ctx,
    vis: Path,
    outputvis: Path,
    keepmms: bool = True,
    field: str = "",
    spw: str = "",
    scan: str = "",
    antenna: str = "",
    correlation: str = "",
    timerange: str = "",
    intent: str = "",
    array: str = "",
    uvrange: str = "",
    observation: str = "",
    feed: str = "",
    smooth_spw: str = "",
    datacolumn: str = "all",
) -> HanningsmoothOutputs:
    """Hanning-smooth channel data to remove Gibbs ringing.

    Args:
        ctx: The pystep execution context.
        vis: Input MS.
        outputvis: Output MS path.
        keepmms: Keep multi-MS output if the input is a multi-MS.
        field: Field selection.
        spw: Spectral window/channel selection.
        scan: Scan-number selection.
        antenna: Antenna/baseline selection.
        correlation: Correlation selection.
        timerange: Time-range selection.
        intent: Observation-intent selection.
        array: (Sub)array selection.
        uvrange: uv-range selection.
        observation: Observation-ID selection.
        feed: Multi-feed selection (not yet implemented by CASA itself).
        smooth_spw: Spectral window(s) to Hanning-smooth (default: all
            selected).
        datacolumn: Which data column(s) to process.

    Returns:
        `HanningsmoothOutputs` with the written `outputvis`.
    """
    _quiet_casa(ctx)
    hanningsmooth_fn = ctx.import_func("hanningsmooth", "casatasks")
    hanningsmooth_fn(
        vis=str(vis),
        outputvis=str(outputvis),
        keepmms=keepmms,
        field=field,
        spw=spw,
        scan=scan,
        antenna=antenna,
        correlation=correlation,
        timerange=timerange,
        intent=intent,
        array=array,
        uvrange=uvrange,
        observation=observation,
        feed=feed,
        smooth_spw=smooth_spw,
        datacolumn=datacolumn,
    )
    return HanningsmoothOutputs(outputvis=outputvis)


class MsuvbinOutputs(BaseModel):
    """Outputs of the `msuvbin` step."""

    outputvis: Path


@shinobi.pystep(image=images.CASA6)
def msuvbin(
    ctx,
    vis: Path,
    outputvis: Path,
    field: str = "",
    spw: str = "",
    taql: str = "",
    phasecenter: str = "",
    imsize: list[int] | None = None,
    cell: str = "1arcsec",
    ncorr: int = 1,
    nchan: int = 1,
    start: str = "",
    width: str = "",
    wproject: bool = False,
    memfrac: float = 0.5,
    mode: str = "bin",
    flagbackup: bool = False,
) -> MsuvbinOutputs:
    """Grid visibility data onto a defined uniform uv-grid, stored as an
    MS (additive: bins into `outputvis` if it already exists).

    Args:
        ctx: The pystep execution context.
        vis: Input MS.
        outputvis: Output (or existing, to bin further into) uv-grid MS.
        field: Field selection (mssel syntax).
        spw: Spectral window selection (mssel syntax).
        taql: TaQL data-selection string.
        phasecenter: uv-grid phase center (default: the first selected field).
        imsize: Pixel count (should be even, factorizable by 2/3/5).
        cell: Sky-plane pixel cell size.
        ncorr: Correlation count to store, `1`/`2`/`4`.
        nchan: Output grid spectral-channel count.
        start: First-channel frequency of the grid.
        width: Spectral channel width.
        wproject: Apply w-projection correction while gridding.
        memfrac: Fraction of available RAM to use.
        mode: Gridding/flag-transfer operation mode.
        flagbackup: Back up flags before saving (`mode` that writes flags back).

    Returns:
        `MsuvbinOutputs` with the written `outputvis`.
    """
    _quiet_casa(ctx)
    msuvbin_fn = ctx.import_func("msuvbin", "casatasks")
    msuvbin_fn(
        vis=str(vis),
        field=field,
        spw=spw,
        taql=taql,
        outputvis=str(outputvis),
        phasecenter=phasecenter,
        imsize=imsize or [100],
        cell=cell,
        ncorr=ncorr,
        nchan=nchan,
        start=start,
        width=width,
        wproject=wproject,
        memfrac=memfrac,
        mode=mode,
        flagbackup=flagbackup,
    )
    return MsuvbinOutputs(outputvis=outputvis)


class PartitionOutputs(BaseModel):
    """Outputs of the `partition` step."""

    outputvis: Path


@shinobi.pystep(image=images.CASA6)
def partition(
    ctx,
    vis: Path,
    outputvis: Path,
    createmms: bool = True,
    separationaxis: str = "auto",
    numsubms: str = "auto",
    flagbackup: bool = True,
    datacolumn: str = "all",
    field: str = "",
    spw: str = "",
    scan: str = "",
    antenna: str = "",
    correlation: str = "",
    timerange: str = "",
    intent: str = "",
    array: str = "",
    uvrange: str = "",
    observation: str = "",
    feed: str = "",
    taql: str = "",
) -> PartitionOutputs:
    """Produce a multi-MS from an MS, for parallelized processing.

    Args:
        ctx: The pystep execution context.
        vis: Input MS.
        outputvis: Output multi-MS path.
        createmms: Create a multi-MS output.
        separationaxis: Parallelization axis (`scan`/`spw`/`baseline`/`auto`).
        numsubms: Sub-MS count (`auto` or an int).
        flagbackup: Back up the FLAG column in the multi-MS.
        datacolumn: Which data column(s) to process.
        field: Field selection.
        spw: Spectral window/channel selection.
        scan: Scan-number selection.
        antenna: Antenna/baseline selection.
        correlation: Correlation selection.
        timerange: Time-range selection.
        intent: Observation-intent selection.
        array: (Sub)array selection.
        uvrange: uv-range selection.
        observation: Observation-ID selection.
        feed: Multi-feed selection (not yet implemented by CASA itself).
        taql: Table-query string for nested selections.

    Returns:
        `PartitionOutputs` with the written `outputvis`.
    """
    _quiet_casa(ctx)
    partition_fn = ctx.import_func("partition", "casatasks")
    partition_fn(
        vis=str(vis),
        outputvis=str(outputvis),
        createmms=createmms,
        separationaxis=separationaxis,
        numsubms=numsubms,
        flagbackup=flagbackup,
        datacolumn=datacolumn,
        field=field,
        spw=spw,
        scan=scan,
        antenna=antenna,
        correlation=correlation,
        timerange=timerange,
        intent=intent,
        array=array,
        uvrange=uvrange,
        observation=observation,
        feed=feed,
        taql=taql,
    )
    return PartitionOutputs(outputvis=outputvis)


class PhaseshiftOutputs(BaseModel):
    """Outputs of the `phaseshift` step."""

    outputvis: Path


@shinobi.pystep(image=images.CASA6)
def phaseshift(
    ctx,
    vis: Path,
    outputvis: Path,
    phasecenter: str,
    keepmms: bool = True,
    field: str = "",
    spw: str = "",
    scan: str = "",
    intent: str = "",
    array: str = "",
    observation: str = "",
    datacolumn: str = "all",
) -> PhaseshiftOutputs:
    """Rotate an MS to a new phase center.

    Args:
        ctx: The pystep execution context.
        vis: Input MS.
        outputvis: Output MS path.
        phasecenter: New phase-center direction coordinates.
        keepmms: Keep multi-MS output if the input is a multi-MS.
        field: Field selection.
        spw: Spectral window/channel selection.
        scan: Scan-number selection.
        intent: Observation-intent selection.
        array: (Sub)array selection.
        observation: Observation-ID selection.
        datacolumn: Which data column(s) to process.

    Returns:
        `PhaseshiftOutputs` with the written `outputvis`.
    """
    _quiet_casa(ctx)
    phaseshift_fn = ctx.import_func("phaseshift", "casatasks")
    phaseshift_fn(
        vis=str(vis),
        outputvis=str(outputvis),
        keepmms=keepmms,
        field=field,
        spw=spw,
        scan=scan,
        intent=intent,
        array=array,
        observation=observation,
        datacolumn=datacolumn,
        phasecenter=phasecenter,
    )
    return PhaseshiftOutputs(outputvis=outputvis)


class RmtablesOutputs(BaseModel):
    """Outputs of the `rmtables` step. No fields: `rmtables` deletes
    `tablenames`, so there is no resulting path for a downstream step to
    wire from -- the meaningful effect is that they no longer exist.
    """


@shinobi.pystep(image=images.CASA6)
def rmtables(ctx, tablenames: list[str]) -> RmtablesOutputs:
    """Remove CASA tables cleanly (use this instead of `rm -rf`).

    Args:
        ctx: The pystep execution context.
        tablenames: Table name(s) to remove; supports `*`/`?` wildcards
            and `[ ]` range notation.

    Returns:
        `RmtablesOutputs` (no fields).
    """
    _quiet_casa(ctx)
    rmtables_fn = ctx.import_func("rmtables", "casatasks")
    rmtables_fn(tablenames=tablenames)
    return RmtablesOutputs()


class SplitOutputs(BaseModel):
    """Outputs of the `split` step."""

    outputvis: Path


@shinobi.pystep(image=images.CASA6)
def split(
    ctx,
    vis: Path,
    outputvis: Path,
    keepmms: bool = True,
    field: str = "",
    spw: str = "",
    scan: str = "",
    antenna: str = "",
    correlation: str = "",
    timerange: str = "",
    intent: str = "",
    array: str = "",
    uvrange: str = "",
    observation: str = "",
    feed: str = "",
    datacolumn: str = "corrected",
    keepflags: bool = True,
    width: str = "1",
    timebin: str = "0s",
    combine: str = "",
) -> SplitOutputs:
    """Create a visibility subset from an existing MS, with optional
    channel/time averaging.

    Args:
        ctx: The pystep execution context.
        vis: Input MS.
        outputvis: Output MS path.
        keepmms: Keep multi-MS output if the input is a multi-MS.
        field: Field selection.
        spw: Spectral window/channel selection.
        scan: Scan-number selection.
        antenna: Antenna/baseline selection.
        correlation: Correlation selection.
        timerange: Time-range selection.
        intent: Observation-intent selection.
        array: (Sub)array selection.
        uvrange: uv-range selection.
        observation: Observation-ID selection.
        feed: Multi-feed selection (not yet implemented by CASA itself).
        datacolumn: Which data column(s) to process.
        keepflags: Keep fully-flagged rows instead of dropping them.
        width: Channel count to average into one output channel.
        timebin: Time-averaging bin width.
        combine: Span the time bin across `scan`/`state`/both.

    Returns:
        `SplitOutputs` with the written `outputvis`.
    """
    _quiet_casa(ctx)
    split_fn = ctx.import_func("split", "casatasks")
    split_fn(
        vis=str(vis),
        outputvis=str(outputvis),
        keepmms=keepmms,
        field=field,
        spw=spw,
        scan=scan,
        antenna=antenna,
        correlation=correlation,
        timerange=timerange,
        intent=intent,
        array=array,
        uvrange=uvrange,
        observation=observation,
        feed=feed,
        datacolumn=datacolumn,
        keepflags=keepflags,
        width=width,
        timebin=timebin,
        combine=combine,
    )
    return SplitOutputs(outputvis=outputvis)


class StatwtOutputs(BaseModel):
    """Outputs of the `statwt` step."""

    vis: Path


@shinobi.pystep(image=images.CASA6)
def statwt(
    ctx,
    vis: Path,
    selectdata: bool = True,
    field: str = "",
    spw: str = "",
    intent: str = "",
    array: str = "",
    observation: str = "",
    scan: str = "",
    combine: str = "",
    timebin: str = "1",
    slidetimebin: bool = False,
    chanbin: str = "spw",
    minsamp: int = 2,
    statalg: str = "classic",
    fence: float = -1.0,
    center: str = "mean",
    lside: bool = True,
    zscore: float = -1.0,
    maxiter: int = -1,
    fitspw: str = "",
    excludechans: bool = False,
    wtrange: list[float] | None = None,
    flagbackup: bool = True,
    preview: bool = False,
    datacolumn: str = "corrected",
) -> StatwtOutputs:
    """Compute and set visibility weights from the data's own variance,
    in place (WEIGHT/WEIGHT_SPECTRUM columns, and flags data outside
    `wtrange` unless `preview=True`).

    Args:
        ctx: The pystep execution context.
        vis: MS to compute and write weights for.
        selectdata: Whether the selection parameters below apply.
        field: Field selection.
        spw: Spectral window/channel selection.
        intent: Observation-intent selection.
        array: (Sub)array selection.
        observation: Observation-ID selection.
        scan: Scan-number selection.
        combine: Axes to ignore column-changes on when computing weights
            (`scan`/`field`/`state`, and/or `corr`).
        timebin: Time-binning length for statistics (int or a quantity).
        slidetimebin: Use a sliding time window instead of block processing.
        chanbin: Channel-bin width (int, `'spw'`, or a frequency quantity).
        minsamp: Minimum unflagged-visibility count required per sample.
        statalg: Variance algorithm (`classic`/`chauvenet`/`fit-half`/
            `hinges-fences`).
        fence: Fence value (`statalg='hinges-fences'`; negative = whole
            dataset).
        center: Center definition (`statalg='fit-half'`: `mean`/`median`/`zero`).
        lside: Real data are `<= center` (`statalg='fit-half'`).
        zscore: Target max std-deviations for inclusion (`statalg='chauvenet'`).
        maxiter: Max iterations (`statalg='chauvenet'`; negative = until
            criterion met).
        fitspw: Channel selection for weight computation.
        excludechans: Invert `fitspw` (exclude it instead of including it).
        wtrange: Acceptable-weight range; data outside it gets flagged.
        flagbackup: Back up flags before running.
        preview: Report flagging impact without changing any data.
        datacolumn: Data column used for weights (`data`/`corrected`/
            `residual`/`residual_data`).

    Returns:
        `StatwtOutputs` echoing `vis`.
    """
    _quiet_casa(ctx)
    statwt_fn = ctx.import_func("statwt", "casatasks")
    statwt_fn(
        vis=str(vis),
        selectdata=selectdata,
        field=field,
        spw=spw,
        intent=intent,
        array=array,
        observation=observation,
        scan=scan,
        combine=combine,
        timebin=timebin,
        slidetimebin=slidetimebin,
        chanbin=chanbin,
        minsamp=minsamp,
        statalg=statalg,
        fence=fence,
        center=center,
        lside=lside,
        zscore=zscore,
        maxiter=maxiter,
        fitspw=fitspw,
        excludechans=excludechans,
        wtrange=wtrange or [],
        flagbackup=flagbackup,
        preview=preview,
        datacolumn=datacolumn,
    )
    return StatwtOutputs(vis=vis)


class UvcontsubOutputs(BaseModel):
    """Outputs of the `uvcontsub` step."""

    outputvis: Path


@shinobi.pystep(image=images.CASA6)
def uvcontsub(
    ctx,
    vis: Path,
    outputvis: Path,
    field: str = "",
    spw: str = "",
    scan: str = "",
    intent: str = "",
    array: str = "",
    observation: str = "",
    datacolumn: str = "data",
    fitspec: str = "",
    fitmethod: str = "gsl",
    fitorder: int = 0,
    writemodel: bool = False,
) -> UvcontsubOutputs:
    """Continuum subtraction in the uv domain.

    Args:
        ctx: The pystep execution context.
        vis: Input MS.
        outputvis: Output MS path.
        field: Field selection.
        spw: Spectral window/channel selection.
        scan: Scan-number selection.
        intent: Observation-intent selection.
        array: (Sub)array selection.
        observation: Observation-ID selection.
        datacolumn: Data column to process.
        fitspec: Polynomial order / line-free-channel spec for the
            continuum fit (global, or per field/spw).
        fitmethod: Fitting method (`gsl`/`casacore`).
        fitorder: Polynomial order for the fit.
        writemodel: Write the fitted model into `outputvis`'s MODEL column.

    Returns:
        `UvcontsubOutputs` with the written `outputvis`.
    """
    _quiet_casa(ctx)
    uvcontsub_fn = ctx.import_func("uvcontsub", "casatasks")
    uvcontsub_fn(
        vis=str(vis),
        outputvis=str(outputvis),
        field=field,
        spw=spw,
        scan=scan,
        intent=intent,
        array=array,
        observation=observation,
        datacolumn=datacolumn,
        fitspec=fitspec,
        fitmethod=fitmethod,
        fitorder=fitorder,
        writemodel=writemodel,
    )
    return UvcontsubOutputs(outputvis=outputvis)


class UvcontsubOldOutputs(BaseModel):
    """Outputs of the `uvcontsub_old` step.

    Attributes:
        contsub_vis: `{vis}.contsub` -- always written.
        cont_vis: `{vis}.cont`, present only when `want_cont=True`.
    """

    contsub_vis: Path
    cont_vis: Path | None = None


@shinobi.pystep(image=images.CASA6)
def uvcontsub_old(
    ctx,
    vis: Path,
    field: list[str] | None = None,
    fitspw: str = "",
    excludechans: bool = False,
    combine: str = "",
    solint: str = "int",
    fitorder: int = 0,
    spw: str = "",
    want_cont: bool = False,
) -> UvcontsubOldOutputs:
    """Continuum fitting and subtraction in the uv plane (the deprecated,
    pre-`uvcontsub` implementation). Output naming is fixed by CASA
    itself, not a caller-supplied path -- `{vis}.contsub` (overwritten if
    it already exists), plus `{vis}.cont` when `want_cont=True`.

    Args:
        ctx: The pystep execution context.
        vis: Input MS.
        field: Field selection.
        fitspw: Spectral window:channel selection for the continuum fit.
        excludechans: Invert `fitspw` (exclude it instead of including it).
        combine: Axes to combine for the continuum estimate (`''`, or
            `spw`/`scan`).
        solint: Continuum-fit timescale (`'int'` recommended).
        fitorder: Polynomial order for the fit.
        spw: Spectral window selection for the output.
        want_cont: Also write `{vis}.cont`, the continuum estimate.

    Returns:
        `UvcontsubOldOutputs` with `contsub_vis` (always) and `cont_vis`
        (when `want_cont=True`).
    """
    _quiet_casa(ctx)
    uvcontsub_old_fn = ctx.import_func("uvcontsub_old", "casatasks")
    uvcontsub_old_fn(
        vis=str(vis),
        field=field or [],
        fitspw=fitspw,
        excludechans=excludechans,
        combine=combine,
        solint=solint,
        fitorder=fitorder,
        spw=spw,
        want_cont=want_cont,
    )
    return UvcontsubOldOutputs(
        contsub_vis=Path(f"{vis}.contsub"), cont_vis=Path(f"{vis}.cont") if want_cont else None
    )


class UvmodelfitOutputs(BaseModel):
    """Outputs of the `uvmodelfit` step."""

    outfile: Path | None = None
    result: list[float] | None = None


@shinobi.pystep(image=images.CASA6)
def uvmodelfit(
    ctx,
    vis: Path,
    field: str = "",
    spw: str = "",
    selectdata: bool = True,
    timerange: str = "",
    uvrange: str = "",
    antenna: str = "",
    scan: str = "",
    msselect: str = "",
    niter: int = 5,
    comptype: str = "P",
    sourcepar: list[float] | None = None,
    varypar: list[bool] | None = None,
    outfile: str = "",
) -> UvmodelfitOutputs:
    """Fit a single-component source model (point/Gaussian/disk) to the
    uv data. Read-only w.r.t. `vis`; the fitted parameters are the actual
    output product, optionally also written to `outfile` as a component
    list.

    Args:
        ctx: The pystep execution context.
        vis: MS to fit against.
        field: Field selection.
        spw: Spectral window/channel selection.
        selectdata: Whether the selection parameters below apply.
        timerange: Time-range selection.
        uvrange: uv-range selection.
        antenna: Antenna/baseline selection.
        scan: Scan-number selection.
        msselect: Raw TaQL data selection.
        niter: Fitting-iteration count.
        comptype: Component model type (`P`oint/`G`aussian/`D`isk).
        sourcepar: Starting-guess component parameters (3 values for `P`,
            5 for `G`/`D`).
        varypar: Which parameters are allowed to vary in the fit.
        outfile: Optional output component-list table.

    Returns:
        `UvmodelfitOutputs` with the fitted `result` and `outfile` if one
        was written.
    """
    _quiet_casa(ctx)
    uvmodelfit_fn = ctx.import_func("uvmodelfit", "casatasks")
    result = uvmodelfit_fn(
        vis=str(vis),
        field=field,
        spw=spw,
        selectdata=selectdata,
        timerange=timerange,
        uvrange=uvrange,
        antenna=antenna,
        scan=scan,
        msselect=msselect,
        niter=niter,
        comptype=comptype,
        sourcepar=sourcepar or [1.0, 0.0, 0.0],
        varypar=varypar or [],
        outfile=outfile,
    )
    return UvmodelfitOutputs(
        outfile=Path(outfile) if outfile else None,
        result=list(result) if isinstance(result, (list, tuple)) else None,
    )


class UvsubOutputs(BaseModel):
    """Outputs of the `uvsub` step."""

    vis: Path


@shinobi.pystep(image=images.CASA6)
def uvsub(ctx, vis: Path, reverse: bool = False) -> UvsubOutputs:
    """Subtract (or, `reverse=True`, add) MODEL_DATA from/to
    CORRECTED_DATA, in place.

    Args:
        ctx: The pystep execution context.
        vis: MS to modify.
        reverse: Add instead of subtracting.

    Returns:
        `UvsubOutputs` echoing `vis`.
    """
    _quiet_casa(ctx)
    uvsub_fn = ctx.import_func("uvsub", "casatasks")
    uvsub_fn(vis=str(vis), reverse=reverse)
    return UvsubOutputs(vis=vis)


class VirtualconcatOutputs(BaseModel):
    """Outputs of the `virtualconcat` step.

    Attributes:
        concatvis: The output multi-MS.
        moved_vis: The input MSs, echoed back only when `keepcopy=False`
            (CASA's own default) -- in that case they are consumed into
            the multi-MS structure rather than left untouched in place.
    """

    concatvis: Path
    moved_vis: list[Path] | None = None


@shinobi.pystep(image=images.CASA6)
def virtualconcat(
    ctx,
    vis: list[Path],
    concatvis: Path,
    freqtol: str = "",
    dirtol: str = "",
    respectname: bool = True,
    visweightscale: list[float] | None = None,
    keepcopy: bool = False,
    copypointing: bool = True,
) -> VirtualconcatOutputs:
    """Concatenate several MSs into one multi-MS, without copying the
    underlying data (a "virtual" concat).

    Args:
        ctx: The pystep execution context.
        vis: Input MSs to concatenate.
        concatvis: Output multi-MS path.
        freqtol: Frequency-shift tolerance for considering data the same spw.
        dirtol: Direction-shift tolerance for considering data the same field.
        respectname: Don't merge same-direction fields with different names.
        visweightscale: Per-input-MS weight-scaling factors.
        keepcopy: Keep a copy of the input MSs in their original place
            (if False, CASA's own default, they're consumed into `concatvis`).
        copypointing: Keep the POINTING table in the output multi-MS.

    Returns:
        `VirtualconcatOutputs` with `concatvis`, plus `moved_vis` echoing
        the inputs when `keepcopy=False`.
    """
    _quiet_casa(ctx)
    virtualconcat_fn = ctx.import_func("virtualconcat", "casatasks")
    virtualconcat_fn(
        vis=[str(v) for v in vis],
        concatvis=str(concatvis),
        freqtol=freqtol,
        dirtol=dirtol,
        respectname=respectname,
        visweightscale=visweightscale or [],
        keepcopy=keepcopy,
        copypointing=copypointing,
    )
    return VirtualconcatOutputs(concatvis=concatvis, moved_vis=None if keepcopy else vis)
