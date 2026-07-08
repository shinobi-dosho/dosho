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
    $ pip install git+https://github.com/caracal-pipeline/dosho.git

This installs the importable ``dosho`` package, and registers it under
shinobi's ``shinobi.cabs`` entry-point group -- so ``ninja cabs
list``/``ninja cabs show`` (from ``stimela-ninja``'s ``ninja`` CLI) pick
it up automatically, with no further configuration.

For development
----------------

The project uses `uv <https://docs.astral.sh/uv/>`_. Clone ``dosho`` next
to a ``stimela-ninja`` checkout (``[tool.uv.sources]`` in
``pyproject.toml`` points at the local sibling path):

.. code-block:: console

    $ git clone https://github.com/SpheMakh/stimela-ninja.git
    $ git clone https://github.com/caracal-pipeline/dosho.git
    $ cd dosho
    $ uv sync --group dev
    $ uv run pytest
    $ uv run ruff check .

To build the documentation locally:

.. code-block:: console

    $ uv sync --group docs
    $ uv run sphinx-build -b html docs docs/_build/html
    $ open docs/_build/html/index.html
