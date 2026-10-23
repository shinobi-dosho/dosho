Installation and the v0.2 boundary
==================================

The base catalogue requires Python 3.11+ and a YAML parser; it can list and
read cab documents without Pydantic or Shinobi::

    pip install dosho

Static schema validation and argv formatting are optional::

    pip install "dosho[validation]>=0.2.0b1,<0.3"

To construct runnable ``Cab``/``StepRef`` objects, install Shinobi::

    pip install "stimela-ninja>=0.2.0b1,<0.3"

Shinobi now requires Dosho validation. The reverse ``dosho[run]`` extra has
been retired. ``dosho.get``, ``dosho.cabs.<name>`` and ``dosho.define_cab``
import the execution adapter lazily; catalogue and validation APIs do not.

Development pairing
-------------------

Dosho's lock resolves independently of Shinobi. Integration tests require an
explicit candidate checkout or wheel of Shinobi; it is deliberately absent
from Dosho's dependency graph::

    uv sync --locked --extra validation --group dev --group docs
    uv build --wheel
    uv build --wheel --directory /path/to/candidate/stimela-ninja
    uv pip install --no-deps dist/dosho-0.2.0b1-py3-none-any.whl /path/to/candidate/stimela-ninja/dist/stimela_ninja-0.2.0b1-py3-none-any.whl

Install the framework's runtime dependencies as well (or install the wheel
pair together without ``--no-deps`` into an isolated environment). Run tests
and docs with ``uv run --no-sync`` so a subsequent sync cannot remove the
explicit candidate. CI takes an explicit ``ninja-ref`` for the paired checkout
and verifies each installed version against its own source checkout plus
package origin. Independent core CI requires no companion framework; paired
full tests/docs run only when a compatible ``ninja-ref`` is supplied.

See :doc:`concepts/validation` for the ownership and migration contract.
