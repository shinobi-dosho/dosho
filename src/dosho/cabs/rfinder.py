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
from dosho._builder import FieldSpec, define_cab

_FIELDS: dict[str, FieldSpec] = {
    "config": ("File", False, None, ParamMeta(info="RFInder configuration file (YAML format)")),
    "input_dir": (
        "Directory", False, None,
        ParamMeta(info="Working directory (MS file assumed to be here)"),
    ),
    "output_dir": ("Directory", False, None, ParamMeta(info="Output directory")),
    "label": (
        "str", False, None,
        ParamMeta(info="Output folder is called: rfi_polarization_label"),
    ),
    "input": ("MS", False, None, ParamMeta(info="Input MS file")),
    "field": ("str", False, None, ParamMeta(info="Field of the MS file to analyze")),
    "telescope": ("str", False, None, ParamMeta(info="Telescope: meerkat, apertif, wsrt")),
    "rfimode": (
        "str", False, None,
        ParamMeta(info="Mode to investigate RFI: use_flags or rms_clip"),
    ),
    "polarization": (
        "str", False, None,
        ParamMeta(info="Stokes parameter: xx, yy, xy, yx, q (also in CAPS)"),
    ),
    "frequency_interval": (
        "List[float]", False, None,
        ParamMeta(info="Frequency interval where to measure noise, in GHz", repeat_as_tokens=True),
    ),
    "spw_av": ("int", False, None, ParamMeta(info="Number of channels to average")),
    "time_step": (
        "float", False, None,
        ParamMeta(info="Time step (minutes) in which to divide the MS analysis"),
    ),
    "sigma_clip": (
        "float", False, None,
        ParamMeta(info="Sigma clip for rms_clip mode to find RFI"),
    ),
    "baseline_cut": (
        "float", False, None,
        ParamMeta(info="Cut in baseline length (m) for differential RFI analysis"),
    ),
    "no_chunks": ("bool", False, None, ParamMeta(info="Disable chunking in time")),
    "yes_chunks": ("bool", False, None, ParamMeta(info="Enable chunking in time")),
    "no_movies": (
        "bool", False, None,
        ParamMeta(info="Disable movies (use if dataset is read as a whole)"),
    ),
    "no_spw_av": ("bool", False, None, ParamMeta(info="Disable averaging in channels")),
    "yes_spw_av": ("bool", False, None, ParamMeta(info="Enable averaging in channels")),
    "no_cleanup": ("bool", False, None, ParamMeta(info="Disable cleanup of intermediate products")),
    "yes_cleanup": ("bool", False, None, ParamMeta(info="Enable cleanup of intermediate products")),
    "plot_details": (
        "bool", False, None,
        ParamMeta(info="Plot percentage of RFI/noise, or factor of noise increase"),
    ),
    "plot_summary": (
        "bool", False, None,
        ParamMeta(info="Plot percentage of RFI per ant/scan/freq/corr"),
    ),
    "summary_options": (
        "List[str]", False, None,
        ParamMeta(info="Summary type(s): ant, corr, scan, freq", repeat_as_tokens=True),
    ),
    "freq_bin": (
        "float", False, None,
        ParamMeta(info="Number of frequencies to bin into a single channel"),
    ),
    "ncpu": (
        "int", False, None,
        ParamMeta(info="Number of CPUs to use when generating summary stats"),
    ),
}

rfinder = define_cab(
    "rfinder",
    "rfinder",
    images.RFINDER,
    _FIELDS,
    policies=Policies(prefix="--"),
    info="rfinder: visualize flagged RFI in a measurement set (https://github.com/Fil8/RFInder)",
)
