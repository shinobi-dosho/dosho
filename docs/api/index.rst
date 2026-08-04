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

``dosho``'s own cabs are YAML documents (see
:doc:`../concepts/authoring`), so nothing in this repository calls this.
It remains supported, and tested, for a downstream project that would
rather define cabs in Python than maintain documents.

.. autofunction:: dosho._builder.define_cab

Tools
--------

Every ``Cab``/pystep dosho ports, by name -- see
:doc:`../concepts/authoring` for where each shape's definition lives and
how it is registered. A ``Cab``'s schema is in its document rather than a
docstring, and the pystep modules explain each tool's provenance and any
real-tool quirks preserved, so neither is documented one-by-one here;
import or inspect them directly, e.g.:

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
