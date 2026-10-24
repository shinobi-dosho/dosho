"""Simms primary-beam utilities and compatibility imports for simulation cabs.

``simms-skysim`` and ``simms-telsim`` are declarative CLI cabs under
``dosho/documents/``. The historical ``from dosho.cabs.simms import skysim,
telsim`` paths resolve to those same cabs through the registry; they no
longer expose pystep ``.step`` or ``.func`` attributes. Recipes can continue
to pass either object directly to ``Recipe.add_step``.

``primary_beam`` keeps its Python adapter, importing ``runit`` only inside
the running Simms container. The pre-3.0 CLI remains a separate ``simms``
cab using its own image.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Literal

from pydantic import BaseModel, Field

import dosho
from dosho import images


class PrimaryBeamOutputs(BaseModel):
    """Passthrough paths of the primary-beam operation: `tag-ms` mutates
    `ms` in place and echoes it back, `to-fits`/`apply`/`correct` write
    `output`. Both are declared so either mode can be wired into a Recipe --
    a `tag-ms` step is otherwise a dead end with no edge to chain from."""

    ms: Path | None = None
    output: Path | None = None


def _opts(local_vars: dict) -> SimpleNamespace:
    """The `SimpleNamespace` simms' `runit` expects, from a wrapper's locals().

    Drops `ctx`, and renders every `Path` back to `str`. The Path types on the
    fields below exist for *shinobi's* benefit -- only path-typed fields get
    absolutized into the workspace and their parents bound into the container
    (see the ragavi cabs for the same rule) -- while simms' own apps are
    written against the plain strings its CLI parses. This wrapper is the
    adaptation layer between the two, so neither side has to compromise.
    """
    return SimpleNamespace(
        **{k: (str(v) if isinstance(v, Path) else v) for k, v in local_vars.items() if k != "ctx"}
    )


@dosho.pystep(
    name="simms-primary-beam",
    image=images.SIMMS,
    info="Primary-beam utilities (build/tag/apply/correct); no visibility simulation (simms 3.0).",
    write_paths=["output"],
)
def primary_beam(
    ctx,
    mode: Literal["to-fits", "tag-ms", "apply", "correct"] = Field(
        ..., description="Operation to perform."
    ),
    beam_pattern: str | None = Field(
        None,
        description="Beam model: a cosine-taper CSV path, a built-in name, a band shorthand (L/UHF), or a FITS cube.",
        json_schema_extra={"abbreviation": "bp"},
    ),
    beam_band: Literal["UHF", "L"] = Field(
        "L", description="Default band for a built-in beam when beam-pattern omits one."
    ),
    beam_pa_step: float = Field(
        1.0, description="Parallactic-angle sampling step (degrees) for the time-averaged beam."
    ),
    fits_format: Literal["simms", "cattery"] = Field(
        "simms",
        description="to-fits output layout: simms's own single-file 4-plane HH/VV cube, or "
        "the Cattery/DDFacet 8-file per-Jones-element schema (--Beam-Model FITS).",
        json_schema_extra={"abbreviation": "ff"},
    ),
    pol_basis: Literal["linear", "circular"] = Field(
        "linear",
        description="Correlation basis for the cattery fits-format output (xx/xy/yx/yy vs "
        "rr/rl/lr/ll); must match the target MS's feed basis.",
        json_schema_extra={"abbreviation": "pol"},
    ),
    beam_l_axis: Literal["-X", "X"] = Field(
        "-X",
        description="Sign convention for the cattery fits-format L axis, matching DDFacet's "
        "--Beam-FITSLAxis (pass the same value to both).",
        json_schema_extra={"abbreviation": "bla"},
    ),
    beam_m_axis: Literal["Y", "-Y"] = Field(
        "Y",
        description="Sign convention for the cattery fits-format M axis, matching DDFacet's "
        "--Beam-FITSMAxis (pass the same value to both).",
        json_schema_extra={"abbreviation": "bma"},
    ),
    ms: Path | None = Field(
        None,
        description="Measurement set (time/PA range, array position and frequencies). Required for tag-ms/apply/correct.",
    ),
    fits_sky: Path | None = Field(
        None,
        description="Input FITS image sky model (apply/correct).",
        json_schema_extra={"abbreviation": "fits"},
    ),
    ascii_sky: Path | None = Field(
        None,
        description="Input ASCII component sky model (apply/correct).",
        json_schema_extra={"abbreviation": "ascii"},
    ),
    ascii_delimiter: str | None = Field(
        None,
        description="Delimiter used in the ascii-sky file. Defaults to whitespace.",
        json_schema_extra={"abbreviation": "ad"},
    ),
    source_schema: Path | None = Field(
        None,
        description="Custom source schema (YAML) mapping the ascii-sky columns to the fields simms expects.",
    ),
    output: Path | None = Field(
        None,
        description="Output path - FITS beam (to-fits, or filename prefix when --fits-format cattery) "
        "or beamed/corrected sky model (apply/correct).",
        json_schema_extra={"abbreviation": "o"},
    ),
    telescope_name_column: str = Field(
        "TELESCOPE_NAME",
        description="ANTENNA-table column holding the per-antenna telescope/type label (tag-ms).",
        json_schema_extra={"abbreviation": "tnc"},
    ),
    label: str | None = Field(
        None, description="Single telescope-name label applied to all antennas (tag-ms)."
    ),
    label_map: Path | None = Field(
        None, description="YAML mapping antenna NAME -> telescope-name label (tag-ms)."
    ),
    from_layout: str | None = Field(
        None,
        description="simms layout whose per-antenna telescope_name is matched to the MS antenna names (tag-ms).",
    ),
    pb_cutoff: float = Field(
        0.1, description="In correct mode, blank (NaN) where the beam is below this level."
    ),
    field_id: int = Field(
        0,
        description="FIELD_ID whose phase centre and time span define the beam (apply/correct).",
        json_schema_extra={"abbreviation": "fi"},
    ),
    spw_id: int = Field(
        0,
        description="Spectral-window (DATA_DESC_ID) whose frequencies define the beam (apply/correct).",
    ),
    pixel_size: str = Field(
        "1arcmin", description="Angular pixel size for the to-fits grid, e.g. '1arcmin'."
    ),
    npix: int = Field(256, description="Number of pixels per side for the to-fits grid."),
    start_freq: str | None = Field(
        None,
        description="Start frequency of the to-fits cube, e.g. '856MHz'. Defaults to the beam's first frequency.",
        json_schema_extra={"abbreviation": "sf"},
    ),
    chan_width: str | None = Field(
        None,
        description="Channel width of the to-fits cube, e.g. '10MHz'. Defaults to spanning the beam range across nchan.",
        json_schema_extra={"abbreviation": "cw"},
    ),
    nchan: int | None = Field(
        None,
        description="Number of output channels in the to-fits cube. Defaults to the beam's channel count.",
        json_schema_extra={"abbreviation": "nc"},
    ),
    nworkers: int = Field(4, description="Number of worker threads."),
    log_level: str = Field("INFO", description="Logging verbosity."),
) -> PrimaryBeamOutputs:
    """Primary-beam utilities (build/tag/apply/correct); no visibility simulation.

    Transcribed from `simms.apps.primary_beam.primary_beam`; runs simms' own
    `simms.apps.primary_beam.runit` inside the simms container.
    """
    opts = _opts(locals())
    ctx.import_func("runit", "simms.apps.primary_beam")(opts)
    return PrimaryBeamOutputs(ms=ms, output=output)


def __getattr__(name: str):
    if name in {"skysim", "telsim"}:
        from dosho.registry import get

        return get(f"simms-{name}")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
