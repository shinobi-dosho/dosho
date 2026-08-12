"""msutils' two console scripts, `msutils` and `gainutils`.

Both are click apps, so what a cab can get wrong here is narrow and specific:
the subcommand path (`msutils flags backup` is three argv tokens), which
parameters are positional arguments rather than options, whether a repeatable
option repeats its flag or comma-joins its values, and whether `--json` takes
a path (info, summary, flagstats, gainutils) or is a bare boolean (du, check,
taql). These check that token shape against the real CLI.

The cabs describe msutils `main`, which is ahead of the released 3.0.0 the
manifest's `build:` installs -- see the MSUTILS `dev:` entry in images.yaml
for what that means and how to build the image these need.
"""

import pytest
from pydantic import ValidationError
from shinobi.policies import build_argv
from shinobi.steps.schema import Mutability

import dosho
from dosho import images

MSUTILS_CABS = [
    "msutils-info",
    "msutils-summary",
    "msutils-addcol",
    "msutils-copycol",
    "msutils-delcol",
    "msutils-renamecol",
    "msutils-sumcols",
    "msutils-addnoise",
    "msutils-flagstats",
    "msutils-subset",
    "msutils-average",
    "msutils-flags-backup",
    "msutils-flags-restore",
    "msutils-flags-list",
    "msutils-flags-delete",
    "msutils-du",
    "msutils-check",
    "msutils-taql",
    "msutils-convert",
    "gainutils-fluxscale",
    "gainutils-normalise",
    "gainutils-smooth",
]

# The ones that change the MS they are given. gainutils is deliberately not
# among them: it never writes gains in place, and says so in its own --help.
IN_PLACE = [
    "msutils-addcol",
    "msutils-copycol",
    "msutils-delcol",
    "msutils-renamecol",
    "msutils-sumcols",
    "msutils-addnoise",
    "msutils-flags-backup",
    "msutils-flags-restore",
    "msutils-flags-delete",
]


def argv(name: str, params: dict) -> list[str]:
    cab = dosho.get(name)
    return build_argv(cab, cab.inputs_model(**params).model_dump())


@pytest.mark.parametrize("name", MSUTILS_CABS)
def test_every_cab_is_on_the_msutils_image_and_calls_a_real_subcommand(name):
    cab = dosho.get(name)
    assert cab.image == images.MSUTILS
    script, *subcommand = cab.command.split()
    assert script == ("gainutils" if name.startswith("gainutils-") else "msutils")
    # the registered name is the argv path: msutils-flags-backup -> `flags backup`
    assert subcommand == name.split("-")[1:]


@pytest.mark.parametrize("name", IN_PLACE)
def test_an_ms_changed_in_place_is_declared_mutable(name):
    """Without this the step runs against a sandbox copy and the column (or
    flag version) it added is thrown away with it -- the tool succeeds and the
    pipeline sees nothing.
    """
    assert dosho.get(name).mutability_of("ms") is Mutability.MUTABLE


def test_flags_subcommands_are_three_argv_tokens():
    assert argv("msutils-flags-backup", {"ms": "obs.ms", "name": "pre-cal"}) == [
        "msutils",
        "flags",
        "backup",
        "--name",
        "pre-cal",
        "obs.ms",
    ]
    assert argv("msutils-flags-restore", {"ms": "obs.ms", "name": "pre-cal"}) == [
        "msutils",
        "flags",
        "restore",
        "obs.ms",
        "pre-cal",
    ]


def test_info_takes_a_json_path_while_du_takes_a_bare_json_flag():
    """Both spell it `--json`; only one of them takes a value. A cab that gets
    this backwards produces a command line click rejects outright.
    """
    tokens = argv("msutils-info", {"ms": "obs.ms", "level": "meta", "json_out": "info.json"})
    assert tokens == ["msutils", "info", "--level", "meta", "--json", "info.json", "obs.ms"]
    assert argv("msutils-du", {"ms": "obs.ms", "as_json": True}) == [
        "msutils",
        "du",
        "--json",
        "obs.ms",
    ]


def test_repeatable_selections_repeat_the_flag():
    """click's `multiple=True` options: `--field 0 --field 1`, not
    `--field 0,1` (one token, which click reads as a single field named
    "0,1").
    """
    tokens = argv(
        "msutils-subset",
        {"ms": "obs.ms", "outms": "sub.ms", "field": ["0", "1"], "scan": [3, 4]},
    )
    assert tokens.count("--field") == 2
    assert tokens[tokens.index("--field") : tokens.index("--field") + 4] == [
        "--field",
        "0",
        "--field",
        "1",
    ]
    assert tokens.count("--scan") == 2
    # input MS then output MS, in that order, after every option
    assert tokens[-2:] == ["obs.ms", "sub.ms"]


def test_repeatable_positional_columns_are_separate_tokens():
    tokens = argv("msutils-delcol", {"ms": "obs.ms", "colnames": ["CORRECTED_DATA", "MODEL_DATA"]})
    assert tokens == ["msutils", "delcol", "obs.ms", "CORRECTED_DATA", "MODEL_DATA"]


def test_subset_and_average_carry_the_options_no_release_has_yet():
    """The reason the MSUTILS `dev:` image exists: 3.0.0's subset takes only
    the four selections, and neither command reindexes.
    """
    tokens = argv(
        "msutils-average",
        {"ms": "obs.ms", "outms": "avg.ms", "time_bin": 8.0, "chan_bin": 4, "reindex": True},
    )
    assert "--time-bin" in tokens and "--chan-bin" in tokens and "--reindex" in tokens
    subset = dosho.get("msutils-subset").inputs_model.model_fields
    assert {"taql", "time_bin", "chan_bin", "reindex"} <= set(subset)


def test_dashed_flags_keep_their_python_field_names():
    """`--no-pointing`/`--json-stdout` are not identifiers; the loader
    sanitises the field and remembers the real flag.
    """
    fields = dosho.get("msutils-convert").inputs_model.model_fields
    assert "no_pointing" in fields
    tokens = argv("msutils-convert", {"ms": "obs.ms", "outpath": "obs.ps", "no_pointing": True})
    assert "--no-pointing" in tokens
    assert "--json-stdout" in argv("msutils-info", {"ms": "obs.ms", "json_stdout": True})


def test_convert_and_subset_declare_the_product_they_write():
    """An output named after the input that names it picks that value up, so a
    downstream step can be wired to it.
    """
    assert set(dosho.get("msutils-convert").outputs_model.model_fields) == {"outpath"}
    assert set(dosho.get("msutils-subset").outputs_model.model_fields) == {"outms"}
    assert dosho.get("msutils-convert").field_meta["outpath"].write_path


def test_taql_query_is_positional_and_the_ms_is_an_option():
    assert argv("msutils-taql", {"query": "SELECT DISTINCT FIELD_ID FROM $1", "ms": "obs.ms"}) == [
        "msutils",
        "taql",
        "--ms",
        "obs.ms",
        "SELECT DISTINCT FIELD_ID FROM $1",
    ]


def test_gainutils_is_its_own_script_with_gain_tables_positional():
    tokens = argv(
        "gainutils-fluxscale",
        {
            "transfer": "transfer.G",
            "reference": "reference.G",
            "transfer_field": "1",
            "reference_field": "0",
            "output": "scaled.G",
            "json_out": "flux.json",
        },
    )
    assert tokens[:2] == ["gainutils", "fluxscale"]
    assert tokens[-1] == "transfer.G"  # TRANSFER is the argument; --reference an option
    assert "--reference" in tokens and "--transfer-field" in tokens
    assert tokens[tokens.index("--json") + 1] == "flux.json"


def test_gainutils_choices_are_narrowed_to_the_tools_own():
    """A wrong `--statistic`/`--axis`/`--scope` is a click.Choice error at run
    time; narrowing them here fails at step construction instead.
    """
    normalise = dosho.get("gainutils-normalise")
    with pytest.raises(ValidationError):
        normalise.inputs_model(gains="b.B", statistic="mode")
    assert normalise.inputs_model(gains="b.B", axis="freq", scope="block")


def test_smooth_windows_take_a_count_or_a_physical_width():
    smooth = dosho.get("gainutils-smooth")
    assert smooth.inputs_model(gains="g.qc", time_window="120s").time_window == "120s"
    assert smooth.inputs_model(gains="g.qc", freq_window=8).freq_window == 8
    tokens = argv("gainutils-smooth", {"gains": "g.qc", "time_window": "5min", "fill": True})
    assert tokens[tokens.index("--time-window") + 1] == "5min"
    assert "--fill" in tokens  # `--fill/--no-fill`; off is the default, so False emits nothing
    assert "--fill" not in argv("gainutils-smooth", {"gains": "g.qc", "fill": False})
