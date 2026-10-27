Schema validation and argv formatting
=====================================

Dosho owns cab parameter schemas, validation, scalar metadata, patterns,
policies and validated-parameter-to-argv formatting. Shinobi owns framework
annotations and declarations, DAG/wiring, execution, filesystems and dataset
lifecycle/recovery. Its mandatory dependency is ``dosho[validation]``; Dosho
validation never imports Shinobi.

The validation extra requires Pydantic 2.14 or newer, matching Shinobi's
minimum for threaded generic product-family handoffs. Dosho's paired CI tests
Python 3.11 and 3.12. Base catalogue access needs neither Pydantic nor Shinobi.

The public ``dosho.validation`` API exposes ``CabSpec``, ``CompiledCab``,
``build_document``, ``describe_cab``, ``parse_document``, ``compile_cab``,
``build_argv``, ``build_model``,
``dtype_to_type``, ``TypeBinding``, ``ParamMeta``, ``Policies``, ``ParamPattern``
and ``ParamSegment``. It can be used independently:

.. code-block:: python

    from dosho.validation import parse_document, compile_cab, build_argv

    spec = parse_document("tool", {
        "command": "tool",
        "inputs": {"count": {"dtype": "int", "required": True}},
    })
    compiled = compile_cab(spec)
    values = compiled.inputs_model(count="4").model_dump()
    assert build_argv(compiled, values) == ["tool", "--count", "4"]

``dosho.get`` and ``dosho.define_cab`` return ``CabSpec`` definitions.
``build_document`` selects a definition from a supported document dialect;
``describe_cab`` exposes normalized parameters and exact declared dtype labels
without instantiating framework types. The catalogue uses this descriptive
view; runtime compilation still requires trusted bindings for strict types.

Python tools remain ordinary functions marked with ``@dosho.pystep``. The
marker stores metadata and preserves their signatures and annotations. Shared
function-schema helpers derive Pydantic models without calling the bodies.

``build_model`` also creates reusable Pydantic input models for Python recipes;
no recipe language is introduced. Shinobi's model-building adapter supplies
explicit trusted bindings for MSv2/CasaTab/FITS/ProductFamily/DirectoryBundle.
Known framework dtypes without bindings are errors, including nested types.
Declarations for dataset accesses, FITS accesses, derived reads and families
are inert JSON until Shinobi validates its authoritative models. Dynamic
matched extras pass through to the tool.

Static YAML composition is safe data processing: ``_include`` containment and
cycles, ``_use`` merge precedence and warnings remain supported. Package roots
are explicit filesystem roots, never imports. ``dynamic_schema`` never runs;
non-binary commands are rejected before executable argv is returned.

Detached workers stage both packages and digest their combined source tree.
Shinobi's versioned cab cache identity separately records schema/formatter
contract versions and argument semantics. Frozen bundle version 3 verifies
those semantics without confusing them with dataset states or worker attempts.

Static definition checks
------------------------

With ``dosho[validation]`` installed:

.. code-block:: console

    $ dosho list
    $ dosho show wsclean
    $ dosho validate my-cabs.yaml

``list`` also works with the base package. ``show NAME`` reads a definition's
schema and resolves its image; Python step bodies are never called.

``validate FILE`` accepts the static YAML dialect: a ``cabs:`` mapping or
a direct mapping of names to definitions. JSON with the same structure works
too. It resolves relative ``_include`` and ``_use`` composition and Dosho's
explicit filesystem root, without importing named packages. It checks every
binary definition's header, metadata, patterns, native dtypes, defaults and
constraints. Required parameters need no supplied values. Empty catalogues,
``dynamic_schema`` and non-binary flavours fail.

Use ``dosho validate FILE --strict`` to fail when any framework checks remain
deferred. It reports every deferred parameter and declaration before
returning a nonzero exit status, without importing Stimela Ninja.

Success reports ``Static definition checks passed`` only after checking every
cab. Parameters needing framework types retain their exact declared dtypes and
are labelled ``requires stimela-ninja to validate``. Their dtype/default
semantics, and access/family declarations, require the framework's authoritative
models. Unknown dtype names retain the compiler's existing string fallback;
this command does not establish that every spelling is recognized. Actual
data validation and execution qualification are outside these static checks.

Runtime adaptation
------------------

Install ``dosho[validation]>=0.2.0b1`` for standalone schema compilation
and argv formatting, or ``stimela-ninja>=0.2.0b1`` for runnable cabs and
recipes. The dependency direction is Shinobi to Dosho validation;
Dosho's independent lock contains no framework dependency.

Import shared metadata and model helpers from ``dosho.validation``. For
framework declarations, use Shinobi's metadata types. ``Policies`` is
re-exported; ``ParamMeta``, ``ParamPattern`` and ``ParamSegment`` extend the
shared types with framework declarations. Shinobi's adapter supplies trusted
dtype bindings for strict datasets and product families.
``dosho.validation.build_argv`` accepts validated parameter values and formats
argv. ``shinobi.policies.build_argv`` additionally normalizes framework inputs
and outputs. A standalone ``CompiledCab`` is not a runnable ``shinobi.Cab``.

Provider documents carry the ``dosho-cab-v1`` dialect tag.
``Recipe.add_step`` and ``Recipe.add_loop`` adapt definitions at the recipe
boundary; ``shinobi.cabs.get`` and ``adapt_definition`` provide explicit
runtime access. Callers needing runtime attributes on a ``dosho.get`` result
use that adapter. Third-party ``yaml_cab`` documents are also supported.

For cross-repository development, use the verified candidate wheel-pair
procedure in :doc:`../contributing` rather than adding a reverse dependency
or a local-path source to either published package.

Automatic paired CI
-------------------

Dosho's core job covers validation, catalogue/image metadata, CLI,
publication authorization and version tests without Shinobi. Pushes to main
and pull requests also run the full paired cab suite on Python 3.11/3.12.
The docs job builds from Dosho definitions without installing Shinobi.
Reusable and manually dispatched CI default
``ninja-ref`` to ``main`` and accept an explicit branch, tag, or commit override.
Push and pull-request checkouts fall back to ``main`` because those events
have no workflow inputs. The publication workflow reuses the complete CI
workflow and requires core tests, paired tests, and docs to pass before upload.

Literal fields support ordinary Pydantic ``min_length`` and ``max_length``
constraints for strings and containers. Bounds must be nonnegative integers
and the minimum cannot exceed the maximum. Constrained defaults are validated
when constructing the model. These shared constraints also serve Shinobi's
worker configuration models; no cab-specific validation callback is loaded.


Non-argv dependency inputs
--------------------------

A declared input may set ``pass_to_command: false``. Its normal type,
requiredness and readonly metadata still apply; it remains available to the
execution adapter for fingerprinting and mounts. Only native argv emission is
suppressed. The default is ``true`` and must be a boolean. This supports, for
example, the explicit FITS dependency referenced by a native a-term parset,
without inventing a nonexistent command-line option. The tool adapter must
validate that the parset references this exact artifact; suppression does not
validate arbitrary file contents or authorize writes.

The shared-screen profiles require candidate Simms a-term support and a
qualified WSClean runtime. Their declarations do not qualify native numerical
behavior. The fixed CASA history SAVE profile declares MS WRITE capability because
native CASA opens the MS read/write, checks exact FLAG/FLAG_ROW preservation
with native casatools and returns the authoritative same-field vis. It accepts
only a fresh history root; callers must run a preserving preflight before creator cleanup. It does
not retain pre-existing history or promise partial-sidecar rollback. SAVE is
cache-enabled for strict mutation recovery; restart reuse requires a fresh
read-only history verification against the actual saved version digest.


``flagversion-restore-replace`` is a separate casatools utility, not a wrapper
around CASA agentflagger RESTORE (which opens history read/write). It requires
the actual SAVE version digest and a fixed fully populated two-column boolean
saved table. Every row/type/shape is checked before the MS is opened for writes;
FLAG and FLAG_ROW are copied independently and post-close identity is verified.
Native oracle equivalence, including inconsistent FLAG_ROW/FLAG cases, remains
an explicit qualification requirement. Partial target writes use the normal
strict MS recovery mechanism; readonly history is never a rollback target.


Guarded WSClean header copies
-----------------------------

``wsclean-normalize-stokes-i`` is an ordinary host binary cab, explicitly run
with the native backend and ``cache: false``. It reads seven explicit native
source families and creates independent corrected FITS families and a receipt.
It never changes the native WSClean producer's files or its MS writer state.
The singleton-I IDG scalar-beam family is an explicit producer dependency.

The helper proves the known uniform I/V signature, grids, units, frequency and
weight lineage, channel apparent/beam division and exact nonfinite masks before
copying. MFS residual/model checks follow native finite-pixel weighted channels;
restored MFS rendering is bounded by separate native stock/fixed parity rather
than a second renderer. Source products may be native cache hits under the
existing structural FITS cache contract. Rendered MFS pixels are preserved as
provided; arbitrary prior corruption of that rendered image is not detected.
Identity BSCALE/BZERO cards are accepted. Native model
unit quirks are preserved, including JY/BEAM on corrected and MFS model files.
The thin batch adapter delegates all copy/header writes to pinned
``fitstoolz==0.2.2`` through its existing ``fitstoolz.apps.header.runit`` operation.
V products request ``edit=["CRVAL4=1"]``; already-I products request no edit.
V inputs with an existing CHECKSUM are refused before writing because this
version does not update that checksum. Already-I checksums must remain valid.
Only the copied STOKES card may change; payload bytes, DATASUM and unrelated
metadata remain exact. A receipt records source/destination paths, checks,
payload digests and actual tool version/operation. Source bytes and modification
times are checked unchanged, including on failure. Failed operations clean only
their newly created files. Fitstoolz writes full independent copies, which can
add several GB per large channel/MFS imaging round.
