"""fitstoolz -- FITS image manipulation sub-commands
(https://github.com/shinobi-dosho/fitstoolz).

Like simms 3.0 (see `simms.py`), fitstoolz authors its apps **inside the
tool itself** as `@shinobi.pystep` functions (`fitstoolz.apps.{header,
stats,slice,add_axis,remove_axis,stack}`), each with a typed outputs model
and a module-level `runit(opts)` its click command and its pystep both
delegate to. dosho therefore consumes them as pysteps rather than shelling
out to the `fitstoolz` CLI -- the `@shinobi.pystep` + `ctx.import_func`
pattern `casatasks.py` documents in full: the wrappers below run *inside
the fitstoolz container* at step-execution time, importing
`fitstoolz.apps.<app>.runit` there and never on the host (the app modules
import `astropy`/`dask`/`xarray` at top level, and dosho's registry
discovery imports this module on the host, which is exactly what the
pattern avoids).

Each wrapper transcribes its fitstoolz counterpart's signature
field-for-field -- same names, same defaults, same `Field(
json_schema_extra={"abbreviation": ...})` short flags -- so validation and
`ninja run --help` match the real `fitstoolz <app> --help`. Keeping the
parameter names identical is load-bearing: `runit` reads them straight off
the `SimpleNamespace` (fitstoolz's own pystep builds it with
`SimpleNamespace(**locals())`).

* `fitstoolz-header` -- show, add, edit or remove FITS header entries.
* `fitstoolz-stats` -- min/max/mean/std over (optionally sliced and
  clipped) image data, returned as real outputs so a following step can
  branch on them.
* `fitstoolz-slice` -- write out a sub-cube along one or more named axes.
* `fitstoolz-add-axis` / `fitstoolz-remove-axis` -- degenerate-axis
  surgery (the FREQ/STOKES axes CASA and wsclean disagree about).
* `fitstoolz-stack` -- concatenate several images along one axis.

fitstoolz's `unstack` app is deliberately not wrapped: upstream's `runit`
is a bare `NotImplementedError`, so a cab for it would only be a more
expensive way to fail. Its `sanitise` module is likewise empty and not
even registered in fitstoolz's own CLI group. Both come back here when
they do something.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import shinobi
from pydantic import BaseModel, Field

from dosho import images


class FitsOutputs(BaseModel):
    """Path of the written FITS file, so a following step can be wired to
    it. `None` for a `header --show` run, which prints and writes nothing
    -- mirrors fitstoolz's own `apps.FitsOutputs`."""

    outfile: Path | None = None


class StatsOutputs(BaseModel):
    """Image statistics, so a following step can branch on them (mirrors
    `fitstoolz.apps.stats.StatsOutputs`)."""

    min: float | None = None
    max: float | None = None
    mean: float | None = None
    std: float | None = None


class StackOutputs(BaseModel):
    """Path of the stacked FITS file."""

    stacked_fits: Path | None = None


def _opts(local_vars: dict) -> SimpleNamespace:
    """The `SimpleNamespace` fitstoolz's `runit` expects, from a wrapper's
    locals().

    Drops `ctx`, and renders every `Path` (or list of them) back to `str`.
    The Path types on the fields below exist for *shinobi's* benefit --
    only path-typed fields get absolutized into the workspace and their
    parents bound into the container -- while fitstoolz's own apps are
    written against the plain strings its click layer parses. Same
    adaptation layer as `simms.py`'s `_opts`.
    """

    def _plain(value):
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, list):
            return [_plain(item) for item in value]
        return value

    return SimpleNamespace(**{k: _plain(v) for k, v in local_vars.items() if k != "ctx"})


@shinobi.pystep(
    name="fitstoolz-header",
    image=images.FITSTOOLZ,
    info="Show, add, edit or remove FITS header entries.",
)
def header(
    ctx,
    fname: Path = Field(..., description="Input file(s)"),
    show: bool = Field(False, description="Show header and exit"),
    edit: list[str] | None = Field(None, description="Edit FITS header entry, as KEY=VALUE"),
    remove: list[str] | None = Field(None, description="Remove header entry"),
    add: list[str] | None = Field(None, description="Add header entry, as KEY=VALUE"),
    outfile: Path | None = Field(None, description="Path of output image"),
    replace: bool = Field(False, description="Overwrite output if it exists"),
    log_level: str = Field("INFO", description="Log level"),
) -> FitsOutputs:
    opts = _opts(locals())
    # `runit` returns the written path -- or None for `--show`, which dumps the
    # header to stdout and writes nothing.
    written = ctx.import_func("runit", "fitstoolz.apps.header")(opts)
    return FitsOutputs(outfile=written)


@shinobi.pystep(
    name="fitstoolz-stats",
    image=images.FITSTOOLZ,
    info="Get image statistics (min, max, mean, standard deviation).",
)
def stats(
    ctx,
    fname: Path = Field(..., description="Input file(s)"),
    show: bool = Field(False, description="Show min, max, mean and standard deviation"),
    slice: list[str] | None = Field(None, description="Slice data, as CTYPE,START,END"),
    clip_below: float | None = Field(None, description="Blank pixels below this value"),
    clip_above: float | None = Field(None, description="Blank pixels above this value"),
    blank_value: float | None = Field(
        None,
        description="Blank value when using --clip-below/above. The values 'inf' and 'nan' are "
        "valid blank values.",
    ),
    log_level: str = Field("INFO", description="Log level"),
) -> StatsOutputs:
    opts = _opts(locals())
    # fitstoolz's `runit` returns *its own* StatsOutputs instance (a class that
    # only exists inside the container); re-wrap field-by-field into this
    # module's model, which is what shinobi validates the step against.
    result = ctx.import_func("runit", "fitstoolz.apps.stats")(opts)
    return StatsOutputs(min=result.min, max=result.max, mean=result.mean, std=result.std)


@shinobi.pystep(
    name="fitstoolz-slice",
    image=images.FITSTOOLZ,
    info="Slice a FITS image along one or more axes.",
)
def slice_(
    ctx,
    fname: Path = Field(..., description="Input file(s)"),
    axis: list[str] | None = Field(None, description="Axis slicing info, as CTYPE,START,END"),
    memmap: bool = Field(True, description="memmap option to pass to astropy.io.fits.open()"),
    ra_chunks: int | None = Field(None, description="RA chunking"),
    dec_chunks: int | None = Field(None, description="Dec chunking"),
    spectral_chunks: int | None = Field(None, description="Spectral chunking"),
    outfile: Path | None = Field(None, description="Path of output image"),
    replace: bool = Field(False, description="Overwrite output if it exists"),
    log_level: str = Field("INFO", description="Log level"),
) -> FitsOutputs:
    opts = _opts(locals())
    return FitsOutputs(outfile=ctx.import_func("runit", "fitstoolz.apps.slice")(opts))


@shinobi.pystep(
    name="fitstoolz-add-axis",
    image=images.FITSTOOLZ,
    info="Add an axis to a FITS image.",
)
def add_axis(
    ctx,
    fname: Path = Field(..., description="Input file(s)"),
    ctype: str = Field(..., description="Axis type; FREQ, STOKES, etc."),
    index: int = Field(..., description="Add axis at this dimension index"),
    crpix: int = Field(0, description="Reference pixel (zero-based indexing)"),
    crval: float = Field(0.0, description="Value at Reference pixel (crval)"),
    cdelt: float = Field(1.0, description="Pixel width"),
    cunit: str = Field("", description="Units (astropy naming convention)"),
    ra_chunks: int | None = Field(None, description="RA chunking"),
    dec_chunks: int | None = Field(None, description="Dec chunking"),
    spectral_chunks: int | None = Field(None, description="Spectral chunking"),
    outfile: Path | None = Field(None, description="Path of output image"),
    replace: bool = Field(False, description="Overwrite output if it exists"),
    log_level: str = Field("INFO", description="Log level"),
) -> FitsOutputs:
    opts = _opts(locals())
    return FitsOutputs(outfile=ctx.import_func("runit", "fitstoolz.apps.add_axis")(opts))


@shinobi.pystep(
    name="fitstoolz-remove-axis",
    image=images.FITSTOOLZ,
    info="Remove an axis from a FITS image.",
)
def remove_axis(
    ctx,
    fname: Path = Field(..., description="Input file(s)"),
    ctype: str = Field(
        ...,
        description="Axis type (or dimension). FREQ, STOKES, etc.",
        json_schema_extra={"abbreviation": "ct"},
    ),
    select_index: int = Field(
        0,
        description="Keep data at this index (zero-based). For example, if removing the frequency "
        "axis, this would be the channel to keep.",
        json_schema_extra={"abbreviation": "si"},
    ),
    ra_chunks: int | None = Field(None, description="RA chunking"),
    dec_chunks: int | None = Field(None, description="Dec chunking"),
    spectral_chunks: int | None = Field(None, description="Spectral chunking"),
    outfile: Path | None = Field(None, description="Path of output image"),
    replace: bool = Field(False, description="Overwrite output if it exists"),
    log_level: str = Field("INFO", description="Log level"),
) -> FitsOutputs:
    opts = _opts(locals())
    return FitsOutputs(outfile=ctx.import_func("runit", "fitstoolz.apps.remove_axis")(opts))


@shinobi.pystep(
    name="fitstoolz-stack",
    image=images.FITSTOOLZ,
    info="Stack FITS images along an axis.",
)
def stack(
    ctx,
    fname: Path = Field(..., description="Input file(s)"),
    axis: str = Field(..., description="Stack files along this axis"),
    extra_files: list[Path] | None = Field(
        None, description="Additional files to stack (use multiple times)"
    ),
    stacked_fits: Path = Field(..., description="Path of stacked output image"),
    ra_chunks: int | None = Field(None, description="RA chunking"),
    dec_chunks: int | None = Field(None, description="Dec chunking"),
    spectral_chunks: int | None = Field(None, description="Spectral chunking"),
    log_level: str = Field("INFO", description="Log level"),
) -> StackOutputs:
    opts = _opts(locals())
    return StackOutputs(stacked_fits=ctx.import_func("runit", "fitstoolz.apps.stack")(opts))
