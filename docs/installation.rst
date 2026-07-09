Installation
============

Requirements
------------

* Python 3.10 or newer
* `shinobi <https://stimela-ninja.readthedocs.io/en/latest/installation.html>`_
  (the ``stimela-ninja`` distribution, published on PyPI) -- installed
  automatically as a dependency.

From GitHub
-----------

``dosho`` itself isn't published to PyPI yet, so install it from GitHub
(its ``stimela-ninja`` dependency resolves normally from PyPI):

.. code-block:: console

    $ pip install git+https://github.com/SpheMakh/dosho.git

This installs the importable ``dosho`` package, and registers it under
shinobi's ``shinobi.cabs`` entry-point group -- so ``ninja cabs
list``/``ninja cabs show`` (from ``stimela-ninja``'s ``ninja`` CLI) pick
it up automatically, with no further configuration.

For development
----------------

The project uses `uv <https://docs.astral.sh/uv/>`_. ``stimela-ninja``
is published on PyPI, so a plain ``uv sync`` resolves it like any other
dependency:

.. code-block:: console

    $ git clone https://github.com/SpheMakh/dosho.git
    $ cd dosho
    $ uv sync --group dev
    $ uv run pytest
    $ uv run ruff check .

If you're working against an unreleased ``stimela-ninja`` change, clone
it next to this repo and layer it in for the duration of a command with
``uv run --with-editable ../stimela-ninja -- <command>`` instead.

To build the documentation locally:

.. code-block:: console

    $ uv sync --group docs
    $ uv run sphinx-build -b html docs docs/_build/html
    $ open docs/_build/html/index.html
