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
