"""Apparent Gaussian models are predicted once, without another beam."""

from pathlib import Path

import pytest
from shinobi.cabs import get
from shinobi.exceptions import ParameterError
from shinobi.policies import build_argv
from shinobi.steps.dispatch import _prepare_inputs
from shinobi.steps.schema import Mutability


def test_apparent_gaul_real_argv_and_passthrough(tmp_path):
    from dosho.cabs import simms_predict_gaul_apparent

    assert simms_predict_gaul_apparent.name == "simms-predict-gaul-apparent"
    cab = get("simms-predict-gaul-apparent")
    prepared = _prepare_inputs(
        cab,
        {
            "ms": tmp_path / "observation.ms",
            "ascii_sky": tmp_path / "apparent.gaul",
            "nworkers": 2,
            "row_chunks": 128,
        },
    )
    argv = build_argv(cab, prepared)
    assert argv[:2] == ["simms", "skysim"]
    assert argv[-1] == str(tmp_path / "observation.ms")
    for flag, value in {
        "--ascii-sky": str(tmp_path / "apparent.gaul"),
        "--ascii-species": "bdsf_gaul",
        "--column": "MODEL_GAUL",
        "--mode": "sim",
        "--smearing": "none",
        "--nworkers": "2",
        "--row-chunks": "128",
    }.items():
        assert argv[argv.index(flag) + 1] == value
    assert "--no-polarisation" in argv
    assert not {
        "--primary-beam",
        "--aterm-config",
        "--aterm-image",
        "--polarisation",
        "--fits-sky",
        "--wsclean-sky",
        "--source-schema",
    } & set(argv)
    assert cab.mutability_of("ms") is Mutability.MUTABLE
    assert "ms" in cab.outputs_model.model_fields
    assert cab.field_meta["model_token"].implicit == "MODEL_GAUL"
    assert cab.field_meta["ascii_sky"].writable is False
    assert not cab.derived_reads
    assert prepared["ascii_sky"] == tmp_path / "apparent.gaul"


@pytest.mark.parametrize(
    "patch",
    [
        {"column": "DATA"},
        {"column": "MODEL_DATA"},
        {"column": None},
        {"mode": "add"},
        {"ascii_species": "wsclean"},
        {"smearing": "time"},
        {"no_polarisation": False},
        {"polarisation": True},
        {"primary_beam": "beam.yaml"},
        {"source_schema": "schema.yaml"},
        {"fits_sky": "sky.fits"},
        {"wsclean_sky": "sky.txt"},
        {"aterm_config": "beam.parset"},
        {"aterm_image": "beam.fits"},
    ],
)
def test_apparent_gaul_rejects_other_prediction_paths(patch):
    cab = get("simms-predict-gaul-apparent")
    with pytest.raises(ParameterError):
        _prepare_inputs(cab, {"ms": Path("obs.ms"), "ascii_sky": Path("sky.gaul"), **patch})


def test_unknown_hyphenated_parameters_cannot_emit_screen_flags():
    # Pre-existing modelgen behavior ignores extra keys rather than forbidding
    # them. Recipe input names are canonical underscores; even unknown CLI
    # spellings must not make it into this profile's emitted argv.
    cab = get("simms-predict-gaul-apparent")
    prepared = _prepare_inputs(
        cab,
        {
            "ms": Path("obs.ms"),
            "ascii_sky": Path("sky.gaul"),
            "aterm-config": "beam.parset",
            "aterm-image": "beam.fits",
            "primary-beam": "beam.yaml",
        },
    )
    argv = build_argv(cab, prepared)
    assert not {"--aterm-config", "--aterm-image", "--primary-beam"} & set(argv)
    assert not {"beam.parset", "beam.fits", "beam.yaml"} & set(argv)
