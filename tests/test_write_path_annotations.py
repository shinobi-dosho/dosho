"""`ParamMeta.write_path`, both of the things it declares, across every cab.

**A string-typed output stem** (stimela-ninja #78). Products are built from
it and the value never exists as a file. It deliberately changes nothing at
run time -- a path dtype there would be absolutized into the sandbox and the
tool would write outside it, which is why these are strings. What the marker
adds is that `Cab` rejects a stem no write declaration names.

**A path-typed destination the tool creates** (stimela-ninja #92). This is
the only thing that separates the two identical-looking spellings of an
output field echoing a same-named input:

    mstransform(vis=..., outputvis=...) -> outputvis   # created here
    flagdata(vis=...)                   -> vis         # the caller's MS

Both declare one name on `inputs_model` and on `outputs_model`, so
`mutated_path_fields` -- and every other structural test -- sees one shape.
Marking says which it is, and `sandbox.clear_stale_outputs` then clears the
stale product before a re-run instead of leaving the tool to trip over it
(CASA refuses to overwrite; anything that appends corrupts silently).
Unmarked is the safe reading, so the interesting half of this file is
`NOT_DESTINATIONS`: every dual declaration deliberately left alone, with the
reason, so a new cab cannot quietly join the wrong side.
"""

from __future__ import annotations

import re
import warnings

import pytest
import yaml
from shinobi.steps.schema import (
    Cab,
    ParamMeta,
    declared_output_dirs,
    path_fields,
    write_path_fields,
)

import dosho.cabs as C
from dosho import registry

# String stems: the value is a prefix, never a file.
STEMS = {
    ("ddfacet", "output_name"),
    ("im-mowjsub", "output_prefix"),
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

# Path-typed destinations: the tool creates the path, so the previous run's
# product is this step's to replace.
DESTINATIONS = {
    # MS-producing CASA tasks -- the family that motivated this. Every one of
    # them checks its output for existence and refuses.
    ("mstransform", "outputvis"),
    ("split", "outputvis"),
    ("cvel", "outputvis"),
    ("cvel2", "outputvis"),
    ("hanningsmooth", "outputvis"),
    ("partition", "outputvis"),
    ("phaseshift", "outputvis"),
    ("uvcontsub", "outputvis"),
    ("conjugatevis", "outputvis"),
    ("fixvis", "outputvis"),
    ("appendantab", "outvis"),
    # other created CASA products
    ("listobs", "listfile"),
    ("feather", "imagename"),
    ("impbcor", "outfile"),
    ("getantposalma", "outfile"),
    ("getcalmodvla", "outfile"),
    ("plotms", "plotfile"),
    # non-CASA pysteps
    ("bdsf-catalog", "outfile_gaul"),
    ("bdsf-catalog", "outfile_srl"),
    ("fitstoolz-add-axis", "outfile"),
    ("fitstoolz-header", "outfile"),
    ("fitstoolz-remove-axis", "outfile"),
    ("fitstoolz-slice", "outfile"),
    ("fitstoolz-stack", "stacked_fits"),
    ("simms-telsim", "ms"),
    ("simms-primary-beam", "output"),
    # document cabs
    ("aegean", "out"),
    ("aimfast", "outfile"),
    ("breizorro", "outcatalog"),
    ("breizorro", "outfile"),
    ("breizorro", "outregion"),
    ("flagms", "export"),
    ("msutils-flagstats", "json_out"),
    ("msutils-flagstats", "plot"),
    ("msutils-summary", "json_out"),
    ("owlcat_plotelev", "output_name"),
    ("ragavi-gains", "htmlname"),
    ("ragavi-gains", "plotname"),
    ("ragavi-vis", "htmlname"),
    ("simms", "msname"),
    ("tigger-convert", "output_model"),
    ("tigger-restore", "output_image"),
    ("tigger-tag", "output"),
    ("vis-mowjsub", "output_ms"),
    ("doppler-mowjsub", "output_ms"),
}

# Every other dual declaration, and why deleting it would be wrong. Grouped by
# the reason, because the reasons are what a new cab has to be checked against
# -- not the names.
NOT_DESTINATIONS = {
    # 1. In-place mutation: the tool rewrites the caller's own data. Deleting
    #    it destroys the pipeline's input mid-run.
    **dict.fromkeys(
        [
            ("applycal", "vis"),
            ("clearcal", "vis"),
            ("defintent", "vis"),
            ("delmod", "vis"),
            ("fixplanets", "vis"),
            ("flagcmd", "vis"),
            ("flagdata", "vis"),
            ("flagmanager", "vis"),
            ("ft", "vis"),
            ("initweights", "vis"),
            ("setjy", "vis"),
            ("statwt", "vis"),
            ("uvsub", "vis"),
            ("aoflagger", "msname"),
            ("chgcentre", "ms"),
            ("crystalball", "ms"),
            ("flagms", "ms"),
            ("msutils-addcol", "ms"),
            ("msutils-addnoise", "ms"),
            ("msutils-copycol", "ms"),
            ("msutils-sumcols", "ms"),
            ("msuvbinflag", "binnedvis"),
            ("quartical-restore", "ms_path"),
            ("simms-primary-beam", "ms"),
            ("simms-skysim", "ms"),
            ("tricolour", "ms"),
            ("vis-mowjsub", "ms"),
        ],
        "rewritten in place -- the caller's data, not this step's product",
    ),
    # 2. Appends to what is already there. Clearing first would silently drop
    #    the accumulated result rather than fail -- the worse half.
    **dict.fromkeys(
        [
            ("accor", "caltable"),
            ("bandpass", "caltable"),
            ("blcal", "caltable"),
            ("fluxscale", "fluxtable"),
            ("fringefit", "caltable"),
            ("gaincal", "caltable"),
            ("gencal", "caltable"),
            ("polcal", "caltable"),
            ("wvrgcal", "caltable"),
        ],
        "calibration tables accumulate: `append=True` adds solutions to an existing table, "
        "and `gencal` accumulates by design. Treated as one family rather than per-task, so "
        "the rule does not depend on which wrapper happens to expose `append`",
    ),
    **dict.fromkeys(
        [
            ("concat", "concatvis"),
            ("virtualconcat", "concatvis"),
            ("msuvbin", "outputvis"),
        ],
        "appends to an existing output if one is there (CASA concat/msuvbin semantics)",
    ),
    # 3. A container the tool writes *into*, not a single product. Replacing
    #    the directory would take everything else in it too.
    **dict.fromkeys(
        [
            ("quartical-backup", "zarr_dir"),
            ("rfinder", "output_dir"),
        ],
        "a directory the tool writes into, holding more than this run's product",
    ),
    # 4. A prefix, not a complete path -- nothing exists at the declared value,
    #    so clearing it could only ever hit something that is not the product.
    ("predictcomp", "prefix"): "a prefix; the products are `<prefix>*.cl`",
}


def _all_scopes() -> dict[str, object]:
    """Every registered cab, by name, as the `Scope` carrying its schema --
    `Cab`s from documents and `StepRef`-wrapped pysteps alike. The audit has to
    see both: the destinations are split roughly evenly between them.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # experimental-cab warnings
        scopes = {}
        for name in registry.list_cabs():
            cab = registry.get(name)
            scopes[name] = getattr(cab, "step", cab)
        return scopes


def _binary_cabs() -> list[Cab]:
    return [c for n in C.__all__ if isinstance(c := getattr(C, n), Cab)]


def test_every_marked_field_is_accounted_for():
    """The audit itself. A new cab whose output echoes a same-named input
    lands in neither set and fails here, which is the point -- someone has to
    decide which of the two shapes it is.
    """
    marked = {
        (name, field) for name, scope in _all_scopes().items() for field in write_path_fields(scope)
    }
    assert marked == STEMS | DESTINATIONS


def test_every_dual_declaration_is_classified():
    dual = {
        (name, field)
        for name, scope in _all_scopes().items()
        for field in path_fields(scope.inputs_model) & path_fields(scope.outputs_model)
    }
    unclassified = dual - DESTINATIONS - set(NOT_DESTINATIONS)
    assert unclassified == set(), (
        f"{sorted(unclassified)} declare a path on both models and are in neither list. "
        "Does the tool CREATE that path (add to DESTINATIONS, mark it write_path) or REWRITE "
        "the caller's data at it (add to NOT_DESTINATIONS with the reason)?"
    )
    assert not (set(NOT_DESTINATIONS) - dual), (
        "NOT_DESTINATIONS names something that is no longer a dual declaration"
    )


def test_nothing_deliberately_left_is_marked():
    """The half that costs data if it is ever wrong."""
    marked = {
        (name, field) for name, scope in _all_scopes().items() for field in write_path_fields(scope)
    }
    wrong = sorted(set(NOT_DESTINATIONS) & marked)
    assert wrong == [], (
        f"{wrong} are marked write_path but documented as not destinations: {[NOT_DESTINATIONS[w] for w in wrong]}"
    )


def test_every_destination_is_declared_as_an_output():
    """What makes the marker legal on a path-typed input: `Cab` accepts one
    whose write target is the same-named output field. A marked path that is
    *not* an output would be a path the tool writes and nothing harvests.
    """
    scopes = _all_scopes()
    for name, field in sorted(DESTINATIONS):
        scope = scopes[name]
        assert field in path_fields(scope.outputs_model), (
            f"{name}.{field} is marked a destination but is not a path-typed output"
        )


def test_no_marked_stem_is_path_typed():
    """The property that keeps the *stem* marker safe. If one of these ever
    becomes a path dtype, `sandbox.absolutize_path_inputs` rewrites it and the
    tool writes outside the sandbox. Destinations are exempt by construction:
    being path-typed and anchored is exactly what they want.
    """
    scopes = _all_scopes()
    for name, field in sorted(STEMS):
        assert field not in path_fields(scopes[name].inputs_model), (
            f"{name}.{field} is marked write_path as a stem but is path-typed"
        )


def test_every_marked_stem_resolves_a_write_directory():
    """The check `Cab` runs is structural -- that *something* names the stem.
    This is the behavioural other half: the declaration actually produces a
    directory to mount.
    """
    for cab in _binary_cabs():
        stems = [
            f
            for f, m in cab.field_meta.items()
            if m.write_path and f not in path_fields(cab.inputs_model)
        ]
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


def test_a_documents_marker_survives_its_own_output_declaration():
    """A document cab marks `write_path` on the *input* side while the same
    name is declared again under `outputs`. stimela-ninja's loader used to
    replace the input meta with the output one, dropping the marker for
    exactly these fields (fixed in ninja #93). Pin it from this side too: the
    marker is worth nothing if it does not survive loading.
    """
    doc_destinations = [(n, f) for n, f in sorted(DESTINATIONS) if isinstance(registry.get(n), Cab)]
    assert doc_destinations, "no document cab carries a destination marker any more"
    for name, field in doc_destinations:
        assert field in write_path_fields(registry.get(name)), (
            f"{name}.{field}: write_path lost while loading the document"
        )


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


def test_the_index_and_the_audit_agree_on_what_exists():
    """`_all_scopes` walks the registry; if a cab were missing from the index
    the audit above would silently pass by not seeing it.
    """
    import pathlib

    index = yaml.safe_load(pathlib.Path("src/dosho/cab_index.yaml").read_text())["cabs"]
    assert set(_all_scopes()) == set(index)
