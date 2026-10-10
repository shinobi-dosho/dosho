Strict MeasurementSet contracts
===============================

An ``MSv2`` port declares a Measurement Set that shinobi plans, snapshots and
checks around execution. A legacy ``MS`` port supplies path handling only.
The strict set is maintained in ``tests/test_dataset_contracts.py``; adding a
new strict cab requires recording its exact access contract there.

The repository's ``examples/strict_ms_pipeline.py`` is a small native-MS
conformance recipe for the annotation work tracked in dosho issue 79. It
creates an MS with Simms, populates DATA from a point source, saves flags,
runs tricolour, restores the saved flags, reads a scalar summary in a custom
Python step, and images the result with WSClean. Every MS input and output is
typed ``MSv2``, including the Python reader and WSClean's list input.

.. list-table:: Declared access in the example
   :header-rows: 1
   :widths: 25 75

   * - Step
     - Contract
   * - Simms telsim
     - Create a new MS; an existing target is refused without explicit overwrite.
   * - Simms skysim
     - Create or replace the selected visibility column (DATA by default), with
       schema-change permission and a required column postcondition.
   * - Flag backup
     - Read FLAG and FLAG_ROW; own and preserve the external flag-version history.
   * - Tricolour
     - Read the selected visibility column; write FLAG, leaving FLAG_ROW unchanged.
   * - Flag restore
     - Read the selected saved version; write FLAG and FLAG_ROW in the MS.
   * - Python summary
     - Read UVW, DATA and FLAG, returning dimensions and counts as scalar data.
   * - WSClean
     - Conservative whole-dataset read/write access, with schema-change permission.

WSClean is deliberately a writer even for dirty imaging: other modes update
MODEL_DATA or create IMAGING_WEIGHT. Naming either under ``create`` would
incorrectly require it after every invocation. The whole-dataset contract
covers reads of the selected visibility column, flags, weights, UVW and
metadata, as well as those mode-dependent writes. The cab selects DATA by
default and exposes the real ``-data-column`` switch as ``column``.

Run the example
---------------

Use a Python 3.11 driver with dosho's locked run dependencies. The qualified
container boundary is Simms 3.0.2, tricolour 0.2.1, MSUtils 3.0.0 and WSClean
3.6/IDG, resolved through ``images.yaml``. Import tool packages inside the
running container; cab loading never imports their schema-generation code.

Prepare these two small input files in a fresh output directory:

.. code-block:: text
   :caption: sky.txt

   #format: name ra dec stokes_i
   centre 0h24m20s -30d12m33s 1

.. code-block:: yaml
   :caption: flags.yaml

   strategies:
     - name: zeros
       task: flag_nans_zeros

The short flagging configuration tests flag mutation and restoration; it is
not a scientific RFI strategy. The four-correlation point source has zero
cross-hands, giving the flagger a deterministic signal to flag. Tricolour's
noninteractive progress timer can add about five minutes to a small run.

.. code-block:: console

   ninja --backend docker run examples/strict_ms_pipeline.py:pipeline \
     --ms simulation.ms --sky sky.txt --flag-config flags.yaml

The result contains the strict MS path, the scalar summary, and an image
product family. Choose its member with
``image.select(time=0, frequency=0, polarization="I", component="real")``.
The custom reader lives in ``examples/strict_ms_summary.py`` so the container
loads its function without also constructing the host-side recipe.
Use fresh output directories for qualification. Explicit overwrite of the
simulation step destroys its existing target and invalidates downstream cache
entries; it is not an instruction to preserve an old observation.

Conformance tests
-----------------

Static tests reject path-only MS ports and check the access-hazard ordering,
including backup before flagging and saved-version production before restore.
The opt-in native suite creates its own disposable MS and executes the
production contracts without weakening them:

.. code-block:: console

   DOSHO_NATIVE_DATASET_CONTRACTS=1 \
     python -m pytest -q tests/test_native_dataset_contracts.py

The driver needs ``python-casacore`` and ``numpy`` in addition to the locked
run/development dependencies. The suite checks the populated visibility
values, restored flags, emitted model FITS file and captured image. Negative
cases refuse an existing creation target and deliberately give skysim an
incomplete column declaration: conformance must fail and restore the original
DATA before that invocation can count as evidence.

This example qualifies ordinary local MSv2 execution. Strict scatter, nested
recipes, Kubernetes and Slurm step backends remain unavailable under the
current framework profile. It does not establish MSv4 adapters, the wider
Paper I backend/scatter evaluation, scientific calibration convergence, or
the deferred WSClean restoration/facet interfaces.

.. literalinclude:: ../../examples/strict_ms_pipeline.py
   :language: python

.. literalinclude:: ../../examples/strict_ms_summary.py
   :language: python
