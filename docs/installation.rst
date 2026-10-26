Installation
============

The base catalogue requires Python 3.11+ and a YAML parser; it can list and
read cab documents without Pydantic or Shinobi::

    pip install "dosho>=0.2.0b1"

Definition building, Python function schemas, validation and argv formatting
are optional and need no Shinobi installation::

    pip install "dosho[validation]>=0.2.0b1"

To construct runnable ``Cab``/``StepRef`` objects and execute recipes, install
Shinobi, which depends on Dosho validation::

    pip install "stimela-ninja>=0.2.0b1"

These docs assume Dosho and Shinobi 0.2.0b1 or newer. ``dosho.get``,
``dosho.cabs.<name>`` and ``dosho.define_cab`` return neutral definitions without
importing Shinobi. ``Recipe.add_step`` adapts them for execution;
``shinobi.cabs.get`` and ``shinobi.cabs.adapt_definition`` expose explicit runtime
adaptation.

Strict MSv2 execution and FITS image-family inspection use optional framework
inspectors. For those workflows, install Shinobi with both extras::

    pip install "stimela-ninja[ms,fits]>=0.2.0b1"

The annotations and catalogue remain available without those inspectors.

Development pairing
-------------------

Dosho's lock resolves independently of Shinobi. Integration tests require an
explicit candidate checkout or wheel of Shinobi; it is deliberately absent
from Dosho's dependency graph::

    uv sync --locked --extra validation --group dev
    bash .github/scripts/install-pair.sh /path/to/candidate/stimela-ninja
    uv run --no-sync pytest -q -o pythonpath=

The helper builds both wheels, installs them together with their runtime
dependencies, and verifies each version and installed package origin. Temporary
files stay under ``.work-cache/pair``. Run integration tests with
``uv run --no-sync`` so a subsequent sync cannot remove the explicit candidate.
Clearing pytest's configured ``pythonpath`` checks the installed wheels.
CI pairs every push to main and every pull request with
Shinobi main, verifying each installed version against its own source checkout
plus package origin. Reusable and manually dispatched CI accept a ``ninja-ref``
override for a specific branch, tag, or commit. Independent core CI requires no
companion framework; the publication workflow also requires the full paired
tests and docs to pass.

Documentation
-------------

The docs group supplies all documentation and schema dependencies. Catalogue
generation reads cab declarations and function annotations without importing
Shinobi::

    uv run --python 3.12 --locked --group docs sphinx-build -E -n -W --keep-going -b html docs docs/_build/html

To regenerate only the committed catalogue::

    uv run --locked --group docs python docs/_ext/cab_catalog.py

See :doc:`concepts/validation` for the ownership and runtime adaptation contract.
