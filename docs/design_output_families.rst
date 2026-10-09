:orphan:

Proposal: typed output families and bundles
===========================================

Status: historical design proposal, 2026-10-07. Shared support landed in
stimela-ninja PR #195 and the cab migrations are implemented as of 2026-10-08;
see :doc:`audits/output_family_migration` and :doc:`concepts/authoring` for
the actual declarations and selection API. The illustrative syntax below
records the design discussion and is not current loader syntax. The scope
includes WSClean, QuartiCal, DDFacet, killMS, and SoFiA-2. Image pins are
unchanged. Source parameter evidence is recorded in
:doc:`audits/output_family_parameters`.

Problem and current cache behaviour
-----------------------------------

WSClean 3.6 chooses filenames from its output channel count, interval count,
and polarization selection. The current scalar ``implicit`` templates
cannot describe those families. ``output_patterns`` validates a reference's
name but neither resolves its value nor declares its concrete files.

A focused probe against shinobi main ``04ab6486`` demonstrated that a cache
hit can return a nonexistent ``deep-image.fits`` alongside a recorded
``deep-MFS-Q-image.fits``. The scalar field is optional, so its existence
is not required for reuse. Deleting the recorded dimensional product does
cause a cache miss. Changing an implicit output declaration changes the
product contract while preserving the scientific cache key.

The required change is accurate logical outputs backed by concrete members,
with their declaration included in the existing product contract. A directory
output also needs a concrete child inventory: checking that ``gains.qc`` or
``*_cubelets`` exists cannot establish that its recorded contents survive.

Requirements from the actual tools
----------------------------------

.. list-table::
   :header-rows: 1
   :widths: 15 35 50

   * - Tool
     - Output shape
     - Shared requirement
   * - WSClean 3.6
     - FITS files per output interval, band, polarization, and component;
       separate MFS and shared PSFs
     - Input-resolved filename families with singleton and aggregate rules
   * - QuartiCal 0.2.7
     - One Zarr store with named gain-term groups, optional net terms and
       baseline corrections; local or S3 location
     - Directory/store bundles and named subresources; solution array axes
       stay inside the store
   * - DDFacet 1.0.0.0
     - Mean images, multi-channel/Stokes cubes, apparent/intrinsic scales,
       MFS restoration, and intermediate major-cycle products
     - Product/representation labels plus runtime-discovered cycle members;
       cube axes do not imply separate files
   * - killMS 3.3.0
     - Solutions and parsets per MS and solution name, optional weight files
     - Nested members under an owned root; time/frequency/Jones dimensions
       are internal to the NPZ solution
   * - SoFiA-2 2.7.1
     - Global catalogues/maps and per-detected-source cubelets, masks,
       moments, spectra, and optional PV products
     - Runtime source-ID discovery, heterogeneous members, format labels,
       and conditional availability

QuartiCal writes ``{gain_directory}::{term}`` via dask-ms. ``G`` is a gain
group, not one file per solution time, frequency, antenna, or direction.
Partition metadata comes from the actual MS grouping. Net terms use names
such as ``KG-net`` and baseline corrections use ``BLCORR``. The MS pass-through
output and mutations of its columns remain ordinary dataset contracts.

DDFacet writes products such as ``image.cube.int.restored.fits`` and
``image.int.restored_mfs.fits``, with Stokes/frequency coordinates inside
the FITS cube. Intermediate outputs include ``image.residual00.fits`` and
``image.00.DicoModel``. The maximum iteration setting is not evidence that
every cycle was executed or saved. ``Output-Images``, ``Output-Also``, and
``Output-Cubes`` control different emitted product sets.

With an explicit ``SolsDir``, killMS writes
``{SolsDir}/{MS basename}/killMS.{solution name}.sols.npz`` and the companion
``.sols.parset``. Without it, the root is the MS directory itself. The default
solution name is the solver type unless ``OutSolsName`` overrides it.
Batch MS input needs distinct MS coordinates, with basename collisions
detected. Prefer an explicit solutions root in examples; deriving tool
default locations must not silently grant ownership of an input MS tree.

SoFiA's source IDs are runtime results. Global maps and individual source
maps are distinct scopes; ``source`` is an axis only for the latter. The
current tool can write FITS or HDF5 products, depending on its build, while
spectra remain text files. Some products depend on data dimensionality or
available measurements, not merely on boolean output flags. No-source runs
currently exit with code 8; the output resolver must not reinterpret that
failure as a successful empty family.

Logical model
-------------

Each product kind has one stable typed collection field, whose type does not
change when an axis has one member. Use a generic ``ProductFamily[T]``, where
``T`` retains its path/storage semantics: a file, a directory bundle, or a
store subresource. Each member records a typed locator and named coordinates.
For a WSClean image these are:

* ``time``: output interval ordinal, starting at zero;
* ``frequency``: output band ordinal, or the distinct label ``mfs``;
* ``polarization``: the selected polarization label, including when it is
  the only selected polarization;
* ``component``: real or imaginary where a correlation product needs it.

Output band ordinals are not input MS channel numbers or physical Hz, and
interval ordinals are not physical timestamps. Physical coordinates belong
in the image metadata rather than being guessed from filenames. Other tools
use different member coordinates, such as ``term``, ``ms``, ``cycle``,
``source``, ``flux_scale``, ``representation``, and ``format``. A coordinate
has a declared scalar type and meaning; it is not a free-form string parsed
differently by each downstream consumer.

The result is a table of actual members, not necessarily a rectangular
Cartesian tensor. Coordinates identify members of a particular field;
missing axes mean not applicable, rather than an invented singleton.
Duplicate addresses and conflicting physical ownership are errors. A
bundle and its child references share ownership and provenance instead of
being claimed as independent writable products.

Keep filesystem locations separate from storage-relative addresses. A
QuartiCal reference may carry the store location and group ``G`` separately;
``gains.qc::G`` must never be fed to the filesystem path walker as a filename.
Group/partition reading stays with the storage consumer. The common resolver
does not inspect scientific arrays or create one member per Zarr chunk.

Singleton axes remain in the logical address. Their filename suffixes are
omitted according to the tool's rules. A single Q image is therefore still
addressed as Q even though its filename contains no ``-Q``.

For three bands, two intervals, and I/Q imaging, representative addresses
and filenames are:

.. list-table::
   :header-rows: 1

   * - Product
     - Coordinates
     - Filename
   * - image
     - time=1, frequency=2, polarization=Q
     - ``deep-t0001-0002-Q-image.fits``
   * - image
     - time=1, frequency=mfs, polarization=Q
     - ``deep-t0001-MFS-Q-image.fits``
   * - psf
     - time=1, frequency=2
     - ``deep-t0001-0002-psf.fits``

PSFs have no polarization axis; repeating their paths for each polarization
would invent distinct logical products for one physical file. Imaginary
correlation products likewise need an explicit component rather than
masquerading as another polarization.

Static declaration, resolved and discovered members
---------------------------------------------------

A family declares its member type, ownership scope, coordinate schema,
and membership rule as data. Two sources feed the same result validator:

* Input-resolved members: bounded counts/enumerations and plain-format names,
  as needed for WSClean and known gain-term groups.
* Execution-discovered members: declared relative filename patterns with
  named, typed captures inside a reserved output root, as needed for SoFiA
  source IDs and DDFacet intermediate cycles.

Both produce the same typed table and concrete product inventory. A directory
bundle supplies a third physical shape, not a third resolver: its tracked
children support whole-bundle reuse and child references. Cab loading
constructs a fixed schema and executes no tool or cab schema callback.

An illustrative declaration for ordinary real image products is:

.. code-block:: yaml

   outputs:
     image:
       dtype: ProductFamily[File]
       family:
         path: '{prefix}{time}{frequency}{polarization}-image.fits'
         axes:
           time:
             count_input: intervals_out
             default: 1
             suffix: '-t{index:04d}'
             singleton_suffix: ''
           frequency:
             count_input: nchan
             default: 1
             suffix: '-{index:04d}'
             singleton_suffix: ''
             aggregate:
               label: mfs
               suffix: '-MFS'
               only_multiple: true
           polarization:
             values_input: pol
             default: [I]
             suffix: '-{value}'
             singleton_suffix: ''

``ProductFamily[File]`` is a proposed typed collection, not a string-valued glob.
Axes bind only to this step's inputs. Counts, enumerated labels, singleton
suffix suppression, and aggregate labels are bounded data operations;
there is no expression evaluation or callback import. Polarization input
normalization must agree with the accepted tool spellings, including case,
comma-separated values, and packed Stokes strings, before expansion.

For a discovered SoFiA cubelet family, the declaration needs an owned root
``{output_directory}/{output_filename}_cubelets``, a literal filename prefix
from ``output.filename``, a named integer capture for ``source``, and a
finite suffix table for ``cube``, ``mask``, moments, spectra, and PV products.
For DDFacet intermediate residuals, it needs the image prefix and a named
integer capture for ``cycle``. These are ordinary anchored pattern data;
input text is treated literally rather than injected as regular expressions.
Matching stays inside the declared scope. Do not turn an unrelated broad
harvest pattern such as ``{output_name}.*`` into a product-kind classifier.

Avoid a per-tool resolver registry, executable format adapters in cab data,
and language features for arbitrary slicing, arithmetic, or branching.
The exact declaration spelling for discovered patterns and store addresses
is still open; commit to the common semantics before freezing loader syntax.

This example covers dimensional naming, not every product's availability.
Its ordinary real members also need the constant coordinate ``component=real``
so a real/imaginary-capable field keeps consistent selection semantics.
The implementation must also distinguish product kinds emitted by dirty
imaging, cleaning, PSF-only, prediction, continuation, and restoration.
An unavailable product has no concrete member; it must not be returned as
a fabricated path. Required members missing after execution fail
publication. Optional members retain their actual presence or absence.
The declaration of these mode-dependent expectations needs to be settled
without adding a general conditional expression language to cab data. Use
explicit finite mode/flag membership data where expectations are knowable
from inputs. Data-dependent optional products must be reported from capture,
not guessed. If mandatory completeness needs scientific metadata that the
declaration cannot express, retain the whole bundle and defer finer claims.

One resolver must serve static planning, writable mounts and reservations,
stale-output handling, sandbox harvesting, result construction, and cache
validation. A bounded family can reserve its output area before execution
even where its actual membership is established afterwards. Unresolved
membership must remain unknown during planning rather than being replaced
with an empty collection or a default scalar path. Distinguish unresolved,
resolved empty/absent, and resolved nonempty results. An empty result is valid
only under the tool's existing success and requiredness rules.

The resolved result retains only members evidenced by the successful
execution. A fresh glob scan of the workspace is insufficient: files from
an earlier channel/polarization configuration may still be present.
Discovery must use the existing execution product capture and validate
members against the declared family. Prediction and continuation inputs
must also remain protected during stale-output handling.

This requires handling deliberate preservation: killMS ``SkipExistingSols``
mode 1 and QuartiCal ``overwrite=False`` do not imply that every accepted
output was newly modified. killMS implements native skipping only in its
batch/list-MS branch; this scalar cab preserves history without claiming
that native skipping occurred. Pre-existing members may count only when explicitly resolved
and evidenced under the successful run's contract. A pre-existing glob
match alone is insufficient. Shared output directories are never cleared
wholesale just because one nested member changed.

Local bundles freeze a recursive inventory of committed files and relevant
structure; deletion of a recorded child must be visible even when the root
still exists. Unchanged children accepted by a declared bundle remain in
that inventory. Existing stat/hash validation policy determines content
verification; family support must not promise stronger validation implicitly.
Remote URI stores need the corresponding storage-backed inventory and
existence checks. Until such backend support exists, mark them explicitly
unsupported for caching rather than treating an S3 URI as a local directory.

References and compatibility
----------------------------

Whole-family wiring consumes the typed collection. Selection uses named
coordinate equality, for example the proposed Python API:

.. code-block:: python

   recipe.outputs.clean.image.select(
       time=1, frequency="mfs", polarization="Q", component="real"
   )

A fully specified selection returns one typed member reference. Unknown or
unavailable coordinates raise a useful error. The graph retains its
ordinary dependency on the producing step; selection does not add runtime
nodes or control flow. Positional indexing into a sorted glob must not
define the public identity of a product.

The same selection operation addresses ``gains.select(term="G")`` or
``cubelets.select(source=17, product="spectrum")``. A selection whose value
is only known after execution resolves on the ordinary producing dependency;
it must not fabricate a compile-time member. Child references retain the
owning bundle's identity and storage locator. Selection does not provide
array slicing or claim access to an internal FITS plane/Zarr partition.

The present scalar fields need an explicit migration. A scalar convenience
reference may resolve only when its selection identifies one available
member. Multi-polarization or multi-interval outputs cannot silently choose
the first member. ``image_mfs`` must not fabricate an MFS file for a
single-band run. Broad validation-only output patterns should be tightened
to the coordinate address contract when real resolution is available.

Cache and publication contract
------------------------------

The existing separation between scientific execution identity and product
declarations remains intact:

* Axis input changes already affect the scientific key through validated
  inputs such as ``pol``, ``nchan``, and ``intervals_out``.
* The product contract must include the family declaration, filename rules,
  coordinate definitions, membership rules, bundle inventory policy,
  storage address semantics, requiredness, and its format version. A mismatch
  invalidates reuse without redefining scientific cache keys or MS snapshot
  identities merely because the output API changed.
* A successful result and cached result restore the same typed coordinate
  table and paths. The concrete inventory contains every produced member.
  Removing any recorded member or bundle child forces a miss, including a
  member of an otherwise optional family. A surviving directory root or a
  new glob match cannot replace missing recorded products.
* A downstream selection carries the producer field and named coordinate
  address in provenance and downstream identity. Changing a selected source,
  cycle, or term must change the consuming dependency identity even when the
  producer is unchanged. Selection cannot depend on list order or a new
  filesystem scan on a cache hit.
* Membership, required-member checks, harvest, and coordinate serialization
  complete before a reusable success is published. Failure preserves
  shinobi's existing rollback and publication ordering.

Logs, scratch caches, and diagnostic files must have an explicit role.
They do not automatically become mandatory scientific products because a
broad harvest pattern happened to capture them. Mutable MS datasets continue
to use shinobi's dataset access/snapshot contracts; family declarations must
not replace those contracts with directory globbing.

Acceptance cases
----------------

Verify all eight combinations of singleton/multiple polarization, band,
and interval axes, plus single Q, CSV/packed polarization spellings,
MFS, shared PSFs, and supported real/imaginary correlation products.
Test the product-emission modes separately and confirm requiredness against
real WSClean 3.6 runs. Additional tool conformance cases are:

* QuartiCal: multiple terms, net terms, ``BLCORR``, different MS partitions,
  and deletion of one recorded Zarr child while its store root survives.
  Internal array dimensions do not expand the file family. Local and remote
  storage support must be tested or explicitly gated independently.
* DDFacet: mean versus cube/MFS representations, apparent/intrinsic products,
  Stokes residual cubes, and early convergence that saves fewer major-cycle
  outputs than the configured maximum. Omitted output codes create no paths.
* killMS: explicit versus default ``SolsDir``, default versus named solutions,
  multiple MSs and basename collisions, nested NPZ/parset products, and
  ``SkipExistingSols`` with an unchanged accepted member. Verify real flat
  CLI flags before attempting container conformance.
* SoFiA: multiple source IDs, per-source spectra/moments/PV products,
  two-dimensional inputs that omit spectral maps, requested HDF5 with and
  without build support, and exit-code-8 no-source failure. Disabled families
  may be empty; a failed run must not publish even if its directory exists.

For caching, verify an unchanged hit restores identical members; deletion
of one band, MFS, or interval product misses; an axis or declaration change
misses; shrinking a dimension does not adopt stale members; changing a
selected coordinate invalidates the appropriate downstream work; and
failure cannot publish a partial family. Also test sparse membership,
duplicate coordinates, a missing nested child with a surviving root,
pre-existing unchanged accepted outputs, and escaped/out-of-scope discovery
matches. Compare sandboxed and direct execution and preserve the same
contract in detached worker serialization, mount planning and ownership.

Every consumer of output paths must use the shared typed walker, including
planning/reservations, clearing, publication, cache reconstruction, and
offloading. Add family/bundle support there once; do not special-case these
tools in each consumer. Pydantic models and serializers own the public types.

Implementation belongs upstream in shinobi. Dosho then supplies static
declarations and conformance tests for these tools. Stage the shared typed
table, selection and cache contract first; add bounded and discovered
membership plus bundle capture through the same resolver. Remote stores
remain gated until their ownership and inventory semantics are implemented.

Sources
-------

* `WSClean 3.6 filename rules
  <https://gitlab.com/aroffringa/wsclean/-/blob/v3.6/io/imagefilename.h>`_.
* `Shinobi product contract and cache lookup at 04ab6486
  <https://github.com/shinobi-dosho/stimela-ninja/blob/04ab64860e663e5b7422ff7d9d0e30ec15b49a65/src/shinobi/cache.py>`_.
* `QuartiCal gain writing at 15c081e1
  <https://github.com/ratt-ru/QuartiCal/blob/15c081e1eee83a17ac063aff4e590cd79aa26139/quartical/gains/datasets.py#L282>`_
  and `baseline corrections
  <https://github.com/ratt-ru/QuartiCal/blob/15c081e1eee83a17ac063aff4e590cd79aa26139/quartical/gains/baseline.py#L9>`_.
* `DDFacet image and cycle writing at 2fe05ab4
  <https://github.com/saopicc/DDFacet/blob/2fe05ab4a3399ef44a631b6116608f21239e2a57/DDFacet/Imager/ClassDeconvMachine.py>`_.
* `killMS solution naming at 350f22c6
  <https://github.com/saopicc/killMS/blob/350f22c67a4b769b2c105327116028e7b13a86fb/killMS/kMS.py#L412>`_.
* `SoFiA-2 output writing at a7434d9f
  <https://gitlab.com/SoFiA-Admin/SoFiA-2/-/blob/a7434d9f91605cd738f2b13cd31b1450304fbc11/sofia.c#L540>`_
  and `cubelet products
  <https://gitlab.com/SoFiA-Admin/SoFiA-2/-/blob/a7434d9f91605cd738f2b13cd31b1450304fbc11/src/DataCube.c#L6347>`_.
* Cult-cargo's local ``genesis/wsclean/__init__.py`` was read as prior art:
  it generates per-mode scalar/list fields through ``dynamic_schema`` and
  ``=GLOB(...)``. Those mechanisms remain excluded here.
