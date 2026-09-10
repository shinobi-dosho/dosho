Installation
============

Requirements
------------

* Python 3.11 or newer.
* `shinobi <https://stimela-ninja.readthedocs.io/en/latest/installation.html>`_
  (the ``stimela-ninja`` distribution, published on PyPI) -- **only** to
  build and run a cab. It is the ``run`` extra, not a hard dependency;
  see below.

From PyPI
---------

.. code-block:: console

    $ pip install dosho          # the cab definitions: names, schemas, images
    $ pip install "dosho[run]"   # ...plus stimela-ninja, to build and run them

``dosho``'s definitions are data -- YAML documents shipped inside the
package -- so a consumer that only wants to read, diff, pin or serve them
needs nothing but a YAML parser, and ``import dosho`` loads no shinobi
modules at all. Turning a definition into a runnable
:class:`~shinobi.Cab` is what needs the framework, so ``dosho.cabs.<tool>``
and :func:`dosho.get` require the ``run`` extra and say so if it is
missing.

Either way the install registers ``dosho`` under shinobi's ``shinobi.cabs``
entry-point group, so ``ninja cabs list``/``ninja cabs show`` (from
``stimela-ninja``'s ``ninja`` CLI) pick it up automatically, with no
further configuration.

To track unreleased cabs, install from the repository instead:

.. code-block:: console

    $ pip install "dosho[run] @ git+https://github.com/shinobi-dosho/dosho.git"

For development
----------------

The project uses `uv <https://docs.astral.sh/uv/>`_. The test suite builds
real cabs, so it needs the ``run`` extra:

.. code-block:: console

    $ git clone https://github.com/shinobi-dosho/dosho.git
    $ cd dosho
    $ uv sync --extra run --group dev
    $ uv run pytest
    $ uv run ruff check .

    # enable the pre-commit hook, once per clone (see Contributing)
    $ git config core.hooksPath .githooks

A development checkout deliberately resolves ``stimela-ninja`` from its
``main`` branch rather than the last PyPI release --
``[tool.uv.sources]`` in ``pyproject.toml`` says so -- which is what lets
a cab use a schema feature the day it lands. ``uv.lock`` pins the commit,
so it does not follow ``main`` on its own; refresh it with ``uv lock
--upgrade-package stimela-ninja``. The redirect is a ``uv``
project-source, invisible to anyone installing ``dosho`` from PyPI.

To build the documentation locally (the build imports ``dosho`` *and*
shinobi, so it needs the ``run`` extra too):

.. code-block:: console

    $ uv sync --extra run --group docs
    $ uv run sphinx-build -b html docs docs/_build/html
    $ open docs/_build/html/index.html

See :doc:`contributing` for the pre-commit hook, the cab-catalog
freshness gate, and what CI checks.
