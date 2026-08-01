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
from tools.generate_documents import documents

# Cabs whose `input_patterns`/`output_patterns` the dialect does not read yet
# -- nested ParamPattern structures rather than scalars, deferred with their
# own design (stimela-ninja #79). Named individually so a fourth one is a
# failure rather than a silent addition.
PATTERN_CABS = {"cubical", "quartical", "wsclean"}


@pytest.fixture(scope="module")
def generated() -> dict:
    return documents()


@pytest.fixture(scope="module")
def built() -> dict[str, Cab]:
    import dosho.cabs as C

    return {c.name: c for n in C.__all__ if isinstance(c := getattr(C, n), Cab)}


def _reload(name: str, body: dict) -> Cab:
    cab = loads(yaml.safe_dump({"cabs": {name: body}}, sort_keys=False))[name]
    # §4.5: the document carries the *manifest key* so a deployment's
    # $DOSHO_IMAGES override still applies at load time. Resolving it belongs
    # in the loader (as `package_roots` already is) and is not there yet, so
    # the test does it -- the one place this round-trip is not yet end to end.
    from dosho import images

    keys = {k: getattr(images, k) for k in dir(images) if k.isupper()}
    return cab.model_copy(update={"image": keys[cab.image]}) if cab.image in keys else cab


def test_every_cab_has_a_document(generated, built):
    assert set(generated) == set(built)


def test_documents_round_trip(generated, built):
    """The gate. Every cab the dialect fully covers must come back identical."""
    failures = {}
    for name, body in generated.items():
        if name in PATTERN_CABS:
            continue
        diffs = cab_differences(built[name], _reload(name, body))
        if diffs:
            failures[name] = diffs[:3]
    assert failures == {}


def test_pattern_cabs_are_the_only_exceptions(generated, built):
    """Pins the deferral: these three fail *only* on patterns. If one starts
    failing for another reason, or a fourth cab joins them, that is news.
    """
    for name in sorted(PATTERN_CABS):
        diffs = cab_differences(built[name], _reload(name, generated[name]))
        assert diffs, f"{name} now round-trips -- remove it from PATTERN_CABS"
        assert all(d.startswith(("input_patterns", "output_patterns")) for d in diffs), (
            f"{name} fails for something other than patterns: {diffs}"
        )


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
