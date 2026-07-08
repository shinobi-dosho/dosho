"""quartical -- QuartiCal calibration package
(https://github.com/ratt-ru/QuartiCal).

Ported from cult-cargo's `quartical.yml`/`genesis/quartical/argument_schema.yaml`
(the real 50-parameter flat schema, cross-checked field-by-field against
that YAML), NOT via `dynamic_schema` -- shinobi never imports/executes
`cultcargo.genesis.quartical.external.make_stimela_schema`.

QuartiCal's real CLI is hydra/omegaconf-style dotted `section.param=value`
tokens (`goquartical input_ms.path=obs.ms input_ms.data_column=DATA
solver.terms=[G]`), not `--flag value` -- `argument_schema.yaml`'s nested
sections (`input_ms:`/`input_model:`/`output:`/`mad_flags:`/`solver:`/
`dask:`) are flattened by joining with `.` (matching the real flag shape
directly, e.g. `input_ms.data_column`), and the cab uses
`Policies(key_value=True, repeat="[]")` (see stimela-ninja's own
`Policies` docstring, added specifically to fix quartical's argv shape)
so every arg emits as one `name=value` token and list values as
`name=[a,b]`, never `--name value`.

The per-solvable-gain-term parameter family (`G.time_interval`,
`K.type`, ...) is declared as a single `ParamPattern`, transcribed from
`gain_schema.yaml`'s 11 attrs -- same shape as `cubical.py`'s per-Jones-
term pattern, and the reason `ParamPattern`/`Cab.input_patterns` exists
in the first place (see stimela-ninja's `AGENTS.md`, which names QuartiCal
by name as the motivating example).

QuartiCal writes corrected visibilities back into the *same* input MS
(via `output.products`/`output.columns`) and gain tables into
`output.gain_directory` -- both declared as real passthrough output
fields (`ms`, `gain_directory`), not synthetic hacks.
"""

from __future__ import annotations

from shinobi.steps.schema import ParamMeta, ParamPattern, ParamSegment, Policies

from dosho import images
from dosho._builder import define_cab

_FIELDS: dict[str, tuple[str, bool, object]] = {
    "input_ms.path": ("URI", True, None),
    "input_ms.data_column": ("str", False, "DATA"),
    "input_ms.sigma_column": ("str", False, None),
    "input_ms.weight_column": ("str", False, None),
    "input_ms.time_chunk": ("str", False, "0"),
    "input_ms.freq_chunk": ("str", False, "0"),
    "input_ms.is_bda": ("bool", False, False),
    "input_ms.group_by": ("List[str]", False, ["SCAN_NUMBER", "FIELD_ID", "DATA_DESC_ID"]),
    "input_ms.select_corr": ("List[int]", False, None),
    "input_ms.select_fields": ("List[int]", False, []),
    "input_ms.select_ddids": ("List[int]", False, []),
    "input_ms.select_uv_range": ("List[float]", False, [0, 0]),
    "input_model.recipe": ("str", False, None),
    "input_model.beam": ("str", False, None),
    "input_model.beam_l_axis": ("str", False, "X"),
    "input_model.beam_m_axis": ("str", False, "Y"),
    "input_model.invert_uvw": ("bool", False, True),
    "input_model.source_chunks": ("int", False, 500),
    "input_model.apply_p_jones": ("bool", False, False),
    "output.gain_directory": ("URI", False, "gains.qc"),
    "output.log_directory": ("Directory", False, "logs.qc"),
    "output.log_to_terminal": ("bool", False, True),
    "output.overwrite": ("bool", False, False),
    "output.products": ("List[str]", False, None),
    "output.columns": ("List[str]", False, None),
    "output.flags": ("bool", False, True),
    "output.apply_p_jones_inv": ("bool", False, False),
    "output.subtract_directions": ("List[int]", False, None),
    "output.net_gains": ("List[Any]", False, None),
    "output.compute_baseline_corrections": ("bool", False, False),
    "output.apply_baseline_corrections": ("bool", False, False),
    "mad_flags.enable": ("bool", False, False),
    "mad_flags.whitening": ("str", False, "disabled"),
    "mad_flags.threshold_bl": ("float", False, 5),
    "mad_flags.threshold_global": ("float", False, 10),
    "mad_flags.max_deviation": ("float", False, 0),
    "mad_flags.use_off_diagonals": ("bool", False, False),
    "solver.terms": ("List[str]", False, ["G"]),
    "solver.iter_recipe": ("List[int]", False, [25]),
    "solver.propagate_flags": ("bool", False, True),
    "solver.robust": ("bool", False, False),
    "solver.threads": ("int", False, 1),
    "solver.convergence_fraction": ("float", False, 0.99),
    "solver.convergence_criteria": ("float", False, 1e-06),
    "solver.reference_antenna": ("int", False, 0),
    "dask.threads": ("int", False, None),
    "dask.workers": ("int", False, 1),
    "dask.address": ("str", False, None),
    "dask.scheduler": ("str", False, "threads"),
    "dask.scheduler_plugin": ("bool", False, True),
}

_GAIN_TERM_PATTERN = ParamPattern(
    separator=".",
    segments=[
        ParamSegment(regex=r".+?"),  # gain term name, e.g. "G"/"K"/"B" -- caller-chosen
        ParamSegment(
            attrs={
                "type": ParamMeta(dtype="str"),
                "solve_per": ParamMeta(dtype="str"),
                "direction_dependent": ParamMeta(dtype="bool"),
                "pinned_directions": ParamMeta(dtype="List[int]"),
                "time_interval": ParamMeta(dtype="str"),
                "freq_interval": ParamMeta(dtype="str"),
                "load_from": ParamMeta(dtype="str"),
                "interp_mode": ParamMeta(dtype="str"),
                "interp_method": ParamMeta(dtype="str"),
                "respect_scan_boundaries": ParamMeta(dtype="bool"),
                "initial_estimate": ParamMeta(dtype="bool"),
            }
        ),
    ],
)

_OUTPUTS: dict[str, tuple[str, bool, object]] = {
    "ms": ("MS", False, None),
    "gain_directory": ("Directory", False, None),
}

cab = define_cab(
    "quartical",
    "goquartical",
    images.QUARTICAL,
    _FIELDS,
    outputs=_OUTPUTS,
    field_meta={
        "ms": ParamMeta(implicit="{input_ms_path}"),
        "gain_directory": ParamMeta(implicit="{output_gain_directory}"),
    },
    policies=Policies(key_value=True, repeat="[]", prefix=""),
    input_patterns=[_GAIN_TERM_PATTERN],
    info="QuartiCal calibration package (https://github.com/ratt-ru/QuartiCal)",
)
