"""wsclean is the highest-priority port (per stimela-ninja's design plan):
cult-cargo's version can't be loaded without either falling back
Union/Tuple dtypes to `str`, or leaving its dynamic output paths
completely unresolved. This checks the real argv shape and the resolved
implicit-template outputs against real WSClean CLI conventions.
"""

import dosho
from shinobi.backends.recording import RecordingBackend
from shinobi.policies import build_argv
from shinobi.steps import register_step_backend
from shinobi.steps.dispatch import _dispatch


def _cab():
    return dosho.get("wsclean")


def test_registered_under_its_own_name():
    cab = _cab()
    assert cab.name == "wsclean"
    assert cab.command == "wsclean"


def test_real_param_count_not_a_hand_picked_subset():
    # cult-cargo's wsclean-base.yml declares 168 input params -- this
    # should be the real schema, not a convenience subset.
    assert len(_cab().inputs_model.model_fields) == 168


def test_tuple_and_union_dtypes_resolve_to_real_python_types():
    fields = _cab().inputs_model.model_fields
    assert fields["size"].annotation == int | tuple[int, int]
    assert fields["scale"].annotation == str | float
    assert fields["weight"].annotation == str | tuple[str, float] | None
    assert fields["channel_range"].annotation == tuple[int, int] | None


def test_build_argv_matches_real_wsclean_cli_shape():
    cab = _cab()
    argv = build_argv(
        cab,
        {
            "ms": ["obs.ms"],
            "prefix": "deep",
            "size": (4096, 4096),
            "scale": "1.3asec",
            "weight": ("briggs", 0.5),
            "channel_range": (10, 20),
            "niter": 400000,
        },
    )
    assert argv[0] == "wsclean"
    assert "-name" in argv and "deep" in argv  # prefix's real nom_de_guerre
    # -size/-weight/-channel-range are each emitted as a flag followed by
    # separate bare tokens, not one comma-joined token.
    i = argv.index("-size")
    assert argv[i : i + 3] == ["-size", "4096", "4096"]
    i = argv.index("-weight")
    assert argv[i : i + 3] == ["-weight", "briggs", "0.5"]
    i = argv.index("-channel-range")
    assert argv[i : i + 3] == ["-channel-range", "10", "20"]
    # "ms" is positional, emitted last, no flag.
    assert argv[-1] == "obs.ms"
    assert "--ms" not in argv and "-ms" not in argv


def test_data_column_default_column_flag_is_data_column_not_column():
    cab = _cab()
    assert cab.field_meta["column"].nom_de_guerre == "data-column"


def test_implicit_output_templates_resolve_against_prepared_prefix():
    cab = _cab().model_copy(update={"backend": "wsclean-record"})
    register_step_backend("wsclean-record", RecordingBackend())
    result = _dispatch(cab, None, ms=["obs.ms"], prefix="deep", size=(4096, 4096), scale="1.3asec")
    assert str(result.outputs.image) == "deep-image.fits"
    assert str(result.outputs.image_mfs) == "deep-MFS-image.fits"
    assert str(result.outputs.dirty) == "deep-dirty.fits"
    assert str(result.outputs.residual) == "deep-residual.fits"
    assert str(result.outputs.model) == "deep-model.fits"
    assert str(result.outputs.psf) == "deep-psf.fits"
    assert str(result.outputs.dirty_mfs) == "deep-MFS-dirty.fits"


def test_output_patterns_validate_combinatorial_names_without_resolving_them():
    cab = _cab()
    assert cab.match_output_pattern("dirty.per-band") is not None
    assert cab.match_output_pattern("restored.i.per-interval.mfs") is not None
    assert cab.match_output_pattern("totally-unknown-shape") is None
