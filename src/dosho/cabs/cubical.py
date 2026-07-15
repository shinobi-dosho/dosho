"""cubical -- CubiCal calibration package (https://github.com/ratt-ru/CubiCal).

Ported from cult-cargo's `cubical.yml`/`genesis/cubical/schema.yaml`
(the real 135-parameter flat schema, cross-checked field-by-field against
that YAML), NOT via `dynamic_schema` -- shinobi never imports/executes
`cultcargo.genesis.cubical.make_stimela_schema`, and never resolves the
package-scoped `_include: (cultcargo.genesis.cubical)schema.yaml` cult-cargo's
own loader can't load either (see `shinobi.loaders.cultcargo`'s own
`CabLoadError` for that form of `_include`).

Two structural differences from the cult-cargo source:

* `schema.yaml`'s nested CLI sections (`data:`/`sel:`/`out:`/`sol:`/...)
  are flattened into real CubiCal flag names by joining with `-`
  (`data.ms` -> `data-ms`, matching CubiCal's actual `--data-ms` CLI flag,
  not a dotted stimela2-internal name) -- this is real, not shinobi-loader
  flattening, since sanitising `"data-ms"` to the pydantic field
  `data_ms` and keeping `"data-ms"` as its `nom_de_guerre` is exactly
  `dosho._builder.define_cab`'s existing auto-derivation.
* The per-solvable-Jones-term parameter family (`g1-solvable`, `g-type`,
  `g-time-int`, ...) is declared as a single `ParamPattern`, transcribed
  from `schema_JONES_TEMPLATE.yaml`'s 37 attrs -- the term names
  themselves (`g1`, `g`, `dE`, ...) are chosen per pipeline call, not
  fixed by CubiCal, so no static field could ever enumerate them (see
  `shinobi.ParamPattern`'s own docstring, which names CubiCal by name as
  the motivating example). This replaces the hand-rolled, `allow_extra`-
  escape-hatch `Cab` caracal2's `selfcal` worker built as a bypass for
  cult-cargo's unloadable schema, and the equivalent stopgap table in
  `shinobi.loaders.cultcargo._dynamic_input_patterns`.

Real CubiCal output (in `sc`/`sr`/`ss` out-mode) is corrected
visibilities written back into the *same* input MS, not a new file --
`ms` is declared as a real output field with `implicit="{data_ms}"`
(a passthrough of the resolved input, not a synthetic hack: this is
CubiCal's actual in-place-mutation behaviour), so a downstream step can
wire a real dependency on "this MS has been calibrated" instead of the
`allow_extra`/synthetic-field workaround the pre-dosho port used.

`parset` mirrors real cult-cargo's own `cubical.yml` (`parset: {dtype:
File, policies: {positional_head: true}}`) -- and for the same real
reason: `cubical/main.py`'s own `main()` checks `sys.argv[1]` literally
(`if len(sys.argv) > 1 and not sys.argv[1][0].startswith('-'):
custom_parset_file = sys.argv[1]`), not "any leftover non-flag token"
the way `DDF.py`'s optparse-based leftover-arg collection does (see
`ddfacet.py`'s docstring). A plain tail `positional` (shinobi's default,
always emitted after every flag) would only be seen as the parset when
it's the *sole* argument -- pair it with any other override flag and
`sys.argv[1]` is that flag instead, `custom_parset_file` stays unset, and
CubiCal's own leftover-arg-count check (`if len(parser.get_arguments())
!= (1 if custom_parset_file else 0): raise UserInputError("Unexpected
number of arguments...")`) then rejects the run outright, since the
trailing parset token is still there as an unrecognised leftover.
`ParamMeta(positional_head=True)` (shinobi's scabha-derived `policies:
{positional_head: true}` equivalent -- see `shinobi.steps.schema.ParamMeta`)
emits it before every flag instead, which is what `sys.argv[1]` actually
needs.
"""

from __future__ import annotations

from shinobi.steps.schema import ParamMeta, ParamPattern, ParamSegment, Policies

from dosho import images
from dosho._builder import define_cab

_FIELDS: dict[str, tuple[str, bool, object]] = {
    "parset": ("File", False, None),
    "data-ms": ("MS", True, None),
    "data-column": ("str", False, None),
    "data-time-chunk": ("str", False, None),
    "data-freq-chunk": ("str", False, None),
    "data-rebin-time": ("str", False, None),
    "data-rebin-freq": ("str", False, None),
    "data-chunk-by": ("str", False, None),
    "data-chunk-by-jump": ("str", False, None),
    "data-single-chunk": ("str", False, None),
    "data-single-tile": ("int", False, None),
    "data-normalize": ("str", False, None),
    "sel-field": ("int", False, None),
    "sel-ddid": ("str", False, None),
    "sel-taql": ("str", False, None),
    "sel-chan": ("str", False, None),
    "sel-diag": ("bool", False, None),
    "out-dir": ("str", False, None),
    "out-name": ("str", False, None),
    "out-overwrite": ("bool", False, None),
    "out-backup": ("str", False, None),
    "out-mode": ("str", False, None),
    "out-apply-solver-flags": ("bool", False, None),
    "out-column": ("str", False, None),
    "out-derotate": ("str", False, None),
    "out-model-column": ("str", False, None),
    "out-weight-column": ("str", False, None),
    "out-reinit-column": ("bool", False, None),
    "out-subtract-model": ("str", False, None),
    "out-subtract-dirs": ("str", False, None),
    "out-correct-dir": ("str", False, None),
    "out-plots": ("str", False, None),
    "out-casa-gaintables": ("bool", False, None),
    "model-list": ("str", False, None),
    "model-ddes": ("str", False, None),
    "model-beam-pattern": ("str", False, None),
    "model-beam-l-axis": ("str", False, None),
    "model-beam-m-axis": ("str", False, None),
    "model-feed-rotate": ("str", False, None),
    "model-pa-rotate": ("bool", False, None),
    "model-null-v": ("str", False, None),
    "montblanc-device-type": ("str", False, None),
    "montblanc-dtype": ("str", False, None),
    "montblanc-mem-budget": ("int", False, None),
    "montblanc-verbosity": ("str", False, None),
    "montblanc-threads": ("int", False, None),
    "montblanc-pa-rotate": ("str", False, None),
    "weight-column": ("str", False, None),
    "weight-fill-offdiag": ("bool", False, None),
    "weight-legacy-v1-2": ("bool", False, None),
    "flags-apply": ("str", False, None),
    "flags-auto-init": ("str", False, None),
    "flags-save": ("str", False, None),
    "flags-save-legacy": ("str", False, None),
    "flags-reinit-bitflags": ("bool", False, None),
    "flags-warn-thr": ("str", False, None),
    "flags-see-no-evil": ("str", False, None),
    "degridding-OverS": ("int", False, None),
    "degridding-Support": ("int", False, None),
    "degridding-Nw": ("int", False, None),
    "degridding-wmax": ("float", False, None),
    "degridding-Padding": ("float", False, None),
    "degridding-NDegridBand": ("int", False, None),
    "degridding-MaxFacetSize": ("str", False, None),
    "degridding-MinNFacetPerAxis": ("str", False, None),
    "degridding-NProcess": ("str", False, None),
    "degridding-BeamModel": ("str", False, None),
    "degridding-NBand": ("int", False, None),
    "degridding-FITSFile": ("str", False, None),
    "degridding-FITSFeed": ("str", False, None),
    "degridding-FITSFeedSwap": ("bool", False, None),
    "degridding-DtBeamMin": ("float", False, None),
    "degridding-FITSParAngleIncDeg": ("float", False, None),
    "degridding-FITSLAxis": ("str", False, None),
    "degridding-FITSMAxis": ("str", False, None),
    "degridding-FITSVerbosity": ("int", False, None),
    "degridding-FeedAngle": ("float", False, None),
    "degridding-FlipVisibilityHands": ("str", False, None),
    "postmortem-enable": ("bool", False, None),
    "postmortem-tf-chisq-median": ("float", False, None),
    "postmortem-tf-np-median": ("float", False, None),
    "postmortem-time-density": ("str", False, None),
    "postmortem-chan-density": ("str", False, None),
    "postmortem-ddid-density": ("str", False, None),
    "madmax-enable": ("str", False, None),
    "madmax-residuals": ("str", False, None),
    "madmax-estimate": ("str", False, None),
    "madmax-diag": ("bool", False, None),
    "madmax-offdiag": ("bool", False, None),
    "madmax-threshold": ("str", False, None),
    "madmax-global-threshold": ("str", False, None),
    "madmax-plot": ("str", False, None),
    "madmax-plot-frac-above": ("str", False, None),
    "madmax-plot-bl": ("str", False, None),
    "madmax-flag-ant": ("str", False, None),
    "madmax-flag-ant-thr": ("str", False, None),
    "sol-jones": ("List[str]", False, None),
    "sol-precision": ("str", False, None),
    "sol-delta-g": ("str", False, None),
    "sol-delta-chi": ("str", False, None),
    "sol-chi-int": ("str", False, None),
    "sol-last-rites": ("bool", False, None),
    "sol-stall-quorum": ("str", False, None),
    "sol-term-iters": ("str", False, None),
    "sol-flag-divergence": ("str", False, None),
    "sol-min-bl": ("float", False, None),
    "sol-max-bl": ("str", False, None),
    "sol-subset": ("str", False, None),
    "sol-terms-iter": ("List[int]", False, None),
    "bbc-load-from": ("str", False, None),
    "bbc-compute-2x2": ("bool", False, None),
    "bbc-apply-2x2": ("bool", False, None),
    "bbc-save-to": ("str", False, None),
    "bbc-per-chan": ("bool", False, None),
    "bbc-plot": ("bool", False, None),
    "dist-ncpu": ("int", False, None),
    "dist-nworker": ("int", False, None),
    "dist-nthread": ("int", False, None),
    "dist-max-chunks": ("int", False, None),
    "dist-min-chunks": ("int", False, None),
    "dist-pin": ("str", False, None),
    "dist-pin-io": ("bool", False, None),
    "dist-pin-main": ("str", False, None),
    "dist-safe": ("float", False, None),
    "log-memory": ("str", False, None),
    "log-stats": ("str", False, None),
    "log-stats-warn": ("str", False, None),
    "log-boring": ("bool", False, None),
    "log-append": ("bool", False, None),
    "log-verbose": ("str", False, None),
    "log-file-verbose": ("str", False, None),
    "debug-pdb": ("bool", False, None),
    "debug-panic-amplitude": ("float", False, None),
    "debug-stop-before-solver": ("bool", False, None),
    "debug-escalate-warnings": ("str", False, None),
    "misc-random-seed": ("str", False, None),
}

_JONES_TERM_PATTERN = ParamPattern(
    separator="-",
    segments=[
        ParamSegment(regex=r".+?"),  # term name, e.g. "g1"/"g"/"dE" -- caller-chosen
        ParamSegment(
            attrs={
                "solvable": ParamMeta(),
                "type": ParamMeta(),
                "delay-estimate-pad-factor": ParamMeta(dtype="int"),
                "load-from": ParamMeta(),
                "xfer-from": ParamMeta(),
                "save-to": ParamMeta(),
                "dd-term": ParamMeta(dtype="bool"),
                "fix-dirs": ParamMeta(),
                "update-type": ParamMeta(),
                "estimate-pzd": ParamMeta(dtype="bool"),
                "time-int": ParamMeta(),
                "freq-int": ParamMeta(),
                "max-prior-error": ParamMeta(dtype="float"),
                "max-post-error": ParamMeta(dtype="float"),
                "low-snr-warn": ParamMeta(),
                "high-gain-var-warn": ParamMeta(),
                "clip-low": ParamMeta(dtype="float"),
                "clip-high": ParamMeta(dtype="float"),
                "clip-after": ParamMeta(),
                "max-iter": ParamMeta(),
                "pin-slope-iters": ParamMeta(),
                "epsilon": ParamMeta(),
                "delta-chi": ParamMeta(),
                "conv-quorum": ParamMeta(),
                "ref-ant": ParamMeta(),
                "prop-flags": ParamMeta(),
                "diag-only": ParamMeta(),
                "offdiag-only": ParamMeta(dtype="bool"),
                "robust-cov": ParamMeta(),
                "robust-scale": ParamMeta(),
                "robust-npol": ParamMeta(),
                "robust-int": ParamMeta(),
                "robust-flag-weights": ParamMeta(),
                "robust-cov-thresh": ParamMeta(),
                "robust-sigma-thresh": ParamMeta(),
                "robust-save-weights": ParamMeta(),
                "estimate-delays": ParamMeta(dtype="bool"),
            }
        ),
    ],
)

_OUTPUTS: dict[str, tuple[str, bool, object]] = {
    "ms": ("MS", False, None),
}

cubical = define_cab(
    "cubical",
    "gocubical",
    images.CUBICAL,
    _FIELDS,
    outputs=_OUTPUTS,
    field_meta={
        "ms": ParamMeta(implicit="{data_ms}"),
        "parset": ParamMeta(
            positional_head=True,
            info="Optional parset to load before applying all other parameters "
            "(cult-cargo's own cubical.yml wording)",
        ),
    },
    # real cubical.yml: policies: {prefix: '--', explicit_true: true,
    # explicit_false: false} -- gocubical's optparse-derived CLI expects
    # every boolean option to always take an explicit value token; a bare
    # `--flag` with none corrupts parsing of everything after it (see
    # stimela-ninja's Policies.explicit_true/explicit_false docstring).
    policies=Policies(prefix="--", explicit_true=True, explicit_false=False),
    input_patterns=[_JONES_TERM_PATTERN],
    info="CubiCal calibration package (https://github.com/ratt-ru/CubiCal)",
)
