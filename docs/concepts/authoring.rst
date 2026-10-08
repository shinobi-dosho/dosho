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
``Cab``       ``dosho/documents/<name>.yaml``     61 tools
pystep        ``dosho/cabs/<family>.py``          68 tools
============  ==================================  ===================

129 tools in total. The live list, with each one's resolved image and
full schema, is the :doc:`cab catalog </reference/cabs>`.

Both are first-class for :meth:`Recipe.add_step
<shinobi.Recipe.add_step>`, and a caller doesn't need to know or care
which one a given tool is.

Defining a ``Cab``
--------------------

A cab is a document under ``dosho/documents/``, named after the tool.
The vocabulary is scabha's -- ``inputs``/``outputs`` with
``dtype``/``required``/``default``/``info``/``choices``, ``policies``,
``command``, ``image`` -- so a cult-cargo file is a readable subset,
plus a few shinobi-native keys (``write_path``, ``mutable``, ``harvest``,
``scratch``) covered below:

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

Four keys are shinobi's rather than scabha's, and each matters for
correctness rather than convenience. Per parameter: ``write_path: true``
marks a path the tool *creates* (so a stale one from a previous run is
cleared before it trips the tool up), and ``mutable: true`` marks an
input the step rewrites in place. Per cab: ``harvest`` is a list of globs
rescued out of a sandboxed run, for products no output field can name,
and ``scratch`` a list of paths the tool needs mounted but that are never
rescued into your workspace -- caches, logs, wisdom files. See
``dosho/documents/ddfacet.yaml`` for both.

.. note::

   ``dosho`` authored its own cabs in Python until the documents replaced
   them. :func:`dosho.define_cab` is still supported and still tested --
   it builds a ``Cab`` from a flat ``{raw_name: (dtype, required,
   default)}`` dict -- so a downstream project can define cabs in Python
   without maintaining documents. It is simply not how this repository
   describes its own.

Strict MeasurementSet contracts
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``dtype: MS`` is a plain path. ``dtype: MSv2`` with a cab-level
``dataset_accesses`` list makes the cab *strict*: shinobi plans, claims,
snapshots and checks the MS around the step, from what the cab says it
reads and writes. ``msutils-flags-restore`` is the shape of a writer:

.. code-block:: yaml

    inputs:
      ms:
        dtype: MSv2
        required: true
        mutable: true
    outputs:
      ms:
        dtype: MSv2
    dataset_accesses:
      - field: ms
        mode: write
        columns:
          write: [FLAG, FLAG_ROW]

A reader (``msutils-flags-backup``) declares ``mode: read`` and is neither
``mutable`` nor echoed as an output. A column chosen by a parameter is a
template over the cab's own input, as in tricolour's ``read:
["{data_column}"]``; ``columns`` left out means the whole dataset. A strict
MS cannot be handed to a path-only cab in the same recipe, so only some cabs
are strict -- ``tests/test_dataset_contracts.py`` lists them.

``msutils-flags-backup`` also sets ``cache: false``: the version it saves in
``<ms>.flagversions`` cannot be a declared output (a declared output is
cleared before each run, which would delete every saved version), so a cache
hit could not notice that directory had gone. See shinobi's
`datasets documentation
<https://stimela-ninja.readthedocs.io/en/latest/concepts/datasets.html>`_
for the modes, the planner and the execution routes that support them.

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

A scalar output whose path depends on inputs uses an ``implicit`` string
resolved by plain ``str.format`` against the step's validated inputs.
Dimensional products use ``ProductFamily[File]`` with a static ``family``
declaration. WSClean's ``image``, ``dirty``, ``residual`` and ``model`` families
have ``time``, ``frequency``, ``polarization`` and ``component`` coordinates.
Its shared ``psf`` family has only ``time`` and ``frequency``. The defaults
are one channel, one interval, and Stokes I, matching WSClean 3.6.

Every run returns a resolved collection of the products actually emitted
or explicitly reused.
Dirty imaging can leave ``model`` and ``residual`` empty; a singleton
frequency has no MFS member. The former scalar ``*_mfs`` fields are replaced
by selection from the corresponding family:

.. code-block:: python

   # result is the executed WSClean step's result.
   image = result.outputs.image.select(
       time=0, frequency="mfs", polarization="Q", component="real"
   )
   psf = result.outputs.psf.select(time=0, frequency="mfs")

Use ``frequency=0`` for a single-channel image. Selection requires exactly
one matching member and fails when the requested product is absent or
ambiguous. ``source_list`` is an optional family without dimensions;
``source_list.select()`` returns its one file when ``-save-source-list``
actually emitted it.

Rules reproduce WSClean's suppression of singleton filename suffixes and
its ``-XY``/``-XYi`` real/imaginary pairing (YX is combined with XY).
Prediction and dry runs reserve no family products. Continuation rules
explicitly preserve and accept the existing model images that ``-continue``
reads before updating them. Output paths stay
inside the run's working directory, including any prefix subdirectory.
The prefix ``harvest`` glob also preserves supplementary products such as
weights and beams, without classifying them as one of these families.
Changing a family declaration or deleting a recorded member invalidates
the cache; an unchanged leftover file is not a newly produced member.

The filename and availability rules are transcribed from the pinned
`WSClean 3.6 filename implementation
<https://gitlab.com/aroffringa/wsclean/-/blob/v3.6/io/imagefilename.h>`_ and
`imaging implementation
<https://gitlab.com/aroffringa/wsclean/-/blob/v3.6/main/wsclean.cpp>`_. The
cab remains inert YAML data; these sources are never executed to load it.

Other product families use the same mechanism. DDFacet declares FITS
representations, flux scales and discovered saved cycles; its time, frequency
and Stokes axes stay inside a FITS cube. SoFiA declares catalogue formats,
moment products and cubelets discovered by source ID and product kind.

QuartiCal's ``gain_directory`` and killMS's ``solutions`` are
``ProductFamily[DirectoryBundle]``. Each captures one whole owned store with
no filename dimensions. Its internal chunks, group metadata and companion
files are inventoried together; losing any recorded child invalidates the
cache. Select the bundle and use its path when a downstream tool expects a
directory:

.. code-block:: python

   gain_store = quartical_result.outputs.gain_directory.select().path
   solutions_root = killms_result.outputs.solutions.select().path
   cubelet = sofia_result.outputs.cubelets.select(
       source=4, product="cube", format="fits"
   )
   restored = ddf_result.outputs.restored.select(
       representation="mean", flux_scale="apparent"
   )

killMS requires an explicit ``solutions_sols_dir`` outside the input MS.
The shared preflight rejects equal, nested or aliased overlapping trees
before running the tool, preserving the MS's separate caching and provenance.
QuartiCal's bundle declaration supports local stores; S3 stores and group
addresses are rejected rather than reported as local directories. See
:doc:`../audits/output_family_migration` for version and mode qualification.

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

``dosho`` builds these images itself -- see the ``dosho images`` CLI
(``list``/``build``/``push``/``build-keys``/``build-plan``/``verify``),
the ``dosho/cargo/`` Dockerfile tree, and the ``images.yml`` workflow
that rebuilds and pushes exactly the images a push touched.

Dev images
~~~~~~~~~~~~

Some tools are developed against their ``main`` branch rather than
waited on for a release. Those entries carry an optional ``dev:`` block
-- the same ``build:`` variables, overlaid, typically just a
``package: git+<repo>@main`` -- and ``dosho images build --dev <KEY>``
builds it. A dev image publishes to the *mutable* tag
``{registry}/{name}:dev``, deliberately outside the immutable
``{version}-{bundle_version}`` scheme and outside the release build
plan, so a dev push can never overwrite a release tag.
``metadata.dev_deps`` is appended to every dev build. Because the tag
moves, a consumer should pin the resulting *digest*, not the tag.
``dosho images build-keys --dev`` lists the keys that declare one.

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
and 48 tools differ this way.

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

Underneath both, shinobi's provider protocol prefers the document form:
it tries :func:`dosho.registry.get_document` first, which returns
``(dialect, text)`` and lets *shinobi* build the ``Cab``, so nothing on
dosho's side parses the document or imports the schema.
:func:`dosho.registry.loader_options` supplies the one thing that
document cannot carry on its own -- the resolved ``{KEY: ref}`` image
map, so a deployment's ``$DOSHO_IMAGES``/``$DOSHO_IMAGE_<KEY>``
overrides still decide the reference at load time. A pystep has no
document, so ``get_document`` raises ``KeyError`` for one and the
protocol falls through to ``get``.
