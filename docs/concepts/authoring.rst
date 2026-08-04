Authoring tools in dosho
=========================

Why not cult-cargo's YAML?
--------------------------------------------------

cult-cargo and scabha did the real work of cataloguing this ecosystem's
tools first, and ``dosho`` leans on that prior art throughout -- this is
a new repository, not a rejection of the old one. ``dosho`` exists
because cult-cargo's cab YAML format -- built for Stimela 2.0/scabha --
carries assumptions shinobi deliberately doesn't carry forward:
``dynamic_schema`` (a Python function imported and *executed* at
cab-load time to compute a real tool's schema), package-scoped
``_include`` composition, and dtype coverage gaps that silently degrade
to ``str``.

Note what that objection is and isn't. It is to *executable and
self-composing content* in a cab, not to static markup: a cab definition
is parameter configuration -- names, dtypes, defaults, metadata,
policies -- which is what YAML and JSON were made for. ``dosho``'s cabs
are YAML documents, in the same scabha dialect minus the parts that are a
programming language wearing YAML. See ``AGENTS.md``'s Core rule for the
constraints that bind a cab definition in any format.

Because a document is inert data, ``import dosho`` needs no shinobi at
all: a consumer that only wants the definitions -- to read, diff, pin or
serve them -- installs ``dosho``, and only *building* a cab from one
needs the framework that runs it (the ``dosho[run]`` extra).

Two shapes: ``Cab`` and pystep
--------------------------------

Not every tool can be a :class:`~shinobi.Cab`. shinobi only ever executes
``flavour="binary"`` cabs -- real standalone executables, argv-built and
shelled out to. A tool that's actually a Python-package function call
with no standalone binary at all (CASA tasks are the running example:
``casatasks.listobs``, ``casaplotms.plotms``) is instead a
:func:`@shinobi.pystep <shinobi.pystep>`-decorated function, producing a
``StepRef`` rather than a ``Cab``.

That's architecturally distinct from, and doesn't violate, "never import
a cab package": a pystep's ``ctx.import_func("<task>", "<package>")``
imports *inside the running container, at step-execution time*, calling
a real Python function the pystep author wrote directly into trusted
source -- not shinobi interpreting untrusted cab data on the host at
load time.

So the two shapes are stored differently, and this is the one thing to
know before adding a tool:

============  ==================================  ===================
Shape         Lives in                            Today
============  ==================================  ===================
``Cab``       ``dosho/documents/<name>.yaml``     44 tools
pystep        ``dosho/cabs/<family>.py``          68 tools
============  ==================================  ===================

Both are first-class for :meth:`Recipe.add_step
<shinobi.Recipe.add_step>`, and a caller doesn't need to know or care
which one a given tool is.

Defining a ``Cab``
--------------------

A cab is a document under ``dosho/documents/``, named after the tool.
The vocabulary is scabha's -- ``inputs``/``outputs`` with
``dtype``/``required``/``default``/``info``/``choices``, ``policies``,
``command``, ``image`` -- so a cult-cargo file is a readable subset:

.. code-block:: yaml

    # dosho/documents/mytool.yaml
    cabs:
      mytool:
        command: mytool
        image: MYTOOL          # a manifest *key*, not a reference
        info: 'mytool: what it does (https://example.org/mytool)'
        inputs:
          data-ms:
            dtype: MS
            required: true
          out-name:
            dtype: str
            default: out
          prefix:
            dtype: str
            required: true
            nom_de_guerre: name    # the flag the tool really takes
            write_path: true
        outputs:
          image:
            dtype: File
            implicit: '{prefix}-image.fits'

Hyphenated or dotted parameter names are sanitised to valid pydantic
field names, so ``data-ms`` is set as ``data_ms=`` in Python while argv
still carries ``--data-ms``. Where the tool's real flag differs from the
parameter name outright, ``nom_de_guerre`` says so.

``image:`` names a key in ``dosho/images.yaml`` rather than a reference,
which is what lets a deployment repoint it (see `Container images`_
below) without editing the document.

Two keys are shinobi's rather than scabha's, and both matter for
correctness rather than convenience: ``write_path: true`` marks a path
the tool *creates* (so a stale one from a previous run is cleared before
it trips the tool up), and ``mutable: true`` marks an input the step
rewrites in place.

.. note::

   ``dosho`` authored its own cabs in Python until the documents replaced
   them. :func:`dosho.define_cab` is still supported and still tested --
   it builds a ``Cab`` from a flat ``{raw_name: (dtype, required,
   default)}`` dict -- so a downstream project can define cabs in Python
   without maintaining documents. It is simply not how this repository
   describes its own.

Choices and CLI abbreviations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A parameter can also carry ``choices`` and ``abbreviation``:

* ``choices`` narrows the built model's field to
  ``typing.Literal[*choices]``, so an out-of-set value fails real pydantic
  validation rather than only being documented in ``info`` text. Every
  field default must be a member of the set (or ``None``).
* ``abbreviation`` attaches a hint so ``ninja run`` can offer a
  single-dash short alias (``--long-flag/-xy``) alongside the generated
  long flag. It never changes the argv the tool itself receives -- that
  still uses ``nom_de_guerre``.

.. code-block:: yaml

    mode:
      dtype: str
      default: clean
      choices: [dirty, clean, predict]
    ascii-sky:
      dtype: File
      abbreviation: as

Dynamic per-instance parameter families
------------------------------------------

Some real tools have parameter names that depend on a caller-chosen
value, not a fixed field set -- CubiCal's ``g1-solvable``/``g-time-int``,
QuartiCal's ``K.time_interval``, one family per solvable-term name chosen
per pipeline call. shinobi's :class:`~shinobi.steps.schema.ParamPattern`
expresses this declaratively, as an ``input_patterns`` entry: a
hand-authored table of the real, known attrs (transcribed once from the
tool's own docs/template), plus a regex-matched wildcard segment for the
caller-chosen term name -- static data, never generated by
importing/executing the tool's own schema function.

.. code-block:: yaml

    input_patterns:
    - separator: '-'
      segments:
      - regex: .+?              # the caller-chosen term name
      - attrs:                  # the enumerable half, transcribed once
          solvable: {}
          time-int: {}
          dd-term:
            dtype: bool

See ``dosho/documents/cubical.yaml`` and ``quartical.yaml`` for the real
tables.

Dynamic output paths
----------------------

Some tools' output *paths* depend on other resolved input values --
WSClean's ``{prefix}-MFS-image.fits``-shaped outputs, for example. An
``implicit`` string template, resolved via plain ``str.format`` against a
step's own validated inputs (never ``eval``, never an expression
language), covers exactly this. Only the handful of outputs a real
pipeline actually wires as a dependency need a resolved ``implicit``
template; anything more exotic (WSClean's open-ended
per-band/per-interval combinatorics) stays validation-only via
``output_patterns``, with a ``harvest`` glob to rescue the files
themselves out of a sandboxed run. See ``dosho/documents/wsclean.yaml``.

Container images
-------------------

``dosho/images.yaml`` is the single source of truth linking each cab to
its container image: top-level ``metadata`` (registry, bundle version)
plus an ``images:`` map keyed by the name a document's ``image:`` field
uses. Each entry is either a ``ref:`` (an existing published image, used
verbatim) or a ``build:`` recipe, resolved to
``{registry}/{name}:{version}-{bundle_version}``. ``dosho/images.py``
loads the manifest and exposes each key as a module constant; bumping a
tool is editing one manifest entry.

``dosho`` builds these images itself -- see the ``dosho images``
CLI (``list``/``build``/``push``/``build-plan``/``verify``), the
``dosho/cargo/`` Dockerfile tree, and the ``images.yml`` workflow that
rebuilds and pushes exactly the images a push touched.

A deployment can repoint any image without editing ``dosho``, via
(lowest to highest precedence) the manifest, a YAML file named by
``$DOSHO_IMAGES``, and per-tool ``$DOSHO_IMAGE_<KEY>`` environment
variables. Overrides are applied at import time, so set them *before* the
process starts.

Registering a tool
--------------------------------------------------

``dosho/cab_index.yaml`` decides what exists. Every tool has an entry
giving its registered name, where its definition lives, and the attribute
``dosho.cabs`` exports it as:

.. code-block:: yaml

    wsclean:                        # a Cab: name, attr and file all agree
      attr: wsclean
      document: wsclean.yaml
    msutils-addcol:                 # ...but they need not
      attr: addcol
      document: msutils-addcol.yaml
    fitstoolz-header:               # a pystep: the module and the symbol in it
      attr: fitstoolz_header
      module: dosho.cabs.fitstoolz
      symbol: header

The index is maintained by hand, not generated: it was generated by
introspecting the Python definitions that the documents replaced,
deriving it from the documents would be circular, and ``attr`` is not
derivable from anything -- ``msutils-addcol`` is imported as ``addcol``,
and 31 tools differ this way.

A pystep's definition sits in a module named for the *tool family*, one
decorated function per sub-command. The decorator takes the ``image``, and
declares which of the function's own path parameters it writes to:

.. code-block:: python

    # dosho/cabs/casatasks.py
    @shinobi.pystep(image=images.CASA6, write_paths=["listfile"])
    def listobs(ctx, vis: Path, listfile: Path, ...) -> ListobsOutputs: ...

    @shinobi.pystep(image=images.CASA6, write_paths=["outputvis"])
    def mstransform(ctx, vis: Path, outputvis: Path, ...) -> MstransformOutputs: ...

A pystep whose registered name isn't a valid Python identifier passes it
explicitly -- ``@shinobi.pystep(name="fitstoolz-header", ...)`` on a
function called ``header``.

Two lookup interfaces, one set of objects
---------------------------------------------

``from dosho.cabs import wsclean`` is the direct interface, for a caller
that knows the tool's name at write-time. Nothing is imported eagerly: a
name resolves on first access, through the same ``dosho.registry.get``
everything else takes, and repeated access returns the same object.

``dosho.get(name)`` is the parallel, string-keyed lookup used by ``ninja
cabs list``/``show`` and shinobi's ``shinobi.cabs`` entry-point
discovery -- for a caller that only knows the tool's name at *runtime*.
It is keyed by registered name (``msutils-addcol``) rather than by the
attribute (``addcol``), and resolves to the exact same objects. Picking
one over the other is purely about whether the caller knows the name at
write-time or run-time.
