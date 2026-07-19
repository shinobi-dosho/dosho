Quickstart
==========

Look up a tool
---------------

Know the tool at write-time? Import it directly. Single-command tools
export one object named after the tool itself; multi-command tools (CASA
tasks, simms) export one object per sub-command from a shared module:

.. code-block:: python

    from dosho.cabs import wsclean, cubical
    from dosho.cabs.casatasks import listobs, gaincal
    from dosho.cabs.simms import skysim, telsim, primary_beam, simms_classic

Only know the name at runtime (e.g. it came from a config file)? Use the
string-keyed registry instead -- the same objects, looked up by name:

.. code-block:: python

    import dosho

    wsclean = dosho.get("wsclean")
    dosho.list_cabs()  # every registered name

``wsclean`` here is a real :class:`~shinobi.Cab` -- ``listobs`` is a
``StepRef`` (from :func:`@shinobi.pystep <shinobi.pystep>`, since CASA
tasks are Python-package calls with no standalone binary). Both are
first-class for :meth:`Recipe.add_step <shinobi.Recipe.add_step>`; a
pipeline author doesn't need to know or care which shape a given tool is.

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

Where to next
-------------

* :doc:`concepts/authoring` -- how tools are authored in ``dosho``, and
  why some are ``Cab``\\ s and others are pysteps.
* `shinobi's own quickstart
  <https://stimela-ninja.readthedocs.io/en/latest/quickstart.html>`_ --
  ``Recipe``, ``Cab``, backends, and ``ninja run``/``--dryrun`` in depth.
