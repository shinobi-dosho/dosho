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

``wsclean`` is a :class:`~dosho.validation.CabSpec` containing its composed
document; ``listobs`` is an ordinary annotated Python function marked with
``@dosho.pystep``. Looking up either needs ``dosho[validation]`` and no
Shinobi installation. Both are accepted by :meth:`Recipe.add_step
<shinobi.Recipe.add_step>`, which adapts them for execution.

For an explicit runtime object, use ``shinobi.cabs.get(name)`` or
``shinobi.cabs.adapt_definition(definition)``. That is the interface for
callers needing runtime attributes such as ``inputs_model`` or ``step``.

Read a definition without shinobi
----------------------------------

A binary cab's definition is a YAML document shipped in the package, and
reading it is not the same as building it. :func:`dosho.registry.get_document`
hands back the raw text, with no framework involved -- useful to diff, pin
or serve the catalogue from an environment that never runs a pipeline:

.. code-block:: python

    from dosho.registry import get_document, list_cabs

    dialect, text = get_document("wsclean")
    assert dialect == "dosho-cab-v1"

It raises ``KeyError`` for a pystep, whose definition is a Python function
and cannot be a document.

Use it in a recipe
-------------------

.. code-block:: python

    from pathlib import Path

    from pydantic import BaseModel
    from shinobi import MSv2, Recipe

    from dosho.cabs import wsclean_readonly


    class Inputs(BaseModel):
        ms: MSv2


    class Outputs(BaseModel):
        pass


    recipe = Recipe(name="image", inputs_model=Inputs, outputs_model=Outputs)
    recipe.add_step(
        "image",
        wsclean_readonly,
        ms=[recipe.inputs.ms],
        temp_dir=Path("wsclean-tmp"),
        prefix="deep",
        size=(4096, 4096),
        scale="1.3asec",
        niter=100000,
    )

.. code-block:: console

    $ ninja run myrecipe.py:recipe --ms data.ms --dryrun

Save the Python snippet as ``myrecipe.py``. This reader leaves the input MS
read-only and places reordered temporary data outside it. The ordinary
``wsclean`` cab retains conservative write access. Strict MS execution also
needs the framework's ``ms`` and ``fits`` extras and a
qualified backend route (see :doc:`installation`); Apptainer
is Shinobi's default backend. ``--dryrun`` inspects the declared plan without
dispatching the tool. See :doc:`concepts/read_only_access` for the guarded
controls and :doc:`concepts/msv2_contracts` for a complete strict pipeline.

A path-only CASA wrapper cannot share the same strict MS in this recipe;
all accesses to a strict dataset must use compatible declared contracts.

Inspect a tool from the command line
--------------------------------------

Inspect every registered tool with Dosho. Install ``dosho[validation]``
for schema inspection; listing names needs only the base package:

.. code-block:: console

    $ dosho list
    $ dosho show wsclean

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
