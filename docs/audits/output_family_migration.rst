:orphan:

Shared scientific output families
=================================

Implemented and checked 2026-10-08. All five cabs use the shared output-family
API from stimela-ninja PR #195, pinned in ``uv.lock`` at
``63cae373ccf5403fa085a8efb13b6f171e77469a`` (including PR #197). No external schema-generation
function is imported or executed to load a cab. Image versions are unchanged.
The latest source parameter inventory is in :doc:`output_family_parameters`;
WSClean's dimensional filename checks are in :doc:`wsclean_output_families`.

Declared products
-----------------

.. list-table::
   :header-rows: 1
   :widths: 16 24 60

   * - Cab
     - Output fields
     - Coordinates and ownership
   * - QuartiCal
     - ``gain_directory``
     - One local directory bundle at ``output.gain_directory``. Gain terms,
       net-gain groups, BLCORR, metadata and chunks remain in one inventoried
       store. ``ms`` remains a scalar pass-through to the input MS.
   * - killMS
     - ``solutions``
     - One directory bundle at the required ``solutions_sols_dir``. Owns the
       configured tree, including its MS-named subdirectory, solution NPZ,
       parset and optional companion files. No synthetic Jones-array axes.
   * - DDFacet
     - ``dirty``, ``restored``, ``model``, ``residual``, ``psf``, ``dico_model``
     - Representation and flux scale label actual mean/cube/MFS files.
       Saved-cycle ordinals are discovered as integers; ``final`` labels
       unnumbered residuals, PSFs and model dictionaries. FITS array axes
       remain inside each file.
   * - SoFiA-2
     - ``catalogue``, ``filtered``, ``mask``, ``moments``, ``noise``,
       ``cubelets``, ``diagnostics``
     - Finite global products and formats; cubelets have discovered integer
       source IDs, product names and actual formats. Optional rules permit
       suppressed 2D/PV products and native HDF5-to-FITS fallback.

All rules are optional and capture emitted products rather than claiming
files that do not exist. Missing products yield resolved empty families.
A successful family returns its concrete member table; deleting a recorded
file or any inventoried bundle child invalidates the cache. The shared
validator resolves aliases and rejects product/input tree overlap before
execution, including writable MS inputs. For literal path spellings, killMS
rejects the MS itself, its descendants, symlink aliases into it, and a solutions
root containing the
MS. Solutions must occupy a disjoint owned tree.

The killMS parser guard uses the shared constraint from `stimela-ninja PR #197
<https://github.com/shinobi-dosho/stimela-ninja/pull/197>`_. killMS's
``FormatValue`` treats strings containing ``None`` as unset and strips
whitespace or comments, which can change the destination after path preflight.
PR #197 adds a shared declarative ``string_pattern`` constraint. The cab rule
rejects reserved tokens and parser syntax before execution; a native solve,
cache hit and missing-NPZ recreation pass with that rule. Requiredness,
parser-token validation and disjoint-tree preflight together enforce the
external solutions directory contract. Constraints also survive model and
recipe offload serialization through the shared upstream codec.

The directory output API changes: QuartiCal consumers use
``result.outputs.gain_directory.select().path``; killMS consumers use
``result.outputs.solutions.select().path``. DDFacet and SoFiA scalar product
fields are replaced by the families above. See :doc:`../concepts/authoring`
for file selection examples. Broader DDFacet products stay harvested;
SoFiA's global file harvest patterns avoid claiming the cubelet directory
alongside its individually owned family files.

Source and CLI corrections
--------------------------

QuartiCal's `gain-store writer
<https://github.com/ratt-ru/QuartiCal/blob/15c081e1eee83a17ac063aff4e590cd79aa26139/quartical/gains/datasets.py#L282>`_
and `baseline-correction writer
<https://github.com/ratt-ru/QuartiCal/blob/15c081e1eee83a17ac063aff4e590cd79aa26139/quartical/gains/baseline.py>`_
establish whole-store ownership. The image stays at 0.2.5 because the manifest
records solver regressions in later releases. Latest-only
``solver.collapse_chain`` and per-term ``scalar`` are consequently not added
to a 0.2.5 cab. Remote gain URIs and group addresses fail local-bundle
validation; remote-store support is outside this contract.

DDFacet rules follow `ClassDeconvMachine
<https://github.com/saopicc/DDFacet/blob/2fe05ab4a3399ef44a631b6116608f21239e2a57/DDFacet/Imager/ClassDeconvMachine.py>`_.
Boolean flags now receive ``0``/``1`` and lists use bracket syntax accepted by
its `ReadCFG parser
<https://github.com/saopicc/DDFacet/blob/2fe05ab4a3399ef44a631b6116608f21239e2a57/DDFacet/Parset/ReadCFG.py>`_.
This preserves singleton HMP scales instead of turning ``[0]`` into a scalar.
``Image.NPix`` and ``Image.Cell`` accept the documented scalar or pair forms.

killMS's 94 flags now use the flat spelling in `read_options
<https://github.com/saopicc/killMS/blob/350f22c67a4b769b2c105327116028e7b13a86fb/killMS/kMS.py>`_,
e.g. ``--MSName`` and ``--SolsDir``. Python field names stay stable.
Booleans receive ``0``/``1``; bracketed pre-apply lists preserve the native
empty-list sentinel. ``TChunk`` and ``DtBeamMin`` accept fractional values.
The driver writes solutions and companion parsets below the explicit root;
its default of writing inside the MS is unavailable through this cab.

SoFiA's `authoritative default table
<https://gitlab.com/SoFiA-Admin/SoFiA-2/-/blob/a7434d9f91605cd738f2b13cd31b1450304fbc11/src/Parameter.c>`_
and `cubelet writer
<https://gitlab.com/SoFiA-Admin/SoFiA-2/-/blob/a7434d9f91605cd738f2b13cd31b1450304fbc11/src/DataCube.c#L6258>`_
provide parameter names, defaults and product suffixes. The nine missing
parameters are added: ``input.primaryBeam``, ``flag.cube``,
``output.dataFormat``, ``output.writeLogFile``, ``output.writePV``,
``output.writeKarma``, ``output.marginAperSpec``,
``output.showPreviewImage`` and ``output.writeDiagnosticPlot``.
They also exist in the pinned 2.7.0 image; latest 2.7.1 has the same table.
The cab has all 109 source control parameters.

WSClean 3.6 fixes include fixed-size tuples for fixed-arity options,
comma-joined channel-division frequencies, fractional memory and beam-update
settings, unit-bearing thresholds and beam sizes, input scratch ``temp-dir``,
and the missing ``local-rms-image``/``direct-ft-precision`` flags. The parser
rejects the help-only ``scalar-beam`` flag, so the cab removes it. Restoration
still mixes read/write filenames in one option and requires imaging inputs;
facet solutions mix paths and soltab strings. Those two existing interfaces
need a separate shared argv/path-role design and are not qualified here.

Native qualification
--------------------

Real-container runs use copies of disposable fixtures, independent of the
recording-backend tests:

* QuartiCal 0.2.5: one complex gain term, MODEL_DATA input, one solver
  iteration; complete Zarr gain store captured.
* killMS 3.3.0: one point-source sky model, scalar CohJones solve;
  actual ``input.ms/killMS.CohJones.sols.npz`` and companion parset captured
  below the external solutions root.
* DDFacet 1.0.0.0: Dirty and one-iteration HMP Clean runs. Mean/cube dirty
  images, restored/model/residual products, numbered residuals, PSFs and
  model dictionary match physical files. Native dirty/PSF caching is disabled
  so the conformance run actually emits the requested images. The DDFacet
  binary comes from the killMS image, which derives from the DDFacet image.
* SoFiA-2 2.7.0: threshold detection in a small synthetic FITS cube; catalogue,
  mask, moment and 13 cubelet products captured, including PV products.

Each run verifies a framework cache hit and a miss followed by recreation
after deleting a recorded family file or bundle child. Checked-in recording
backend tests additionally cover sandboxed and direct execution, discovered
cycle/source coordinates, empty products, remote-store rejection and killMS
MS-overlap rejection. Native tests do not establish scientific convergence,
beam-mode, multi-MS/batch, multi-direction or HDF5-build qualification.
DDFacet and killMS retain experimental status with those limits stated.

Run the native tests with Docker and small existing fixtures:

.. code-block:: console

   DOSHO_OUTPUT_FAMILY_TEST_MS=/path/to/tiny.ms \
   DOSHO_KILLMS_TEST_SKY_MODEL=/path/to/matching-model.npy \
   DOSHO_SOFIA_TEST_CUBE=/path/to/source-cube.fits \
   pytest tests/test_native_output_families.py

The MS needs DATA, MODEL_DATA, WEIGHT, four linear correlations, at least two
channels and two timestamps, valid antenna metadata and a consistent
POLARIZATION table. The sky model must match its phase centre. The cube
needs a source above the test's five-sigma threshold and valid FITS WCS.
All MS inputs are copied before native execution. To reproduce the tested
DDFacet container, set ``DOSHO_IMAGE_DDFACET`` to
``ghcr.io/shinobi-dosho/killms:3.3.0-d0.1.0`` before the test process starts.
