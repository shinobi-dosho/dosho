dosho
=====

*A shinobi's tool bag.*

**dosho** is the native cab repository for `shinobi
<https://stimela-ninja.readthedocs.io/>`_ (stimela-ninja, Stimela 3.0).
Every tool is authored directly in Python instead of a YAML dialect --
a :class:`~shinobi.Cab` for a real binary, or a :func:`@shinobi.pystep
<shinobi.pystep>`-produced ``StepRef`` for a Python-package tool with no
standalone binary (CASA tasks are the running example). There is no
``dynamic_schema``-style Python-execution step at cab-load time, and no
dtype coverage gaps -- see :doc:`concepts/authoring` for why this exists
and how it's structured.

.. code-block:: python

    from dosho.cabs import wsclean
    from dosho.cabs.casatasks import listobs

.. code-block:: python

    import dosho

    wsclean = dosho.get("wsclean")

.. code-block:: console

    $ ninja cabs list
    $ ninja cabs show wsclean

.. toctree::
   :maxdepth: 2
   :caption: Getting started

   installation
   quickstart

.. toctree::
   :maxdepth: 2
   :caption: Concepts

   concepts/authoring

.. toctree::
   :maxdepth: 2
   :caption: Reference

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
