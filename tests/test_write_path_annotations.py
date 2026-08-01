"""Every string-typed output stem is declared, and the declaration is checked.

`ParamMeta.write_path` (stimela-ninja #78) marks a `str` input that names a
filesystem path the tool writes under. It deliberately changes nothing at run
time -- a path dtype there would be absolutized into the sandbox and the tool
would write outside it, which is why these are strings. What it adds is that
`Cab` rejects a marked stem no write declaration names, turning a convention
that was previously prose in `declared_output_dirs` into something enforced.
"""

from __future__ import annotations

import re

import pytest
from shinobi.steps.schema import Cab, ParamMeta, declared_output_dirs, path_fields

import dosho.cabs as C

EXPECTED = {
    # stems: products are built from these; the value never exists as a file
    ("ddfacet", "output_name"),
    ("sofia2", "output_directory"),
    ("sofia2", "output_filename"),
    ("spimple-imconv", "output_filename"),
    ("spimple-spifit", "output_filename"),
    ("wsclean", "prefix"),
    # complete paths, written directly. Marked once the field was renamed from
    # `path_prefix`, which described the shape above and not these.
    ("ddfacet", "cache_dir"),
    ("ddfacet", "montblanc_log_file"),
    ("killms", "image_sky_model_ddf_cache_dir"),
}


def _binary_cabs() -> list[Cab]:
    return [c for n in C.__all__ if isinstance(c := getattr(C, n), Cab)]


def _marked() -> set[tuple[str, str]]:
    return {(c.name, f) for c in _binary_cabs() for f, m in c.field_meta.items() if m.write_path}


def test_the_expected_stems_are_marked():
    assert _marked() == EXPECTED


def test_no_marked_stem_is_path_typed():
    """The property that keeps the marker safe. If one of these ever becomes a
    path dtype, `sandbox.absolutize_path_inputs` rewrites it and the tool
    writes outside the sandbox.
    """
    for cab in _binary_cabs():
        paths = path_fields(cab.inputs_model)
        for field, meta in cab.field_meta.items():
            if meta.write_path:
                assert field not in paths, f"{cab.name}.{field} is marked write_path but path-typed"


def test_every_marked_stem_resolves_a_write_directory():
    """The check `Cab` runs is structural -- that *something* names the stem.
    This is the behavioural other half: the declaration actually produces a
    directory to mount.
    """
    for cab in _binary_cabs():
        stems = [f for f, m in cab.field_meta.items() if m.write_path]
        if not stems:
            continue
        # All of a cab's stems at once: sofia2's template is
        # "{output_directory}/{output_filename}...", and `declared_output_dirs`
        # skips a template it cannot fully resolve, so feeding one at a time
        # would report a correctly-declared cab as declaring nothing.
        dirs = declared_output_dirs(cab, dict.fromkeys(stems, "/tmp/dosho-probe/stem"))
        assert dirs, f"{cab.name}: stems {stems} declare no write directory"


def test_no_unmarked_string_stem_remains():
    """Guards against the set drifting: any `str` input named by a write
    declaration is a stem, so it should carry the marker. A new cab that adds
    one without marking it fails here.
    """
    missed = []
    for cab in _binary_cabs():
        decls = [
            str(m.implicit)
            for f, m in cab.field_meta.items()
            if f in cab.outputs_model.model_fields and isinstance(m.implicit, str)
        ]
        decls += list(cab.harvest or []) + list(cab.scratch or [])
        referenced = set(re.findall(r"\{(\w+)", " ".join(decls)))
        paths = path_fields(cab.inputs_model)
        for ref in referenced:
            if ref not in cab.inputs_model.model_fields or ref in paths:
                continue
            meta = cab.field_meta.get(ref)
            if meta is None or not meta.write_path:
                missed.append((cab.name, ref))
    # No allowlist. Every string input named by a write declaration is marked;
    # the three that used to sit here were exempt only because `path_prefix`
    # described a stem and they are complete paths, which the rename fixed.
    assert missed == []


def test_the_check_actually_fires():
    """Not vacuous: a marked stem nothing declares is rejected."""
    from shinobi.loaders import build_model

    with pytest.raises(ValueError, match="marked write_path but named by no write declaration"):
        Cab(
            name="probe",
            command="x",
            inputs_model=build_model("I", {"stem": ("str", False, None)}),
            outputs_model=build_model("O", {}),
            field_meta={"stem": ParamMeta(write_path=True)},
        )
