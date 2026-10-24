Installation and the v0.2 boundary
==================================

The base catalogue requires Python 3.11+ and a YAML parser; it can list and
read cab documents without Pydantic or Shinobi::

    pip install "dosho>=0.2.0b1,<0.3"

Static schema validation and argv formatting are optional::

    pip install "dosho[validation]>=0.2.0b1,<0.3"

To construct runnable ``Cab``/``StepRef`` objects, install the compatible
Shinobi adapter. Until its v0.2 beta is published, use the current source::

    pip install "stimela-ninja @ git+https://github.com/shinobi-dosho/stimela-ninja.git@main"

Once available from PyPI, ``stimela-ninja>=0.2.0b1,<0.3`` selects the same
adapter generation. The older stable v0.1 release cannot build these documents.
Pin the source commit for a reproducible environment.

The explicit Dosho beta floor selects the v0.2 APIs even while an older stable
release remains available. Shinobi requires Dosho validation. The reverse
``dosho[run]`` extra has been retired. ``dosho.get``, ``dosho.cabs.<name>`` and ``dosho.define_cab``
import the execution adapter lazily; catalogue and validation APIs do not.

Strict MSv2 execution and FITS image-family inspection use optional framework
inspectors. For those workflows, install the source adapter with both extras::

    pip install "stimela-ninja[ms-contract,fits-contract] @ git+https://github.com/shinobi-dosho/stimela-ninja.git@main"

The annotations and catalogue remain available without those inspectors.

Development pairing
-------------------

Dosho's lock resolves independently of Shinobi. Integration tests require an
explicit candidate checkout or wheel of Shinobi; it is deliberately absent
from Dosho's dependency graph::

    uv sync --locked --extra validation --group dev --group docs
    bash .github/scripts/install-pair.sh /path/to/candidate/stimela-ninja
    uv run --no-sync pytest -q -o pythonpath=
    uv run --no-sync sphinx-build -b html docs docs/_build/html -W --keep-going

The helper builds both wheels, installs them together with their runtime
dependencies, and verifies each version and installed package origin. Temporary
files stay under ``.work-cache/pair``. Run tests and docs with
``uv run --no-sync`` so a subsequent sync cannot remove the explicit candidate.
Clearing pytest's configured ``pythonpath`` checks the installed wheels.
CI pairs every push to main and every pull request with
Shinobi main, verifying each installed version against its own source checkout
plus package origin. Reusable and manually dispatched CI accept a ``ninja-ref``
override for a specific branch, tag, or commit. Independent core CI requires no
companion framework; the publication workflow also requires the full paired
tests and docs to pass.

See :doc:`concepts/validation` for the ownership and migration contract.
