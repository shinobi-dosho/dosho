dosho
=====

*A shinobi's tool bag.*

**dosho** is the native cab repository for `shinobi
<https://stimela-ninja.readthedocs.io/>`_ (stimela-ninja, Stimela 3.0).
A tool here is one of two shapes. A real binary is a YAML **document**,
built into a :class:`~shinobi.Cab` on demand; a Python-package tool with
no standalone binary (CASA tasks are the running example) is a
:func:`@shinobi.pystep <shinobi.pystep>`-decorated function, producing a
``StepRef``. Either way a cab is parameter configuration, so what matters
is that it stays declarative rather than which format carries it: there
is no ``dynamic_schema``-style Python-execution step at cab-load time, no
expression language, and no dtype coverage gaps -- see
:doc:`concepts/authoring` for why this exists and how it's structured.

Because a document is inert data, ``import dosho`` needs no shinobi at
all. Reading the catalogue is a plain install; *building* a cab from a
definition into a runnable object needs Shinobi, which installs Dosho validation:

.. code-block:: console

    $ pip install "dosho>=0.2.0b1,<0.3"             # catalogue data only
    $ pip install "dosho[validation]>=0.2.0b1,<0.3"  # standalone schemas and argv
    $ pip install "stimela-ninja @ git+https://github.com/shinobi-dosho/stimela-ninja.git@main"

The last command installs the compatible source adapter while Ninja's v0.2
beta awaits publication. Pin a source commit for reproducibility; see
:doc:`installation` for development wheel pairing and the future PyPI floor.

Since v0.2.0b1, Dosho owns parameter validation, metadata, policies, patterns
and argv formatting. Shinobi owns framework types, DAG construction and
execution, filesystem enforcement and dataset lifecycle. See
:doc:`concepts/validation` for the APIs and migration notes, and
:doc:`concepts/read_only_access` for guarded MS readers and exclusive
flag-history reservations.

Know the tool at write-time? Import it directly:

.. code-block:: python

    from dosho.cabs import wsclean
    from dosho.cabs.casatasks import listobs

Only know the name at runtime? Use the string-keyed registry:

.. code-block:: python

    import dosho

    wsclean = dosho.get("wsclean")

Or reach the same objects from shinobi's own CLI, which discovers dosho
through the ``shinobi.cabs`` entry point:

.. code-block:: console

    $ ninja cabs list
    $ ninja cabs show wsclean

Every registered tool, with its resolved container image and full
input/output schema, is in the :doc:`cab catalog <reference/cabs>` --
generated from the live registry at build time.

.. toctree::
   :maxdepth: 2
   :caption: Getting started

   installation
   quickstart

.. toctree::
   :maxdepth: 2
   :caption: Concepts

   concepts/authoring
   concepts/validation
   concepts/read_only_access
   concepts/msv2_contracts

.. toctree::
   :maxdepth: 2
   :caption: Reference

   reference/cabs
   reference/experimental
   api/index

.. toctree::
   :maxdepth: 2
   :caption: Project

   contributing


Indices
-------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
