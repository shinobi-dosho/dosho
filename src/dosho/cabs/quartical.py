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

`parset` is real, source-verified against `quartical/config/parser.py`'s
own `parse_inputs`: it scans the *whole* `sys.argv` for any bare token
ending in `.yaml`/`.yml` (`if arg.endswith(('.yaml', '.yml')):
config_files.append(arg)`), strips every match out before the rest of
argv is parsed as hydra-style `section.param=value` overrides -- unlike
CubiCal/killMS (see `cubical.py`'s docstring), position genuinely doesn't
matter here. Modelled as `ParamMeta(positional_head=True)` anyway (not
plain `positional`) purely for consistency with the other three parset
fields, and because `build_argv`'s positional handling bypasses this
cab's own `key_value=True` policy either way (a positional is emitted as
a bare `_format_value` token, never `name=value`), so head vs. tail
changes nothing observable for QuartiCal itself.
"""

from __future__ import annotations

from shinobi.steps.schema import ParamMeta, ParamPattern, ParamSegment, Policies

from dosho import images
from dosho._builder import define_cab

_FIELDS: dict[str, tuple[str, bool, object]] = {
    "parset": ("File", False, None),
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

quartical = define_cab(
    "quartical",
    "goquartical",
    images.QUARTICAL,
    _FIELDS,
    outputs=_OUTPUTS,
    field_meta={
        "ms": ParamMeta(implicit="{input_ms_path}"),
        "gain_directory": ParamMeta(implicit="{output_gain_directory}"),
        "parset": ParamMeta(
            positional_head=True,
            info="Optional YAML config file to load before applying all other parameters "
            "(any bare *.yaml/*.yml argv token, per goquartical's own parser.py)",
        ),
    },
    policies=Policies(key_value=True, repeat="[]", prefix=""),
    input_patterns=[_GAIN_TERM_PATTERN],
    info="QuartiCal calibration package (https://github.com/ratt-ru/QuartiCal)",
)

# --- quartical-backup/-restore/-plotter -------------------------------------
# The QuartiCal package's three auxiliary console scripts
# (`goquartical-backup`/`-restore`/`-plot`) -- ordinary argparse CLIs
# (unlike `goquartical` itself), so plain `--flag value` argv, no
# hydra/key-value policy. Ported field-by-field from each real `--help`
# (quartical 0.2.7); not in cult-cargo (whose `quartical.yml` only has
# stale field names for these three -- e.g. `quartical-plotter` there
# doesn't match `goquartical-plot`'s real flags).

_BACKUP_FIELDS: dict[str, tuple[str, bool, object]] = {
    "ms_path": ("MS", True, None),
    "zarr_dir": ("Directory", True, None),
    "column_name": ("str", True, None),
    "label": ("str", False, None),
    "nthread": ("int", False, None),
    "field_id": ("int", False, None),
}

_BACKUP_FIELD_META: dict[str, ParamMeta] = {
    "ms_path": ParamMeta(info="Path to the input measurement set (also accepts s3 URLs)", positional=True),
    "zarr_dir": ParamMeta(
        info="Directory for the backup location (not the zarr name itself; also accepts s3 URLs)",
        positional=True,
    ),
    "column_name": ParamMeta(info="Name of the column to back up", positional=True),
    "label": ParamMeta(
        info="Explicit label for the backup name [default: datetime]; full name is [label]-[msname]-[column].bkp.qc"
    ),
    "nthread": ParamMeta(info="Number of threads to use"),
    "field_id": ParamMeta(nom_de_guerre="field-id", info="Field ID to back up"),
}

quartical_backup = define_cab(
    "quartical-backup",
    "goquartical-backup",
    images.QUARTICAL,
    _BACKUP_FIELDS,
    field_meta=_BACKUP_FIELD_META,
    policies=Policies(prefix="--"),
    info="goquartical-backup: back up a measurement set column to zarr",
)

_RESTORE_FIELDS: dict[str, tuple[str, bool, object]] = {
    "zarr_path": ("Directory", True, None),
    "ms_path": ("MS", True, None),
    "column_name": ("str", True, None),
    "nthread": ("int", False, None),
}

_RESTORE_FIELD_META: dict[str, ParamMeta] = {
    "zarr_path": ParamMeta(
        info="Path to the backup zarr column, e.g. path/to/dir/20211201-154457-foo.MS-FLAG.bkp.qc",
        positional=True,
    ),
    "ms_path": ParamMeta(info="Path to the measurement set to restore into", positional=True),
    "column_name": ParamMeta(
        info="Column to populate from the backup (need not match the column the backup was made from)",
        positional=True,
    ),
    "nthread": ParamMeta(info="Number of threads to use"),
}

quartical_restore = define_cab(
    "quartical-restore",
    "goquartical-restore",
    images.QUARTICAL,
    _RESTORE_FIELDS,
    outputs={"ms_path": ("MS", False, None)},
    field_meta=_RESTORE_FIELD_META,
    policies=Policies(prefix="--"),
    info="goquartical-restore: restore a zarr column backup into a measurement set",
)

_PLOTTER_FIELDS: dict[str, tuple[str, bool, object]] = {
    "input_path": ("Directory", True, None),
    "output_path": ("str", True, None),
    "plot_var": ("str", False, None),
    "flag_var": ("str", False, None),
    "xaxis": ("str", False, None),
    "transform": ("str", False, None),
    "iter_attrs": ("List[str]", False, None),
    "iter_axes": ("List[str]", False, None),
    "mean_axis": ("str", False, None),
    "colourize_axis": ("str", False, None),
    "time_range": ("List[float]", False, None),
    "freq_range": ("List[float]", False, None),
    "nworker": ("int", False, None),
    "colourmap": ("str", False, None),
    "fig_size": ("List[float]", False, None),
}

_PLOTTER_FIELD_META: dict[str, ParamMeta] = {
    "input_path": ParamMeta(info="Path to input gains, e.g. path/to/dir/G (also accepts s3 URLs)", positional=True),
    "output_path": ParamMeta(info="Path to the desired output location", positional=True),
    "plot_var": ParamMeta(nom_de_guerre="plot-var", info="Name of the data variable to plot"),
    "flag_var": ParamMeta(nom_de_guerre="flag-var", info="Name of the data variable to use as flags"),
    "xaxis": ParamMeta(info="Coordinate to use for the x-axis: gain_time, gain_freq, param_time, param_freq"),
    "transform": ParamMeta(info="Transform to apply before plotting: raw, amplitude, phase, real, imag"),
    "iter_attrs": ParamMeta(
        nom_de_guerre="iter-attrs",
        info="Attributes (datasets) to iterate over; omitting one concatenates across it",
        repeat_as_tokens=True,
    ),
    "iter_axes": ParamMeta(
        nom_de_guerre="iter-axes",
        info="Axes to iterate over, producing one plot per unique combination",
        repeat_as_tokens=True,
    ),
    "mean_axis": ParamMeta(
        nom_de_guerre="mean-axis", info="If set, plot a heavier line for the mean along this axis"
    ),
    "colourize_axis": ParamMeta(nom_de_guerre="colourize-axis", info="Axis to colour by"),
    "time_range": ParamMeta(nom_de_guerre="time-range", info="Time range to plot", repeat_as_tokens=True),
    "freq_range": ParamMeta(nom_de_guerre="freq-range", info="Frequency range to plot", repeat_as_tokens=True),
    "nworker": ParamMeta(info="Number of processes to use while plotting"),
    "colourmap": ParamMeta(info="Matplotlib colourmap to use with --colourize-axis"),
    "fig_size": ParamMeta(
        nom_de_guerre="fig-size", info="Figure size in inches: width height", repeat_as_tokens=True
    ),
}

quartical_plotter = define_cab(
    "quartical-plotter",
    "goquartical-plot",
    images.QUARTICAL,
    _PLOTTER_FIELDS,
    field_meta=_PLOTTER_FIELD_META,
    policies=Policies(prefix="--"),
    info="goquartical-plot: rudimentary plotter for QuartiCal gain solutions",
)
