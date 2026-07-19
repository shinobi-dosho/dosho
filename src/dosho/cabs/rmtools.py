"""RM-Tools -- Faraday rotation measure synthesis/CLEAN
(https://github.com/CIRADA-Tools/RM-Tools). One shared `RM_TOOLS` image,
three sibling commands (`rmsynth1d`/`rmsynth3d`/`rmclean3d`), the same
"one image, several module-level cabs" shape as `simms.py`/`casatasks.py`.

Ported field-by-field from each tool's own `--help` (RM-Tools 1.4.11), not
cult-cargo's `rmsynth1d.yml`/`rmsynth3d.yml`/`rmclean3d.yml`: those are
stale relative to the current CLI in ways that would silently
mis-transcribe real flags -- e.g. cult-cargo's `rmsynth1d.yml` has `-f`
meaning "max Faraday depth" and `-l` meaning "channel width", the reverse
of the real tool (`-l PHIMAX_RADM2`, `-f FIT_FUNCTION`); `rmsynth3d.yml`
declares its three positional FITS/frequency arguments as ordinary `--`
flags (the real CLI takes them positionally); and `rmclean3d.yml`'s
`ncores`/`chunk`/`mpi` have no `nom_de_guerre`, so under its own `prefix:
'-'` policy they'd emit as `-ncores` etc, which the real (long-flag-only)
CLI doesn't recognise.

All three tools use single-dash short flags under a `prefix="-"` policy;
`rmclean3d`'s `--ncores`/`--chunk`/`--mpi` have no short form, so their
`nom_de_guerre` embeds the second dash (`"-ncores"` -> `"-" + "-ncores"` =
`"--ncores"`) rather than switching the whole cab to a `--` prefix.
"""

from __future__ import annotations

from shinobi.steps.schema import ParamMeta, Policies

from dosho import images
from dosho._builder import FieldSpec, define_cab

_POLICIES = Policies(prefix="-")

# --- rmsynth1d ---------------------------------------------------------------
_RMSYNTH1D_FIELDS: dict[str, FieldSpec] = {
    "data_file": (
        "File",
        True,
        None,
        ParamMeta(
            info="ASCII file containing Stokes spectra & errors: [freq_Hz, I, Q, U, I_err, Q_err, U_err] "
            "or [freq_Hz, Q, U, Q_err, U_err]",
            positional=True,
        ),
    ),
    "fit_rmsf_gaussian": (
        "bool",
        False,
        None,
        ParamMeta(nom_de_guerre="t", info="Fit a Gaussian to the RMSF"),
    ),
    "max_faraday_depth": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="l", info="Absolute max Faraday depth sampled [Auto if not set]"
        ),
    ),
    "dphi_radm2": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="d",
            info="Width of Faraday depth channel [Auto if not set] (overrides nsamples)",
        ),
    ),
    "nsamples": (
        "int",
        False,
        10,
        ParamMeta(nom_de_guerre="s", info="Number of samples across the RMSF lobe"),
    ),
    "weight_type": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="w", info="Weighting: inverse 'variance' [default] or 'uniform' (all 1s)"
        ),
    ),
    "fit_function": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="f",
            info="Stokes I fitting function: 'linear' or 'log' [default] polynomials",
        ),
    ),
    "poly_order": (
        "int",
        False,
        2,
        ParamMeta(
            nom_de_guerre="o",
            info="Polynomial order to fit to the I spectrum: 0-5, or negative for dynamic order selection",
        ),
    ),
    "ignore_stokes_i": (
        "bool",
        False,
        None,
        ParamMeta(nom_de_guerre="i", info="Ignore the Stokes I spectrum"),
    ),
    "use_64bit": (
        "bool",
        False,
        None,
        ParamMeta(
            nom_de_guerre="b", info="Use 64-bit floating point precision [default: 32-bit]"
        ),
    ),
    "show_plots": ("bool", False, None, ParamMeta(nom_de_guerre="p", info="Show the plots")),
    "verbose": ("bool", False, None, ParamMeta(nom_de_guerre="v", info="Verbose output")),
    "save_outputs": (
        "bool",
        False,
        None,
        ParamMeta(nom_de_guerre="S", info="Save the arrays and plots"),
    ),
    "debug": (
        "bool",
        False,
        None,
        ParamMeta(nom_de_guerre="D", info="Turn on debugging messages & plots"),
    ),
    "units": (
        "str",
        False,
        "Jy/beam",
        ParamMeta(nom_de_guerre="U", info="Intensity units of the data"),
    ),
    "super_resolution": (
        "bool",
        False,
        None,
        ParamMeta(
            nom_de_guerre="r", info="Optimise the resolution of the RMSF (Rudnick & Cotton)"
        ),
    ),
}

rmsynth1d = define_cab(
    "rmsynth1d",
    "rmsynth1d",
    images.RM_TOOLS,
    _RMSYNTH1D_FIELDS,
    policies=_POLICIES,
    info="RM-Tools rmsynth1d: RM-synthesis on Stokes I/Q/U spectra (1D, ASCII)",
)

# --- rmsynth3d ---------------------------------------------------------------
_RMSYNTH3D_FIELDS: dict[str, FieldSpec] = {
    "stokes_q": (
        "File",
        True,
        None,
        ParamMeta(info="FITS cube containing Stokes Q data", positional=True),
    ),
    "stokes_u": (
        "File",
        True,
        None,
        ParamMeta(info="FITS cube containing Stokes U data", positional=True),
    ),
    "freqs": (
        "File",
        True,
        None,
        ParamMeta(info="ASCII file containing the frequency vector (Hz)", positional=True),
    ),
    "stokes_i_model": (
        "File",
        False,
        None,
        ParamMeta(nom_de_guerre="i", info="FITS cube containing a Stokes I model [None]"),
    ),
    "noise_file": (
        "File",
        False,
        None,
        ParamMeta(nom_de_guerre="n", info="Text file containing channel noise values [None]"),
    ),
    "weight_type": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="w", info="Weighting: 'uniform' [default] (all 1s) or 'variance'"
        ),
    ),
    "fit_rmsf_gaussian": (
        "bool",
        False,
        None,
        ParamMeta(nom_de_guerre="t", info="Fit a Gaussian to the RMSF"),
    ),
    "max_faraday_depth": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="l",
            info="Absolute max Faraday depth sampled (overrides nsamples) [Auto if not set]",
        ),
    ),
    "dphi_radm2": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="d", info="Width of Faraday depth channel [Auto if not set]"),
    ),
    "prefix_out": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="o", info="Prefix to prepend to output files [None]"),
    ),
    "nsamples": (
        "int",
        False,
        None,
        ParamMeta(nom_de_guerre="s", info="Number of samples across the FWHM RMSF"),
    ),
    "fits_extensions": (
        "bool",
        False,
        None,
        ParamMeta(
            nom_de_guerre="f",
            info="Store different Stokes as FITS extensions [default: separate files]",
        ),
    ),
    "verbose": ("bool", False, None, ParamMeta(nom_de_guerre="v", info="Verbose output")),
    "skip_rmsf": (
        "bool",
        False,
        None,
        ParamMeta(nom_de_guerre="R", info="Skip calculation of the RMSF"),
    ),
    "super_resolution": (
        "bool",
        False,
        None,
        ParamMeta(
            nom_de_guerre="r", info="Optimise the resolution of the RMSF (Rudnick & Cotton)"
        ),
    ),
}

rmsynth3d = define_cab(
    "rmsynth3d",
    "rmsynth3d",
    images.RM_TOOLS,
    _RMSYNTH3D_FIELDS,
    policies=_POLICIES,
    info="RM-Tools rmsynth3d: RM-synthesis on Stokes Q/U cubes (3D)",
)

# --- rmclean3d ---------------------------------------------------------------
_RMCLEAN3D_FIELDS: dict[str, FieldSpec] = {
    "fdf_dirty": (
        "File",
        True,
        None,
        ParamMeta(
            info="FITS cube containing the dirty FDF (any FDF output cube from rmsynth3d)",
            positional=True,
        ),
    ),
    "rmsf": (
        "File",
        True,
        None,
        ParamMeta(
            info="FITS cube containing the RMSF and FWHM image (any RMSF output cube from rmsynth3d, not _FWHM.fits)",
            positional=True,
        ),
    ),
    "cutoff": (
        "float",
        False,
        1.0,
        ParamMeta(nom_de_guerre="c", info="Initial CLEAN cutoff in flux units"),
    ),
    "window": (
        "float",
        False,
        None,
        ParamMeta(
            nom_de_guerre="w", info="Threshold for (deeper) windowed clean [not used if not set]"
        ),
    ),
    "max_iter": (
        "int",
        False,
        1000,
        ParamMeta(nom_de_guerre="n", info="Maximum number of CLEAN iterations per pixel"),
    ),
    "gain": ("float", False, 0.1, ParamMeta(nom_de_guerre="g", info="CLEAN loop gain")),
    "prefix_out": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="o", info="Prefix to prepend to output files [None]"),
    ),
    "fits_extensions": (
        "bool",
        False,
        None,
        ParamMeta(
            nom_de_guerre="f",
            info="Store different Stokes as FITS extensions [default: separate files]",
        ),
    ),
    "verbose": ("bool", False, None, ParamMeta(nom_de_guerre="v", info="Verbose output")),
    # Long-flag-only options (no short form) -- embed the second dash in
    # nom_de_guerre since the cab's shared policy prefix is "-" (see module
    # docstring).
    "ncores": (
        "int",
        False,
        None,
        ParamMeta(nom_de_guerre="-ncores", info="Number of processes (uses multiprocessing)"),
    ),
    "chunk": (
        "int",
        False,
        None,
        ParamMeta(
            nom_de_guerre="-chunk",
            info="Chunk size (uses multiprocessing -- not available in MPI)",
        ),
    ),
    "mpi": ("bool", False, None, ParamMeta(nom_de_guerre="-mpi", info="Run with MPI")),
}

rmclean3d = define_cab(
    "rmclean3d",
    "rmclean3d",
    images.RM_TOOLS,
    _RMCLEAN3D_FIELDS,
    policies=_POLICIES,
    info="RM-Tools rmclean3d: RM-CLEAN on a cube of Faraday dispersion functions",
)
