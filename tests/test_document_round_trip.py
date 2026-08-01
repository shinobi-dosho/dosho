"""The migration gate: every cab must survive Python -> document -> Cab.

`docs/design_data_registry.md` §4.6. Two checks, because one cannot cover
everything:

* the comparator (`tests/cab_compare`) for everything a built `Cab` knows;
* a direct dtype-string comparison for what it does not. `dtype_to_type` is
  many-to-one (`Path` <- File/MS/Directory/URI), so 16% of fields lose their
  declared dtype the moment the `Cab` exists. Both sides of a comparison are
  already `Path` by then, which is why this needs checking against *source*
  rather than against the reloaded object.

If a cab fails either, stop and reassess -- do not loosen a check to make it
pass. That is the whole point of a gate.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml
from shinobi.loaders.yaml_cab import loads
from shinobi.steps.schema import Cab

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.cab_compare import cab_differences
from tools.cab_source import read_sources
from tools.generate_documents import DOCUMENT_DIR, documents, render, write_documents


@pytest.fixture(scope="module")
def generated() -> dict:
    """The documents as *committed*, not as freshly generated.

    The distinction is the point of this file. A gate that regenerates and
    then checks its own output proves the generator self-consistent and
    nothing about the files anyone actually loads; `test_committed_documents_
    are_current` is what ties the two together.
    """
    out = {}
    for path in sorted(DOCUMENT_DIR.glob("*.yml")):
        body = yaml.safe_load(path.read_text())["cabs"]
        (name,) = body
        out[name] = body[name]
    return out


@pytest.fixture(scope="module")
def built() -> dict[str, Cab]:
    import dosho.cabs as C

    return {c.name: c for n in C.__all__ if isinstance(c := getattr(C, n), Cab)}


def _image_keys() -> dict[str, str]:
    """dosho's own manifest, as the loader's `images` mapping.

    Exactly what a real consumer passes: the document names `WSCLEAN`, and
    which reference that is stays the deployment's decision at load time
    (§4.5) rather than being fixed when the document was written.
    """
    from dosho import images

    return {k: getattr(images, k) for k in dir(images) if k.isupper()}


def _reload(name: str, body: dict) -> Cab:
    text = yaml.safe_dump({"cabs": {name: body}}, sort_keys=False)
    return loads(text, images=_image_keys())[name]


def test_every_cab_has_a_document(generated, built):
    assert set(generated) == set(built)


def test_committed_documents_are_current(tmp_path):
    """Regenerating must reproduce the committed files byte for byte.

    Without this the documents are a snapshot that drifts the first time a cab
    changes and nobody reruns the generator -- and every other test here would
    keep passing against the stale copy, since they read the same stale files.
    """
    write_documents(tmp_path)
    committed = {p.name: p.read_text() for p in DOCUMENT_DIR.glob("*.yml")}
    fresh = {p.name: p.read_text() for p in tmp_path.glob("*.yml")}
    assert set(committed) == set(fresh), "a cab was added or removed without regenerating"
    stale = sorted(n for n in committed if committed[n] != fresh[n])
    assert stale == [], (
        f"stale documents: {stale} -- regenerate with "
        "`uv run python -m tools.generate_documents` and commit"
    )


def test_the_generator_and_the_committed_files_agree_on_content(built):
    """Belt and braces on the above: compare through the generator's own
    renderer rather than only file text, so a change in how files are written
    (indent, width) is not mistaken for a change in what they say.
    """
    for name, body in documents().items():
        path = DOCUMENT_DIR / f"{name}.yml"
        assert path.exists(), f"{name} has no committed document"
        assert path.read_text() == render(body, name)


def test_documents_round_trip(generated, built):
    """The gate. Every cab, with no exceptions -- there is no allowlist here,
    deliberately: an exception that outlives its reason is how a migration
    quietly stops covering what it claims to.
    """
    failures = {}
    for name, body in generated.items():
        diffs = cab_differences(built[name], _reload(name, body))
        if diffs:
            failures[name] = diffs[:3]
    assert failures == {}


def test_pattern_cabs_round_trip_with_their_patterns(generated, built):
    """The three that needed the dialect extended, checked for the thing that
    was missing rather than only for overall equality -- so a regression that
    dropped patterns while leaving everything else intact still fails here.
    """
    for name in ("cubical", "quartical", "wsclean"):
        reloaded = _reload(name, generated[name])
        original = built[name]
        assert original.input_patterns or original.output_patterns, f"{name} has no patterns"
        assert reloaded.input_patterns == original.input_patterns
        assert reloaded.output_patterns == original.output_patterns


def test_every_declared_dtype_survives(generated):
    """The check the comparator structurally cannot do.

    Compares the document against *source*, not against the reloaded cab:
    `File` and `MS` are both `Path` on either side of a rebuilt object, so a
    migration that flattened one into the other would compare equal.
    """
    sources = read_sources()
    checked = mismatched = 0
    for name, body in generated.items():
        for section, specs in (
            ("inputs", sources[name].inputs),
            ("outputs", sources[name].outputs),
        ):
            for raw, (dtype, _, _) in specs.items():
                checked += 1
                if body.get(section, {}).get(raw, {}).get("dtype") != dtype:
                    mismatched += 1
    assert checked > 1500, f"only {checked} dtypes checked -- the scan is not finding fields"
    assert mismatched == 0


def test_file_like_dtypes_specifically(generated):
    """The 16%. Guarded on its own so a regression here cannot hide inside the
    bulk count above.
    """
    sources = read_sources()
    file_like = {"File", "MS", "Directory", "URI"}
    total = lost = 0
    for name, src in sources.items():
        for section, specs in (("inputs", src.inputs), ("outputs", src.outputs)):
            for raw, (dtype, _, _) in specs.items():
                if dtype not in file_like and not dtype.startswith(
                    ("List[File", "List[MS", "List[Directory")
                ):
                    continue
                total += 1
                if generated[name].get(section, {}).get(raw, {}).get("dtype") != dtype:
                    lost += 1
    assert total > 200, f"only {total} file-like dtypes found -- the scan is wrong"
    assert lost == 0
