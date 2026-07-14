"""sofia2 -- SoFiA-2 source finder for spectral-line data cubes
(https://gitlab.com/SoFiA-Admin/SoFiA-2).

Ported field-by-field from cult-cargo's sofia2.yml (a flat, static
100-parameter schema -- no dynamic_schema).

Real SoFiA-2 derives `output.directory`/`output.filename` from
`input.data` when either is left unset (cwd and the input cube's own
basename, respectively) -- a run-time default `ParamMeta.implicit`
templates can't express (no imported tool code, no eval; see wsclean.py's
own docstring for the same constraint). So, like wsclean's `prefix`, both
are pinned to concrete dosho-level defaults (`"."`/`"sofia"`) here rather
than left `None`, trading exact fidelity to SoFiA's own inference for
outputs that resolve to a real, predictable path a pipeline can chain a
step onto. Each `output_write*` toggle below has a same-shaped output
field templated off those two; `output_writeNoise`'s `_noise.txt`
alternative (only when spectral, not local, noise scaling is enabled) is
the one exotic case left unmodeled -- `noise` always resolves to the
FITS-cube path.
"""

from __future__ import annotations

from shinobi.steps.schema import ParamMeta, Policies

from dosho import images
from dosho._builder import define_cab

_FIELDS: dict[str, tuple[str, bool, object]] = {
    "pipeline_pedantic": ("bool", False, True),
    "pipeline_threads": ("int", False, 0),
    "pipeline_verbose": ("bool", False, False),
    "input_data": ("File", False, None),
    "input_gain": ("File", False, None),
    "input_invert": ("bool", False, False),
    "input_mask": ("File", False, None),
    "input_noise": ("File", False, None),
    "input_region": ("list:int", False, None),
    "input_weights": ("File", False, None),
    "contsub_enable": ("bool", False, False),
    "contsub_order": ("int", False, 0),
    "contsub_padding": ("int", False, 3),
    "contsub_shift": ("int", False, 4),
    "contsub_threshold": ("float", False, 2.0),
    "flag_auto": ("str", False, "false"),
    "flag_catalog": ("File", False, None),
    "flag_log": ("bool", False, False),
    "flag_radius": ("int", False, 5),
    "flag_region": ("list:int", False, None),
    "flag_threshold": ("float", False, 5.0),
    "rippleFilter_enable": ("bool", False, False),
    "rippleFilter_gridXY": ("int", False, 0),
    "rippleFilter_gridZ": ("int", False, 0),
    "rippleFilter_interpolate": ("bool", False, False),
    "rippleFilter_statistic": ("str", False, "median"),
    "rippleFilter_windowXY": ("int", False, 31),
    "rippleFilter_windowZ": ("int", False, 31),
    "scaleNoise_enable": ("bool", False, False),
    "scaleNoise_fluxRange": ("str", False, "negative"),
    "scaleNoise_gridXY": ("int", False, 0),
    "scaleNoise_gridZ": ("int", False, 0),
    "scaleNoise_interpolate": ("bool", False, False),
    "scaleNoise_mode": ("str", False, "spectral"),
    "scaleNoise_scfind": ("bool", False, False),
    "scaleNoise_statistic": ("str", False, "mad"),
    "scaleNoise_windowXY": ("int", False, 25),
    "scaleNoise_windowZ": ("int", False, 15),
    "scfind_enable": ("bool", False, True),
    "scfind_fluxRange": ("str", False, "negative"),
    "scfind_kernelsXY": ("list:float", False, [0, 3, 6]),
    "scfind_kernelsZ": ("list:int", False, [0, 3, 7, 15]),
    "scfind_replacement": ("float", False, 2.0),
    "scfind_statistic": ("str", False, "mad"),
    "scfind_threshold": ("float", False, 5.0),
    "threshold_enable": ("bool", False, False),
    "threshold_fluxRange": ("str", False, "negative"),
    "threshold_mode": ("str", False, "relative"),
    "threshold_statistic": ("str", False, "mad"),
    "threshold_threshold": ("float", False, 5.0),
    "linker_enable": ("bool", False, True),
    "linker_keepNegative": ("bool", False, False),
    "linker_maxFill": ("float", False, 0.0),
    "linker_maxPixels": ("int", False, 0),
    "linker_maxSizeXY": ("int", False, 0),
    "linker_maxSizeZ": ("int", False, 0),
    "linker_minFill": ("float", False, 0.0),
    "linker_minPixels": ("int", False, 0),
    "linker_minSizeXY": ("int", False, 5),
    "linker_minSizeZ": ("int", False, 5),
    "linker_positivity": ("bool", False, False),
    "linker_radiusXY": ("int", False, 1),
    "linker_radiusZ": ("int", False, 1),
    "reliability_autoKernel": ("bool", False, False),
    "reliability_catalog": ("File", False, None),
    "reliability_debug": ("bool", False, False),
    "reliability_enable": ("bool", False, False),
    "reliability_iterations": ("int", False, 30),
    "reliability_minPixels": ("int", False, 0),
    "reliability_minSNR": ("float", False, 3.0),
    "reliability_parameters": ("list:str", False, ["peak", "sum", "mean"]),
    "reliability_plot": ("bool", False, True),
    "reliability_scaleKernel": ("float", False, 0.4),
    "reliability_threshold": ("float", False, 0.9),
    "reliability_tolerance": ("float", False, 0.05),
    "dilation_enable": ("bool", False, False),
    "dilation_iterationsXY": ("int", False, 10),
    "dilation_iterationsZ": ("int", False, 5),
    "dilation_threshold": ("float", False, 0.001),
    "parameter_enable": ("bool", False, True),
    "parameter_offset": ("bool", False, False),
    "parameter_physical": ("bool", False, False),
    "parameter_prefix": ("str", False, "SoFiA"),
    "parameter_wcs": ("bool", False, True),
    "output_directory": ("str", False, "."),
    "output_filename": ("str", False, "sofia"),
    "output_marginCubelets": ("int", False, 10),
    "output_overwrite": ("bool", False, True),
    "output_thresholdMom12": ("float", False, 0.0),
    "output_writeCatASCII": ("bool", False, True),
    "output_writeCatSQL": ("bool", False, False),
    "output_writeCatXML": ("bool", False, True),
    "output_writeCubelets": ("bool", False, False),
    "output_writeFiltered": ("bool", False, False),
    "output_writeMask": ("bool", False, False),
    "output_writeMask2d": ("bool", False, False),
    "output_writeMoments": ("bool", False, False),
    "output_writeNoise": ("bool", False, False),
    "output_writeRawMask": ("bool", False, False),
    "port2tigger": ("bool", False, False),
}

_FIELD_META: dict[str, ParamMeta] = {
    "pipeline_pedantic": ParamMeta(
        nom_de_guerre="pipeline.pedantic",
        info="If set to true, the pipeline will terminate with an error message if an unknown parameter name is encountered in the input parameter file. If set to false, unknown parameters will instead be ignored.",
    ),
    "pipeline_threads": ParamMeta(
        nom_de_guerre="pipeline.threads",
        info="Sets the maximum number of parallel threads that multi-threaded algorithms within SoFiA are allowed to use. If set to 0 (default value), then the OMP_NUM_THREADS environment variable is used to control the number of threads. If the value equals (or exceeds) the number of available threads, then all CPU cores will be utilised, which minimises the runtime of the pipeline at the cost of maximal CPU load.",
    ),
    "pipeline_verbose": ParamMeta(
        nom_de_guerre="pipeline.verbose",
        info="Determines the level of output messages produced by the pipeline. Additional warning messages can be enabled by setting the value to true.",
    ),
    "input_data": ParamMeta(
        nom_de_guerre="input.data",
        info="Name of the input data cube on which to run the source finder. The absolute path to the data file must be provided. If only the file name is specified, the pipeline will assume the file to be located in the current working directory. Currently, only the FITS format is supported.",
    ),
    "input_gain": ParamMeta(
        nom_de_guerre="input.gain",
        info="Name of an optional data cube containing the gain across the image. If specified, the input data cube will be divided by the gain cube prior to source parameterisation to ensure that the correct flux values are extracted. The gain cube must have the same dimensions as the input data cube. The absolute path to the gain file must be provided. If only the file name is specified, the pipeline will assume the file to be located in the current working directory. Currently, only the FITS format is supported.",
    ),
    "input_invert": ParamMeta(
        nom_de_guerre="input.invert",
        info="If set to true, invert the data cube prior to processing. This is useful when searching for negative rather than positive signals such as absorption lines. Note that all flux-related parameters and maps will be inverted, too, in this case and hence be positive rather than negative.",
    ),
    "input_mask": ParamMeta(
        nom_de_guerre="input.mask",
        info="File name of an input mask cube. Any additional pixels detected by the source finder will be added to the input mask. This can be useful if the results from two different source finding runs should be combined into a single mask. The mask cube must have the same dimensions as the input data cube. The absolute path to the mask file must be provided. If only the file name is specified, the pipeline will assume the file to be located in the current working directory. Currently, only the FITS format is supported.",
    ),
    "input_noise": ParamMeta(
        nom_de_guerre="input.noise",
        info="Name of an optional data cube containing the noise levels across the image. If specified, the input data cube will be divided by the noise cube prior to source finding to ensure that a constant source finding threshold can be applied. The noise cube must have the same dimensions as the input data cube. The absolute path to the noise file must be provided. If only the file name is specified, the pipeline will assume the file to be located in the current working directory. Currently, only the FITS format is supported. Note that either a noise cube or a weights cube can be applied, but not both",
    ),
    "input_region": ParamMeta(
        nom_de_guerre="input.region",
        info="Region of the input data cube to be searched. Only the specified region will be loaded into memory and processed. A region must contain six comma-separated integer values of the following format: x_min, x_max, y_min, y_max, z_min, z_max (all in units of pixels and 0-based). If no region is specified, then the entire data cube will be loaded.",
    ),
    "input_weights": ParamMeta(
        nom_de_guerre="input.weights",
        info="Name of an optional data cube containing the weights across the image. If specified, the input data cube will be multiplied by the square root of the weights cube prior to source finding to ensure that a constant source finding threshold can be applied. The weights cube must have the same dimensions as the input data cube. The absolute path to the weights file must be provided. If only the file name is specified, the pipeline will assume the file to be located in the current working directory. Currently, only the FITS format is supported. Note that either a noise cube or a weights cube can be applied, but not both.",
    ),
    "contsub_enable": ParamMeta(
        nom_de_guerre="contsub.enable",
        info="If enabled, SoFiA will try to subtract any residual continuum emission from the data cube prior to source finding by fitting and subtracting a polynomial of order 0 (offset) or 1 (offset + slope). The order of the polynomial is defined by contsub.order.",
    ),
    "contsub_order": ParamMeta(
        nom_de_guerre="contsub.order",
        info="Order of the polynomial to be used in continuum subtraction if contsub.enable is set to true. Can either be 0 for a simple offset or 1 for an offset + slope. Higher orders are not currently supported.",
    ),
    "contsub_padding": ParamMeta(
        nom_de_guerre="contsub.padding",
        info="The amount of additional padding (in channels) applied to either side of channels excluded from the fit.",
    ),
    "contsub_shift": ParamMeta(
        nom_de_guerre="contsub.shift",
        info="The number of channels by which the spectrum will be shifted (symmetrically in both directions) before self-subtraction.",
    ),
    "contsub_threshold": ParamMeta(
        nom_de_guerre="contsub.threshold",
        info="Relative clipping threshold. All channels with a flux density > contsub.threshold times the noise will be clipped and excluded from the polynomial fit.",
    ),
    "flag_auto": ParamMeta(
        nom_de_guerre="flag.auto",
        info="If set to true, SoFiA will attempt to automatically flag spectral channels and spatial pixels affected by interference or artefacts based on their RMS noise level. If set to channels, only spectral channels will be flagged. If set to pixels, only spatial pixels will be flagged. If set to false, auto-flagging will be disabled. Please see the user manual for details.",
    ),
    "flag_catalog": ParamMeta(
        nom_de_guerre="flag.catalog",
        info="Path to a catalogue file containing two columns that specify the longitude and latitude coordinates of sky positions to be flagged in the native coordinate system and units of the input data cube. The two columns can be separated by spaces, tabulators or commas. Also see flag.radius.",
    ),
    "flag_log": ParamMeta(
        nom_de_guerre="flag.log",
        info="If set to true, write a list of the channels and pixels flagged by the auto-flagger to a log file. Note that if no channels or pixels were found to be in need of flagging, then the log file will not be written irrespective of the value of flag.log.",
    ),
    "flag_radius": ParamMeta(
        nom_de_guerre="flag.radius",
        info="Radius around the sky positions listed in the catalogue provided by flag.catalog that should be flagged. If 0, then only the nearest pixel to the position will be flagged. Otherwise, pixels within the specified radius around the nearest pixel will be flagged.",
    ),
    "flag_region": ParamMeta(
        nom_de_guerre="flag.region",
        info="Region(s) to be flagged in the input data cube prior to processing. The flagging region must contain a multiple of six comma-separated integer values of the following format: x_min, x_max, y_min, y_max, z_min, z_max, ... (all in units of pixels and 0-based). Pixels within those regions will be set to blank in the input cube. If unset, no flagging will occur.",
    ),
    "flag_threshold": ParamMeta(
        nom_de_guerre="flag.threshold",
        info="Relative threshold in multiples of the standard deviation to be applied by the automatic flagging algorithm. Only relevant if flag.auto is enabled. Please see the documentation for details",
    ),
    "rippleFilter_enable": ParamMeta(
        nom_de_guerre="rippleFilter.enable",
        info="If set to true, then the ripple filter will be applied to the data cube prior to source finding. The filter works by measuring and subtracting either the mean or median across a running window. This can be useful if a DC offset or spatial/spectral ripple is present in the data.",
    ),
    "rippleFilter_gridXY": ParamMeta(
        nom_de_guerre="rippleFilter.gridXY",
        info="Spatial grid separation in pixels for the running window used in the ripple filter. The value must be an odd integer value and specifies the spatial step by which the window is moved. Alternatively, it can be set to 0, in which case it will default to half the spatial window size (see rippleFilter.windowXY).",
    ),
    "rippleFilter_gridZ": ParamMeta(
        nom_de_guerre="rippleFilter.gridZ",
        info="Spectral grid separation in channels for the running window used in the ripple filter. The value must be an odd integer value and specifies the spectral step by which the window is moved. Alternatively, it can be set to 0, in which case it will default to half the spectral window size (see rippleFilter.windowZ).",
    ),
    "rippleFilter_interpolate": ParamMeta(
        nom_de_guerre="rippleFilter.interpolate",
        info="If set to true, then the mean or median values measured across the running window in the ripple filter will be linearly interpolated in between the grid points. If set to false, the mean or median will be subtracted from the entire grid cell without interpolation.",
    ),
    "rippleFilter_statistic": ParamMeta(
        nom_de_guerre="rippleFilter.statistic",
        info="Controls whether the mean or median should be measured and subtracted in the running window of the ripple filter. The median is strongly recommended, as it is more robust.",
    ),
    "rippleFilter_windowXY": ParamMeta(
        nom_de_guerre="rippleFilter.windowXY",
        info="Spatial size in pixels of the running window used in the ripple filter. The size must be an odd integer number.",
    ),
    "rippleFilter_windowZ": ParamMeta(
        nom_de_guerre="rippleFilter.windowZ",
        info="Spatial size in pixels of the running window used in the ripple filter. The size must be an odd integer number.",
    ),
    "scaleNoise_enable": ParamMeta(
        nom_de_guerre="scaleNoise.enable",
        info="If set to true, noise scaling will be enabled. The purpose of the noise scaling modules is to measure the noise level in the input cube and then divide the input cube by the noise. This can be used to correct for spatial or spectral noise variations across the input cube prior to running the source finder.",
    ),
    "scaleNoise_fluxRange": ParamMeta(
        nom_de_guerre="scaleNoise.fluxRange",
        info="Flux range to be used in the noise measurement. If set to negative or positive, only pixels with negative or positive flux will be used, respectively. This can be useful to prevent real emission or artefacts from affecting the noise measurement. If set to full, all pixels will be used in the noise measurement irrespective of their flux.",
    ),
    "scaleNoise_gridXY": ParamMeta(
        nom_de_guerre="scaleNoise.gridXY",
        info="Size of the spatial grid across which noise measurement window will be moved across the data cube. It must be an odd integer value. If set to 0 instead, the spatial grid size will default to half the spatial window size.",
    ),
    "scaleNoise_gridZ": ParamMeta(
        nom_de_guerre="scaleNoise.gridZ",
        info="Size of the spatial grid across which noise measurement window will be moved across the data cube. It must be an odd integer value. If set to 0 instead, the spatial grid size will default to half the spatial window size.",
    ),
    "scaleNoise_interpolate": ParamMeta(
        nom_de_guerre="scaleNoise.interpolate",
        info="If set to true, linear interpolation will be used to interpolate the measured local noise values in between grid points. If set to false, the entire grid cell will instead be filled with the measured noise value.",
    ),
    "scaleNoise_mode": ParamMeta(
        nom_de_guerre="scaleNoise.mode",
        info="Noise scaling mode. If set to spectral, the noise level will be determined for each spectral channel by measuring the noise within each image plane. This is useful for data cubes where the noise varies with frequency. If set to local, the noise level will be measured locally in window running across the entire cube in all three dimensions. This is useful for data cubes with more complex noise variations, such as interferometric images with primary-beam correction applied.",
    ),
    "scaleNoise_scfind": ParamMeta(
        nom_de_guerre="scaleNoise.scfind",
        info="If true and global or local noise scaling is enabled, then noise scaling will additionally be applied after each smoothing operation in the S+C finder. This might be useful in certain situations where large-scale artefacts are present in interferometric data. However, this feature should be used with great caution, as it has the potential to do more harm than good.",
    ),
    "scaleNoise_statistic": ParamMeta(
        nom_de_guerre="scaleNoise.statistic",
        info="Statistic to be used in the noise measurement process. Possible values are std, mad and gauss for standard deviation, median absolute deviation and Gaussian fitting to the flux histogram, respectively. Standard deviation is by far the fastest algorithm, but it is also the least robust one with respect to emission and artefacts in the data. Median absolute deviation and Gaussian fitting are far more robust in the presence of strong, extended emission or artefacts, but will usually take longer.",
    ),
    "scaleNoise_windowXY": ParamMeta(
        nom_de_guerre="scaleNoise.windowXY",
        info="Spatial size of the window used in determining the local noise level. It must be an odd integer value. If set to 0, the pipeline will use the default value instead.",
    ),
    "scaleNoise_windowZ": ParamMeta(
        nom_de_guerre="scaleNoise.windowZ",
        info="Spectral size of the window used in determining the local noise level. It must be an odd integer value. If set to 0, the pipeline will use the default value instead.",
    ),
    "scfind_enable": ParamMeta(
        nom_de_guerre="scfind.enable",
        info="If set to true, the Smooth + Clip (S+C) finder will be enabled. The S+C finder operates by iteratively smoothing the data cube with a user-defined set of smoothing kernels, measuring the noise level on each smoothing scale, and adding all pixels with an absolute flux above a user-defined relative threshold to the source detection mask.",
    ),
    "scfind_fluxRange": ParamMeta(
        nom_de_guerre="scfind.fluxRange",
        info="Flux range to be used in the noise measurement. If set to negative or positive, only pixels with negative or positive flux will be used, respectively. This can be useful to prevent real emission or artefacts from affecting the noise measurement. If set to full, all pixels will be used in the noise measurement irrespective of their flux.",
    ),
    "scfind_kernelsXY": ParamMeta(
        nom_de_guerre="scfind.kernelsXY",
        info="Comma-separated list of spatial Gaussian kernel sizes to apply. The individual kernel sizes must be floating-point values and denote the full width at half maximum (FWHM) of the Gaussian used to smooth the data in the spatial domain. A value of 0 means that no spatial smoothing will be applied.",
    ),
    "scfind_kernelsZ": ParamMeta(
        nom_de_guerre="scfind.kernelsZ",
        info="Comma-separated list of spectral Boxcar kernel sizes to apply. The individual kernel sizes must be odd integer values of 3 or greater and denote the full width of the Boxcar filter used to smooth the data in the spectral domain. A value of 0 means that no spectral smoothing will be applied.",
    ),
    "scfind_replacement": ParamMeta(
        nom_de_guerre="scfind.replacement",
        info="Before smoothing the data cube during an S+C iteration, every pixel in the data cube that was already detected in a previous iteration will be replaced by this value multiplied by the original noise level in the non-smoothed data cube, while keeping the original sign of the data value. This feature can be disabled altogether by specifying a value of < 0.",
    ),
    "scfind_statistic": ParamMeta(
        nom_de_guerre="scfind.statistic",
        info="Statistic to be used in the noise measurement process. Possible values are std, mad and gauss for standard deviation, median absolute deviation and Gaussian fitting to the flux histogram, respectively. Standard deviation is by far the fastest algorithm, but it is also the least robust one with respect to emission and artefacts in the data. Median absolute deviation and Gaussian fitting are far more robust in the presence of strong, extended emission or artefacts, but will usually take longer.",
    ),
    "scfind_threshold": ParamMeta(
        nom_de_guerre="scfind.threshold",
        info="Flux threshold to be used by the S+C finder relative to the measured noise level in each smoothing iteration. In practice, values in the range of about 3 to 5 have proven to be useful in most situations, with lower values in that range requiring use of the reliability filter to reduce the number of false detections.",
    ),
    "threshold_enable": ParamMeta(
        nom_de_guerre="threshold.enable",
        info="If set to true, the threshold finder will be enabled. The threshold finder is a very basic source finder that simply applies a fixed threshold (either absolute or relative to the noise) to the original data cube. It can be useful if a simple flux threshold is to be applied to a pre-processed or filtered data cube",
    ),
    "threshold_fluxRange": ParamMeta(
        nom_de_guerre="threshold.fluxRange",
        info="Flux range to be used in the noise measurement. If set to negative or positive, only pixels with negative or positive flux will be used, respectively. This can be useful to prevent real emission or artefacts from affecting the noise measurement. If set to full, all pixels will be used in the noise measurement irrespective of their flux.",
    ),
    "threshold_mode": ParamMeta(
        nom_de_guerre="threshold.mode",
        info="If set to absolute, the flux threshold of the threshold finder will be interpreted as an absolute flux threshold in the native flux unit of the data cube. If set to relative, the threshold will be interpreted in units of the noise level across the data cube.",
    ),
    "threshold_statistic": ParamMeta(
        nom_de_guerre="threshold.statistic",
        info="Statistic to be used in the noise measurement process if threshold.mode is set to relative. Possible values are std, mad and gauss for standard deviation, median absolute deviation and Gaussian fitting to the flux histogram, respectively. Standard deviation is by far the fastest algorithm, but it is also the least robust one with respect to emission and artefacts in the data. Median absolute deviation and Gaussian fitting are far more robust in the presence of strong, extended emission or artefacts, but will usually take longer.",
    ),
    "threshold_threshold": ParamMeta(
        nom_de_guerre="threshold.threshold",
        info="Flux threshold to be applied by the threshold finder. Depending on the threshold.mode parameter, this can either be absolute (in native flux units of the data cube) or relative to the noise level of the cube.",
    ),
    "linker_enable": ParamMeta(
        nom_de_guerre="linker.enable",
        info="If true, then the linker will be run to merge the pixels detected by the source finder into coherent detections that can then be parameterised and catalogued. If false, the pipeline will be terminated after source finding, and no catalogue or source products will be created. Disabling the linker can be useful if only the raw mask from the source finder is needed.",
    ),
    "linker_keepNegative": ParamMeta(
        nom_de_guerre="linker.keepNegative",
        info="If set to true, then the linker will not discard detections with negative flux. Reliability filtering must be disabled for negative sources to be retained. Also note that negative sources will not appear in moment 1 and 2 maps. This option should only ever be used for testing or debugging purposes, but never in production mode.",
    ),
    "linker_maxFill": ParamMeta(
        nom_de_guerre="linker.maxFill",
        info="Maximum allowed filling factor of a source within its rectangular bounding box, defined as the number of spatial and spectral pixels that make up the source divided by the number of pixels in the bounding box. The default value of 0.0 disables maximum filling factor filtering.",
    ),
    "linker_maxPixels": ParamMeta(
        nom_de_guerre="linker.maxPixels",
        info="Maximum allowed number of spatial and spectral pixels that a source must not exceed. The default value of 0 disables maximum size filtering.",
    ),
    "linker_maxSizeXY": ParamMeta(
        nom_de_guerre="linker.maxSizeXY",
        info="Maximum size of sources in the spatial dimension in pixels. Sources that exceed this limit will be discarded by the linker. If the value is set to 0, maximum size filtering will be disabled.",
    ),
    "linker_maxSizeZ": ParamMeta(
        nom_de_guerre="linker.maxSizeZ",
        info="Maximum size of sources in the spectral dimension in pixels. Sources that exceed this limit will be discarded by the linker. If the value is set to 0, maximum size filtering will be disabled.",
    ),
    "linker_minFill": ParamMeta(
        nom_de_guerre="linker.minFill",
        info="Minimum allowed filling factor of a source within its rectangular bounding box, defined as the number of spatial and spectral pixels that make up the source divided by the number of pixels in the bounding box. The default value of 0.0 disables minimum filling factor filtering.",
    ),
    "linker_minPixels": ParamMeta(
        nom_de_guerre="linker.minPixels",
        info="Minimum allowed number of spatial and spectral pixels that a source must have. The default value of 0 disables minimum size filtering.",
    ),
    "linker_minSizeXY": ParamMeta(
        nom_de_guerre="linker.minSizeXY",
        info="Minimum size of sources in the spatial dimension in pixels. Sources that fall below this limit will be discarded by the linker.",
    ),
    "linker_minSizeZ": ParamMeta(
        nom_de_guerre="linker.minSizeZ",
        info="Minimum size of sources in the spectral dimension in pixels. Sources that fall below this limit will be discarded by the linker.",
    ),
    "linker_positivity": ParamMeta(
        nom_de_guerre="linker.positivity",
        info="If set to true, then the linker will only merge positive pixels and discard all negative pixels by removing them from the mask. This option should be used with extreme caution and will render the reliability filter useless. It can be useful, though, if there are significant negative artefacts such as residual sidelobes in the data.",
    ),
    "linker_radiusXY": ParamMeta(
        nom_de_guerre="linker.radiusXY",
        info="Maximum merging length in the spatial dimension. Pixels with a separation of up to this value will be merged into the same source.",
    ),
    "linker_radiusZ": ParamMeta(
        nom_de_guerre="linker.radiusZ",
        info="Maximum merging length in the spectral dimension. Pixels with a separation of up to this value will be merged into the same source.",
    ),
    "reliability_autoKernel": ParamMeta(
        nom_de_guerre="reliability.autoKernel",
        info="If set to true, SoFiA will try to automatically determine the optimal reliability kernel scale factor by iteratively increasing the kernel size until the absolute value of the median of the Skellam distribution decreases below reliability.tolerance. If the algorithm fails to converge after reliability.iterations steps, then the default value of reliability.scaleKernel will be used instead.",
    ),
    "reliability_catalog": ParamMeta(
        nom_de_guerre="reliability.catalog",
        info="Path to a file containing positions on the sky to be excluded from the reliability analysis. The file must contain two columns separated by a space, tabulator or comma that specify the longitude and latitude of the position to be excluded in the native WCS coordinates and units of the input FITS file. Negative detections that contain any of those positions within their bounding box will be excluded from the reliability analysis, although they will still show up in the reliability plot.",
    ),
    "reliability_debug": ParamMeta(
        nom_de_guerre="reliability.debug",
        info="If set to true and the reliability module is enabled, then two catalogue files containing relevant reliability parameters of negative and positive detections are created for debugging purposes. The catalogues will be written in VOTable format.",
    ),
    "reliability_enable": ParamMeta(
        nom_de_guerre="reliability.enable",
        info="If set to true, reliability calculation and filtering will be enabled. This will determine the reliability of each detection with positive total flux by comparing the density of positive and negative detections in a three-dimensional parameter space. Sources below the specified reliability threshold will then be discarded. Note that this will require a sufficient number of negative detections, which can usually be achieved by setting the source finding threshold to somewhere around 3 to 4 times the noise level.",
    ),
    "reliability_iterations": ParamMeta(
        nom_de_guerre="reliability.iterations",
        info="Maximum number of iterations for the reliability kernel auto-scaling algorithm to converge. If convergence is not achieved, then reliability.scaleKernel will instead be applied.",
    ),
    "reliability_minPixels": ParamMeta(
        nom_de_guerre="reliability.minPixels",
        info="Minimum total number of spatial and spectral pixels within the source mask for detections to be considered reliable. The reliability of any detection with fewer pixels will be set to zero by default.",
    ),
    "reliability_minSNR": ParamMeta(
        nom_de_guerre="reliability.minSNR",
        info="Lower signal-to-noise limit for reliable sources. Detections that fall below this threshold will be deemed unreliable and assigned a reliability of 0. The value denotes the integrated signal-to-noise ratio, SNR = F_sum / [RMS * sqrt(N * Ω)], of the source, where Ω is the solid angle (in pixels) of the point spread function of the data, N is the number of spatial and spectral pixels of the source, F_sum is the summed flux density and RMS is the local RMS noise level (assumed to be constant). Note that the spectral resolution is assumed to be equal to the channel width.",
    ),
    "reliability_parameters": ParamMeta(
        nom_de_guerre="reliability.parameters",
        info="Parameter space to be used in deriving the reliability of detections. This must be a list of parameters the number of which defines the dimensionality of the parameter space. Possible values are peak for the peak flux density, sum for the summed flux density, mean for mean flux density, chan for the number of spectral channels, pix for the total number of spatial and spectral pixels, fill for the filling factor, std for the standard deviation, skew for the skewness and kurt for the kurtosis across the source mask. Flux densities will be divided by the global RMS noise level. peak, sum, mean, pix and fill will be logarithmic, all other parameters linear.",
    ),
    "reliability_plot": ParamMeta(
        nom_de_guerre="reliability.plot",
        info="If set to true, diagnostic plots (in EPS format) will be created to allow the quality of the reliability estimation to be assessed. It is advisable to generate and inspect these plots to ensure that the outcome of the reliability filtering procedure is satisfactory.",
    ),
    "reliability_scaleKernel": ParamMeta(
        nom_de_guerre="reliability.scaleKernel",
        info="When estimating the density of positive and negative detections in parameter space, the size of the Gaussian kernel used in this process is determined from the covariance of the distribution of negative detections in parameter space. This parameter setting can be used to scale that kernel by a constant factor.",
    ),
    "reliability_threshold": ParamMeta(
        nom_de_guerre="reliability.threshold",
        info="Reliability threshold in the range of 0 to 1. Sources with a reliability below this threshold will be discarded.",
    ),
    "reliability_tolerance": ParamMeta(
        nom_de_guerre="reliability.tolerance",
        info="Convergence tolerance for the reliability kernel auto-scaling algorithm. Convergence is achieved when the absolute value of the median of the Skellam distribution drops below this tolerance.",
    ),
    "dilation_enable": ParamMeta(
        nom_de_guerre="dilation.enable",
        info="Set to true to enable source mask dilation whereby the mask of each source will be grown outwards until the resulting increase in integrated flux drops below a given threshold or the maximum number of iterations is reached.",
    ),
    "dilation_iterationsXY": ParamMeta(
        nom_de_guerre="dilation.iterationsXY",
        info="Sets the maximum number of spatial iterations for the mask dilation algorithm. Once this number of iterations has been reached, mask dilation in the spatial plane will stop even if the flux increase still exceeds the threshold set by dilation.threshold.",
    ),
    "dilation_iterationsZ": ParamMeta(
        nom_de_guerre="dilation.iterationsZ",
        info="Sets the maximum number of spectral iterations for the mask dilation algorithm. Once this number of iterations has been reached, mask dilation in the spectral axis will stop even if the flux increase still exceeds the threshold set by dilation.threshold.",
    ),
    "dilation_threshold": ParamMeta(
        nom_de_guerre="dilation.threshold",
        info="If a positive value is provided, mask dilation will end when the increment in the integrated flux during a single iteration drops below this value times the total integrated flux (from the previous iteration), or when the maximum number of iterations has been reached. Specifying a negative threshold will disable flux checking altogether and always carry out the maximum number of iterations.",
    ),
    "parameter_enable": ParamMeta(
        nom_de_guerre="parameter.enable",
        info="If set to true, the parametrisation module will be enabled to measure the basic parameters of each detected source.",
    ),
    "parameter_offset": ParamMeta(
        nom_de_guerre="parameter.offset",
        info="If set to false and a region of the data cube is read in using the input.region parameter, then the position parameters x, y, z, x_min, x_max, y_min, y_max, z_min and z_max in the source catalogue will be specified relative to the region. If set to true, the position parameters will instead be relative to the full cube. Note that the auto-flagging log file will also adhere to this setting.",
    ),
    "parameter_physical": ParamMeta(
        nom_de_guerre="parameter.physical",
        info="If set to true, SoFiA will attempt to convert relevant parameters to physical units. This involves conversion of channel widths to frequency/velocity units and division of flux-based parameters by the solid angle of the beam. For this to work, the relevant header parameters, including CTYPE3, CDELT3, BMAJ and BMIN, must have been correctly set. It is further assumed that the beam does not vary with frequency or position.",
    ),
    "parameter_prefix": ParamMeta(
        nom_de_guerre="parameter.prefix",
        info="Prefix to be used in source names. The default prefix is SoFiA, and the resulting default source name is SoFiA Jhhmmss.ss-ddmmss.s for J2000 equatorial coordinates (and likewise for other coordinate types).",
    ),
    "parameter_wcs": ParamMeta(
        nom_de_guerre="parameter.wcs",
        info="If set to true, SoFiA will attempt to convert the source centroid position (x, y, z) to world coordinates using the WCS information stored in the header. In addition, spectra and moment map units will be converted from channels to WCS units as well.",
    ),
    "output_directory": ParamMeta(
        nom_de_guerre="output.directory",
        info="Full path to the directory to which all output files will be written. Defaults to '.' here (real SoFiA would fall back to the input data cube's own directory) so this cab's output paths stay predictable.",
    ),
    "output_filename": ParamMeta(
        nom_de_guerre="output.filename",
        info="File name that will be used as the template for all output files. For example, if output.filename = my_data, then the output files will be named my_data_cat.xml, my_data_mom0.fits, etc. Defaults to 'sofia' here (real SoFiA would fall back to the input data cube's own name) so this cab's output paths stay predictable.",
    ),
    "output_marginCubelets": ParamMeta(
        nom_de_guerre="output.marginCubelets",
        info="Margin (in pixels) around detections to be added when creating cubelets, moment maps and spectra of individual sources. The same margin will be applied to all axes of the cube. A value of 0 will create tight cutouts without any extra margin, thus minimising file sizes. The default is 10 pixels.",
    ),
    "output_overwrite": ParamMeta(
        nom_de_guerre="output.overwrite",
        info="If true, existing output files will be overwritten without warning. If false, SoFiA will refuse to run if any of the output files and directories to be created already exists.",
    ),
    "output_thresholdMom12": ParamMeta(
        nom_de_guerre="output.thresholdMom12",
        info="If output.cubelets is enabled, then the moment 1 and 2 maps for each individual detection will be created using only those spectral channels where the flux density exceeds this value times the local RMS noise level. E.g., setting output.thresholdMom12 to a value of 3.0 would set a 3-sigma flux density threshold for moments 1 and 2. Note that this setting has no effect on moment 0 maps or global moment 1 and 2 maps.",
    ),
    "output_writeCatASCII": ParamMeta(
        nom_de_guerre="output.writeCatASCII",
        info="If set to true, an output source catalogue will be produced in human-readable ASCII format. The catalogue file will have the suffix _cat.txt.",
    ),
    "output_writeCatSQL": ParamMeta(
        nom_de_guerre="output.writeCatSQL",
        info="If set to true, an output source catalogue will be produced in SQL format. The catalogue file will have the suffix _cat.sql. The SQL catalogue can be imported into any SQL-compatible database. A new data table containing the source parameters, named SoFiA-Catalogue by default, will be generated.",
    ),
    "output_writeCatXML": ParamMeta(
        nom_de_guerre="output.writeCatXML",
        info="If set to true, an output source catalogue will be produced in VO-compatible XML format. The catalogue file will have the suffix _cat.xml.",
    ),
    "output_writeCubelets": ParamMeta(
        nom_de_guerre="output.writeCubelets",
        info="If set to true, then individual source products for each detected source will be created, including sub-cubes, masks, moment maps and integrated spectra. The source products will be written to a sub-directory with the suffix _cubelets. Each source product will be labelled with the source ID number for identification.",
    ),
    "output_writeFiltered": ParamMeta(
        nom_de_guerre="output.writeFiltered",
        info="If set to true and any input filtering algorithm is enabled, then a data cube containing the filtered data will be written in FITS format. The filtered cube will have the suffix _filtered.fits.",
    ),
    "output_writeMask": ParamMeta(
        nom_de_guerre="output.writeMask",
        info="If set to true, then a data cube containing the final source mask produced by the source finder will be written in FITS format. The pixel values in the source mask will correspond to the respective source ID numbers in the catalogue. The mask cube will have the suffix _mask.fits.",
    ),
    "output_writeMask2d": ParamMeta(
        nom_de_guerre="output.writeMask2d",
        info="If set to true, then an image containing a two-dimensional projection of the 3D mask cube will be written in FITS format. The 2D mask image will have the suffix _mask-2d.fits. Note that some sources may be hidden behind others in this 2D projection.",
    ),
    "output_writeMoments": ParamMeta(
        nom_de_guerre="output.writeMoments",
        info="If set to true, then images of the spectral moments 0, 1 and 2 and the number of channels in each pixel of the moment 0 map will be written in FITS format. The maps will have the suffix _mom0.fits, _mom1.fits, _mom2.fits and _chan.fits. Note that moments 1 and 2 and the number of channels will not be produced if the input data cube is only two-dimensional.",
    ),
    "output_writeNoise": ParamMeta(
        nom_de_guerre="output.writeNoise",
        info="If set to true and local noise scaling is enabled, then a data cube containing the measured local noise values will be written in FITS format. The noise cube will have the suffix _noise.fits. If spectral noise scaling is enabled, then the measured noise in each channel (in native data cube flux units) will be written to a plain text file with the suffix _noise.txt.",
    ),
    "output_writeRawMask": ParamMeta(
        nom_de_guerre="output.writeRawMask",
        info="If set to true, then a data cube containing the raw, binary source mask produced by the source finder prior to linking will be written in FITS format. The raw mask cube will have the suffix _mask-raw.fits.",
    ),
    # dynamic output paths, one per `output_write*` toggle -- see module
    # docstring for why `output_directory`/`output_filename` are pinned to
    # concrete defaults rather than SoFiA's own input-derived ones.
    "cat_ascii": ParamMeta(implicit="{output_directory}/{output_filename}_cat.txt"),
    "cat_sql": ParamMeta(implicit="{output_directory}/{output_filename}_cat.sql"),
    "cat_xml": ParamMeta(implicit="{output_directory}/{output_filename}_cat.xml"),
    "cubelets": ParamMeta(implicit="{output_directory}/{output_filename}_cubelets"),
    "filtered": ParamMeta(implicit="{output_directory}/{output_filename}_filtered.fits"),
    "mask": ParamMeta(implicit="{output_directory}/{output_filename}_mask.fits"),
    "mask_2d": ParamMeta(implicit="{output_directory}/{output_filename}_mask-2d.fits"),
    "mask_raw": ParamMeta(implicit="{output_directory}/{output_filename}_mask-raw.fits"),
    "mom0": ParamMeta(implicit="{output_directory}/{output_filename}_mom0.fits"),
    "mom1": ParamMeta(implicit="{output_directory}/{output_filename}_mom1.fits"),
    "mom2": ParamMeta(implicit="{output_directory}/{output_filename}_mom2.fits"),
    "chan_map": ParamMeta(implicit="{output_directory}/{output_filename}_chan.fits"),
    "noise": ParamMeta(implicit="{output_directory}/{output_filename}_noise.fits"),
}

_OUTPUTS: dict[str, tuple[str, bool, object]] = {
    "cat_ascii": ("File", False, None),
    "cat_sql": ("File", False, None),
    "cat_xml": ("File", False, None),
    "cubelets": ("Directory", False, None),
    "filtered": ("File", False, None),
    "mask": ("File", False, None),
    "mask_2d": ("File", False, None),
    "mask_raw": ("File", False, None),
    "mom0": ("File", False, None),
    "mom1": ("File", False, None),
    "mom2": ("File", False, None),
    "chan_map": ("File", False, None),
    "noise": ("File", False, None),
}

sofia2 = define_cab(
    "sofia2",
    "sofia",
    images.SOFIA2,
    _FIELDS,
    outputs=_OUTPUTS,
    field_meta=_FIELD_META,
    policies=Policies(prefix="--"),
    info="SoFiA-2: Source Finding Application for spectral-line data (https://gitlab.com/SoFiA-Admin/SoFiA-2)",
)
