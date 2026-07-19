"""ddfacet -- DDFacet, a facet-based radio-interferometric imager/deconvolver
(https://github.com/saopicc/DDFacet).

Ported from DDFacet 1.0.0.0's own `DDFacet/Parset/DefaultParset.cfg` --
not cult-cargo's `ddfacet.yml` (which declares `dynamic_schema`, unresolved
per AGENTS.md) -- cross-checked against DDFacet's own
`DDFacet/Parset/ddfacet_stimela_inputs_schema.yaml` (a real stimela cab
schema DDFacet's own `generate_stimela_schema.py` publishes) for the
handful of fields (`Data.MS`, ...) whose real dtype the YAML declares but
the `.cfg`'s own `#type:` annotation omits.

`DefaultParset.cfg` documents its own format at the end of the file: every
option becomes `--Section-OptionName` on the real CLI (case preserved
exactly, hence the literal-cased `nom_de_guerre` below rather than the
usual all-lowercase hyphenation), an explicit `#type:X` comment tag pins
the type, and in its absence the raw default is parsed the same way
DDFacet's own `ReadCFG.py` does (`ast.literal_eval`, falling back to a
plain string when that fails -- e.g. bare words like `Clean`/`auto`/`Briggs`
are just `str` defaults, matching the tool's own real fallback behaviour,
not a transcription shortcut). Fields marked `#no_cmdline:1` in the `.cfg`
(parset-only, e.g. `Misc.ParsetVersion`) are excluded -- they can't be set
via the CLI DDFacet itself exposes.

273 real options across 30 sections -- far past SOFiA-2-scale, not hand-curated the
way `bdsf.catalog` deliberately is (DDFacet has no equivalent
"cult-cargo already narrowed this down" precedent to defer to). Comma-
separated list-valued fields (`Data-MS`, `Selection-UVRangeKm`, ...) use
shinobi's default `list_sep=","` formatting -- no `repeat_list`/
`repeat_as_tokens` override needed, since none of these fields repeat the
flag itself.

No outputs are modelled: DDFacet's own `Output-Images` letter-code system
produces a dynamically-named set of FITS files (`{Output-Name}.<code>.fits`
per requested code) that isn't a single, statically-knowable path -- the
same "no dynamic-naming implicit" call as `breizorro.py`'s `outfile`.

`parset` is a real, separate thing from any `--Section-Option` flag:
`DDF.py`'s own `main()` (`DDF.py [parset file] <options>`) treats a lone
non-flag argument as a parset file to read defaults from before applying
the rest of the CLI, via `MyOptParse`'s leftover positional args
(`args = OP.GiveArguments()`; `if len(args) == 1: ParsetFile = args[0]`).
`optparse`'s leftover-arg collection is order-insensitive (it doesn't
care where the bare token sits among recognised `--flag value` pairs),
so either `positional` or `positional_head` would work here -- modelled
as `ParamMeta(positional_head=True)` anyway, both to match `DDF.py`'s own
documented `[parset file] <options>` usage order and for consistency
with `cubical.py`/`killms.py`, whose own tools genuinely require head
placement (see `cubical.py`'s docstring). Optional: `None` -> omitted,
per `build_argv`'s `if value is None: continue`.
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
            "(DDF.py [parset file] <options>)",
        ),
    ),
    "data_ms": (
        "List[MS]",
        False,
        None,
        ParamMeta(
            nom_de_guerre="Data-MS",
            info="Single MS name, or list of comma-separated MSs, or name of *.txt file listing MSs. Note that each MS may also be specified as a glob pattern (e.g. *.MS), and may be suffixed with '//Dx' and/or '//Fy' to select specific DATA_DESC_ID and FIELD_IDs in the MS. 'x' and 'y' can take the form of a single number, a Pythonic range (e.g. '0:16'), an inclusive range ('0~15'), or '*' to select all. E.g. 'foo.MS//D*//F0:2' selects all DDIDs, and fields 0 and 1 from foo.MS. If D and/or F is not specified, --Selection-Field and --Selection-DDID is used as the default.",
        ),
    ),
    "data_col_name": (
        "str",
        False,
        "CORRECTED_DATA",
        ParamMeta(
            nom_de_guerre="Data-ColName", info="MS column to image (Default: CORRECTED_DATA)"
        ),
    ),
    "data_chunk_hours": (
        "float",
        False,
        0.0,
        ParamMeta(
            nom_de_guerre="Data-ChunkHours",
            info="Process data in chunks of <=N hours. Use 0 for no chunking. (Default: 0.0)",
        ),
    ),
    "data_chunk_rows": (
        "int",
        False,
        0,
        ParamMeta(
            nom_de_guerre="Data-ChunkRows",
            info="Process data in chunks of <=N rows, for dask mode. Overrides ChunkHours. Use -1 for native dataset chunking (required in zarr mode).",
        ),
    ),
    "data_sort": (
        "bool",
        False,
        False,
        ParamMeta(
            nom_de_guerre="Data-Sort",
            info="if True, data will be resorted by baseline-time order internally. This usually speeds up processing. (Default: False)",
        ),
    ),
    "data_dask": (
        "bool",
        False,
        False,
        ParamMeta(
            nom_de_guerre="Data-Dask", info="If True, uses dask-ms IO layer instead of casacore"
        ),
    ),
    "predict_col_name": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="Predict-ColName",
            info="MS column to write predict to. Can be empty to disable.",
        ),
    ),
    "predict_mask_square": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="Predict-MaskSquare",
            info="Use this field if you want to predict (in/out)side a square region. Syntax is (MaskOutSide,NpixInside). For example setting (0,1000) will predict the outer (1000x1000) square only",
        ),
    ),
    "predict_from_image": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="Predict-FromImage",
            info="In --Image-Mode=Predict, will predict data from this image, rather than --Data-InitDicoModel",
        ),
    ),
    "predict_init_dico_model": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="Predict-InitDicoModel", info="Resume deconvolution from given DicoModel"
        ),
    ),
    "predict_overwrite": (
        "bool",
        False,
        True,
        ParamMeta(
            nom_de_guerre="Predict-Overwrite",
            info="Allow overwriting of predict column (Default: True)",
        ),
    ),
    "selection_field": (
        "int",
        False,
        0,
        ParamMeta(
            nom_de_guerre="Selection-Field",
            info="default FIELD_ID to read, if not specified in --Data-MS. (Default: 0)",
        ),
    ),
    "selection_ddid": (
        "int",
        False,
        0,
        ParamMeta(
            nom_de_guerre="Selection-DDID",
            info="default DATA_DESC_ID to read, if not specified in --Data-MS. (Default: 0)",
        ),
    ),
    "selection_ta_ql": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="Selection-TaQL", info="additional TaQL selection string"),
    ),
    "selection_chan_start": (
        "int",
        False,
        0,
        ParamMeta(nom_de_guerre="Selection-ChanStart", info="First channel (Default: 0)"),
    ),
    "selection_chan_end": (
        "int",
        False,
        -1,
        ParamMeta(
            nom_de_guerre="Selection-ChanEnd",
            info="Last channel+1, -1 means up and including last channel. (Default: -1)",
        ),
    ),
    "selection_chan_step": (
        "int",
        False,
        1,
        ParamMeta(nom_de_guerre="Selection-ChanStep", info="Channel stepping (Default: 1)"),
    ),
    "selection_flag_ants": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="Selection-FlagAnts",
            info="List of antennas to be flagged, e.g. 'RS,CS017LBA'",
        ),
    ),
    "selection_uv_range_km": (
        "List[float]",
        False,
        [0, 2000],
        ParamMeta(
            nom_de_guerre="Selection-UVRangeKm", info="Select baseline range (Default: [0, 2000])"
        ),
    ),
    "selection_time_range": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="Selection-TimeRange",
            info="Select time range (two comma separated values) containing UTC start and end times in ISO8601",
        ),
    ),
    "selection_time_range_from_start_min": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="Selection-TimeRangeFromStartMin", info="In minutes before start of obs."
        ),
    ),
    "selection_dist_max_to_core": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="Selection-DistMaxToCore",
            info="Select antennas by specifying a maximum distance to core",
        ),
    ),
    "selection_auto_flag_nyquist": (
        "int",
        False,
        0,
        ParamMeta(
            nom_de_guerre="Selection-AutoFlagNyquist",
            info="flag those baselines that are not properly sampled",
        ),
    ),
    "output_mode": (
        "str",
        False,
        "Clean",
        ParamMeta(
            nom_de_guerre="Output-Mode",
            choices=["Dirty", "Clean", "Predict", "PSF"],
            info="What to do. (Default: Clean) [choices: Dirty, Clean, Predict, PSF]",
        ),
    ),
    "output_clobber": (
        "bool",
        False,
        False,
        ParamMeta(
            nom_de_guerre="Output-Clobber",
            info="Allow overwriting of existing parset and images (can't be specified via parset!) (Default: False)",
        ),
    ),
    "output_name": (
        "str",
        False,
        "image",
        ParamMeta(nom_de_guerre="Output-Name", info="Base name of output images (Default: image)"),
    ),
    "output_shift_facets_file": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="Output-ShiftFacetsFile",
            info="Astrometric correction per facet, when Image-Mode=RestoreAndShift",
        ),
    ),
    "output_restoring_beam": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="Output-RestoringBeam", info=""),
    ),
    "output_also": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="Output-Also",
            info="Save also these images (i.e. adds to the default set of --Output-Images)",
        ),
    ),
    "output_cubes": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="Output-Cubes",
            info="Also save cube versions for these images (only MmRrIi codes recognized)",
        ),
    ),
    "output_images": (
        "str",
        False,
        "DdPAMRIikemz",
        ParamMeta(
            nom_de_guerre="Output-Images",
            info="Combination of letter codes indicating what images to save. Uppercase for intrinsic flux scale [D]irty, [M]odel, [C]onvolved model, [R]esiduals, restored [I]mage; Lowercase for apparent flux scale [d]irty, [m]odel, [c]onvolved model, [r]esiduals, restored [i]mage; Other images: [P]SF, [N]orm, [n]orm facets, [S] flux scale, [A]lpha (spectral index), [X] mixed-scale (intrinsic model, apparent residuals, i.e. Cyrils original output), [o] intermediate mOdels (Model_i), [e] intermediate rEsiduals (Residual_i), [k] intermediate masK image, [z] intermediate auto mask-related noiZe image, [g] intermediate dirty images (only if [Debugging] SaveIntermediateDirtyImages is enabled). [F] intrinsic MFS restored image [f] apparent MFS restored image Use 'all' to save all. (Default: DdPAMRIikze)",
        ),
    ),
    "output_stokes_residues": (
        "str",
        False,
        "I",
        ParamMeta(
            nom_de_guerre="Output-StokesResidues",
            choices=["I", "IQ", "IV", "QU", "IQUV"],
            info="After cleaning Stokes I, output specified residues if [r] or [R] is specified in option Output-Images. Note that the imager does not perform deconvolution on any Stokes products other than I - it only outputs residues. (Default: I) [choices: I, IQ, IV, QU, IQUV]",
        ),
    ),
    "spi_maps_alpha_threshold": (
        "int",
        False,
        15,
        ParamMeta(
            nom_de_guerre="SPIMaps-AlphaThreshold",
            info="Multiple of the RMS in final residual which determines threshold for fitting alpha map. (Default: 15)",
        ),
    ),
    "image_n_pix": (
        "int",
        False,
        5000,
        ParamMeta(nom_de_guerre="Image-NPix", info="Image size. (Default: 5000)"),
    ),
    "image_cell": (
        "float",
        False,
        5.0,
        ParamMeta(nom_de_guerre="Image-Cell", info="Cell size. (Default: 5.0)"),
    ),
    "image_phase_center_radec": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="Image-PhaseCenterRADEC",
            info="Use non-default phase centre. If 'align' is used, all MSs will be rephased to the phase centre of the first MS. Otherwise, specify [HH:MM:SS,DD:MM:SS] direction. If empty, no rephasing is done. (Default: align)",
        ),
    ),
    "image_image_center_radec": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="Image-ImageCenterRADEC",
            info="The central coordinates of the field's image. While PhaseCenterRADEC rotate the visibilities, this will image on the tangential plane to the phase center but centered on ImageCenterRADEC.",
        ),
    ),
    "image_sidelobe_search_window": (
        "int",
        False,
        200,
        ParamMeta(
            nom_de_guerre="Image-SidelobeSearchWindow",
            info="Size of PSF subwindow (centred around the main lobe) to search for the highest sidelobe when fitting the PSF size. (Default: 200)",
        ),
    ),
    "image_multi_field_file": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="Image-MultiFieldFile",
            info="This is in dev. Takes a txt file as input containing the (ra, dec, FOVarcsec) coordinates of the fields",
        ),
    ),
    "facets_n_facets": (
        "int",
        False,
        3,
        ParamMeta(nom_de_guerre="Facets-NFacets", info="Number of facets to use. (Default: 3)"),
    ),
    "facets_cat_nodes": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="Facets-CatNodes",
            info="An .npy file containing the ra/dec coordnidates (in radians) of the tessel domain directions.",
        ),
    ),
    "facets_diam_max": (
        "float",
        False,
        180.0,
        ParamMeta(
            nom_de_guerre="Facets-DiamMax",
            info="Max facet size, for tessellations. Larger facets will be broken up. (Default: 180.0)",
        ),
    ),
    "facets_diam_min": (
        "float",
        False,
        0.0,
        ParamMeta(
            nom_de_guerre="Facets-DiamMin",
            info="Min facet size, for tessellations. Smaller facets will be merged. (Default: 0.0)",
        ),
    ),
    "facets_mixing_width": (
        "int",
        False,
        10,
        ParamMeta(
            nom_de_guerre="Facets-MixingWidth",
            info="Sigma of the gaussian (in pixels) being used to mix the facets on their edges (Default: 10)",
        ),
    ),
    "facets_single_psf": (
        "int",
        False,
        0,
        ParamMeta(
            nom_de_guerre="Facets-SinglePSF",
            info="Use a single, central PSF instead of one per facet",
        ),
    ),
    "facets_psf_oversize": (
        "float",
        False,
        1.0,
        ParamMeta(
            nom_de_guerre="Facets-PSFOversize",
            info="For cleaning, use oversize PSF relative to size of facet. (Default: 1.0)",
        ),
    ),
    "facets_psf_facets": (
        "int",
        False,
        0,
        ParamMeta(
            nom_de_guerre="Facets-PSFFacets",
            info="Number of PSF facets to make. 0: same as NFacets (one PSF per facet) 1: one PSF for entire field. (Default: 0)",
        ),
    ),
    "facets_padding": (
        "float",
        False,
        1.7,
        ParamMeta(nom_de_guerre="Facets-Padding", info="Facet padding factor. (Default: 1.7)"),
    ),
    "facets_circumcision": (
        "int",
        False,
        0,
        ParamMeta(
            nom_de_guerre="Facets-Circumcision",
            info="Set to non-0 to override NPixMin computation in FacetsToIm(). Debugging option, really. (Default: 0)",
        ),
    ),
    "facets_flux_padding_app_model": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="Facets-FluxPaddingAppModel",
            info="For flux-dependent facet-padding, the apparant model image (or cube)",
        ),
    ),
    "facets_flux_padding_scale": (
        "float",
        False,
        2.0,
        ParamMeta(
            nom_de_guerre="Facets-FluxPaddingScale",
            info="The factor applied to the --Facets-Padding for the facet with the highest flux",
        ),
    ),
    "facets_skip_th": (
        "float",
        False,
        0.0,
        ParamMeta(
            nom_de_guerre="Facets-SkipTh",
            info="Skip gridding/degridding if the mean Jones power is lower than this level (useful in mosaicing mode)",
        ),
    ),
    "weight_col_name": (
        "str",
        False,
        "WEIGHT_SPECTRUM",
        ParamMeta(
            nom_de_guerre="Weight-ColName",
            info="Read data weights from specified column. Use WEIGHT_SPECTRUM or WEIGHT, more rarely IMAGING_WEIGHT. (Default: WEIGHT_SPECTRUM)",
        ),
    ),
    "weight_mode": (
        "str",
        False,
        "Briggs",
        ParamMeta(
            nom_de_guerre="Weight-Mode",
            choices=["Natural", "Uniform", "Robust", "Briggs"],
            info="Image weighting. (Default: Briggs) [choices: Natural, Uniform, Robust, Briggs]",
        ),
    ),
    "weight_mfs": (
        "bool",
        False,
        True,
        ParamMeta(
            nom_de_guerre="Weight-MFS",
            info="If True, MFS uniform/Briggs weighting is used (all channels binned onto one uv grid). If 0, binning is per-band. (Default: True)",
        ),
    ),
    "weight_robust": (
        "float",
        False,
        0.0,
        ParamMeta(
            nom_de_guerre="Weight-Robust",
            info="Briggs robustness parameter, from -2 to 2. (Default: 0.0)",
        ),
    ),
    "weight_super_uniform": (
        "float",
        False,
        1.0,
        ParamMeta(
            nom_de_guerre="Weight-SuperUniform",
            info="Super/subuniform weighting: FoV for weighting purposes is taken as X*Image_Size (Default: 1.0)",
        ),
    ),
    "weight_out_col_name": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="Weight-OutColName",
            info="Save the internally computed weights into this column",
        ),
    ),
    "weight_enable_sigmoid_taper": (
        "int",
        False,
        0,
        ParamMeta(
            nom_de_guerre="Weight-EnableSigmoidTaper",
            info="Toggles sigmoid tapering type:bool (Default: 0)",
        ),
    ),
    "weight_sigmoid_taper_inner_cutoff": (
        "float",
        False,
        0.0,
        ParamMeta(
            nom_de_guerre="Weight-SigmoidTaperInnerCutoff",
            info="Inner taper cutoff in uvwavelengths type:float (Default: 0.0)",
        ),
    ),
    "weight_sigmoid_taper_outer_cutoff": (
        "float",
        False,
        0.0,
        ParamMeta(
            nom_de_guerre="Weight-SigmoidTaperOuterCutoff",
            info="Outer taper cutoff in uvwavelengths type:float (Default: 0.0)",
        ),
    ),
    "weight_sigmoid_taper_inner_rolloff_strength": (
        "float",
        False,
        0.5,
        ParamMeta(
            nom_de_guerre="Weight-SigmoidTaperInnerRolloffStrength",
            info="Rolloff strength on inner taper if enabled. 1.0 is essentially a boxcar, 0.0 means very long rolloffs type:float (Default: 0.5)",
        ),
    ),
    "weight_sigmoid_taper_outer_rolloff_strength": (
        "float",
        False,
        0.5,
        ParamMeta(
            nom_de_guerre="Weight-SigmoidTaperOuterRolloffStrength",
            info="Rolloff strength on outer taper if enabled. 1.0 is essentially a boxcar, 0.0 means very long rolloffs type:float (Default: 0.5)",
        ),
    ),
    "rime_precision": (
        "str",
        False,
        "S",
        ParamMeta(
            nom_de_guerre="RIME-Precision",
            choices=["S", "D"],
            info="Single or double precision gridding. DEPRECATED? (Default: S) [choices: S, D]",
        ),
    ),
    "rime_pol_mode": (
        "str",
        False,
        "I",
        ParamMeta(
            nom_de_guerre="RIME-PolMode",
            choices=["I", "IQ", "IU", "IV", "IQU", "IQUV"],
            info="(DIRTY ONLY) Polarization mode. (Default: I) [choices: I, IQ, IU, IV, IQU, IQUV]",
        ),
    ),
    "rime_full_m_tilde": (
        "bool",
        False,
        False,
        ParamMeta(
            nom_de_guerre="RIME-FullMTilde",
            info="Uee the full MTilde as described in the paper to do the image plane correction type:bool",
        ),
    ),
    "rime_fft_machine": (
        "str",
        False,
        "FFTW",
        ParamMeta(nom_de_guerre="RIME-FFTMachine", info="(Default: FFTW)"),
    ),
    "rime_forward_mode": (
        "str",
        False,
        "BDA-degrid",
        ParamMeta(
            nom_de_guerre="RIME-ForwardMode",
            choices=["BDA-degrid", "Classic", "Montblanc"],
            info="Forward predict mode. (Default: BDA-degrid) [choices: BDA-degrid, Classic, Montblanc]",
        ),
    ),
    "rime_backward_mode": (
        "str",
        False,
        "BDA-grid",
        ParamMeta(
            nom_de_guerre="RIME-BackwardMode",
            choices=["BDA-grid", "Classic"],
            info="Backward mode. (Default: BDA-grid) [choices: BDA-grid, Classic]",
        ),
    ),
    "rime_decorr_mode": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="RIME-DecorrMode", info="decorrelation mode"),
    ),
    "rime_decorr_location": (
        "str",
        False,
        "Edge",
        ParamMeta(
            nom_de_guerre="RIME-DecorrLocation",
            choices=["Center", "Edge"],
            info="where decorrelation is estimated (Default: Edge) [choices: Center, Edge]",
        ),
    ),
    "cf_over_s": (
        "int",
        False,
        11,
        ParamMeta(nom_de_guerre="CF-OverS", info="Oversampling factor. (Default: 11)"),
    ),
    "cf_support": (
        "int",
        False,
        7,
        ParamMeta(nom_de_guerre="CF-Support", info="CF support size. (Default: 7)"),
    ),
    "cf_nw": (
        "int",
        False,
        100,
        ParamMeta(
            nom_de_guerre="CF-Nw",
            info="Number of w-planes. Setting this to 1 enables AIPS style faceting. (Default: 100)",
        ),
    ),
    "cf_wmax": (
        "float",
        False,
        0.0,
        ParamMeta(
            nom_de_guerre="CF-wmax",
            info="Maximum w coordinate. Visibilities with larger w will not be gridded. If 0, no maximum is imposed. (Default: 0.0)",
        ),
    ),
    "comp_grid_decorr": (
        "float",
        False,
        0.02,
        ParamMeta(
            nom_de_guerre="Comp-GridDecorr",
            info="Maximum BDA decorrelation factor (gridding) (Default: 0.02)",
        ),
    ),
    "comp_grid_fo_v": (
        "str",
        False,
        "Facet",
        ParamMeta(
            nom_de_guerre="Comp-GridFoV",
            choices=["Full", "Facet"],
            info="FoV over which decorrelation factor is computed (gridding) (Default: Facet) [choices: Full, Facet]",
        ),
    ),
    "comp_degrid_decorr": (
        "float",
        False,
        0.02,
        ParamMeta(
            nom_de_guerre="Comp-DegridDecorr",
            info="Maximum BDA decorrelation factor (degridding) (Default: 0.02)",
        ),
    ),
    "comp_degrid_fo_v": (
        "str",
        False,
        "Facet",
        ParamMeta(
            nom_de_guerre="Comp-DegridFoV",
            choices=["Full", "Facet"],
            info="FoV over which decorrelation factor is computed (degridding) (Default: Facet) [choices: Full, Facet]",
        ),
    ),
    "comp_sparsification": (
        "int",
        False,
        0,
        ParamMeta(
            nom_de_guerre="Comp-Sparsification",
            info="apply sparsification compression to initial major cycles. Sparsification refers to throwing away random visibilities. Supply a list of factors: e.g. 100,30,10 would mean only 1/100 of the data is used for the first major cycle, 1/30 for the second, 1/10 for the third, and full data for the fourth cycle onwards. This can substantially accelerate deconvolution of deep observations, since, in these regimes, very little sensitivity is required for model construction in the initial cycles. (Default: 0)",
        ),
    ),
    "comp_bda_mode": (
        "int",
        False,
        1,
        ParamMeta(
            nom_de_guerre="Comp-BDAMode",
            choices=[1, 2],
            info="BDA block computation mode. 1 for Cyril's old mode, 2 for Oleg's new mode. 2 is faster but see issue #319. (Default: 1) [choices: 1, 2]",
        ),
    ),
    "comp_bda_jones": (
        "int",
        False,
        0,
        ParamMeta(
            nom_de_guerre="Comp-BDAJones",
            info="If disabled, gridders and degridders will apply a Jones terms per visibility. If 'grid', gridder will apply them per BDA block, if 'both' so will the degridder. This is faster but possibly less accurate, if you have rapidly evolving Jones terms. (Default: 0)",
        ),
    ),
    "parallel_ncpu": (
        "int",
        False,
        0,
        ParamMeta(
            nom_de_guerre="Parallel-NCPU",
            info="Number of CPUs to use in parallel mode. 0: use all available. 1: disable parallelism. (Default: 0)",
        ),
    ),
    "parallel_affinity": (
        "int",
        False,
        1,
        ParamMeta(
            nom_de_guerre="Parallel-Affinity",
            info="pin processes to cores. -1/1/2 determines stepping used in selecting cores. Alternatively specifies a list of length NCPU. Alternatively 'disable' to disable affinity settings Alternatively 'enable_ht' uses stepping of 1 (equivalent to Parallel.Affinity=1), will use all vthreads - the obvious exception is if HT is disabled at BIOS level Alternatively 'disable_ht' autodetects the NUMA layout of the chip for Debian-based systems and dont use both vthreads per core Use 1 if unsure. (Default: 1)",
        ),
    ),
    "parallel_main_process_affinity": (
        "str",
        False,
        "disable",
        ParamMeta(
            nom_de_guerre="Parallel-MainProcessAffinity",
            info="this should be set to a core that is not used by forked processes, this option is ignored when using option 'disable or disable_ht' for Parallel.Affinity (Default: 0)",
        ),
    ),
    "cache_reset": (
        "bool",
        False,
        False,
        ParamMeta(
            nom_de_guerre="Cache-Reset",
            info="Reset all caches (including PSF and dirty image) (Default: False)",
        ),
    ),
    "cache_jones": (
        "str",
        False,
        "auto",
        ParamMeta(
            nom_de_guerre="Cache-Jones",
            choices=["reset", "auto"],
            info="Reset cached Jones [choices: reset, auto]",
        ),
    ),
    "cache_smooth_beam": (
        "str",
        False,
        "auto",
        ParamMeta(
            nom_de_guerre="Cache-SmoothBeam",
            choices=["reset", "auto", "force"],
            info="Reset cached smmoth beam (Default: auto) [choices: reset, auto, force]",
        ),
    ),
    "cache_weight": (
        "str",
        False,
        "auto",
        ParamMeta(
            nom_de_guerre="Cache-Weight",
            choices=["reset", "auto"],
            info="Reset cached smmoth beam (Default: auto) [choices: reset, auto]",
        ),
    ),
    "cache_psf": (
        "str",
        False,
        "auto",
        ParamMeta(
            nom_de_guerre="Cache-PSF",
            choices=["off", "reset", "auto", "force"],
            info="Cache PSF data. (Default: auto) [choices: off, reset, auto, force]",
        ),
    ),
    "cache_dirty": (
        "str",
        False,
        "auto",
        ParamMeta(
            nom_de_guerre="Cache-Dirty",
            choices=["off", "reset", "auto", "forcedirty", "forceresidual"],
            info="Cache dirty image data. (Default: auto) [choices: off, reset, auto, forcedirty, forceresidual]",
        ),
    ),
    "cache_vis_data": (
        "str",
        False,
        "auto",
        ParamMeta(
            nom_de_guerre="Cache-VisData",
            choices=["off", "auto", "force"],
            info="Cache visibility data and flags at runtime. (Default: auto) [choices: off, auto, force]",
        ),
    ),
    "cache_last_residual": (
        "bool",
        False,
        1,
        ParamMeta(
            nom_de_guerre="Cache-LastResidual",
            info="Cache last residual data (at end of last minor cycle) (Default: True)",
        ),
    ),
    "cache_dir": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="Cache-Dir",
            info="Directory to store caches in. Default is to keep cache next to the MS, but this can cause performance issues with e.g. NFS volumes. If you have fast local storage, point to it. %metavar:DIR",
        ),
    ),
    "cache_dir_wisdom_fftw": (
        "str",
        False,
        "~/.fftw_wisdom",
        ParamMeta(
            nom_de_guerre="Cache-DirWisdomFFTW",
            info="Directory in which to store the FFTW wisdom files (Default: ~/.fftw_wisdom)",
        ),
    ),
    "cache_reset_wisdom": (
        "bool",
        False,
        False,
        ParamMeta(nom_de_guerre="Cache-ResetWisdom", info="Reset Wisdom file (Default: False)"),
    ),
    "cache_cf": (
        "bool",
        False,
        True,
        ParamMeta(
            nom_de_guerre="Cache-CF",
            info="Cache convolution functions. With many CPUs, may be faster to recompute. (Default: True)",
        ),
    ),
    "cache_hmp": (
        "bool",
        False,
        False,
        ParamMeta(
            nom_de_guerre="Cache-HMP",
            info="Cache HMP basis functions. With many CPUs, may be faster to recompute. (Default: False)",
        ),
    ),
    "cache_remnant": (
        "bool",
        False,
        False,
        ParamMeta(
            nom_de_guerre="Cache-Remnant",
            info="If set to True, some structures survive to the death of DDFacet, so they can be revived faster",
        ),
    ),
    "beam_model": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="Beam-Model",
            choices=["None", "LOFAR", "FITS", "GMRT", "ATCA", "NENUFAR", "Everybeam"],
            info="Beam model to use. [choices: None, LOFAR, FITS, GMRT, ATCA, NENUFAR, Everybeam]",
        ),
    ),
    "beam_at": (
        "str",
        False,
        "facet",
        ParamMeta(
            nom_de_guerre="Beam-At",
            choices=["facet", "tessel"],
            info="when DDESolutions are enabled, compute beam per facet, or per larger solution tessel (Default: facet) [choices: facet, tessel]",
        ),
    ),
    "beam_phased_array_mode": (
        "str",
        False,
        "A",
        ParamMeta(
            nom_de_guerre="Beam-PhasedArrayMode",
            choices=["A", "AE"],
            info="PhasedArrayMode beam mode. [choices: A, AE]",
        ),
    ),
    "beam_force_scalar": (
        "bool",
        False,
        False,
        ParamMeta(
            nom_de_guerre="Beam-ForceScalar",
            info="Force Jones matrix to be scalar (used for FITS beam mode for instance)",
        ),
    ),
    "beam_n_band": (
        "int",
        False,
        0,
        ParamMeta(
            nom_de_guerre="Beam-NBand",
            info="Number of channels over which same beam value is used. 0 means use every channel. (Default: 0)",
        ),
    ),
    "beam_center_norm": (
        "bool",
        False,
        False,
        ParamMeta(
            nom_de_guerre="Beam-CenterNorm",
            info="Normalize beam so that its amplitude at the centre is 1. (Default: False)",
        ),
    ),
    "beam_smooth": (
        "bool",
        False,
        False,
        ParamMeta(
            nom_de_guerre="Beam-Smooth",
            info="Compute the interpolated smooth beam (Default: False)",
        ),
    ),
    "beam_smooth_n_pix": (
        "int",
        False,
        11,
        ParamMeta(
            nom_de_guerre="Beam-SmoothNPix",
            info="Number of pixels the beam is evaluated and smoothed (Default: 11)",
        ),
    ),
    "beam_smooth_interp_mode": (
        "str",
        False,
        "Linear",
        ParamMeta(nom_de_guerre="Beam-SmoothInterpMode", info="Linear/Log"),
    ),
    "beam_fits_file": (
        "str",
        False,
        "beam_$(corr)_$(reim).fits",
        ParamMeta(
            nom_de_guerre="Beam-FITSFile",
            info="Beam FITS file pattern. A beam pattern consists of eight FITS files, i.e. a real and imaginary part for each of the four Jones terms. The following substitutions are performed to form up the eight filenames: $(corr) or $(xy) is replaced by the Jones element label (e.g. 'xx' or 'rr'), $(reim) is replaced by 're' or 'im', $(realimag) is replaced by 'real' or 'imag'. Uppercase variables are replaced by uppercase values, e.g. $(REIM) by 'RE' pr 'IM'. Use 'unity' if you want to apply a unity matrix for the E term (e.g. only want to do visibility derotations). Correlation labels (XY or RL) are determined by reading the MS, but may be overridden by the FITSFeed option. (Default: beam_$(corr)_$(reim).fits)",
        ),
    ),
    "beam_fits_feed": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="Beam-FITSFeed",
            choices=["None", "xy", "XY", "rl", "RL"],
            info="If set, overrides correlation labels given by the measurement set. [choices: None, xy, XY, rl, RL]",
        ),
    ),
    "beam_fits_feed_swap": (
        "bool",
        False,
        False,
        ParamMeta(
            nom_de_guerre="Beam-FITSFeedSwap",
            info="swap feed patterns (X to Y and R to L) (Default: False)",
        ),
    ),
    "beam_dt_beam_min": (
        "float",
        False,
        5.0,
        ParamMeta(
            nom_de_guerre="Beam-DtBeamMin",
            info="change in minutes on which the beam is re-evaluated (Default: 5.0)",
        ),
    ),
    "beam_fits_par_angle_inc_deg": (
        "float",
        False,
        5.0,
        ParamMeta(
            nom_de_guerre="Beam-FITSParAngleIncDeg",
            info="increment in PA in degrees at which the beam is to be re-evaluated (on top of DtBeamMin) (Default: 5.0)",
        ),
    ),
    "beam_fitsl_axis": (
        "str",
        False,
        "-X",
        ParamMeta(
            nom_de_guerre="Beam-FITSLAxis",
            info="L axis of FITS file. Minus sign indicates reverse coordinate convention. (Default: -X)",
        ),
    ),
    "beam_fitsm_axis": (
        "str",
        False,
        "Y",
        ParamMeta(
            nom_de_guerre="Beam-FITSMAxis",
            info="M axis of FITS file. Minus sign indicates reverse coordinate convention. (Default: Y)",
        ),
    ),
    "beam_fits_verbosity": (
        "int",
        False,
        0,
        ParamMeta(
            nom_de_guerre="Beam-FITSVerbosity",
            info="set to >0 to have verbose output from FITS interpolator classes. (Default: 0)",
        ),
    ),
    "beam_fits_frame": (
        "str",
        False,
        "altaz",
        ParamMeta(
            nom_de_guerre="Beam-FITSFrame",
            choices=["altaz", "altazgeo", "equatorial", "zenith"],
            info="coordinate frame for FITS beams. Currently, alt-az, equatorial and zenith mounts are supported. (Default: altaz) [choices: altaz, altazgeo, equatorial, zenith]",
        ),
    ),
    "beam_feed_angle": (
        "float",
        False,
        0.0,
        ParamMeta(
            nom_de_guerre="Beam-FeedAngle",
            info="offset feed angle to add to parallactic angle (Default: 0.0)",
        ),
    ),
    "beam_apply_p_jones": (
        "int",
        False,
        0,
        ParamMeta(
            nom_de_guerre="Beam-ApplyPJones",
            info="derotate visibility data (only when FITS beam is active and also time sampled) (Default: 0)",
        ),
    ),
    "beam_flip_visibility_hands": (
        "int",
        False,
        0,
        ParamMeta(
            nom_de_guerre="Beam-FlipVisibilityHands",
            info="apply anti-diagonal matrix if FITS beam is enabled effectively swapping X and Y or R and L and their respective hands (Default: 0)",
        ),
    ),
    "beam_pointing_centre": (
        "str",
        False,
        "PhaseDir",
        ParamMeta(nom_de_guerre="Beam-PointingCentre", info=""),
    ),
    "beam_rotation_direction": (
        "str",
        False,
        "North2East",
        ParamMeta(nom_de_guerre="Beam-RotationDirection", info=""),
    ),
    "freq_band_m_hz": (
        "float",
        False,
        0.0,
        ParamMeta(
            nom_de_guerre="Freq-BandMHz",
            info="Gridding cube frequency step. If 0, --Freq-NBand is used instead. (Default: 0.0)",
        ),
    ),
    "freq_degrid_band_m_hz": (
        "float",
        False,
        0.0,
        ParamMeta(
            nom_de_guerre="Freq-DegridBandMHz",
            info="Degridding cube frequency step. If 0, --Freq-NDegridBand is used instead. (Default: 0.0)",
        ),
    ),
    "freq_n_band": (
        "int",
        False,
        1,
        ParamMeta(
            nom_de_guerre="Freq-NBand", info="Number of image bands for gridding. (Default: 1)"
        ),
    ),
    "freq_n_degrid_band": (
        "int",
        False,
        0,
        ParamMeta(
            nom_de_guerre="Freq-NDegridBand",
            info="Number of image bands for degridding. 0 means degrid each channel. (Default: 0)",
        ),
    ),
    "dde_solutions_dd_sols": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="DDESolutions-DDSols", info="Name of the DDE solution file"),
    ),
    "dde_solutions_sols_dir": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="DDESolutions-SolsDir",
            info="Name of the directry of the DDE Solutions which contains <SolsDir>/<MSNames>/killMS.<SolsName>.sols.npz",
        ),
    ),
    "dde_solutions_global_norm": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="DDESolutions-GlobalNorm",
            info="Option to normalise the Jones matrices (options: MeanAbs, MeanAbsAnt, BLBased or SumBLBased). See code for more detail",
        ),
    ),
    "dde_solutions_jones_norm_list": (
        "str",
        False,
        "AP",
        ParamMeta(nom_de_guerre="DDESolutions-JonesNormList", info="Deprecated? (Default: AP)"),
    ),
    "dde_solutions_jones_mode": (
        "str",
        False,
        "Full",
        ParamMeta(
            nom_de_guerre="DDESolutions-JonesMode",
            choices=["Scalar", "Diag", "Full"],
            info="(Default: Full) [choices: Scalar, Diag, Full]",
        ),
    ),
    "dde_solutions_dd_mode_grid": (
        "str",
        False,
        "AP",
        ParamMeta(
            nom_de_guerre="DDESolutions-DDModeGrid",
            info="In the gridding step, apply Jones matrices Amplitude (A) or Phase (P) or Amplitude&Phase (AP) (Default: AP)",
        ),
    ),
    "dde_solutions_dd_mode_de_grid": (
        "str",
        False,
        "AP",
        ParamMeta(
            nom_de_guerre="DDESolutions-DDModeDeGrid",
            info="In the degridding step, apply Jones matrices Amplitude (A) or Phase (P) or Amplitude&Phase (AP) (Default: AP)",
        ),
    ),
    "dde_solutions_scale_amp_grid": (
        "int",
        False,
        0,
        ParamMeta(nom_de_guerre="DDESolutions-ScaleAmpGrid", info="Deprecated? (Default: 0)"),
    ),
    "dde_solutions_scale_amp_de_grid": (
        "int",
        False,
        0,
        ParamMeta(nom_de_guerre="DDESolutions-ScaleAmpDeGrid", info="Deprecated? (Default: 0)"),
    ),
    "dde_solutions_calib_err": (
        "float",
        False,
        10.0,
        ParamMeta(nom_de_guerre="DDESolutions-CalibErr", info="Deprecated? (Default: 10.0)"),
    ),
    "dde_solutions_type": (
        "str",
        False,
        "Nearest",
        ParamMeta(
            nom_de_guerre="DDESolutions-Type",
            choices=["Krigging", "Nearest"],
            info="Deprecated? (Default: Nearest) [choices: Krigging, Nearest]",
        ),
    ),
    "dde_solutions_scale": (
        "float",
        False,
        1.0,
        ParamMeta(nom_de_guerre="DDESolutions-Scale", info="Deprecated? (Default: 1.0)"),
    ),
    "dde_solutions_gamma": (
        "float",
        False,
        4.0,
        ParamMeta(nom_de_guerre="DDESolutions-gamma", info="Deprecated? (Default: 4.0)"),
    ),
    "dde_solutions_restore_sub": (
        "bool",
        False,
        False,
        ParamMeta(nom_de_guerre="DDESolutions-RestoreSub", info="Deprecated? (Default: False)"),
    ),
    "dde_solutions_re_weight_snr": (
        "float",
        False,
        0.0,
        ParamMeta(nom_de_guerre="DDESolutions-ReWeightSNR", info="Deprecated? (Default: 0.0)"),
    ),
    "pointing_solutions_pointing_sols_csv": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="PointingSolutions-PointingSolsCSV",
            info="Filename of CSV containing time-variable pointing solutions. None initializes all antenna pointing offsets to 0, 0",
        ),
    ),
    "pointing_solutions_interpolation_mode": (
        "str",
        False,
        "LERP",
        ParamMeta(
            nom_de_guerre="PointingSolutions-InterpolationMode",
            choices=["LERP"],
            info="Interpolation mode (Default: LERP) [choices: LERP]",
        ),
    ),
    "deconv_mode": (
        "str",
        False,
        "HMP",
        ParamMeta(
            nom_de_guerre="Deconv-Mode",
            choices=["HMP", "Hogbom", "SSD", "WSCMS", "SSD2"],
            info="Deconvolution algorithm. (Default: HMP) [choices: HMP, Hogbom, SSD, WSCMS, SSD2]",
        ),
    ),
    "deconv_max_major_iter": (
        "int",
        False,
        20,
        ParamMeta(
            nom_de_guerre="Deconv-MaxMajorIter", info="Max number of major cycles. (Default: 20)"
        ),
    ),
    "deconv_max_minor_iter": (
        "int",
        False,
        20000,
        ParamMeta(
            nom_de_guerre="Deconv-MaxMinorIter",
            info="Max number of (overall) minor cycle iterations (HMP, Hogbom). (Default: 20000)",
        ),
    ),
    "deconv_allow_negative": (
        "bool",
        False,
        True,
        ParamMeta(
            nom_de_guerre="Deconv-AllowNegative",
            info="Allow negative components (HMP, Hogbom). (Default: True)",
        ),
    ),
    "deconv_gain": (
        "float",
        False,
        0.1,
        ParamMeta(nom_de_guerre="Deconv-Gain", info="Loop gain (HMP, Hogbom). (Default: 0.1)"),
    ),
    "deconv_flux_threshold": (
        "float",
        False,
        0.0,
        ParamMeta(
            nom_de_guerre="Deconv-FluxThreshold",
            info="Absolute flux threshold at which deconvolution is stopped (HMP, Hogbom, SSD). (Default: 0.0)",
        ),
    ),
    "deconv_cycle_factor": (
        "float",
        False,
        0.0,
        ParamMeta(
            nom_de_guerre="Deconv-CycleFactor",
            info="Cycle factor: used to set a minor cycle stopping threshold based on PSF sidelobe level (HMP, Hogbom). Use 0 to disable, otherwise 2.5 is a reasonable value, but may lead to very shallow minor cycle. (Default: 0.0)",
        ),
    ),
    "deconv_rms_factor": (
        "float",
        False,
        0.0,
        ParamMeta(
            nom_de_guerre="Deconv-RMSFactor",
            info="Set minor cycle stopping threshold to X*{residual RMS at start of major cycle} (HMP, Hogbom, SSD). (Default: 0.0)",
        ),
    ),
    "deconv_peak_factor": (
        "float",
        False,
        0.15,
        ParamMeta(
            nom_de_guerre="Deconv-PeakFactor",
            info="Set minor cycle stopping threshold to X*{peak residual at start of major cycle} (HMP, Hogbom, SSD). (Default: 0.15)",
        ),
    ),
    "deconv_prev_peak_factor": (
        "float",
        False,
        0.0,
        ParamMeta(
            nom_de_guerre="Deconv-PrevPeakFactor",
            info="Set minor cycle stopping threshold to X*{peak residual at end of previous major cycle} (HMP). (Default: 0.0)",
        ),
    ),
    "deconv_num_rms_samples": (
        "int",
        False,
        10000,
        ParamMeta(
            nom_de_guerre="Deconv-NumRMSSamples",
            info="How many samples to draw for RMS computation. Use 0 to use all pixels (most precise). (Default: 10000)",
        ),
    ),
    "deconv_approximate_psf": (
        "int",
        False,
        0,
        ParamMeta(
            nom_de_guerre="Deconv-ApproximatePSF",
            info="when --Comp-Sparsification is on, use approximate (i.e. central facet) PSF for cleaning while operating above the given sparsification factor (SF). This speeds up HMP reinitialization in major cycles. A value of 1-10 is sensible. Set to 0 to always use precise per-facet PSF. (Default: 0)",
        ),
    ),
    "deconv_psf_box": (
        "str",
        False,
        "auto",
        ParamMeta(
            nom_de_guerre="Deconv-PSFBox",
            info="determines the size of the PSF subtraction box used in CLEAN-style deconvolution (if appropriate). Use 'auto' (or 'sidelobe') for a Clark-CLEAN-style box taken out to a certain sidelobe (faster). Use 'full' to subtract the full PSF, Hogbom-style (more accurate, can also combine with --Image-PSFOversize for maximum accuracy). Use an integer number to set an explicit box radius, in pixels. (HMP) (Default: auto)",
        ),
    ),
    "mask_external": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="Mask-External", info="External clean mask image (FITS format)."),
    ),
    "mask_auto": (
        "bool",
        False,
        False,
        ParamMeta(nom_de_guerre="Mask-Auto", info="Do automatic masking (Default: False)"),
    ),
    "mask_auto_rms_factor": (
        "int",
        False,
        3,
        ParamMeta(nom_de_guerre="Mask-AutoRMSFactor", info="RMS Factor for automasking HMP"),
    ),
    "mask_sig_th": (
        "int",
        False,
        10,
        ParamMeta(
            nom_de_guerre="Mask-SigTh",
            info="set Threshold (in sigma) for automatic masking (Default: 10)",
        ),
    ),
    "mask_flux_image_type": (
        "str",
        False,
        "ModelConv",
        ParamMeta(
            nom_de_guerre="Mask-FluxImageType",
            info="If Auto enabled, does the cut of SigTh either on the ModelConv or the Restored (Default: ModelConv)",
        ),
    ),
    "mask_th_filter_rfi": (
        "bool",
        False,
        False,
        ParamMeta(
            nom_de_guerre="Mask-ThFilterRFI", info="Automatic filter RFI in the residual cube"
        ),
    ),
    "noise_min_stats": (
        "List[float]",
        False,
        [60, 2],
        ParamMeta(
            nom_de_guerre="Noise-MinStats",
            info="The parameters to compute the noise-map-based mask for step i+1 from the residual image at step i. Should be [box_size,box_step] (Default: [60, 2])",
        ),
    ),
    "noise_brutal_hmp": (
        "bool",
        False,
        True,
        ParamMeta(
            nom_de_guerre="Noise-BrutalHMP",
            info="If noise map is computed, this option enabled, it first computes an image plane deconvolution with a high gain value, and compute the noise-map-based mask using the brutal-restored image (Default: True)",
        ),
    ),
    "hmp_alpha": (
        "List[float]",
        False,
        [-1.0, 1.0, 11],
        ParamMeta(
            nom_de_guerre="HMP-Alpha", info="List of alphas to fit. (Default: [-1.0, 1.0, 11])"
        ),
    ),
    "hmp_scales": (
        "List[float]",
        False,
        [0],
        ParamMeta(nom_de_guerre="HMP-Scales", info="List of scales to use. (Default: [0])"),
    ),
    "hmp_ratios": (
        "List[str]",
        False,
        [],
        ParamMeta(nom_de_guerre="HMP-Ratios", info="@cyriltasse please document (Default: [''])"),
    ),
    "hmp_n_theta": (
        "int",
        False,
        6,
        ParamMeta(nom_de_guerre="HMP-NTheta", info="Number of PA steps to use. (Default: 6)"),
    ),
    "hmp_solver_mode": (
        "str",
        False,
        "PI",
        ParamMeta(
            nom_de_guerre="HMP-SolverMode",
            choices=["PI", "NNLS"],
            info="Solver mode: pseudoinverse, or non-negative least squares. (Default: PI) [choices: PI, NNLS]",
        ),
    ),
    "hmp_allow_resid_increase": (
        "float",
        False,
        0.1,
        ParamMeta(
            nom_de_guerre="HMP-AllowResidIncrease",
            info="Allow the maximum residual to increase by at most this much relative to the lowest residual, before bailing out due to divergence. (Default: 0.1)",
        ),
    ),
    "hmp_major_stall_threshold": (
        "float",
        False,
        0.8,
        ParamMeta(
            nom_de_guerre="HMP-MajorStallThreshold",
            info="Major cycle stall threshold. If the residual at the beginning of a major cycle is above X*residual at the beginning of the previous major cycle, then we consider the deconvolution stalled and bail out. (Default: 0.8)",
        ),
    ),
    "hmp_taper": (
        "int",
        False,
        0,
        ParamMeta(
            nom_de_guerre="HMP-Taper",
            info="Weighting taper size for HMP fit. If 0, determined automatically. (Default: 0)",
        ),
    ),
    "hmp_support": (
        "int",
        False,
        0,
        ParamMeta(
            nom_de_guerre="HMP-Support",
            info="Basis function support size. If 0, determined automatically. (Default: 0)",
        ),
    ),
    "hmp_peak_weight_image": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="HMP-PeakWeightImage", info="weigh the peak finding by given image"
        ),
    ),
    "hmp_kappa": (
        "float",
        False,
        0.0,
        ParamMeta(
            nom_de_guerre="HMP-Kappa",
            info="Regularization parameter. If stddev of per-alpha solutions exceeds the maximum solution amplitude divided by Kappa, forces a fully-regularized solution. Use 0 for no such regularization. (Default: 0.0)",
        ),
    ),
    "hmp_outer_space_th": (
        "float",
        False,
        2.0,
        ParamMeta(nom_de_guerre="HMP-OuterSpaceTh", info="(Default: 2.0)"),
    ),
    "hmp_fraction_random_peak": (
        "str",
        False,
        None,
        ParamMeta(nom_de_guerre="HMP-FractionRandomPeak", info=""),
    ),
    "hogbom_poly_fit_order": (
        "int",
        False,
        4,
        ParamMeta(
            nom_de_guerre="Hogbom-PolyFitOrder",
            info="polynomial order for frequency fitting (Default: 4)",
        ),
    ),
    "hogbom_linear_peakfinding": (
        "str",
        False,
        "Joint",
        ParamMeta(
            nom_de_guerre="Hogbom-LinearPeakfinding",
            choices=["Joint", "Separate"],
            info="Perform EVPA-preserving (complex-valued) polarization CLEAN (Pratley-Johnston-Hollitt) or separate Q and U cleaning. [choices: Joint, Separate]",
        ),
    ),
    "wscms_num_freq_basis_funcs": (
        "int",
        False,
        4,
        ParamMeta(
            nom_de_guerre="WSCMS-NumFreqBasisFuncs",
            info="number of basis functions to use for the fit to the frequency axis (Default: 4)",
        ),
    ),
    "wscms_multi_scale": (
        "bool",
        False,
        True,
        ParamMeta(
            nom_de_guerre="WSCMS-MultiScale",
            info="whether to use multi-scale or not (recommended to use Hogbom if not using multi-scale) (Default: True)",
        ),
    ),
    "wscms_multi_scale_bias": (
        "float",
        False,
        0.55,
        ParamMeta(
            nom_de_guerre="WSCMS-MultiScaleBias",
            info="scale bias parameter (smaller values give more weight to larger scales) (Default: 0.55)",
        ),
    ),
    "wscms_scale_basis": (
        "str",
        False,
        "Gauss",
        ParamMeta(
            nom_de_guerre="WSCMS-ScaleBasis",
            info="the kind of scale kernels to use (only Gauss available for now) (Default: Gauss)",
        ),
    ),
    "wscms_scales": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="WSCMS-Scales",
            info="Scale sizes in pixels/FWHM eg. [0, 4, 8, 16] (if None determined automatically)",
        ),
    ),
    "wscms_max_scale": (
        "int",
        False,
        250,
        ParamMeta(
            nom_de_guerre="WSCMS-MaxScale",
            info="The maximum extent of the scale functions in pixels (Default: 250)",
        ),
    ),
    "wscms_n_sub_minor_iter": (
        "int",
        False,
        250,
        ParamMeta(
            nom_de_guerre="WSCMS-NSubMinorIter",
            info="Number of iterations for the sub minor loop (Default: 250)",
        ),
    ),
    "wscms_sub_minor_peak_fact": (
        "float",
        False,
        0.85,
        ParamMeta(
            nom_de_guerre="WSCMS-SubMinorPeakFact",
            info="Peak factor of sub minor loop (Default: 0.85)",
        ),
    ),
    "wscms_minor_stall_threshold": (
        "float",
        False,
        1e-07,
        ParamMeta(
            nom_de_guerre="WSCMS-MinorStallThreshold",
            info="if the peak in the minor cycle decreases by less than this fraction it has stalled and we go back to the major cycle (Default: 1e-07)",
        ),
    ),
    "wscms_minor_divergence_factor": (
        "float",
        False,
        1.3,
        ParamMeta(
            nom_de_guerre="WSCMS-MinorDivergenceFactor",
            info="if the peak flux increases by more than this fraction between minor cycles then it has diverged and we go back to a major cycle (Default: 1.3)",
        ),
    ),
    "wscms_auto_mask": (
        "bool",
        False,
        True,
        ParamMeta(
            nom_de_guerre="WSCMS-AutoMask",
            info="whether to use scale dependent auto-masking (Default: True)",
        ),
    ),
    "wscms_auto_mask_threshold": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="WSCMS-AutoMaskThreshold",
            info="Threshold at which the scale dependent mask should be fixed.",
        ),
    ),
    "wscms_auto_mask_rms_factor": (
        "int",
        False,
        3,
        ParamMeta(
            nom_de_guerre="WSCMS-AutoMaskRMSFactor",
            info="Default multiple of RMS at which to start AutoMasking in case no (Default: 3)",
        ),
    ),
    "wscms_cache_size": (
        "int",
        False,
        3,
        ParamMeta(
            nom_de_guerre="WSCMS-CacheSize",
            info="the number of items to keep in the cache dict before spilling over to disk (Default: 3)",
        ),
    ),
    "wscms_padding": (
        "float",
        False,
        1.2,
        ParamMeta(
            nom_de_guerre="WSCMS-Padding",
            info="padding in the minor cycle. Can often be much smaller than facet padding (Default: 1.2)",
        ),
    ),
    "montblanc_tensorflow_server_target": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="Montblanc-TensorflowServerTarget",
            info="URL for the TensorflowServer, e.g. grpc://tensorflow.server.com:8888/",
        ),
    ),
    "montblanc_log_file": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="Montblanc-LogFile",
            info="None to dump as Output-Name.montblanc.log, otherwise user-specified filename",
        ),
    ),
    "montblanc_memory_budget": (
        "float",
        False,
        4.0,
        ParamMeta(
            nom_de_guerre="Montblanc-MemoryBudget",
            info="Predictor memory budget in GiB (Default: 4.0)",
        ),
    ),
    "montblanc_log_level": (
        "str",
        False,
        "WARNING",
        ParamMeta(
            nom_de_guerre="Montblanc-LogLevel",
            choices=["NOTSET", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            info="Log level to write to console, rest of the messages goes to log file (Default: WARNING) [choices: NOTSET, DEBUG, INFO, WARNING, ERROR, CRITICAL]",
        ),
    ),
    "montblanc_solver_d_type": (
        "str",
        False,
        "double",
        ParamMeta(
            nom_de_guerre="Montblanc-SolverDType",
            choices=["single", "double"],
            info="Data type used in solver, (Default: double) [choices: single, double]",
        ),
    ),
    "montblanc_driver_version": (
        "str",
        False,
        "tf",
        ParamMeta(
            nom_de_guerre="Montblanc-DriverVersion",
            choices=["tf"],
            info="Backend to use, (Default: tf) [choices: tf]",
        ),
    ),
    "ssd_clean_parallel": (
        "bool",
        False,
        True,
        ParamMeta(nom_de_guerre="SSDClean-Parallel", info="Enable parallel mode. (Default: True)"),
    ),
    "ssd_clean_island_deconv_mode": (
        "str",
        False,
        "GA",
        ParamMeta(
            nom_de_guerre="SSDClean-IslandDeconvMode", info="Moresane, GA, Sasir, ... (Default: GA)"
        ),
    ),
    "ssd_clean_ssd_solve_pars": (
        "str",
        False,
        "[S,Alpha]",
        ParamMeta(nom_de_guerre="SSDClean-SSDSolvePars", info="(Default: ['S', 'Alpha'])"),
    ),
    "ssd_clean_ssd_cost_func": (
        "str",
        False,
        "[Chi2,MinFlux]",
        ParamMeta(nom_de_guerre="SSDClean-SSDCostFunc", info="(Default: ['Chi2', 'MinFlux'])"),
    ),
    "ssd_clean_bic_factor": (
        "float",
        False,
        0.0,
        ParamMeta(nom_de_guerre="SSDClean-BICFactor", info="(Default: 0.0)"),
    ),
    "ssd_clean_artifact_robust": (
        "bool",
        False,
        False,
        ParamMeta(nom_de_guerre="SSDClean-ArtifactRobust", info="(Default: False)"),
    ),
    "ssd_clean_conv_fft_switch": (
        "int",
        False,
        1000,
        ParamMeta(nom_de_guerre="SSDClean-ConvFFTSwitch", info="(Default: 1000)"),
    ),
    "ssd_clean_n_enlarge_pars": (
        "int",
        False,
        0,
        ParamMeta(nom_de_guerre="SSDClean-NEnlargePars", info="(Default: 0)"),
    ),
    "ssd_clean_n_enlarge_data": (
        "int",
        False,
        2,
        ParamMeta(nom_de_guerre="SSDClean-NEnlargeData", info="(Default: 2)"),
    ),
    "ssd_clean_restore_metro_switch": (
        "int",
        False,
        0,
        ParamMeta(nom_de_guerre="SSDClean-RestoreMetroSwitch", info="(Default: 0)"),
    ),
    "ssd_clean_min_max_group_distance": (
        "List[float]",
        False,
        [10, 50],
        ParamMeta(nom_de_guerre="SSDClean-MinMaxGroupDistance", info="(Default: [10, 50])"),
    ),
    "ssd_clean_max_island_size": (
        "int",
        False,
        0,
        ParamMeta(
            nom_de_guerre="SSDClean-MaxIslandSize",
            info="if Island size larger than this, will be split",
        ),
    ),
    "ssd_clean_init_type": (
        "str",
        False,
        "HMP",
        ParamMeta(
            nom_de_guerre="SSDClean-InitType", info="Islands can be initialised by HMP or MORESANE"
        ),
    ),
    "ssd2_solve_pars": (
        "str",
        False,
        "[Poly]",
        ParamMeta(
            nom_de_guerre="SSD2-SolvePars",
            info="Poly: use polynomial, GSig: use gaussians (not really tested/useful - to be deprecated)",
        ),
    ),
    "ssd2_poly_freq_order": (
        "int",
        False,
        2,
        ParamMeta(nom_de_guerre="SSD2-PolyFreqOrder", info="Add Polyi to --SSDClean-SSDSolvePars."),
    ),
    "ssd2_init_type": (
        "str",
        False,
        "[HMP,MultiSlice:Orieux]",
        ParamMeta(nom_de_guerre="SSD2-InitType", info="Method to initialise islands"),
    ),
    "ssd2_convexify_islands": (
        "int",
        False,
        1,
        ParamMeta(
            nom_de_guerre="SSD2-ConvexifyIslands", info="Convexify island before deconvolution"
        ),
    ),
    "ssd2_n_last_cycles_deconv_all": (
        "int",
        False,
        1,
        ParamMeta(
            nom_de_guerre="SSD2-NLastCyclesDeconvAll",
            info="This parameter sets how many of the last cycles will deconvolve all islands. If set to 0, SSD2 will use --Deconv-CycleFactor, --Deconv-PeakFactor, --Deconv-RMSFactor to determine threshold above which islands are reestimated. If set to 2, in the last 2 major cycle all islands are estimated. If -1: Always deconv all islands regardless of the cycle number",
        ),
    ),
    "ssd3_poly_freq_order": (
        "int",
        False,
        2,
        ParamMeta(nom_de_guerre="SSD3-PolyFreqOrder", info="Add Polyi to --SSDClean-SSDSolvePars."),
    ),
    "ssd3_solve_pars": ("str", False, "[Poly]", ParamMeta(nom_de_guerre="SSD3-SolvePars", info="")),
    "ssd3_init_type": (
        "str",
        False,
        "[HMP_0-50,MultiSlice:Orieux]",
        ParamMeta(
            nom_de_guerre="SSD3-InitType",
            info="Use deconv method for island initialisation. HMP_0-50 will initialise islands only with sizes in 0-50 pixels",
        ),
    ),
    "ssd3_ga_isl_size": (
        "str",
        False,
        "0-50",
        ParamMeta(
            nom_de_guerre="SSD3-GAIslSize",
            info="Run the GA with eth GAClean parameters for islands with size in that range",
        ),
    ),
    "ssd3_run_simple_clean": (
        "bool",
        False,
        True,
        ParamMeta(
            nom_de_guerre="SSD3-RunSimpleClean",
            info="Run simplistic clean for the islands that have not been initialised with neither of the SSD3 InitType methods",
        ),
    ),
    "ssd3_propagate_prev_gen": (
        "bool",
        False,
        True,
        ParamMeta(
            nom_de_guerre="SSD3-PropagatePrevGen",
            info="Propagate previous generations best individual into current cycle",
        ),
    ),
    "ssd3_alpha_scale_model": (
        "bool",
        False,
        False,
        ParamMeta(
            nom_de_guerre="SSD3-AlphaScaleModel",
            info="Agressively scale the residual power that has not been modeled by previous cycle. Helps when PSF is really bad",
        ),
    ),
    "ssd3_convexify_islands": (
        "int",
        False,
        1,
        ParamMeta(
            nom_de_guerre="SSD3-ConvexifyIslands",
            info="Convexify the islands prior to deconvolution",
        ),
    ),
    "ssd3_unique_island": (
        "int",
        False,
        0,
        ParamMeta(
            nom_de_guerre="SSD3-UniqueIsland", info="Make a unique island with the entire image"
        ),
    ),
    "ssd3_allow_facet_overlap": (
        "int",
        False,
        0,
        ParamMeta(
            nom_de_guerre="SSD3-AllowFacetOverlap",
            info="Allow the islands to be overlapping the facets, otherwise cut the islands when crossing a facet boundary",
        ),
    ),
    "ssd3_n_look_back_models": (
        "int",
        False,
        2,
        ParamMeta(
            nom_de_guerre="SSD3-NLookBackModels",
            info="Use previous models to constrain current model estimate. Helps when SSD3 stabilise residual goes instable (+/-)",
        ),
    ),
    "ssd3_posterior": (
        "int",
        False,
        0,
        ParamMeta(
            nom_de_guerre="SSD3-Posterior",
            info="Holy grail of radio astronomy - not ready yet, maybe never",
        ),
    ),
    "ssd3_posterior_n_iter": (
        "int",
        False,
        100,
        ParamMeta(nom_de_guerre="SSD3-PosteriorNIter", info=""),
    ),
    "ssd3_posterior_n_points": (
        "int",
        False,
        50,
        ParamMeta(nom_de_guerre="SSD3-PosteriorNPoints", info=""),
    ),
    "ssd3_posterior_alpha": (
        "float",
        False,
        0.01,
        ParamMeta(nom_de_guerre="SSD3-PosteriorAlpha", info=""),
    ),
    "ssd3_force_positive_model": (
        "bool",
        False,
        False,
        ParamMeta(nom_de_guerre="SSD3-ForcePositiveModel", info="Force model to be positive"),
    ),
    "ssd3_n_last_cycles_deconv_all": (
        "int",
        False,
        2,
        ParamMeta(
            nom_de_guerre="SSD3-NLastCyclesDeconvAll",
            info="This parameter sets how many of the last cycles will deconvolve all islands. If set to 0, SSD3 will use --Deconv-CycleFactor, --Deconv-PeakFactor, --Deconv-RMSFactor to determine threshold above which islands are reestimated. If set to 2, in the last 2 major cycle all islands are estimated. If -1: Always deconv all islands regardless of the cycle number",
        ),
    ),
    "multi_slice_deconv_type": (
        "str",
        False,
        "MORESANE",
        ParamMeta(nom_de_guerre="MultiSliceDeconv-Type", info="MORESANE, Orieux, etc"),
    ),
    "multi_slice_deconv_poly_fit_order": (
        "int",
        False,
        2,
        ParamMeta(
            nom_de_guerre="MultiSliceDeconv-PolyFitOrder",
            info="Number of Taylor terms in the deconvolution",
        ),
    ),
    "multi_slice_deconv_force_positive_model": (
        "int",
        False,
        1,
        ParamMeta(
            nom_de_guerre="MultiSliceDeconv-ForcePositiveModel",
            info="Force the model to be positive",
        ),
    ),
    "multi_slice_deconv_hyper_smooth": (
        "int",
        False,
        1,
        ParamMeta(
            nom_de_guerre="MultiSliceDeconv-HyperSmooth",
            info="When using Orieux, sets the Hyper parameter to 10**ThisValue",
        ),
    ),
    "ga_clean_n_source_kin": (
        "int",
        False,
        50,
        ParamMeta(nom_de_guerre="GAClean-NSourceKin", info="(Default: 50)"),
    ),
    "ga_clean_n_max_gen": (
        "int",
        False,
        50,
        ParamMeta(nom_de_guerre="GAClean-NMaxGen", info="(Default: 50)"),
    ),
    "ga_clean_min_size_init": (
        "int",
        False,
        10,
        ParamMeta(nom_de_guerre="GAClean-MinSizeInit", info="(Default: 10)"),
    ),
    "ga_clean_alpha_init_hmp": (
        "List[float]",
        False,
        [-4.0, 1.0, 6],
        ParamMeta(nom_de_guerre="GAClean-AlphaInitHMP", info="(Default: [-4.0, 1.0, 6])"),
    ),
    "ga_clean_scales_init_hmp": (
        "List[float]",
        False,
        [0, 1, 2, 4, 8, 16, 24, 32],
        ParamMeta(
            nom_de_guerre="GAClean-ScalesInitHMP", info="(Default: [0, 1, 2, 4, 8, 16, 24, 32])"
        ),
    ),
    "ga_clean_gain_init_hmp": (
        "float",
        False,
        0.1,
        ParamMeta(nom_de_guerre="GAClean-GainInitHMP", info="(Default: 0.1)"),
    ),
    "ga_clean_ratios_init_hmp": (
        "List[str]",
        False,
        [],
        ParamMeta(nom_de_guerre="GAClean-RatiosInitHMP", info="(Default: [''])"),
    ),
    "ga_clean_n_theta_init_hmp": (
        "int",
        False,
        4,
        ParamMeta(nom_de_guerre="GAClean-NThetaInitHMP", info="(Default: 4)"),
    ),
    "ga_clean_max_minor_iter_init_hmp": (
        "int",
        False,
        10000,
        ParamMeta(nom_de_guerre="GAClean-MaxMinorIterInitHMP", info="(Default: 10000)"),
    ),
    "ga_clean_allow_negative_init_hmp": (
        "bool",
        False,
        False,
        ParamMeta(nom_de_guerre="GAClean-AllowNegativeInitHMP", info="(Default: False)"),
    ),
    "ga_clean_rms_factor_init_hmp": (
        "float",
        False,
        3.0,
        ParamMeta(nom_de_guerre="GAClean-RMSFactorInitHMP", info="(Default: 3.0)"),
    ),
    "ga_clean_parallel_init": (
        "bool",
        False,
        True,
        ParamMeta(
            nom_de_guerre="GAClean-ParallelInit",
            info="run island init in parallel. Serial mode may reduce RAM pressure, and could be useful for debugging.",
        ),
    ),
    "ga_clean_ncpu": (
        "int",
        False,
        0,
        ParamMeta(
            nom_de_guerre="GAClean-NCPU",
            info="number of cores to use for parallel fitness calculations (in large-island mode). Default of 0 means use as many as specified by --Parallel-NCPU. If you find yourself running out of memory here, you might want to specify a small number of cores for this step. (Default: 0)",
        ),
    ),
    "moresane_n_major_iter": (
        "int",
        False,
        200,
        ParamMeta(
            nom_de_guerre="MORESANE-NMajorIter",
            info="Maximum number of iterations allowed in the major loop. Exit condition. (Default: 200)",
        ),
    ),
    "moresane_n_minor_iter": (
        "int",
        False,
        200,
        ParamMeta(
            nom_de_guerre="MORESANE-NMinorIter",
            info="Maximum number of iterations allowed in the minor loop. Serves as an exit condition when the SNR is does not reach a maximum. (Default: 200)",
        ),
    ),
    "moresane_gain": (
        "float",
        False,
        0.1,
        ParamMeta(
            nom_de_guerre="MORESANE-Gain", info="Loop gain for the deconvolution. (Default: 0.1)"
        ),
    ),
    "moresane_force_positive": (
        "bool",
        False,
        True,
        ParamMeta(
            nom_de_guerre="MORESANE-ForcePositive",
            info="Boolean specifier for whether or not a model must be strictly positive. (Default: True)",
        ),
    ),
    "moresane_sigma_cut_level": (
        "int",
        False,
        1,
        ParamMeta(
            nom_de_guerre="MORESANE-SigmaCutLevel",
            info="Number of sigma at which thresholding is to be performed. (Default: 1)",
        ),
    ),
    "log_memory": (
        "bool",
        False,
        False,
        ParamMeta(nom_de_guerre="Log-Memory", info="log memory use (Default: False)"),
    ),
    "log_boring": (
        "bool",
        False,
        False,
        ParamMeta(
            nom_de_guerre="Log-Boring",
            info="disable progress bars and other pretty console output (Default: False)",
        ),
    ),
    "log_append": (
        "bool",
        False,
        False,
        ParamMeta(
            nom_de_guerre="Log-Append",
            info="append to log file if it exists (default truncates) (Default: False)",
        ),
    ),
    "debug_pause_workers": (
        "bool",
        False,
        False,
        ParamMeta(
            nom_de_guerre="Debug-PauseWorkers",
            info="Pauses worker processes upon launch (with SIGSTOP). Useful to attach gdb to workers. (Default: False)",
        ),
    ),
    "debug_facet_phase_shift": (
        "List[float]",
        False,
        [0.0, 0.0],
        ParamMeta(
            nom_de_guerre="Debug-FacetPhaseShift",
            info="Shift in facet coordinates in arcseconds for l and m (this phase steers the sky over the image plane). (Default: [0.0, 0.0])",
        ),
    ),
    "debug_print_minor_cycle_rms": (
        "bool",
        False,
        False,
        ParamMeta(
            nom_de_guerre="Debug-PrintMinorCycleRMS",
            info="Compute and print RMS in minor cycle iterations. (Default: False)",
        ),
    ),
    "debug_dump_clean_solutions": (
        "int",
        False,
        0,
        ParamMeta(
            nom_de_guerre="Debug-DumpCleanSolutions",
            info="Dump intermediate minor cycle solutions to a file. Use 0 or 1, or give an explicit list of things to dump (Default: 0)",
        ),
    ),
    "debug_dump_clean_postage_stamps": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="Debug-DumpCleanPostageStamps",
            info="Also dump postage stamps when cleaning within a radius R of X,Y. Implies --Debug-DumpCleanSolutions.",
        ),
    ),
    "debug_clean_stall_threshold": (
        "float",
        False,
        0.0,
        ParamMeta(
            nom_de_guerre="Debug-CleanStallThreshold",
            info="Throw an exception when a fitted CLEAN component is below this threshold in flux. Useful for debugging. (Default: 0.0)",
        ),
    ),
    "debug_memory_greedy": (
        "bool",
        False,
        True,
        ParamMeta(
            nom_de_guerre="Debug-MemoryGreedy",
            info="Enable memory-greedy mode. Retain certain shared arrays in RAM as long as possible. (Default: True)",
        ),
    ),
    "debug_app_verbose": (
        "int",
        False,
        0,
        ParamMeta(
            nom_de_guerre="Debug-APPVerbose",
            info="Verbosity level for multiprocessing. (Default: 0)",
        ),
    ),
    "debug_pdb": (
        "str",
        False,
        "auto",
        ParamMeta(
            nom_de_guerre="Debug-Pdb",
            choices=["never", "always", "auto"],
            info="Invoke pdb on unexpected error conditions (rather than exit). If set to 'auto', then invoke pdb only if --Log-Boring is 0. (Default: auto) [choices: never, always, auto]",
        ),
    ),
    "misc_random_seed": (
        "str",
        False,
        None,
        ParamMeta(
            nom_de_guerre="Misc-RandomSeed",
            info="seed random number generator with explicit seed, if given. Useful for reproducibility of the random-based optimizations (sparsification, etc.).",
        ),
    ),
    "misc_conserve_memory": (
        "int",
        False,
        0,
        ParamMeta(
            nom_de_guerre="Misc-ConserveMemory",
            info="if true, tries to minimize memory use at possible expense of runtime. (Default: 0)",
        ),
    ),
    "misc_ignore_deprecation_marking": (
        "bool",
        False,
        False,
        ParamMeta(
            nom_de_guerre="Misc-IgnoreDeprecationMarking",
            info="if true, tries to run deprecated modes. Currently this means that deconvolution machines are reset and reinitialized each major cycle. (Default: False)",
        ),
    ),
    "katdal_apply_cal": (
        "str",
        False,
        "default",
        ParamMeta(
            nom_de_guerre="katdal-ApplyCal",
            info="List of calibration solutions to apply to data as a string of comma-separated names, e.g. 'l1' or #'K,B,G'. Use 'default' for L1 + L2 and 'all' for all available products.",
        ),
    ),
}

ddfacet = define_cab(
    "ddfacet",
    "DDF.py",
    images.DDFACET,
    _FIELDS,
    policies=Policies(prefix="--"),
    info="DDFacet: facet-based radio-interferometric imager/deconvolver "
    "(https://github.com/saopicc/DDFacet)",
)
