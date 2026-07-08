"""wsclean -- WSClean imager (https://wsclean.readthedocs.io).

Ported from cult-cargo's `wsclean.yml`/`genesis/wsclean/wsclean-base.yml`
(the real ~168-parameter schema, cross-checked field-by-field against that
YAML), NOT via `dynamic_schema` -- shinobi never imports/executes
`cultcargo.genesis.wsclean.make_stimela_schema`. Two things that YAML's
own schema can't express without running that function are handled here
declaratively instead:

* `Union[...]`/`Tuple[...]`-typed fields (`size`, `scale`, `weight`,
  `channel-range`, `interval`, `beam-shape`, ...) resolve to real Python
  union/tuple types (`shinobi.loaders._modelgen.dtype_to_type` gained
  `Tuple[...]`/`Union[...]` support for this) instead of cult-cargo-loader's
  silent fallback to plain `str` -- so e.g. `weight=("briggs", 0.5)` or
  `size=(4096, 4096)` are real typed values, not hand-formatted strings.
* wsclean's output *paths* depend on which of `nchan`/`pol`/`intervals-out`
  are set -- cult-cargo's `make_stimela_schema` computes the real output
  dict at run time. Instead, the single-channel/single-interval/Stokes-I
  case (`dirty`/`image`/`residual`/`model`/`psf`) and the MFS
  multi-channel case (`*_mfs`) are declared as real `outputs_model` fields
  with a `ParamMeta.implicit` `{prefix}-...`/`{prefix}-MFS-...` template,
  resolved by `shinobi.steps.dispatch._fill_outputs` via plain
  `str.format` -- no eval, no imported tool code. A pipeline picks
  whichever field matches its own `nchan`/`join-channels` config. Anything
  more exotic (per-band, per-interval, per-Stokes combinations) is
  deliberately left validation-only via `output_patterns`, same as the
  stopgap this replaces (`shinobi.loaders.cultcargo._WSCLEAN_IMAGETYPES`).

`source-list`/`temp-dir` are wsclean's own declared (non-dynamic) outputs
from `base-outputs`, ported as-is.
"""

from __future__ import annotations

from shinobi.steps.schema import ParamMeta, ParamPattern, ParamSegment, Policies

from dosho import images
from dosho._builder import define_cab

_FIELDS: dict[str, tuple[str, bool, object]] = {
    "ms": ("List[MS]", True, None),
    "prefix": ("str", True, None),
    "column": ("str", False, "DATA"),
    "model-column": ("str", False, None),
    "model-storage-manager": ("str", False, None),
    "nchan": ("int", False, None),
    "deconvolution-channels": ("int", False, None),
    "channel-range": ("Tuple[int, int]", False, None),
    "channel-division-frequencies": ("List[float]", False, None),
    "gap-channel-division": ("bool", False, None),
    "pol": ("Union[str, List[str]]", False, None),
    "join-polarizations": ("bool", False, None),
    "link-polarizations": ("Union[str, List[str]]", False, None),
    "intervals-out": ("int", False, None),
    "interval": ("Tuple[int, int]", False, None),
    "even-timesteps": ("bool", False, None),
    "odd-timesteps": ("bool", False, None),
    "field": ("Union[str, List[int]]", False, None),
    "spws": ("List[int]", False, None),
    "threads": ("int", False, None),
    "parallel-gridding": ("int", False, None),
    "parallel-reordering": ("int", False, None),
    "no-work-on-master": ("bool", False, None),
    "channel-to-node": ("List[int]", False, None),
    "max-mpi-message-size": ("str", False, None),
    "mem": ("int", False, None),
    "abs-mem": ("int", False, None),
    "verbose": ("bool", False, None),
    "log-time": ("bool", False, None),
    "quiet": ("bool", False, None),
    "reorder": ("bool", False, None),
    "no-reorder": ("bool", False, None),
    "reuse-reordered": ("bool", False, None),
    "save-reordered": ("bool", False, None),
    "update-model-required": ("bool", False, None),
    "no-update-model-required": ("bool", False, None),
    "no-dirty": ("bool", False, None),
    "save-first-residual": ("bool", False, None),
    "save-weights": ("bool", False, None),
    "save-uv": ("bool", False, None),
    "reuse-psf": ("str", False, None),
    "reuse-dirty": ("str", False, None),
    "make-psf": ("bool", False, None),
    "make-psf-only": ("bool", False, None),
    "weight": ("Union[str, Tuple[str, float]]", False, None),
    "super-weight": ("float", False, None),
    "mf-weighting": ("bool", False, None),
    "no-mf-weighting": ("bool", False, None),
    "weighting-rank-filter": ("float", False, None),
    "weighting-rank-filter-size": ("int", False, None),
    "taper-gaussian": ("str", False, None),
    "taper-tukey": ("float", False, None),
    "taper-inner-tukey": ("float", False, None),
    "taper-edge": ("float", False, None),
    "taper-edge-tukey": ("float", False, None),
    "use-weights-as-taper": ("bool", False, None),
    "store-imaging-weights": ("bool", False, None),
    "size": ("Union[int, Tuple[int, int]]", True, None),
    "padding": ("float", False, None),
    "scale": ("Union[str, float]", True, None),
    "predict": ("bool", False, None),
    "continue": ("bool", False, None),
    "subtract-model": ("bool", False, None),
    "gridder": ("str", False, None),
    "use-wgridder": ("bool", False, None),
    "shift": ("List[str]", False, None),
    "facet-regions": ("File", False, None),
    "feather-size": ("int", False, None),
    "no-min-grid-resolution": ("bool", False, None),
    "min-grid-resolution": ("bool", False, None),
    "visibility-weighting-mode": ("str", False, None),
    "baseline-averaging": ("float", False, None),
    "simulate-noise": ("float", False, None),
    "simulate-baseline-noise": ("File", False, None),
    "idg-mode": ("str", False, None),
    "wstack-nwlayers": ("int", False, None),
    "wstack-nwlayers-factor": ("float", False, None),
    "wstack-nwlayers-for-size": ("List[int]", False, None),
    "wstack-grid-mode": ("str", False, None),
    "wstack-kernel-size": ("int", False, None),
    "wstack-oversampling": ("int", False, None),
    "wgridder-accuracy": ("float", False, None),
    "compound-tasks": ("bool", False, None),
    "shared-facet-reads": ("bool", False, None),
    "aterm-config": ("File", False, None),
    "grid-with-beam": ("bool", False, None),
    "beam-aterm-update": ("int", False, None),
    "aterm-kernel-size": ("float", False, None),
    "apply-facet-solutions": ("List[Union[File, str]]", False, None),
    "no-solution-directions-check": ("bool", False, None),
    "scalar-visibilities": ("bool", False, None),
    "diagonal-visibilities": ("bool", False, None),
    "apply-facet-beam": ("bool", False, None),
    "facet-beam-update": ("int", False, None),
    "save-aterms": ("bool", False, None),
    "apply-primary-beam": ("bool", False, None),
    "reuse-primary-beam": ("bool", False, None),
    "use-differential-lofar-beam": ("bool", False, None),
    "primary-beam-limit": ("float", False, None),
    "scalar-beam": ("bool", False, None),
    "mwa-path": ("Directory", False, None),
    "save-psf-pb": ("bool", False, None),
    "pb-grid-size": ("int", False, None),
    "dd-psf-grid": ("List[int]", False, None),
    "beam-model": ("str", False, None),
    "beam-mode": ("str", False, None),
    "beam-normalisation-mode": ("str", False, None),
    "dry-run": ("bool", False, None),
    "maxuvw-m": ("float", False, None),
    "minuvw-m": ("float", False, None),
    "maxuv-l": ("float", False, None),
    "minuv-l": ("float", False, None),
    "maxw": ("float", False, None),
    "niter": ("int", False, None),
    "nmiter": ("int", False, None),
    "auto-threshold": ("float", False, None),
    "abs-threshold": ("float", False, None),
    "auto-mask": ("float", False, None),
    "abs-auto-mask": ("float", False, None),
    "local-rms": ("bool", False, None),
    "local-rms-strength": ("float", False, None),
    "local-rms-window": ("int", False, None),
    "local-rms-method": ("str", False, None),
    "gain": ("float", False, None),
    "mgain": ("float", False, None),
    "join-channels": ("bool", False, None),
    "spectral-correction": ("List[Union[float, str]]", False, None),
    "no-fast-subminor": ("bool", False, None),
    "multiscale": ("bool", False, None),
    "multiscale-scale-bias": ("float", False, None),
    "multiscale-max-scales": ("int", False, None),
    "multiscale-scales": ("List[float]", False, None),
    "multiscale-shape": ("str", False, None),
    "multiscale-gain": ("float", False, None),
    "multiscale-convolution-padding": ("float", False, None),
    "asp": ("bool", False, None),
    "no-multiscale-fast-subminor": ("bool", False, None),
    "python-deconvolution": ("File", False, None),
    "iuwt": ("bool", False, None),
    "iuwt-snr-test": ("bool", False, None),
    "no-iuwt-snr-test": ("bool", False, None),
    "moresane-ext": ("Directory", False, None),
    "moresane-arg": ("str", False, None),
    "moresane-sl": ("List[float]", False, None),
    "save-source-list": ("bool", False, None),
    "clean-border": ("float", False, None),
    "fits-mask": ("File", False, None),
    "casa-mask": ("File", False, None),
    "horizon-mask": ("str", False, None),
    "no-negative": ("bool", False, None),
    "negative": ("bool", False, None),
    "stop-negative": ("bool", False, None),
    "fit-spectral-pol": ("int", False, None),
    "fit-spectral-log-pol": ("int", False, None),
    "force-spectrum": ("File", False, None),
    "squared-channel-joining": ("bool", False, None),
    "parallel-deconvolution": ("int", False, None),
    "deconvolution-threads": ("int", False, None),
    "restore": ("List[File]", False, None),
    "restore-list": ("List[File]", False, None),
    "beam-size": ("float", False, None),
    "beam-shape": ("List[Union[str, float]]", False, None),
    "fit-beam": ("bool", False, None),
    "no-fit-beam": ("bool", False, None),
    "beam-fitting-size": ("float", False, None),
    "theoretic-beam": ("bool", False, None),
    "circular-beam": ("bool", False, None),
    "elliptical-beam": ("bool", False, None),
}

_FIELD_META: dict[str, ParamMeta] = {
    "ms": ParamMeta(positional=True, repeat_as_tokens=True),
    "prefix": ParamMeta(nom_de_guerre="name"),
    "column": ParamMeta(nom_de_guerre="data-column"),
    "channel_range": ParamMeta(repeat_as_tokens=True),
    "channel_division_frequencies": ParamMeta(repeat_as_tokens=True),
    "interval": ParamMeta(repeat_as_tokens=True),
    "threads": ParamMeta(nom_de_guerre="j"),
    "verbose": ParamMeta(nom_de_guerre="v"),
    "weight": ParamMeta(repeat_as_tokens=True),
    "size": ParamMeta(repeat_as_tokens=True),
    "shift": ParamMeta(repeat_as_tokens=True),
    "wstack_nwlayers": ParamMeta(nom_de_guerre="nwlayers"),
    "wstack_nwlayers_factor": ParamMeta(nom_de_guerre="nwlayers-factor"),
    "wstack_nwlayers_for_size": ParamMeta(repeat_as_tokens=True),
    "apply_facet_solutions": ParamMeta(repeat_as_tokens=True),
    "dd_psf_grid": ParamMeta(repeat_as_tokens=True),
    "abs_threshold": ParamMeta(nom_de_guerre="threshold"),
    "spectral_correction": ParamMeta(repeat_as_tokens=True),
    "restore": ParamMeta(repeat_as_tokens=True),
    "restore_list": ParamMeta(repeat_as_tokens=True),
    "beam_shape": ParamMeta(repeat_as_tokens=True),
    # dynamic output paths -- see module docstring.
    "dirty": ParamMeta(implicit="{prefix}-dirty.fits"),
    "image": ParamMeta(implicit="{prefix}-image.fits"),
    "residual": ParamMeta(implicit="{prefix}-residual.fits"),
    "model": ParamMeta(implicit="{prefix}-model.fits"),
    "psf": ParamMeta(implicit="{prefix}-psf.fits"),
    "dirty_mfs": ParamMeta(implicit="{prefix}-MFS-dirty.fits"),
    "image_mfs": ParamMeta(implicit="{prefix}-MFS-image.fits"),
    "residual_mfs": ParamMeta(implicit="{prefix}-MFS-residual.fits"),
    "model_mfs": ParamMeta(implicit="{prefix}-MFS-model.fits"),
    "psf_mfs": ParamMeta(implicit="{prefix}-MFS-psf.fits"),
    "source_list": ParamMeta(nom_de_guerre="source-list"),
    "temp_dir": ParamMeta(nom_de_guerre="temp-dir"),
}

_OUTPUTS: dict[str, tuple[str, bool, object]] = {
    "dirty": ("File", False, None),
    "image": ("File", False, None),
    "residual": ("File", False, None),
    "model": ("File", False, None),
    "psf": ("File", False, None),
    "dirty_mfs": ("File", False, None),
    "image_mfs": ("File", False, None),
    "residual_mfs": ("File", False, None),
    "model_mfs": ("File", False, None),
    "psf_mfs": ("File", False, None),
    "source_list": ("File", False, None),
    "temp_dir": ("Directory", False, None),
}

# Validation-only catch-all for the combinatorial output names wsclean's
# own `dynamic_schema` can produce beyond the handful resolved above (e.g.
# "dirty.per-band", "restored.i.per-interval.mfs") -- accepted by
# `recipe.outputs(step, name)` without raising, never resolved to a path.
_OUTPUT_PATTERNS = [
    ParamPattern(
        separator=".",
        segments=[
            ParamSegment(
                attrs={
                    "dirty": ParamMeta(dtype="File"),
                    "image": ParamMeta(dtype="File"),
                    "restored": ParamMeta(dtype="File"),
                    "residual": ParamMeta(dtype="File"),
                    "model": ParamMeta(dtype="File"),
                    "psf": ParamMeta(dtype="File"),
                }
            ),
            ParamSegment(regex=r".+"),
        ],
    )
]

wsclean = define_cab(
    "wsclean",
    "wsclean",
    images.WSCLEAN,
    _FIELDS,
    outputs=_OUTPUTS,
    field_meta=_FIELD_META,
    policies=Policies(prefix="-", replace={"_": "-"}),
    output_patterns=_OUTPUT_PATTERNS,
    info="WSClean imager (https://wsclean.readthedocs.io)",
)
