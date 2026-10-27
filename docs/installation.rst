Installation
============

You need **Python 3.11 or newer** to install Dosho. If you only want to see
which tools are available, browse the :doc:`tool catalogue <reference/cabs>`
without installing anything.

For running tools and pipelines
-------------------------------

Install **Stimela Ninja**, which includes Dosho and the ``ninja`` command.
You do not need to install Dosho separately.

In a Linux or macOS terminal, create and activate a Python environment:

.. code-block:: console

    $ python3 -m venv .venv
    $ source .venv/bin/activate
    $ pip install "stimela-ninja>=0.2.0b1"

If you already have an environment for your pipeline work, activate it and
run just the last command. These docs use Dosho 0.2.0b2 and Shinobi 0.2.0b1 or newer.
Activate the same environment whenever you open a new terminal.

Check that the tool definitions are available:

.. code-block:: console

    $ ninja cabs list
    $ ninja cabs show wsclean

These commands list tools and show their parameters. They do not run a tool
or need astronomy data.

The astronomy software runs separately, either in a container or from an
installation on your computer. Stimela Ninja uses Apptainer by default;
its ``apptainer`` command must be available to run containerized tools.
See `Stimela Ninja installation
<https://stimela-ninja.readthedocs.io/en/latest/installation.html>`_ for
other ways to run tools and the optional ``ms`` and ``fits`` extras needed
by recipes that check Measurement Sets or FITS files. The strict WSClean
example in :doc:`quickstart` needs both:

.. code-block:: console

    $ pip install "stimela-ninja[ms,fits]>=0.2.0b1"

Follow :doc:`quickstart` to use a tool definition in a recipe.

For using Dosho on its own
--------------------------

You can work with tool definitions without installing Stimela Ninja.
Choose one of the following in your activated Python environment.

To list tool names and read the raw definitions:

.. code-block:: console

    $ pip install "dosho>=0.2.0b2"
    $ dosho list

To also look up definitions in Python, check parameter values, and build
command-line arguments:

.. code-block:: console

    $ pip install "dosho[validation]>=0.2.0b2"
    $ dosho show wsclean
    $ dosho validate my-cabs.yaml

``show`` displays a named schema. ``validate`` checks every resolved static
binary definition in a YAML file, including native parameter defaults and
constraints. Framework types and access/family declarations are labelled
``requires stimela-ninja to validate``. Data and execution qualification remain
with Stimela Ninja. Add ``--strict`` to ``validate`` to fail when checks remain
deferred. These commands do not run the astronomy tools.
See :doc:`concepts/validation` for the standalone Python API.

For contributors
----------------

See :doc:`contributing` for source setup, testing Dosho with a Shinobi
checkout, documentation builds and catalogue regeneration.
