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

``dosho.get``/``dosho.list_cabs`` above are re-exports from here. The rest
of this module is the ``shinobi.cabs`` provider protocol: ``get_document``
(preferred -- hands shinobi the raw document, so nothing here parses it)
and ``loader_options`` (the resolved image map the document names by key).

.. automodule:: dosho.registry
   :members:

Container images
--------------------

The resolved image reference for every cab, and the per-deployment
overrides that repoint one without editing ``dosho`` -- see
:doc:`../concepts/authoring` for the manifest's own schema and the
``dosho images`` build CLI.

.. automodule:: dosho.images
   :members:

Cab-authoring helper
------------------------

``dosho``'s own cabs are YAML documents (see
:doc:`../concepts/authoring`), so no cab in this repository uses this.
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
read them in the generated :doc:`cab catalog <../reference/cabs>`, or
import and inspect them directly, e.g.:

.. code-block:: python

    from dosho.cabs import wsclean
    from dosho.cabs.casatasks import listobs

.. code-block:: console

    $ ninja cabs show wsclean

.. automodule:: dosho.cabs
   :no-members:

Standalone validation
---------------------

These APIs require ``dosho[validation]`` and never import Shinobi. A
``CabSpec`` is inert document data; ``CompiledCab`` contains validated
parameter models and formatting metadata, rather than an executable step.
See :doc:`../concepts/validation` for the boundary and a complete example.

.. autofunction:: dosho.validation.build_document

.. autofunction:: dosho.validation.describe_cab

.. autofunction:: dosho.validation.parse_document

.. autofunction:: dosho.validation.compile_cab

.. autofunction:: dosho.validation.build_model

.. autofunction:: dosho.validation.dtype_to_type

.. autofunction:: dosho.validation.build_argv

.. autoclass:: dosho.validation.CabSpec
   :members:

.. autoclass:: dosho.validation.CompiledCab
   :members:

.. autoclass:: dosho.validation.compiled.CompiledParamMeta
   :members:

.. autoclass:: dosho.validation.description.CabDescription
   :members:

.. autoclass:: dosho.validation.description.ParameterDescription
   :members:

.. autoclass:: dosho.validation.TypeBinding
   :members:

Parameter metadata and policies
-------------------------------

Dosho owns these shared schema types. Shinobi re-exports ``Policies`` and
extends ``ParamMeta``, ``ParamPattern`` and ``ParamSegment`` with framework
declarations. Framework-specific annotations such as ``MSv2``,
``FITSImage`` and ``ProductFamily`` remain Shinobi-owned; callers compiling
those dtypes must supply trusted type bindings or use Shinobi's adapter.

.. autoclass:: dosho.validation.ParamMeta
   :members:

.. autoclass:: dosho.validation.ParamPattern
   :members:

.. autoclass:: dosho.validation.ParamSegment
   :members:

.. autoclass:: dosho.validation.Policies
   :members:
