Dosho
=====

*A shinobi's tool bag.*

**Dosho** provides ready-made tool definitions for radio astronomy pipelines,
including WSClean, CASA tasks, CubiCal, QuartiCal and AOFlagger.
Use them with `Stimela Ninja <https://stimela-ninja.readthedocs.io/>`_
to build a pipeline without describing each tool's command-line options
yourself.

Each tool definition is called a **cab**. It describes the inputs a tool
accepts, the outputs it produces, and the container image used to run it.
Dosho supplies these definitions; Stimela Ninja runs the tools.

Find a tool
-----------

Browse the :doc:`tool catalogue <reference/cabs>` for available tools and
their parameters. You can read it here without installing anything.
See :doc:`reference/experimental` for tools with known limitations.

Start using Dosho
-----------------

Install Stimela Ninja to get both the runner and Dosho:

.. code-block:: console

    $ pip install "stimela-ninja>=0.2.0b1"
    $ ninja cabs list
    $ ninja cabs show wsclean

The last command shows WSClean's inputs and outputs; it does not run WSClean.
See :doc:`installation` for environment setup and tool requirements, then
follow :doc:`quickstart` to use a cab in a recipe.

You can also use Dosho on its own: ``dosho list`` lists tool names,
``dosho show wsclean`` displays a schema, and
``dosho validate my-cabs.yaml`` checks static definitions.
Install ``dosho[validation]`` for the last two commands. The :doc:`installation` page covers those options.
For writing your own definitions, see :doc:`concepts/authoring`.

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
