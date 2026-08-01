"""killms -- killMS, direction-dependent calibration for radio
interferometric data (https://github.com/saopicc/killMS). Builds on top of
DDFacet (reuses dosho's `DDFACET` image as its `base`, matching killMS's
own real Dockerfile, which does `FROM bhugo/ddfacet:...` then installs
killMS into that image's venv).

Ported the same way as `ddfacet.py`: from killMS 3.3.0's own
`killMS/Parset/DefaultParset.cfg` (the same `ReadCFG.py`-based
`--Section-OptionName` format DDFacet uses -- see that module's docstring
for the parsing rules), not cult-cargo (no `killms`/`kMS` cab exists there
to cross-check against). `nom_de_guerre` preserves the `.cfg`'s literal
case (e.g. `VisData-MSName`, `SolverType`); fields with no `#type:` tag get
the same `ast.literal_eval`-or-string fallback DDFacet's own parser uses.

One output is modelled, and it is a directory rather than a file:
`Solutions-SolsDir`. killMS builds the solutions filename itself as
`"%skillMS.%s.sols.npz" % (reformat(MSName), SolsName)`, and `reformat()` is
an internal transformation of the MS name that no `str.format` template can
reproduce -- so the `.npz` path is not declarable. The directory it lands in
is, and that is the one that matters: it is what bind-mounts the solutions
into reach of the host when SolsDir points outside the working directory
(stimela-ninja issue #60), and it is what a pipeline actually wires, since
the consumer of these solutions is DDFacet, whose `DDESolutions-SolsDir`
takes the directory and whose `DDESolutions-DDSols` takes the solution
*name*. `ImageSkyModel-DDFCacheDir` is declared as `Scope.scratch`: a cache is a
write target that must be mounted but must never be rescued into the caller's
workspace, which is the distinction `scratch` exists to draw (stimela-ninja
#66).

**Path-typed fields.** `DefaultParset.cfg` carries a `#type:` tag on
almost nothing, so the `ast.literal_eval`-or-string fallback this port
inherits from DDFacet's parser lands every path on `str` -- including
`VisData-MSName`, killMS's own input MS. A `str` is not a path to
shinobi: `path_fields` never sees it, so it is neither bind-mounted into
the container (`backends.container.bind_dirs`) nor workspace-anchored
under a sandbox (`sandbox.absolutize_path_inputs`), and a containerised
run only finds it by accident. The dtype is therefore taken from each
option's role in killMS's own `kMS.py` option table rather than from the
untagged `.cfg`:

* `VisData-MSName` -> `MS` ("Input MS to draw"; `kMS.py`'s own usage
  string is `--MSName=somename.MS`).
* Read-side files -> `File`: `SkyModel-SkyModel` (`--SkyModel=SM.npy`),
  `ImageSkyModel-DicoModel` (loaded via `MyPickle.Load`),
  `-MaskImage`, `-NodesFile`, `-ImagePredictParset`, `Solutions-ExtSols`
  ("External solution file"), `Compression-CompressionDirFile`,
  `KAFCA-EvolutionSolFile`.
* `Beam-FITSFile` ("FITS beam mode filename template", default
  `beam_$(corr)_$(reim).fits`) and `ImageSkyModel-BaseImageName` (a
  DDFacet image *prefix*, from which killMS derives `<Base>.DicoModel`)
  are `File` too, even though neither value is literally one file.
  Nothing in shinobi opens a path input: a bind mount is derived from the
  value's *parent directory* and anchoring only rewrites a relative value
  to an absolute one, both of which are exactly right here -- and both
  are reads, so anchoring them at the workspace finds the caller's real
  files rather than empty sandbox paths.

Deliberately left as `str`: `Solutions-SolsDir` and
`ImageSkyModel-DDFCacheDir`, which killMS *writes*. A string-typed write
target stays relative under a sandbox on purpose, so the tool writes
inside the sandbox for harvest to pick up -- see
`sandbox.absolutize_path_inputs`' own docstring on output prefixes.
Promoting those two *inputs* to `Directory` would anchor them at the
workspace and route killMS's writes around the sandbox; the declaration
happens on the output side instead (see `_OUTPUTS`), which leaves the input
relative and still tells shinobi where the tool writes.
`Solutions-OutSolsName` also stays `str`: despite "save the estimated
solutions in this file", `kMS.py` uses it as a *name component*
(`"%skillMS.%s.sols.npz" % (reformat(MSName), SolsName)`), never as a
path. So do `SkyModel-kills` (source names/indices) and every `*Col`
field (MS column names).

`parset` is source-verified against `killMS/kMS.py`'s own `driver()`:
`ParsetFile=sys.argv[1]` -- read unconditionally (no `.startswith('-')`
guard the way CubiCal has), and `driver()` never checks leftover-arg
count the way `DDF.py`/CubiCal's `main()` do. So pairing a tail
`positional` parset with any other override flag wouldn't crash killMS --
it would just silently fail to read the parset at all (`sys.argv[1]`
would be the first `--flag` instead, `ReadCFG.Parset("--flag")` fails to
open a nonexistent file, `TestParset.Success` stays `False`, and the
trailing parset token is left as an unvalidated, silently-ignored
leftover). `ParamMeta(positional_head=True)` -- same as `cubical.py` --
makes sure it actually lands at `sys.argv[1]`.
"""

from __future__ import annotations

from shinobi.steps.schema import Mutability, ParamMeta, Policies

from dosho import images
from dosho._builder import FieldSpec, define_cab

_FIELDS: dict[str, FieldSpec] = {
    "parset": (
        "File",
        False,
        None,
        ParamMeta(
            positional_head=True,
            info="Parset file to read option defaults from, overridden by any of the flags below "
            "(kMS.py's own driver() reads sys.argv[1] as the parset unconditionally)",
        ),
    ),
    "vis_data_ms_name": ("MS", False, None, ParamMeta(nom_de_guerre="VisData-MSName", info="")),
    "vis_data_t_chunk": ("int", False, 15, ParamMeta(nom_de_guerre="VisData-TChunk", info="")),
    "vis_data_in_col": (
        "str",
        False,
        "CORRECTED_DATA_BACKUP",
        ParamMeta(nom_de_guerre="VisData-InCol", info=""),
    ),
    "vis_data_out_col": (
        "str",
        False,
        "CORRECTED_DATA",
        ParamMeta(nom_de_guerre="VisData-OutCol", info=""),
    ),
    "vis_data_free_predict_gain_col_name": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="VisData-FreePredictGainColName", info=""),
    ),
    "vis_data_free_predict_col_name": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="VisData-FreePredictColName", info=""),
    ),
    "vis_data_parallel": ("int", False, 1, ParamMeta(nom_de_guerre="VisData-Parallel", info="")),
    "sky_model_sky_model": (
        "File",
        False,
        None,
        ParamMeta(nom_de_guerre="SkyModel-SkyModel", info=""),
    ),
    "sky_model_kills": ("str", False, None, ParamMeta(nom_de_guerre="SkyModel-kills", info="")),
    "sky_model_invert": ("bool", False, False, ParamMeta(nom_de_guerre="SkyModel-invert", info="")),
    "sky_model_decorrelation": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="SkyModel-Decorrelation", info=""),
    ),
    "sky_model_free_full_sub": (
        "int",
        False,
        0,
        ParamMeta(nom_de_guerre="SkyModel-FreeFullSub", info=""),
    ),
    "sky_model_sky_model_col": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="SkyModel-SkyModelCol", info=""),
    ),
    "beam_beam_model": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="Beam-BeamModel", info="None/LOFAR"),
    ),
    "beam_beam_at": (
        "str",
        False,
        "facet",
        ParamMeta(nom_de_guerre="Beam-BeamAt", info="tessel/facet"),
    ),
    "beam_lofar_beam_mode": (
        "str",
        False,
        "AE",
        ParamMeta(nom_de_guerre="Beam-LOFARBeamMode", info="A/AE"),
    ),
    "beam_dt_beam_min": ("int", False, 5, ParamMeta(nom_de_guerre="Beam-DtBeamMin", info="")),
    "beam_center_norm": ("bool", False, True, ParamMeta(nom_de_guerre="Beam-CenterNorm", info="")),
    "beam_n_chan_beam_per_ms": (
        "int",
        False,
        1,
        ParamMeta(nom_de_guerre="Beam-NChanBeamPerMS", info=""),
    ),
    "beam_fits_file": (
        "File",
        False,
        "beam_$(corr)_$(reim).fits",
        ParamMeta(nom_de_guerre="Beam-FITSFile", info=""),
    ),
    "beam_fits_par_angle_inc_deg": (
        "int",
        False,
        5,
        ParamMeta(nom_de_guerre="Beam-FITSParAngleIncDeg", info=""),
    ),
    "beam_fitsl_axis": (
        "str",
        False,
        "-X",
        ParamMeta(
            nom_de_guerre="Beam-FITSLAxis",
            info="L axis of FITS file. Minus sign indicates reverse coordinate convention.",
        ),
    ),
    "beam_fitsm_axis": (
        "str",
        False,
        "Y",
        ParamMeta(
            nom_de_guerre="Beam-FITSMAxis",
            info="M axis of FITS file. Minus sign indicates reverse coordinate convention.",
        ),
    ),
    "beam_fits_feed": ("str", False, None, ParamMeta(nom_de_guerre="Beam-FITSFeed", info="")),
    "beam_fits_verbosity": (
        "int",
        False,
        1,
        ParamMeta(nom_de_guerre="Beam-FITSVerbosity", info=""),
    ),
    "beam_feed_angle": ("int", False, 0, ParamMeta(nom_de_guerre="Beam-FeedAngle", info="")),
    "beam_apply_p_jones": (
        "int",
        False,
        0,
        ParamMeta(
            nom_de_guerre="Beam-ApplyPJones",
            info="derotate visibility data (only when FITS beam is active and also time sampled)",
        ),
    ),
    "beam_flip_visibility_hands": (
        "int",
        False,
        0,
        ParamMeta(
            nom_de_guerre="Beam-FlipVisibilityHands",
            info="apply anti-diagonal matrix if FITS beam is enabled effectively swapping X and Y or R and L and their respective hands",
        ),
    ),
    "beam_fits_feed_swap": ("int", False, 0, ParamMeta(nom_de_guerre="Beam-FITSFeedSwap", info="")),
    "beam_fits_frame": (
        "str",
        False,
        "altaz",
        ParamMeta(
            nom_de_guerre="Beam-FITSFrame",
            info="coordinate frame for FITS beams. Currently, alt-az, equatorial and zenith mounts are supported.",
        ),
    ),
    "image_sky_model_base_image_name": (
        "File",
        False,
        None,
        ParamMeta(nom_de_guerre="ImageSkyModel-BaseImageName", info=""),
    ),
    "image_sky_model_dico_model": (
        "File",
        False,
        None,
        ParamMeta(nom_de_guerre="ImageSkyModel-DicoModel", info=""),
    ),
    "image_sky_model_nodes_file": (
        "File",
        False,
        None,
        ParamMeta(nom_de_guerre="ImageSkyModel-NodesFile", info=""),
    ),
    "image_sky_model_image_predict_parset": (
        "File",
        False,
        None,
        ParamMeta(nom_de_guerre="ImageSkyModel-ImagePredictParset", info=""),
    ),
    "image_sky_model_over_s": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="ImageSkyModel-OverS", info=""),
    ),
    "image_sky_model_mask_image": (
        "File",
        False,
        None,
        ParamMeta(nom_de_guerre="ImageSkyModel-MaskImage", info=""),
    ),
    "image_sky_model_wmax": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="ImageSkyModel-wmax", info=""),
    ),
    "image_sky_model_max_facet_size": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="ImageSkyModel-MaxFacetSize", info=""),
    ),
    "image_sky_model_min_facet_size": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="ImageSkyModel-MinFacetSize", info=""),
    ),
    "image_sky_model_remove_ddf_cache": (
        "bool",
        False,
        False,
        ParamMeta(nom_de_guerre="ImageSkyModel-RemoveDDFCache", info=""),
    ),
    "image_sky_model_ddf_cache_dir": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="ImageSkyModel-DDFCacheDir", info="", write_path=True),
    ),
    "image_sky_model_filter_neg_comp": (
        "bool",
        False,
        False,
        ParamMeta(nom_de_guerre="ImageSkyModel-FilterNegComp", info=""),
    ),
    "image_sky_model_th_solve": (
        "float",
        False,
        0.0,
        ParamMeta(nom_de_guerre="ImageSkyModel-ThSolve", info=""),
    ),
    "data_selection_uv_min_max": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="DataSelection-UVMinMax", info=""),
    ),
    "data_selection_chan_slice": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="DataSelection-ChanSlice", info=""),
    ),
    "data_selection_flag_ants": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="DataSelection-FlagAnts", info=""),
    ),
    "data_selection_dist_max_to_core": (
        "float",
        False,
        10000.0,
        ParamMeta(nom_de_guerre="DataSelection-DistMaxToCore", info=""),
    ),
    "data_selection_fill_factor": (
        "float",
        False,
        1.0,
        ParamMeta(nom_de_guerre="DataSelection-FillFactor", info=""),
    ),
    "data_selection_field_id": (
        "int",
        False,
        0,
        ParamMeta(nom_de_guerre="DataSelection-FieldID", info=""),
    ),
    "data_selection_ddid": (
        "int",
        False,
        0,
        ParamMeta(nom_de_guerre="DataSelection-DDID", info=""),
    ),
    "weighting_resolution": (
        "float",
        False,
        0.0,
        ParamMeta(nom_de_guerre="Weighting-Resolution", info=""),
    ),
    "weighting_weight_in_col": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="Weighting-WeightInCol", info=""),
    ),
    "weighting_weighting": (
        "str",
        False,
        "Natural",
        ParamMeta(nom_de_guerre="Weighting-Weighting", info=""),
    ),
    "weighting_robust": ("float", False, 0.0, ParamMeta(nom_de_guerre="Weighting-Robust", info="")),
    "weighting_weight_uv_min_max": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="Weighting-WeightUVMinMax", info=""),
    ),
    "weighting_wtuv": ("int", False, 1, ParamMeta(nom_de_guerre="Weighting-WTUV", info="")),
    "actions_do_plot": ("int", False, 0, ParamMeta(nom_de_guerre="Actions-DoPlot", info="")),
    "actions_sub_only": ("int", False, 0, ParamMeta(nom_de_guerre="Actions-SubOnly", info="")),
    "actions_ncpu": ("int", False, 1, ParamMeta(nom_de_guerre="Actions-NCPU", info="")),
    "actions_do_bar": ("int", False, 1, ParamMeta(nom_de_guerre="Actions-DoBar", info="")),
    "actions_n_thread": ("int", False, 1, ParamMeta(nom_de_guerre="Actions-NThread", info="")),
    "actions_debug_pdb": ("int", False, 1, ParamMeta(nom_de_guerre="Actions-DebugPdb", info="")),
    "actions_update_weights": (
        "int",
        False,
        1,
        ParamMeta(nom_de_guerre="Actions-UpdateWeights", info=""),
    ),
    "pre_apply_pre_apply_sols": (
        "List[str]",
        False,
        [],
        ParamMeta(nom_de_guerre="PreApply-PreApplySols", info=""),
    ),
    "pre_apply_pre_apply_mode": (
        "List[str]",
        False,
        [],
        ParamMeta(nom_de_guerre="PreApply-PreApplyMode", info=""),
    ),
    "solutions_ext_sols": (
        "File",
        False,
        None,
        ParamMeta(nom_de_guerre="Solutions-ExtSols", info=""),
    ),
    "solutions_clip_method": (
        "str",
        False,
        "[ResidAnt]",
        ParamMeta(nom_de_guerre="Solutions-ClipMethod", info=""),
    ),
    "solutions_out_sols_name": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="Solutions-OutSolsName", info=""),
    ),
    "solutions_apply_to_dir": (
        "int",
        False,
        -2,
        ParamMeta(nom_de_guerre="Solutions-ApplyToDir", info=""),
    ),
    "solutions_merge_beam_to_applied_sol": (
        "int",
        False,
        0,
        ParamMeta(nom_de_guerre="Solutions-MergeBeamToAppliedSol", info=""),
    ),
    "solutions_apply_mode": (
        "str",
        False,
        "AP",
        ParamMeta(nom_de_guerre="Solutions-ApplyMode", info=""),
    ),
    "solutions_skip_existing_sols": (
        "int",
        False,
        0,
        ParamMeta(nom_de_guerre="Solutions-SkipExistingSols", info=""),
    ),
    "solutions_sols_dir": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="Solutions-SolsDir", info=""),
    ),
    "compression_compression_mode": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="Compression-CompressionMode", info="auto, manual"),
    ),
    "compression_compression_dir_file": (
        "File",
        False,
        None,
        ParamMeta(nom_de_guerre="Compression-CompressionDirFile", info=""),
    ),
    "compression_merge_stations": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="Compression-MergeStations", info=""),
    ),
    "solvers_solver_type": (
        "str",
        False,
        "CohJones",
        ParamMeta(nom_de_guerre="Solvers-SolverType", info=""),
    ),
    "solvers_precision_dot": (
        "str",
        False,
        "D",
        ParamMeta(nom_de_guerre="Solvers-PrecisionDot", info=""),
    ),
    "solvers_pol_mode": (
        "str",
        False,
        "Scalar",
        ParamMeta(nom_de_guerre="Solvers-PolMode", info=""),
    ),
    "solvers_dt": ("int", False, 30, ParamMeta(nom_de_guerre="Solvers-dt", info="")),
    "solvers_n_chan_sols": ("int", False, 1, ParamMeta(nom_de_guerre="Solvers-NChanSols", info="")),
    "coh_jones_n_iter_lm": ("int", False, 7, ParamMeta(nom_de_guerre="CohJones-NIterLM", info="")),
    "coh_jones_lambda_lm": ("int", False, 1, ParamMeta(nom_de_guerre="CohJones-LambdaLM", info="")),
    "coh_jones_lambda_tk": (
        "float",
        False,
        0.0,
        ParamMeta(nom_de_guerre="CohJones-LambdaTk", info=""),
    ),
    "kafca_n_iter_kf": ("int", False, 6, ParamMeta(nom_de_guerre="KAFCA-NIterKF", info="")),
    "kafca_lambda_kf": ("float", False, 0.5, ParamMeta(nom_de_guerre="KAFCA-LambdaKF", info="")),
    "kafca_init_lm": ("int", False, 0, ParamMeta(nom_de_guerre="KAFCA-InitLM", info="")),
    "kafca_init_l_mdt": ("int", False, 5, ParamMeta(nom_de_guerre="KAFCA-InitLMdt", info="")),
    "kafca_cov_p": ("float", False, 0.1, ParamMeta(nom_de_guerre="KAFCA-CovP", info="")),
    "kafca_cov_q": ("float", False, 0.1, ParamMeta(nom_de_guerre="KAFCA-CovQ", info="")),
    "kafca_power_smooth": (
        "float",
        False,
        1.0,
        ParamMeta(nom_de_guerre="KAFCA-PowerSmooth", info=""),
    ),
    "kafca_ev_p_step": ("int", False, 120, ParamMeta(nom_de_guerre="KAFCA-evPStep", info="")),
    "kafca_ev_p_step_start": (
        "int",
        False,
        1,
        ParamMeta(nom_de_guerre="KAFCA-evPStepStart", info=""),
    ),
    "kafca_evolution_sol_file": (
        "File",
        False,
        None,
        ParamMeta(nom_de_guerre="KAFCA-EvolutionSolFile", info=""),
    ),
}

_OUTPUTS: dict[str, FieldSpec] = {
    # Same-named passthrough (the `tigger`/`rfinder` shape): the *input* stays
    # `str` so it keeps working relative under a sandbox, while the output side
    # -- path-typed, so `path_fields` sees it -- is what declares that killMS
    # writes there. `_fill_outputs` copies the input's value across, and an
    # unset SolsDir stays None and declares nothing, which is right: the
    # solutions then land inside the MS directory, already mounted as an input.
    #
    # The directory, not the file: `kMS.py` builds the filename itself as
    # `"%skillMS.%s.sols.npz" % (reformat(MSName), SolsName)`, and `reformat()`
    # is internal. That costs nothing in practice -- the consumer of these
    # solutions is DDFacet, whose `DDESolutions-SolsDir` takes the directory and
    # whose `DDESolutions-DDSols` takes the solution *name*, so a pipeline wires
    # `killms.solutions_sols_dir -> ddfacet.dde_solutions_sols_dir` and never
    # needs the `.npz` path itself.
    #
    # No 4th element on purpose -- `field_meta` is `{**input_meta,
    # **output_meta}`, so an output-side `ParamMeta` here would drop the input's
    # own `nom_de_guerre` and stop emitting `--Solutions-SolsDir`.
    "solutions_sols_dir": ("Directory", False, None),
}

killms = define_cab(
    "killms",
    "kMS.py",
    images.KILLMS,
    _FIELDS,
    outputs=_OUTPUTS,
    # killMS's cache: mounted so the write lands on the host, never rescued
    # into the caller's workspace (`Scope.scratch`). Defaults to None, so it
    # declares nothing when unset.
    scratch=["{image_sky_model_ddf_cache_dir}/*"],
    # kMS.py opens the MS for writing: it writes its solved column
    # (`VisData-OutCol`), the full predicted data when `FreePredictColName`
    # is set (`GiveMainTable(readonly=False)`, kMS.py:773/803), imaging
    # weights when `UpdateWeights` is on -- and, when `Solutions-SolsDir` is
    # unset, the `.sols.npz` itself lands *inside* the MS directory
    # (`"%skillMS.%s.sols.npz" % (reformat(MSName), SolsName)`). This cab
    # models no outputs (see the module docstring), so the name-intersection
    # spelling of "mutated in place" has nothing to intersect; without the
    # declaration `compute_cache_key` fingerprints an MS the step rewrites.
    # This is the plain flag/gaincal shape `Mutability.MUTABLE` exists for.
    # (keyed by the `_FIELDS` key, which for this cab is already the
    # sanitised name -- the cfg's literal `VisData-MSName` lives in the
    # field's `nom_de_guerre`, not in the key)
    input_mutability={"vis_data_ms_name": Mutability.MUTABLE},
    policies=Policies(prefix="--"),
    experimental=(
        "killMS is a rogue sibling upstream dosho supports on a best-effort basis: its `DefaultParset.cfg` declares almost no types, and it mangles its own output name internally (`reformat(MSName)` + `SolsName`). Its I/O *is* declared -- the solutions directory as an output, the DDF cache as `scratch` -- so nothing is silently lost. What remains: the `.sols.npz` path itself cannot be named, so a downstream step wires the solutions *directory* plus the solution name, which is what DDFacet's `DDESolutions-SolsDir`/`DDESolutions-DDSols` want anyway. Expect to verify a killMS upgrade against this cab rather than assuming the schema held still"
    ),
    info="killMS: direction-dependent calibration for radio interferometric data "
    "(https://github.com/saopicc/killMS)",
)
