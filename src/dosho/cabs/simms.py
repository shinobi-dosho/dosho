"""simms -- simms 3.0's sub-commands, one module-level object per
sub-command (matching `casatasks.py`'s multi-export convention).

`skysim` (simms 3.0's sky-model visibility simulator, replacing caracal
1.x's separate simulator worker -- see stimela-ninja/caracal migration
notes: simulator -> simms 3.0 skysim) is the only sub-command ported so
far, transcribed field-by-field from cult-cargo's simms.yml. That file
also declares `simms-telsim`/`simms` cabs -- not yet ported; add them
here as `telsim`/`simms` when a pipeline needs them.
"""

from __future__ import annotations

from shinobi.steps.schema import ParamMeta, Policies

from dosho import images
from dosho._builder import define_cab

_FIELDS: dict[str, tuple[str, bool, object]] = {
    "ms": ("MS", True, None),
    "ascii_sky": ("File", False, None),
    "fits_sky": ("Union[File, List[File]]", False, None),
    "fits_sky_interp": ("str", False, "nearest"),
    "polarisation": ("bool", False, True),
    "pol_basis": ("str", False, "linear"),
    "pixel_tol": ("float", False, "1e-7"),
    "fft_precision": ("str", False, "double"),
    "do_wstacking": ("bool", False, True),
    "ascii_delimiter": ("str", False, None),
    "column": ("str", False, "DATA"),
    "nworkers": ("int", False, 4),
    "row_chunks": ("int", False, 10000),
    "field_id": ("int", False, 0),
    "spw_id": ("int", False, 0),
    "sefd": ("float", False, None),
    "ascii_species": ("str", False, None),
    "input_column": ("str", False, None),
    "mode": ("str", False, "sim"),
    "source_schema": ("File", False, None),
}

_FIELD_META: dict[str, ParamMeta] = {
    "ms": ParamMeta(info="Measurement set", positional=True),
    "ascii_sky": ParamMeta(
        nom_de_guerre="ascii-sky",
        info="Catalogue of sources. A full description of accepted units can be found in the documentation.",
    ),
    "fits_sky": ParamMeta(nom_de_guerre="fits-sky", info="FITS file(s) containing the sky model"),
    "fits_sky_interp": ParamMeta(
        nom_de_guerre="fits-sky-interp",
        info="Interpolation method when MS and FITS image grids do not match. Interpolation is only done within the overlap region.",
    ),
    "polarisation": ParamMeta(
        info="Simulate all available stokes parameters (correlations). If false, only consider stokes I"
    ),
    "pol_basis": ParamMeta(
        nom_de_guerre="pol-basis",
        info="Polarization basis for the simulation. The default is circular polarization.",
    ),
    "pixel_tol": ParamMeta(
        nom_de_guerre="pixel-tol",
        info="minimum brightness for a pixel to be considered in direct Fourier transform",
    ),
    "fft_precision": ParamMeta(
        nom_de_guerre="fft-precision",
        info="Precision of the FFT calculation. The default is double precision.",
    ),
    "do_wstacking": ParamMeta(
        nom_de_guerre="do-wstacking",
        info="Whether to use w-stacking for FFT-based visibility prediction.",
    ),
    "ascii_delimiter": ParamMeta(
        nom_de_guerre="ascii-delimiter", info="Delimiter that is used in the ascii-sky"
    ),
    "column": ParamMeta(info="Data column for simulation"),
    "nworkers": ParamMeta(info="Number of workers (one per CPU)"),
    "row_chunks": ParamMeta(
        nom_de_guerre="row-chunks", info="Chunking strategy for the simulation"
    ),
    "field_id": ParamMeta(nom_de_guerre="field-id", info="Field ID"),
    "spw_id": ParamMeta(nom_de_guerre="spw-id", info="Spectral Window ID"),
    "sefd": ParamMeta(info="Add noise using the this SEFD value"),
    "ascii_species": ParamMeta(nom_de_guerre="ascii-species", info="Non-simms sky model type."),
    "input_column": ParamMeta(
        nom_de_guerre="input-column", info="Input column (see option --mode)"
    ),
    "mode": ParamMeta(
        info='Simulation mode. To create a new column use "sim"; to add to column use "add"; to subtract from column use "subtract".'
    ),
    "source_schema": ParamMeta(
        info="Specify a custom source schema via a YAML file that specifies how to map columns in custom sky model to the columns expected by simms. See the bdsf_gaul schema file at 'https://github.com/wits-cfa/simms/tree/main/simms/schemas'"
    ),
}

skysim = define_cab(
    "simms-skysim",
    "simms skysim",
    images.SIMMS,
    _FIELDS,
    field_meta=_FIELD_META,
    policies=Policies(),
    info="simms skysim: simulate visibilities from a sky model (simms 3.0)",
)
