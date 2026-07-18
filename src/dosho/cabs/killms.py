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

No outputs are modelled: killMS's real output (a `.sols.npz` solutions
file) is named from `--SkyModel-SkyModel`/`--SkyModel-Kills`-derived
defaults inside the tool itself, not a single flag-controlled path.

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

from shinobi.steps.schema import ParamMeta, Policies

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
    "vis_data_ms_name": ("str", False, None, ParamMeta(nom_de_guerre="VisData-MSName", info='')),
    "vis_data_t_chunk": ("int", False, 15, ParamMeta(nom_de_guerre="VisData-TChunk", info='')),
    "vis_data_in_col": (
        "str",
        False,
        'CORRECTED_DATA_BACKUP',
        ParamMeta(nom_de_guerre="VisData-InCol", info=''),
    ),
    "vis_data_out_col": (
        "str",
        False,
        'CORRECTED_DATA',
        ParamMeta(nom_de_guerre="VisData-OutCol", info=''),
    ),
    "vis_data_free_predict_gain_col_name": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="VisData-FreePredictGainColName", info=''),
    ),
    "vis_data_free_predict_col_name": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="VisData-FreePredictColName", info=''),
    ),
    "vis_data_parallel": ("int", False, 1, ParamMeta(nom_de_guerre="VisData-Parallel", info='')),
    "sky_model_sky_model": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="SkyModel-SkyModel", info=''),
    ),
    "sky_model_kills": ("str", False, None, ParamMeta(nom_de_guerre="SkyModel-kills", info='')),
    "sky_model_invert": ("bool", False, False, ParamMeta(nom_de_guerre="SkyModel-invert", info='')),
    "sky_model_decorrelation": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="SkyModel-Decorrelation", info=''),
    ),
    "sky_model_free_full_sub": (
        "int",
        False,
        0,
        ParamMeta(nom_de_guerre="SkyModel-FreeFullSub", info=''),
    ),
    "sky_model_sky_model_col": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="SkyModel-SkyModelCol", info=''),
    ),
    "beam_beam_model": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="Beam-BeamModel", info='None/LOFAR'),
    ),
    "beam_beam_at": (
        "str",
        False,
        'facet',
        ParamMeta(nom_de_guerre="Beam-BeamAt", info='tessel/facet'),
    ),
    "beam_lofar_beam_mode": (
        "str",
        False,
        'AE',
        ParamMeta(nom_de_guerre="Beam-LOFARBeamMode", info='A/AE'),
    ),
    "beam_dt_beam_min": ("int", False, 5, ParamMeta(nom_de_guerre="Beam-DtBeamMin", info='')),
    "beam_center_norm": ("bool", False, True, ParamMeta(nom_de_guerre="Beam-CenterNorm", info='')),
    "beam_n_chan_beam_per_ms": (
        "int",
        False,
        1,
        ParamMeta(nom_de_guerre="Beam-NChanBeamPerMS", info=''),
    ),
    "beam_fits_file": (
        "str",
        False,
        'beam_$(corr)_$(reim).fits',
        ParamMeta(nom_de_guerre="Beam-FITSFile", info=''),
    ),
    "beam_fits_par_angle_inc_deg": (
        "int",
        False,
        5,
        ParamMeta(nom_de_guerre="Beam-FITSParAngleIncDeg", info=''),
    ),
    "beam_fitsl_axis": (
        "str",
        False,
        '-X',
        ParamMeta(
            nom_de_guerre="Beam-FITSLAxis",
            info='L axis of FITS file. Minus sign indicates reverse coordinate convention.',
        ),
    ),
    "beam_fitsm_axis": (
        "str",
        False,
        'Y',
        ParamMeta(
            nom_de_guerre="Beam-FITSMAxis",
            info='M axis of FITS file. Minus sign indicates reverse coordinate convention.',
        ),
    ),
    "beam_fits_feed": ("str", False, None, ParamMeta(nom_de_guerre="Beam-FITSFeed", info='')),
    "beam_fits_verbosity": (
        "int",
        False,
        1,
        ParamMeta(nom_de_guerre="Beam-FITSVerbosity", info=''),
    ),
    "beam_feed_angle": ("int", False, 0, ParamMeta(nom_de_guerre="Beam-FeedAngle", info='')),
    "beam_apply_p_jones": (
        "int",
        False,
        0,
        ParamMeta(
            nom_de_guerre="Beam-ApplyPJones",
            info='derotate visibility data (only when FITS beam is active and also time sampled)',
        ),
    ),
    "beam_flip_visibility_hands": (
        "int",
        False,
        0,
        ParamMeta(
            nom_de_guerre="Beam-FlipVisibilityHands",
            info='apply anti-diagonal matrix if FITS beam is enabled effectively swapping X and Y or R and L and their respective hands',
        ),
    ),
    "beam_fits_feed_swap": ("int", False, 0, ParamMeta(nom_de_guerre="Beam-FITSFeedSwap", info='')),
    "beam_fits_frame": (
        "str",
        False,
        'altaz',
        ParamMeta(
            nom_de_guerre="Beam-FITSFrame",
            info='coordinate frame for FITS beams. Currently, alt-az, equatorial and zenith mounts are supported.',
        ),
    ),
    "image_sky_model_base_image_name": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="ImageSkyModel-BaseImageName", info=''),
    ),
    "image_sky_model_dico_model": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="ImageSkyModel-DicoModel", info=''),
    ),
    "image_sky_model_nodes_file": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="ImageSkyModel-NodesFile", info=''),
    ),
    "image_sky_model_image_predict_parset": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="ImageSkyModel-ImagePredictParset", info=''),
    ),
    "image_sky_model_over_s": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="ImageSkyModel-OverS", info=''),
    ),
    "image_sky_model_mask_image": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="ImageSkyModel-MaskImage", info=''),
    ),
    "image_sky_model_wmax": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="ImageSkyModel-wmax", info=''),
    ),
    "image_sky_model_max_facet_size": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="ImageSkyModel-MaxFacetSize", info=''),
    ),
    "image_sky_model_min_facet_size": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="ImageSkyModel-MinFacetSize", info=''),
    ),
    "image_sky_model_remove_ddf_cache": (
        "bool",
        False,
        False,
        ParamMeta(nom_de_guerre="ImageSkyModel-RemoveDDFCache", info=''),
    ),
    "image_sky_model_ddf_cache_dir": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="ImageSkyModel-DDFCacheDir", info=''),
    ),
    "image_sky_model_filter_neg_comp": (
        "bool",
        False,
        False,
        ParamMeta(nom_de_guerre="ImageSkyModel-FilterNegComp", info=''),
    ),
    "image_sky_model_th_solve": (
        "float",
        False,
        0.0,
        ParamMeta(nom_de_guerre="ImageSkyModel-ThSolve", info=''),
    ),
    "data_selection_uv_min_max": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="DataSelection-UVMinMax", info=''),
    ),
    "data_selection_chan_slice": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="DataSelection-ChanSlice", info=''),
    ),
    "data_selection_flag_ants": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="DataSelection-FlagAnts", info=''),
    ),
    "data_selection_dist_max_to_core": (
        "float",
        False,
        10000.0,
        ParamMeta(nom_de_guerre="DataSelection-DistMaxToCore", info=''),
    ),
    "data_selection_fill_factor": (
        "float",
        False,
        1.0,
        ParamMeta(nom_de_guerre="DataSelection-FillFactor", info=''),
    ),
    "data_selection_field_id": (
        "int",
        False,
        0,
        ParamMeta(nom_de_guerre="DataSelection-FieldID", info=''),
    ),
    "data_selection_ddid": (
        "int",
        False,
        0,
        ParamMeta(nom_de_guerre="DataSelection-DDID", info=''),
    ),
    "weighting_resolution": (
        "float",
        False,
        0.0,
        ParamMeta(nom_de_guerre="Weighting-Resolution", info=''),
    ),
    "weighting_weight_in_col": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="Weighting-WeightInCol", info=''),
    ),
    "weighting_weighting": (
        "str",
        False,
        'Natural',
        ParamMeta(nom_de_guerre="Weighting-Weighting", info=''),
    ),
    "weighting_robust": ("float", False, 0.0, ParamMeta(nom_de_guerre="Weighting-Robust", info='')),
    "weighting_weight_uv_min_max": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="Weighting-WeightUVMinMax", info=''),
    ),
    "weighting_wtuv": ("int", False, 1, ParamMeta(nom_de_guerre="Weighting-WTUV", info='')),
    "actions_do_plot": ("int", False, 0, ParamMeta(nom_de_guerre="Actions-DoPlot", info='')),
    "actions_sub_only": ("int", False, 0, ParamMeta(nom_de_guerre="Actions-SubOnly", info='')),
    "actions_ncpu": ("int", False, 1, ParamMeta(nom_de_guerre="Actions-NCPU", info='')),
    "actions_do_bar": ("int", False, 1, ParamMeta(nom_de_guerre="Actions-DoBar", info='')),
    "actions_n_thread": ("int", False, 1, ParamMeta(nom_de_guerre="Actions-NThread", info='')),
    "actions_debug_pdb": ("int", False, 1, ParamMeta(nom_de_guerre="Actions-DebugPdb", info='')),
    "actions_update_weights": (
        "int",
        False,
        1,
        ParamMeta(nom_de_guerre="Actions-UpdateWeights", info=''),
    ),
    "pre_apply_pre_apply_sols": (
        "List[str]",
        False,
        [],
        ParamMeta(nom_de_guerre="PreApply-PreApplySols", info=''),
    ),
    "pre_apply_pre_apply_mode": (
        "List[str]",
        False,
        [],
        ParamMeta(nom_de_guerre="PreApply-PreApplyMode", info=''),
    ),
    "solutions_ext_sols": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="Solutions-ExtSols", info=''),
    ),
    "solutions_clip_method": (
        "str",
        False,
        '[ResidAnt]',
        ParamMeta(nom_de_guerre="Solutions-ClipMethod", info=''),
    ),
    "solutions_out_sols_name": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="Solutions-OutSolsName", info=''),
    ),
    "solutions_apply_to_dir": (
        "int",
        False,
        -2,
        ParamMeta(nom_de_guerre="Solutions-ApplyToDir", info=''),
    ),
    "solutions_merge_beam_to_applied_sol": (
        "int",
        False,
        0,
        ParamMeta(nom_de_guerre="Solutions-MergeBeamToAppliedSol", info=''),
    ),
    "solutions_apply_mode": (
        "str",
        False,
        'AP',
        ParamMeta(nom_de_guerre="Solutions-ApplyMode", info=''),
    ),
    "solutions_skip_existing_sols": (
        "int",
        False,
        0,
        ParamMeta(nom_de_guerre="Solutions-SkipExistingSols", info=''),
    ),
    "solutions_sols_dir": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="Solutions-SolsDir", info=''),
    ),
    "compression_compression_mode": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="Compression-CompressionMode", info='auto, manual'),
    ),
    "compression_compression_dir_file": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="Compression-CompressionDirFile", info=''),
    ),
    "compression_merge_stations": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="Compression-MergeStations", info=''),
    ),
    "solvers_solver_type": (
        "str",
        False,
        'CohJones',
        ParamMeta(nom_de_guerre="Solvers-SolverType", info=''),
    ),
    "solvers_precision_dot": (
        "str",
        False,
        'D',
        ParamMeta(nom_de_guerre="Solvers-PrecisionDot", info=''),
    ),
    "solvers_pol_mode": (
        "str",
        False,
        'Scalar',
        ParamMeta(nom_de_guerre="Solvers-PolMode", info=''),
    ),
    "solvers_dt": ("int", False, 30, ParamMeta(nom_de_guerre="Solvers-dt", info='')),
    "solvers_n_chan_sols": ("int", False, 1, ParamMeta(nom_de_guerre="Solvers-NChanSols", info='')),
    "coh_jones_n_iter_lm": ("int", False, 7, ParamMeta(nom_de_guerre="CohJones-NIterLM", info='')),
    "coh_jones_lambda_lm": ("int", False, 1, ParamMeta(nom_de_guerre="CohJones-LambdaLM", info='')),
    "coh_jones_lambda_tk": (
        "float",
        False,
        0.0,
        ParamMeta(nom_de_guerre="CohJones-LambdaTk", info=''),
    ),
    "kafca_n_iter_kf": ("int", False, 6, ParamMeta(nom_de_guerre="KAFCA-NIterKF", info='')),
    "kafca_lambda_kf": ("float", False, 0.5, ParamMeta(nom_de_guerre="KAFCA-LambdaKF", info='')),
    "kafca_init_lm": ("int", False, 0, ParamMeta(nom_de_guerre="KAFCA-InitLM", info='')),
    "kafca_init_l_mdt": ("int", False, 5, ParamMeta(nom_de_guerre="KAFCA-InitLMdt", info='')),
    "kafca_cov_p": ("float", False, 0.1, ParamMeta(nom_de_guerre="KAFCA-CovP", info='')),
    "kafca_cov_q": ("float", False, 0.1, ParamMeta(nom_de_guerre="KAFCA-CovQ", info='')),
    "kafca_power_smooth": (
        "float",
        False,
        1.0,
        ParamMeta(nom_de_guerre="KAFCA-PowerSmooth", info=''),
    ),
    "kafca_ev_p_step": ("int", False, 120, ParamMeta(nom_de_guerre="KAFCA-evPStep", info='')),
    "kafca_ev_p_step_start": (
        "int",
        False,
        1,
        ParamMeta(nom_de_guerre="KAFCA-evPStepStart", info=''),
    ),
    "kafca_evolution_sol_file": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="KAFCA-EvolutionSolFile", info=''),
    ),
}

killms = define_cab(
    "killms",
    "kMS.py",
    images.KILLMS,
    _FIELDS,
    policies=Policies(prefix="--"),
    info="killMS: direction-dependent calibration for radio interferometric data "
    "(https://github.com/saopicc/killMS)",
)
