Quickstart
==========

Look up a tool
---------------

Know the tool at write-time? Import it directly. Every tool is exported
from ``dosho.cabs``, whatever shape it is; a pystep family is also
importable from its own module:

.. code-block:: python

    from dosho.cabs import wsclean, cubical
    from dosho.cabs import skysim, telsim, primary_beam, simms_classic
    from dosho.cabs.casatasks import listobs, gaincal

A tool whose registered name isn't a valid Python identifier is exported
under one that is -- ``msutils-addcol`` is ``from dosho.cabs import
addcol``, ``simms-skysim`` is ``skysim`` -- so the attribute and the
registered name are not always the same string.

Only know the name at runtime (e.g. it came from a config file)? Use the
string-keyed registry instead -- the same objects, looked up by their
registered names:

.. code-block:: python

    import dosho

    wsclean = dosho.get("wsclean")
    listobs = dosho.get("listobs")
    dosho.list_cabs()  # every registered name

``wsclean`` here is a real :class:`~shinobi.Cab` -- ``listobs`` is a
``StepRef`` (from :func:`@shinobi.pystep <shinobi.pystep>`, since CASA
tasks are Python-package calls with no standalone binary). Both are
first-class for :meth:`Recipe.add_step <shinobi.Recipe.add_step>`; a
pipeline author doesn't need to know or care which shape a given tool is.

Both of these build a cab, so both need the ``dosho[run]`` extra (see
:doc:`installation`).

Read a definition without shinobi
----------------------------------

A binary cab's definition is a YAML document shipped in the package, and
reading it is not the same as building it. :func:`dosho.registry.get_document`
hands back the raw text, with no framework involved -- useful to diff, pin
or serve the catalogue from an environment that never runs a pipeline:

.. code-block:: python

    from dosho.registry import get_document, list_cabs

    dialect, text = get_document("wsclean")   # ("yaml_cab", "cabs:\n  wsclean:\n    ...")

It raises ``KeyError`` for a pystep, whose definition is a Python function
and cannot be a document.

Use it in a recipe
-------------------

.. code-block:: python

    from pathlib import Path

    from pydantic import BaseModel
    from shinobi import Recipe

    from dosho.cabs import wsclean
    from dosho.cabs.casatasks import listobs


    class Inputs(BaseModel):
        ms: Path


    class Outputs(BaseModel):
        pass


    recipe = Recipe(name="image", inputs_model=Inputs, outputs_model=Outputs)
    recipe.add_step("listobs", listobs, vis=recipe.inputs.ms, listfile=Path("obs.txt"))
    recipe.add_step(
        "image",
        wsclean,
        ms=[recipe.inputs.ms],
        prefix="deep",
        size=(4096, 4096),
        scale="1.3asec",
        niter=100000,
    )

.. code-block:: console

    $ ninja run myrecipe.py:recipe --ms data.ms --dryrun

Inspect a tool from the command line
--------------------------------------

Every registered ``dosho`` tool is discoverable through shinobi's own
``ninja`` CLI, without importing anything:

.. code-block:: console

    $ ninja cabs list
    $ ninja cabs show wsclean

Or read the whole set, with resolved container images and full
input/output schemas, in the :doc:`cab catalog <reference/cabs>`.

Where to next
-------------

* :doc:`concepts/authoring` -- how tools are authored in ``dosho``, why
  some are documents and others are pysteps, and how images are pinned.
* :doc:`reference/experimental` -- the cabs whose upstream schema doesn't
  permit full support, and what that costs.
* `shinobi's own quickstart
  <https://stimela-ninja.readthedocs.io/en/latest/quickstart.html>`_ --
  ``Recipe``, ``Cab``, backends, and ``ninja run``/``--dryrun`` in depth.
