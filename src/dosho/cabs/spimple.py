"""spimple -- simple image-plane spectral tools for radio interferometric
imaging (https://github.com/ratt-ru/spimple). One shared `SPIMPLE` image,
three sibling commands (`binterp`/`imconv`/`spifit`), matching cult-cargo's
`spimple_binterp.yml`/`spimple_imconv.yml`/`spimple-spifit.yml`.

Ported field-by-field from each real `--help` (spimple 0.0.5). Flags with
`nargs='+'` (`-ms`, `-pp`, `-cw`, `-cf`, `-db`) use `repeat_as_tokens` --
one flag occurrence, then each value as a bare token.

**`output-filename` is a prefix, not a directory.** All three commands
describe it as "Path to output directory" in their own `--help`, and all
three use it as a filename stem. Source-verified against spimple v0.0.5, the
version `images.SPIMPLE` pins:

* `power_beam_maker.py` (binterp) writes it *verbatim* as a single FITS file
  -- `save_fits(opts.output_filename, beam_image, new_hdr)`, no suffix at all
  -- so it is the output path itself, declared here as a same-named
  passthrough output.
* `image_convolver.py` (imconv) and `spi_fitter.py` (spifit) both do
  `outfile = opts.output_filename` and then concatenate a fixed suffix per
  requested product letter (`outfile + '.convolved.fits'`, `outfile +
  '.alpha.fits'`, ...). Those suffixes are static, so each product becomes a
  real output field with a resolved `ParamMeta.implicit` template.

Taking the help text at its word would have declared all of these one path
level too high -- products declared under a directory the tool never writes.

Declaring them matters beyond output wiring: a write target that reaches
shinobi only as a `str` input contributes no bind mount, so an
`output-filename` outside the working directory would have its products
written inside the container and discarded on `docker run --rm`
(stimela-ninja issue #60). `bind_dir_modes` reads the output side --
`schema.declared_output_dirs`, i.e. exactly the `implicit` templates and
`harvest` globs below -- to mount it. The inputs stay `str` on purpose, so
they keep working relative under a sandbox.

`products` decides which subset a given run actually writes (imconv defaults
to the convolved image alone, spifit to all), so a pipeline wires the fields
matching its own `products` value -- the same "declare the family, let the
caller pick" arrangement as `wsclean.py`'s single-channel-vs-MFS fields. The
`harvest` glob on the two prefix-shaped commands covers the whole family in
one line for sandboxed runs, including the letters a pipeline never wires.
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

_BINTERP_OUTPUTS: dict[str, FieldSpec] = {
    # `save_fits(opts.output_filename, ...)` -- the value *is* the file, so a
    # same-named passthrough is the whole declaration. No 4th element: an
    # output-side `ParamMeta` would replace the input's `nom_de_guerre` and
    # stop emitting `--output-filename`.
    "output_filename": ("File", False, None),
}

binterp = define_cab(
    "spimple-binterp",
    "spimple-binterp",
    images.SPIMPLE,
    _BINTERP_FIELDS,
    outputs=_BINTERP_OUTPUTS,
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
        ParamMeta(
            nom_de_guerre="output-filename", info="Path to output directory", write_path=True
        ),
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

# One per `products` letter in `image_convolver.py`: c/i/b/w.
_IMCONV_OUTPUTS: dict[str, FieldSpec] = {
    "clean_psf": ("File", False, None, ParamMeta(implicit="{output_filename}.clean_psf.fits")),
    "convolved": ("File", False, None, ParamMeta(implicit="{output_filename}.convolved.fits")),
    "power_beam": ("File", False, None, ParamMeta(implicit="{output_filename}.power_beam.fits")),
    "spatial_weight": (
        "File",
        False,
        None,
        ParamMeta(implicit="{output_filename}.spatial_weight.fits"),
    ),
}

imconv = define_cab(
    "spimple-imconv",
    "spimple-imconv",
    images.SPIMPLE,
    _IMCONV_FIELDS,
    outputs=_IMCONV_OUTPUTS,
    policies=_POLICIES,
    harvest=["{output_filename}.*"],
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
        ParamMeta(
            nom_de_guerre="output-filename",
            info="Path to output directory + prefix",
            write_path=True,
        ),
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

# One per `products` letter in `spi_fitter.py`, mapping each letter from that
# flag's own help text to the suffix the tool concatenates:
# a=alpha, e=alpha error, i=I0, k=I0 error, I=reconstructed cube,
# c=restoring beam, m=convolved model, r=convolved residual,
# b=average power beam, d=data-model difference.
_SPIFIT_OUTPUTS: dict[str, FieldSpec] = {
    "alpha": ("File", False, None, ParamMeta(implicit="{output_filename}.alpha.fits")),
    "alpha_err": ("File", False, None, ParamMeta(implicit="{output_filename}.alpha_err.fits")),
    "i0": ("File", False, None, ParamMeta(implicit="{output_filename}.I0.fits")),
    "i0_err": ("File", False, None, ParamMeta(implicit="{output_filename}.I0_err.fits")),
    "irec_cube": ("File", False, None, ParamMeta(implicit="{output_filename}.Irec_cube.fits")),
    "clean_psf": ("File", False, None, ParamMeta(implicit="{output_filename}.clean_psf.fits")),
    "convolved_model": (
        "File",
        False,
        None,
        ParamMeta(implicit="{output_filename}.convolved_model.fits"),
    ),
    "convolved_residual": (
        "File",
        False,
        None,
        ParamMeta(implicit="{output_filename}.convolved_residual.fits"),
    ),
    "power_beam": ("File", False, None, ParamMeta(implicit="{output_filename}.power_beam.fits")),
    "fit_diff": ("File", False, None, ParamMeta(implicit="{output_filename}.fit_diff.fits")),
}

spifit = define_cab(
    "spimple-spifit",
    "spimple-spifit",
    images.SPIMPLE,
    _SPIFIT_FIELDS,
    outputs=_SPIFIT_OUTPUTS,
    policies=_POLICIES,
    harvest=["{output_filename}.*"],
    info="spimple-spifit: simple spectral index fitting tool (https://github.com/ratt-ru/spimple)",
)
