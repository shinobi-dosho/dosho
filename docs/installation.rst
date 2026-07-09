Installation
============

Requirements
------------

* Python 3.10 or newer
* `shinobi <https://stimela-ninja.readthedocs.io/en/latest/installation.html>`_
  (the ``stimela-ninja`` distribution) -- installed automatically as a
  dependency, but not yet published to PyPI itself; see below.

From GitHub
-----------

Neither ``dosho`` nor its ``stimela-ninja`` dependency is on PyPI yet, so
install both from GitHub:

.. code-block:: console

    $ pip install git+https://github.com/SpheMakh/stimela-ninja.git
    $ pip install git+https://github.com/SpheMakh/dosho.git

This installs the importable ``dosho`` package, and registers it under
shinobi's ``shinobi.cabs`` entry-point group -- so ``ninja cabs
list``/``ninja cabs show`` (from ``stimela-ninja``'s ``ninja`` CLI) pick
it up automatically, with no further configuration.

For development
----------------

The project uses `uv <https://docs.astral.sh/uv/>`_. ``dosho`` declares
a plain ``stimela-ninja`` dependency with no pinned source, so it
resolves correctly when synced as part of a larger uv workspace (e.g.
alongside ``stimela-ninja`` itself). Standalone, that means a bare
``uv sync`` may pull ``stimela-ninja``'s latest PyPI release, which can
lag its git ``main`` -- ``dosho`` tracks ``main``. Clone
``stimela-ninja`` next to this repo and layer it in as an editable
override for the duration of each command with ``uv run
--with-editable``:

.. code-block:: console

    $ git clone https://github.com/SpheMakh/stimela-ninja.git
    $ git clone https://github.com/SpheMakh/dosho.git
    $ cd dosho
    $ uv sync --group dev
    $ uv run --with-editable ../stimela-ninja -- pytest
    $ uv run --with-editable ../stimela-ninja -- ruff check .

To build the documentation locally:

.. code-block:: console

    $ uv sync --group docs
    $ uv run --with-editable ../stimela-ninja -- sphinx-build -b html docs docs/_build/html
    $ open docs/_build/html/index.html
