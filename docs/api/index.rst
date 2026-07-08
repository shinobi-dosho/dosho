API reference
=============

This reference is generated from the source docstrings. See
:doc:`../concepts/authoring` for the design behind these modules.

Top-level package
-------------------

.. automodule:: dosho
   :members:

Registry (string-keyed lookup)
----------------------------------

.. automodule:: dosho.registry
   :members:

Cab-authoring helper
------------------------

.. autofunction:: dosho._builder.define_cab

Tools
--------

Every ``Cab``/pystep dosho ports, re-exported at package level -- see
:doc:`../concepts/authoring` for the single-command vs. multi-command
module convention. Individual tool modules aren't documented
one-by-one here (their own docstrings explain each tool's provenance and
any real-tool quirks preserved); import or inspect them directly, e.g.:

.. code-block:: python

    from dosho.cabs import wsclean
    from dosho.cabs.casatasks import listobs

.. code-block:: console

    $ ninja cabs show wsclean

.. automodule:: dosho.cabs
   :members:
   :imported-members:

Shinobi schema types
------------------------

Supporting types used when defining a ``Cab``, re-exported from
``shinobi`` for convenience -- documented in full in `shinobi's own API
reference
<https://stimela-ninja.readthedocs.io/en/latest/api/index.html>`_.

.. autoclass:: shinobi.steps.schema.ParamMeta
   :members:
   :no-index:

.. autoclass:: shinobi.steps.schema.ParamPattern
   :members:
   :no-index:

.. autoclass:: shinobi.steps.schema.ParamSegment
   :members:
   :no-index:

.. autoclass:: shinobi.steps.schema.Policies
   :members:
   :no-index:
