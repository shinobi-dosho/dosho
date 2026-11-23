"""katdal 0.24's `mvftoms.py`, without importing katdal on the launcher.

The flag spellings below are the ones `mvftoms.py --help` prints, including
its one underscore option (`--full_pol`) and the `append` options
(`--target`, `--target-tag`, `--ant`) that take one value per occurrence.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError
from shinobi import Cab, InputRef, MSv2, Recipe
from shinobi.cabs import get as get_runtime
from shinobi.dataset_access import DatasetAccessError, plan_recipe_accesses
from shinobi.datasets import DatasetKind, dataset_declarations
from shinobi.policies import build_argv
from shinobi.steps.schema import Mutability

from dosho import get as get_definition, images
from dosho.validation import CabSpec

ARCHIVE_URL = (
    "https://archive-gw-1.kat.ac.za/1700000000/1700000000_sdp_l0.full.rdb?token=eyJhbGciOi.payload"
)


def _cab() -> Cab:
    return get_runtime("katdal-mvftoms")


def _argv(**params) -> list[str]:
    cab = _cab()
    return build_argv(cab, cab.inputs_model(**params).model_dump())


def _value(argv: list[str], flag: str) -> str:
    return argv[argv.index(flag) + 1]


def test_local_h5_conversion_has_the_real_cli_shape(tmp_path):
    h5 = tmp_path / "1234567890.h5"
    h5.touch()
    argv = _argv(
        dataset=h5,
        output_ms="obs.ms",
        full_pol=True,
        channel_range="100,3999",
        target=["J1939-6342", "J0408-6545"],
        target_tag=["bpcal"],
        ant=["m000", "m001"],
        no_auto=True,
        model_data=True,
        applycal="l1",
        dumptime=8.0,
        chanbin=4,
        flagav=True,
        quack=2,
        scans="5~10",
        ref_ant="m000",
    )
    assert argv[0] == "mvftoms.py"
    # The dataset is argparse's trailing `datasets` positional.
    assert argv[-1] == str(h5)
    assert _value(argv, "--output-ms") == "obs.ms"
    for flag, value in {
        "--channel-range": "100,3999",
        "--applycal": "l1",
        "--dumptime": "8.0",
        "--chanbin": "4",
        "--quack": "2",
        "--scans": "5~10",
        "--ref-ant": "m000",
        # Tool defaults, stated in the document and passed explicitly.
        "--flags": "all",
    }.items():
        assert _value(argv, flag) == value
    # store_true switches are bare flags; mvftoms spells full-pol with an underscore.
    for flag in ("--full_pol", "--no-auto", "--model-data", "--flagav"):
        assert flag in argv
        assert _value(argv, flag) not in {"true", "True"}
    assert "--full-pol" not in argv
    # action="append": one flag occurrence per value.
    assert [argv[i + 1] for i, t in enumerate(argv) if t == "--target"] == [
        "J1939-6342",
        "J0408-6545",
    ]
    assert [argv[i + 1] for i, t in enumerate(argv) if t == "--target-tag"] == ["bpcal"]
    assert [argv[i + 1] for i, t in enumerate(argv) if t == "--ant"] == ["m000", "m001"]
    # Unset switches and options stay off the command line.
    for flag in ("--circular", "--verbose", "--stop-w", "--uvfits", "--keep-spaces", "--tar"):
        assert flag not in argv
    assert "--pols-to-use" not in argv and "--elevation-range" not in argv


def test_defaults_match_the_tool():
    argv = _argv(dataset="obs.h5", output_ms="obs.ms")
    assert argv == [
        "mvftoms.py",
        "--output-ms",
        "obs.ms",
        "--flags",
        "all",
        "--dumptime",
        "0.0",
        "--chanbin",
        "0",
        "--quack",
        "1",
        "obs.h5",
    ]


def test_archive_rdb_url_is_passed_verbatim_with_its_token():
    """The token travels in the URL query string; nothing redacts it."""
    argv = _argv(archive_url=ARCHIVE_URL, output_ms="obs.ms", pols_to_use="HH,HV,VH,VV")
    assert argv[-1] == ARCHIVE_URL
    assert "token=" in argv[-1]
    assert _value(argv, "--pols-to-use") == "HH,HV,VH,VV"
    assert "--archive-url" not in argv and "--dataset" not in argv
    assert "TOKEN RISK" in _cab().info


def test_both_dataset_inputs_concatenate_in_declaration_order():
    argv = _argv(dataset="first.h5", archive_url=ARCHIVE_URL, output_ms="joint.ms")
    assert argv[-2:] == ["first.h5", ARCHIVE_URL]


@pytest.mark.parametrize(
    "params",
    [
        {"dataset": "obs.h5"},  # the output MS is required, never the tool's guess
        {"archive_url": "archive-gw-1.kat.ac.za/1/1_sdp_l0.rdb", "output_ms": "obs.ms"},
        {"archive_url": "https://archive/1 2.rdb", "output_ms": "obs.ms"},
        {"dataset": "obs.h5", "output_ms": "obs.ms", "channel_range": "100-200"},
        {"dataset": "obs.h5", "output_ms": "obs.ms", "channel_range": "100"},
        {"dataset": "obs.h5", "output_ms": "obs.ms", "pols_to_use": "XX,YY"},
        {"dataset": "obs.h5", "output_ms": "obs.ms", "pols_to_use": "hh,vv"},
    ],
)
def test_invalid_inputs_are_refused(params):
    with pytest.raises(ValidationError):
        _cab().inputs_model(**params)


def test_redis_and_http_urls_are_accepted():
    model = _cab().inputs_model
    model(archive_url="redis://cal5.sdp.mkat.karoo.kat.ac.za:31852", output_ms="obs.ms")
    model(archive_url="http://localhost:9000/1/1_sdp_l0.rdb", output_ms="obs.ms")


def test_the_output_ms_is_a_strict_create():
    cab = _cab()
    assert cab.image == images.KATDAL
    assert isinstance(get_definition("katdal-mvftoms"), CabSpec)
    assert [(a.field, a.mode.value) for a in cab.dataset_accesses] == [("output_ms", "create")]
    inputs = dataset_declarations(cab.inputs_model)
    outputs = dataset_declarations(cab.outputs_model)
    assert inputs["output_ms"].kind is DatasetKind.MEASUREMENT_SET_V2
    assert outputs["output_ms"].kind is DatasetKind.MEASUREMENT_SET_V2
    assert cab.mutability_of("output_ms") is not Mutability.MUTABLE
    assert cab.inputs_model.model_fields["output_ms"].is_required()
    # The source dataset is only read: its directory may be mounted read-only.
    assert cab.field_meta["dataset"].writable is False


class _Obs(BaseModel):
    ms: MSv2


class _Empty(BaseModel):
    pass


def _convert_then_flag() -> Recipe:
    recipe = Recipe(name="mvf-to-flags", inputs_model=_Obs, outputs_model=_Empty)
    recipe.add_step(
        "convert",
        _cab(),
        archive_url=ARCHIVE_URL,
        output_ms=InputRef(field="ms"),
    )
    recipe.add_step("flag", get_runtime("tricolour"), ms=InputRef(field="ms"))
    return recipe


def test_conversion_plans_ahead_of_a_strict_writer(tmp_path):
    plan = plan_recipe_accesses(
        _convert_then_flag(), {"ms": tmp_path / "obs.ms"}, workspace=tmp_path
    )
    modes = {step: [a.mode.value for a in accesses] for step, accesses in plan.accesses.items()}
    assert modes == {"convert": ["create"], "flag": ["write"]}
    names = plan.graph.names
    assert names.index("convert") in plan.graph.deps[names.index("flag")]


def test_an_existing_output_ms_is_refused_before_mvftoms_can_resume_into_it(tmp_path):
    """mvftoms.py silently continues writing into an existing MS. The strict
    CREATE contract is what stops a stale MS being extended."""
    existing = tmp_path / "obs.ms"
    existing.mkdir()
    with pytest.raises(DatasetAccessError, match="already exists"):
        plan_recipe_accesses(_convert_then_flag(), {"ms": existing}, workspace=tmp_path)
