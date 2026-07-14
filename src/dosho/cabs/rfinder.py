"""rfinder -- visualize flagged RFI in a measurement set
(https://github.com/Fil8/RFInder).

Ported field-by-field from `rfinder --help` (rfinder 1.1.0). cult-cargo's
`rfinder.yml` uses several of the short single-dash flag names as its own
field names (e.g. `noCh`, `noSpw`, `noClp`) -- this port uses the real
long-form flags instead (e.g. `--no_chunks`, `--no_spw_av`,
`--no_cleanup`), which turn out to *not* match those short flags'
mnemonics 1:1 (`-noClp`'s long form is `--no_cleanup`, not `--no_clip`).
"""

from __future__ import annotations

from shinobi.steps.schema import ParamMeta, Policies

from dosho import images
from dosho._builder import define_cab

_FIELDS: dict[str, tuple[str, bool, object]] = {
    "config": ("File", False, None),
    "input_dir": ("Directory", False, None),
    "output_dir": ("Directory", False, None),
    "label": ("str", False, None),
    "input": ("MS", False, None),
    "field": ("str", False, None),
    "telescope": ("str", False, None),
    "rfimode": ("str", False, None),
    "polarization": ("str", False, None),
    "frequency_interval": ("List[float]", False, None),
    "spw_av": ("int", False, None),
    "time_step": ("float", False, None),
    "sigma_clip": ("float", False, None),
    "baseline_cut": ("float", False, None),
    "no_chunks": ("bool", False, None),
    "yes_chunks": ("bool", False, None),
    "no_movies": ("bool", False, None),
    "no_spw_av": ("bool", False, None),
    "yes_spw_av": ("bool", False, None),
    "no_cleanup": ("bool", False, None),
    "yes_cleanup": ("bool", False, None),
    "plot_details": ("bool", False, None),
    "plot_summary": ("bool", False, None),
    "summary_options": ("List[str]", False, None),
    "freq_bin": ("float", False, None),
    "ncpu": ("int", False, None),
}

_FIELD_META: dict[str, ParamMeta] = {
    "config": ParamMeta(info="RFInder configuration file (YAML format)"),
    "input_dir": ParamMeta(info="Working directory (MS file assumed to be here)"),
    "output_dir": ParamMeta(info="Output directory"),
    "label": ParamMeta(info="Output folder is called: rfi_polarization_label"),
    "input": ParamMeta(info="Input MS file"),
    "field": ParamMeta(info="Field of the MS file to analyze"),
    "telescope": ParamMeta(info="Telescope: meerkat, apertif, wsrt"),
    "rfimode": ParamMeta(info="Mode to investigate RFI: use_flags or rms_clip"),
    "polarization": ParamMeta(info="Stokes parameter: xx, yy, xy, yx, q (also in CAPS)"),
    "frequency_interval": ParamMeta(
        info="Frequency interval where to measure noise, in GHz", repeat_as_tokens=True
    ),
    "spw_av": ParamMeta(info="Number of channels to average"),
    "time_step": ParamMeta(info="Time step (minutes) in which to divide the MS analysis"),
    "sigma_clip": ParamMeta(info="Sigma clip for rms_clip mode to find RFI"),
    "baseline_cut": ParamMeta(info="Cut in baseline length (m) for differential RFI analysis"),
    "no_chunks": ParamMeta(info="Disable chunking in time"),
    "yes_chunks": ParamMeta(info="Enable chunking in time"),
    "no_movies": ParamMeta(info="Disable movies (use if dataset is read as a whole)"),
    "no_spw_av": ParamMeta(info="Disable averaging in channels"),
    "yes_spw_av": ParamMeta(info="Enable averaging in channels"),
    "no_cleanup": ParamMeta(info="Disable cleanup of intermediate products"),
    "yes_cleanup": ParamMeta(info="Enable cleanup of intermediate products"),
    "plot_details": ParamMeta(info="Plot percentage of RFI/noise, or factor of noise increase"),
    "plot_summary": ParamMeta(info="Plot percentage of RFI per ant/scan/freq/corr"),
    "summary_options": ParamMeta(
        info="Summary type(s): ant, corr, scan, freq", repeat_as_tokens=True
    ),
    "freq_bin": ParamMeta(info="Number of frequencies to bin into a single channel"),
    "ncpu": ParamMeta(info="Number of CPUs to use when generating summary stats"),
}

rfinder = define_cab(
    "rfinder",
    "rfinder",
    images.RFINDER,
    _FIELDS,
    field_meta=_FIELD_META,
    policies=Policies(prefix="--"),
    info="rfinder: visualize flagged RFI in a measurement set (https://github.com/Fil8/RFInder)",
)
