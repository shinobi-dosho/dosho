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
fields (`ms`, `gain_directory`), not synthetic hacks. *Both* are also
declared `Mutability.MUTABLE` on the input they echo: a passthrough
output makes the write wirable by a downstream step, but only the
mutability declaration makes it visible to
`shinobi.steps.schema.mutated_path_fields`, whose other spelling is a
plain input/output *name* intersection that an `implicit`-templated
output under a different name (`ms` vs `input_ms_path`,
`gain_directory` vs `output_gain_directory`) never satisfies. See
`dosho._builder.define_cab`'s `input_mutability` for what that costs
and buys.

`output.gain_directory` is the less obvious of the two, because it is
not a *pre-existing* file the tool rewrites -- it is where goquartical
puts gains it just solved. It needs the declaration for the same reason
all the same: it is a path-typed *input* naming a location the step
itself writes, so an undeclared run keys on "gains.qc absent", creates
it, and keys differently ever after. QuartiCal has an
`output.overwrite` flag precisely because the directory may already be
there, which is the in-place rewrite in its plainest form.

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

from shinobi.steps.schema import Mutability, ParamMeta, ParamPattern, ParamSegment, Policies

from dosho import images
from dosho._builder import FieldSpec, define_cab

_FIELDS: dict[str, FieldSpec] = {
    "parset": (
        "File",
        False,
        None,
        ParamMeta(
            positional_head=True,
            info="Optional YAML config file to load before applying all other parameters "
            "(any bare *.yaml/*.yml argv token, per goquartical's own parser.py)",
        ),
    ),
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
                # `Directory`, not `str` -- this one attr names a path *into*
                # the filesystem (a previous run's `output.gain_directory`
                # plus the per-term zarr group, e.g. `gains.qc/G`), and
                # shinobi classifies a pattern-matched param as needing a
                # bind mount and workspace anchoring purely by its dtype
                # (`is_file_dtype`, consumed by `backends.container.bind_dirs`
                # and `sandbox.absolutize_path_inputs`). Declared `str` it is
                # neither bound into the container nor anchored, so loading a
                # gain set only works by accident -- when the sandbox is off
                # *and* the directory happens to sit under the mounted
                # workdir. QuartiCal's own `gain_schema.yaml` says
                # `Optional[str]`, but that is a Python type, not an I/O
                # classification; the sibling `gain_directory` output is
                # already `Directory`.
                "load_from": ParamMeta(dtype="Directory"),
                "interp_mode": ParamMeta(dtype="str"),
                "interp_method": ParamMeta(dtype="str"),
                "respect_scan_boundaries": ParamMeta(dtype="bool"),
                "initial_estimate": ParamMeta(dtype="bool"),
            }
        ),
    ],
)

_OUTPUTS: dict[str, FieldSpec] = {
    "ms": ("MS", False, None, ParamMeta(implicit="{input_ms_path}")),
    "gain_directory": ("Directory", False, None, ParamMeta(implicit="{output_gain_directory}")),
}

quartical = define_cab(
    "quartical",
    "goquartical",
    images.QUARTICAL,
    _FIELDS,
    outputs=_OUTPUTS,
    # The `ms` output above resolves to the very path `input_ms.path` named,
    # but shinobi's name-intersection spelling of "mutated in place" can't
    # see through an `implicit` template -- the two fields are spelled
    # differently, so `input_paths & output_paths` is empty. Say it in the
    # other spelling shinobi provides for exactly this shape. Without it,
    # `compute_cache_key` fingerprints the MS QuartiCal is about to rewrite,
    # so a re-run of an unchanged step can never hit its own cache entry,
    # and `snapshots.eligible_fields` finds nothing to protect.
    #
    # `output.gain_directory` is the same shape one field over: a path-typed
    # *input* that names where the tool writes, echoed by an output spelled
    # differently again (`gain_directory`). Undeclared, the first run keys on
    # "gains.qc absent", creates it, and every re-run keys on "gains.qc
    # present" -- a permanent miss, exactly as for the MS.
    #
    # `output.log_directory` is the same again and has no echoing output at
    # all, which is why it is easy to miss and why it is listed here rather
    # than left for later: this cab has exactly four path-typed inputs, three
    # of them write targets, and one undeclared write target is enough to
    # move the key on every run. Declaring two of three would have fixed
    # nothing measurable.
    input_mutability={
        "input_ms.path": Mutability.MUTABLE,
        "output.gain_directory": Mutability.MUTABLE,
        "output.log_directory": Mutability.MUTABLE,
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

_BACKUP_FIELDS: dict[str, FieldSpec] = {
    "ms_path": (
        "MS",
        True,
        None,
        ParamMeta(info="Path to the input measurement set (also accepts s3 URLs)", positional=True),
    ),
    "zarr_dir": (
        "Directory",
        True,
        None,
        ParamMeta(
            info="Directory for the backup location (not the zarr name itself; "
            "also accepts s3 URLs)",
            positional=True,
        ),
    ),
    "column_name": (
        "str",
        True,
        None,
        ParamMeta(info="Name of the column to back up", positional=True),
    ),
    "label": (
        "str",
        False,
        None,
        ParamMeta(
            info="Explicit label for the backup name [default: datetime]; full name is "
            "[label]-[msname]-[column].bkp.qc"
        ),
    ),
    "nthread": ("int", False, None, ParamMeta(info="Number of threads to use")),
    "field_id": (
        "int",
        False,
        None,
        ParamMeta(nom_de_guerre="field-id", info="Field ID to back up"),
    ),
}

quartical_backup = define_cab(
    "quartical-backup",
    "goquartical-backup",
    images.QUARTICAL,
    _BACKUP_FIELDS,
    policies=Policies(prefix="--"),
    info="goquartical-backup: back up a measurement set column to zarr",
)

_RESTORE_FIELDS: dict[str, FieldSpec] = {
    "zarr_path": (
        "Directory",
        True,
        None,
        ParamMeta(
            info="Path to the backup zarr column, e.g. "
            "path/to/dir/20211201-154457-foo.MS-FLAG.bkp.qc",
            positional=True,
        ),
    ),
    "ms_path": (
        "MS",
        True,
        None,
        ParamMeta(info="Path to the measurement set to restore into", positional=True),
    ),
    "column_name": (
        "str",
        True,
        None,
        ParamMeta(
            info="Column to populate from the backup "
            "(need not match the column the backup was made from)",
            positional=True,
        ),
    ),
    "nthread": ("int", False, None, ParamMeta(info="Number of threads to use")),
}

quartical_restore = define_cab(
    "quartical-restore",
    "goquartical-restore",
    images.QUARTICAL,
    _RESTORE_FIELDS,
    outputs={"ms_path": ("MS", False, None)},
    policies=Policies(prefix="--"),
    info="goquartical-restore: restore a zarr column backup into a measurement set",
)

_PLOTTER_FIELDS: dict[str, FieldSpec] = {
    "input_path": (
        "Directory",
        True,
        None,
        ParamMeta(
            info="Path to input gains, e.g. path/to/dir/G (also accepts s3 URLs)",
            positional=True,
        ),
    ),
    "output_path": (
        "str",
        True,
        None,
        ParamMeta(info="Path to the desired output location", positional=True),
    ),
    "plot_var": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="plot-var", info="Name of the data variable to plot"),
    ),
    "flag_var": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="flag-var", info="Name of the data variable to use as flags"),
    ),
    "xaxis": (
        "str",
        False,
        None,
        ParamMeta(
            info="Coordinate to use for the x-axis: gain_time, gain_freq, param_time, param_freq"
        ),
    ),
    "transform": (
        "str",
        False,
        None,
        ParamMeta(info="Transform to apply before plotting: raw, amplitude, phase, real, imag"),
    ),
    "iter_attrs": (
        "List[str]",
        False,
        None,
        ParamMeta(
            nom_de_guerre="iter-attrs",
            info="Attributes (datasets) to iterate over; omitting one concatenates across it",
            repeat_as_tokens=True,
        ),
    ),
    "iter_axes": (
        "List[str]",
        False,
        None,
        ParamMeta(
            nom_de_guerre="iter-axes",
            info="Axes to iterate over, producing one plot per unique combination",
            repeat_as_tokens=True,
        ),
    ),
    "mean_axis": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="mean-axis",
            info="If set, plot a heavier line for the mean along this axis",
        ),
    ),
    "colourize_axis": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="colourize-axis", info="Axis to colour by"),
    ),
    "time_range": (
        "List[float]",
        False,
        None,
        ParamMeta(nom_de_guerre="time-range", info="Time range to plot", repeat_as_tokens=True),
    ),
    "freq_range": (
        "List[float]",
        False,
        None,
        ParamMeta(
            nom_de_guerre="freq-range",
            info="Frequency range to plot",
            repeat_as_tokens=True,
        ),
    ),
    "nworker": ("int", False, None, ParamMeta(info="Number of processes to use while plotting")),
    "colourmap": (
        "str",
        False,
        None,
        ParamMeta(info="Matplotlib colourmap to use with --colourize-axis"),
    ),
    "fig_size": (
        "List[float]",
        False,
        None,
        ParamMeta(
            nom_de_guerre="fig-size",
            info="Figure size in inches: width height",
            repeat_as_tokens=True,
        ),
    ),
}

quartical_plotter = define_cab(
    "quartical-plotter",
    "goquartical-plot",
    images.QUARTICAL,
    _PLOTTER_FIELDS,
    policies=Policies(prefix="--"),
    info="goquartical-plot: rudimentary plotter for QuartiCal gain solutions",
)
