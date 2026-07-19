"""spimple -- simple image-plane spectral tools for radio interferometric
imaging (https://github.com/ratt-ru/spimple). One shared `SPIMPLE` image,
three sibling commands (`binterp`/`imconv`/`spifit`), matching cult-cargo's
`spimple_binterp.yml`/`spimple_imconv.yml`/`spimple-spifit.yml`.

Ported field-by-field from each real `--help` (spimple 0.0.5). Flags with
`nargs='+'` (`-ms`, `-pp`, `-cw`, `-cf`, `-db`) use `repeat_as_tokens` --
one flag occurrence, then each value as a bare token.
"""

from __future__ import annotations

from shinobi.steps.schema import ParamMeta, Policies

from dosho import images
from dosho._builder import FieldSpec, define_cab

_POLICIES = Policies(prefix="--")

# --- binterp -------------------------------------------------------------
_BINTERP_FIELDS: dict[str, FieldSpec] = {
    "image": (
        "File",
        True,
        None,
        ParamMeta(info="A FITS image providing the coordinates to interpolate to"),
    ),
    "ms": (
        "List[MS]",
        False,
        None,
        ParamMeta(
            info="Measurement set(s) used to make the image (for parallactic angles, primary beam correction)",
            repeat_as_tokens=True,
        ),
    ),
    "field": ("int", False, None, ParamMeta(info="Field ID")),
    "output_filename": (
        "str",
        True,
        None,
        ParamMeta(nom_de_guerre="output-filename", info="Path to output directory"),
    ),
    "beam_model": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="beam-model",
            info="FITS beam model to use: path up to name, e.g. /home/user/beams/meerkat_lband "
            "(pattern path_to_beam/name_corr_re/im.fits)",
        ),
    ),
    "sparsify_time": (
        "int",
        False,
        None,
        ParamMeta(nom_de_guerre="sparsify-time", info="Used to select a subset of time"),
    ),
    "nthreads": ("int", False, None, ParamMeta(info="Number of threads to use [0: all threads]")),
    "corr_type": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="corr-type", info="Correlation type: linear or circular"),
    ),
}

binterp = define_cab(
    "spimple-binterp",
    "spimple-binterp",
    images.SPIMPLE,
    _BINTERP_FIELDS,
    policies=_POLICIES,
    info="spimple-binterp: beam interpolation tool (https://github.com/ratt-ru/spimple)",
)

# --- imconv ----------------------------------------------------------------
_IMCONV_FIELDS: dict[str, FieldSpec] = {
    "image": ("File", True, None, ParamMeta(info="Input image")),
    "output_filename": (
        "str",
        True,
        None,
        ParamMeta(nom_de_guerre="output-filename", info="Path to output directory"),
    ),
    "products": (
        "str",
        False,
        None,
        ParamMeta(
            info="Outputs to write: c=restoring beam, i=convolved image, b=average power beam, "
            "w=beam**2 weight image [default: convolved image only]"
        ),
    ),
    "psf_pars": (
        "List[float]",
        False,
        None,
        ParamMeta(
            nom_de_guerre="psf-pars",
            info="Restoring beam FWHM as emaj emin pa [default: from the FITS header]",
            repeat_as_tokens=True,
        ),
    ),
    "nthreads": ("int", False, None, ParamMeta(info="Number of threads to use [0: all threads]")),
    "circ_psf": (
        "bool",
        False,
        None,
        ParamMeta(
            nom_de_guerre="circ-psf",
            info="Convolve with a circularised beam instead of elliptical",
        ),
    ),
    "dilate": (
        "float",
        False,
        None,
        ParamMeta(
            info="Dilate the psf-pars in the FITS header by this amount (sometimes needed for stability)"
        ),
    ),
    "beam_model": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="beam-model", info="FITS beam model to use (see power_beam_maker)"),
    ),
    "band": ("str", False, None, ParamMeta(info="Band to use with JimBeam: L, UHF or S")),
    "pb_min": (
        "float",
        False,
        None,
        ParamMeta(nom_de_guerre="pb-min", info="Set image to zero where pb falls below this value"),
    ),
    "padding_frac": (
        "float",
        False,
        None,
        ParamMeta(
            nom_de_guerre="padding-frac", info="Padding fraction for FFTs (half on either side)"
        ),
    ),
    "out_dtype": (
        "str",
        False,
        None,
        ParamMeta(info="Data type of output [default: single precision]"),
    ),
}

imconv = define_cab(
    "spimple-imconv",
    "spimple-imconv",
    images.SPIMPLE,
    _IMCONV_FIELDS,
    policies=_POLICIES,
    info="spimple-imconv: convolve images to a common resolution (https://github.com/ratt-ru/spimple)",
)

# --- spifit ------------------------------------------------------------
_SPIFIT_FIELDS: dict[str, FieldSpec] = {
    "model": ("List[File]", False, None, ParamMeta(info="Model image(s)", repeat_as_tokens=True)),
    "residual": (
        "List[File]",
        False,
        None,
        ParamMeta(info="Residual image(s)", repeat_as_tokens=True),
    ),
    "output_filename": (
        "str",
        True,
        None,
        ParamMeta(nom_de_guerre="output-filename", info="Path to output directory + prefix"),
    ),
    "psf_pars": (
        "List[float]",
        False,
        None,
        ParamMeta(
            nom_de_guerre="psf-pars",
            info="Restoring beam FWHM as emaj emin pa [default: from the residual's FITS header]",
            repeat_as_tokens=True,
        ),
    ),
    "circ_psf": (
        "bool",
        False,
        None,
        ParamMeta(
            nom_de_guerre="circ-psf",
            info="Convolve with a circularised beam instead of elliptical",
        ),
    ),
    "threshold": (
        "float",
        False,
        None,
        ParamMeta(
            info="Multiple of the residual rms to threshold on; only components above are fit"
        ),
    ),
    "maxDR": (
        "float",
        False,
        None,
        ParamMeta(
            info="Max dynamic range used to determine the threshold if no residual is passed in"
        ),
    ),
    "nthreads": ("int", False, None, ParamMeta(info="Number of threads to use [0: all threads]")),
    "pb_min": (
        "float",
        False,
        None,
        ParamMeta(nom_de_guerre="pb-min", info="Set image to zero where pb falls below this value"),
    ),
    "products": (
        "str",
        False,
        None,
        ParamMeta(
            info="Outputs to write: a=alpha, e=alpha error, i=I0, k=I0 error, I=reconstructed cube, "
            "c=restoring beam, m=convolved model, r=convolved residual, b=average power beam, "
            "d=data-model difference [default: all]"
        ),
    ),
    "padding_frac": (
        "float",
        False,
        None,
        ParamMeta(nom_de_guerre="padding-frac", info="Padding fraction for FFTs"),
    ),
    "dont_convolve": (
        "bool",
        False,
        None,
        ParamMeta(nom_de_guerre="dont-convolve", info="Bypass the convolution by the clean beam"),
    ),
    "channel_weights": (
        "List[float]",
        False,
        None,
        ParamMeta(
            info="Per-channel weights for the frequency-axis fit (only if no residual is passed in)",
            repeat_as_tokens=True,
        ),
    ),
    "channel_freqs": (
        "List[float]",
        False,
        None,
        ParamMeta(
            info="Per-channel freqs for the frequency-axis fit [default: from the FITS header]",
            repeat_as_tokens=True,
        ),
    ),
    "ref_freq": (
        "float",
        False,
        None,
        ParamMeta(nom_de_guerre="ref-freq", info="Reference frequency where the I0 map is sought"),
    ),
    "out_dtype": (
        "str",
        False,
        None,
        ParamMeta(info="Data type of output [default: single precision]"),
    ),
    "add_convolved_residuals": (
        "bool",
        False,
        None,
        ParamMeta(
            nom_de_guerre="add-convolved-residuals",
            info="Add in the convolved residuals before fitting components",
        ),
    ),
    "ms": (
        "List[MS]",
        False,
        None,
        ParamMeta(
            info="Measurement set(s) used to make the image (for parallactic angles, primary beam correction)",
            repeat_as_tokens=True,
        ),
    ),
    "field": ("int", False, None, ParamMeta(info="Field ID")),
    "beam_model": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="beam-model",
            info="FITS beam model to use: path up to name (pattern path_to_beam/name_corr_re/im.fits)",
        ),
    ),
    "sparsify_time": (
        "int",
        False,
        None,
        ParamMeta(nom_de_guerre="sparsify-time", info="Used to select a subset of time"),
    ),
    "corr_type": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="corr-type", info="Correlation type: linear or circular"),
    ),
    "band": ("str", False, None, ParamMeta(info="Band to use with JimBeam: L, UHF or S")),
    "deselect_bands": (
        "List[int]",
        False,
        None,
        ParamMeta(
            nom_de_guerre="deselect-bands",
            info="Indices of sub-bands to exclude from the fitting, e.g. 1 2",
            repeat_as_tokens=True,
        ),
    ),
}

spifit = define_cab(
    "spimple-spifit",
    "spimple-spifit",
    images.SPIMPLE,
    _SPIFIT_FIELDS,
    policies=_POLICIES,
    info="spimple-spifit: simple spectral index fitting tool (https://github.com/ratt-ru/spimple)",
)
