"""`import dosho` must not require shinobi.

dosho is a catalogue of tool definitions; shinobi is the framework that runs
them. A consumer who only wants the definitions -- to read, diff, pin, vendor
into an image, or serve -- should not have to install the runner, and
`docs/design_data_registry.md` §4.1 turns on that being true.

It was not: `dosho/__init__.py` imported `_builder` for `define_cab`, and
`_builder` builds real `Cab` objects so it imports the schema. One line, 29
shinobi modules. These tests pin the layering so it cannot come back by
accident -- an import added to `__init__.py` for convenience is exactly how it
would.
"""

from __future__ import annotations

import subprocess
import sys

# Run in a subprocess: the test session has already imported shinobi for other
# tests, so measuring `sys.modules` in-process would prove nothing.
_PROBE = """
import sys
import {module}
print(len([m for m in sys.modules if m == "shinobi" or m.startswith("shinobi.")]))
"""


def _shinobi_modules_after_importing(module: str) -> int:
    out = subprocess.run(
        [sys.executable, "-c", _PROBE.format(module=module)],
        capture_output=True,
        text=True,
        check=True,
    )
    return int(out.stdout.strip())


def test_importing_dosho_loads_no_shinobi():
    assert _shinobi_modules_after_importing("dosho") == 0


def test_importing_the_registry_loads_no_shinobi():
    """Name lookup is the data-only consumer's entry point, so it must stay on
    the shinobi-free side. Its shinobi imports are `TYPE_CHECKING` only.
    """
    assert _shinobi_modules_after_importing("dosho.registry") == 0


def test_importing_the_image_manifest_loads_no_shinobi():
    assert _shinobi_modules_after_importing("dosho.images") == 0


def test_define_cab_still_resolves_and_is_what_pulls_shinobi_in():
    """The other half: deferring it must not break the authoring API, and it
    must actually be the thing that was costing the import.
    """
    import dosho

    assert callable(dosho.define_cab)
    assert "define_cab" in dir(dosho)

    probe = "import dosho, sys; dosho.define_cab; print(len([m for m in sys.modules if m.startswith('shinobi')]))"
    out = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, check=True)
    assert int(out.stdout.strip()) > 0


def test_getting_a_cab_still_works():
    """`get()` returns a real `Cab`, so it needs shinobi -- correctly. The
    layering is about what `import dosho` costs, not about pretending the
    objects can exist without the schema that defines them.
    """
    import dosho

    assert dosho.get("breizorro").name == "breizorro"


# --------------------------------------------------------------------------
# shinobi is the `dosho[run]` extra, not a dependency
# --------------------------------------------------------------------------

# Simulating absence rather than building a shinobi-free venv per test: the
# test environment necessarily has shinobi (the rest of the suite needs it),
# and a meta-path finder that refuses it reproduces the condition faithfully
# in-process. The real thing is checked once, by installing into a clean venv
# -- see this PR -- but that is too slow to run per case.
_BLOCK = """
import sys, importlib.abc, importlib.machinery


class _Blocked(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "shinobi" or fullname.startswith("shinobi."):
            raise ImportError(f"no module named {fullname!r} (blocked)")
        return None


sys.meta_path.insert(0, _Blocked())
for name in [m for m in sys.modules if m == "shinobi" or m.startswith("shinobi.")]:
    del sys.modules[name]
"""


def _without_shinobi(body: str) -> subprocess.CompletedProcess:
    # `check=False`: these assert on the child's own output, and a non-zero
    # exit is a finding to report rather than an exception to raise here.
    return subprocess.run(
        [sys.executable, "-c", _BLOCK + body], capture_output=True, text=True, check=False
    )


def test_the_data_path_works_without_shinobi():
    """Listing what exists, fetching a definition, and resolving an image
    reference are what a catalogue is for, and none of them need the runner.
    """
    out = _without_shinobi(
        "import dosho\n"
        "d = dosho.registry.get_document('wsclean')\n"
        "print(len(dosho.list_cabs()), d[0], len(dosho.registry.loader_options()['images']))\n"
    )
    assert out.returncode == 0, out.stderr
    count, dialect, images = out.stdout.split()
    assert int(count) > 100 and dialect == "yaml_cab" and int(images) > 20


def test_importing_dosho_cabs_works_without_shinobi():
    """Naming a tool is not building one. `import dosho.cabs` must not be the
    thing that fails, or the package is unusable without the extra.
    """
    out = _without_shinobi("import dosho.cabs; print(len(dosho.cabs.__all__))")
    assert out.returncode == 0, out.stderr
    assert int(out.stdout.strip()) > 100


def test_building_a_cab_without_shinobi_says_what_to_install():
    """The failure a user actually meets. A bare ModuleNotFoundError three
    frames deep in a loader does not tell them they wanted `dosho[run]`.
    """
    out = _without_shinobi(
        "import dosho.cabs\n"
        "try:\n"
        "    dosho.cabs.wsclean\n"
        "except ImportError as exc:\n"
        "    print(exc)\n"
    )
    assert out.returncode == 0, out.stderr
    assert "dosho[run]" in out.stdout
    assert "stimela-ninja" in out.stdout
