:orphan:

WSClean output-family migration
===============================

Checked 2026-10-08 against ``ghcr.io/shinobi-dosho/wsclean:3.6-idg-d0.1.0``.
The lock was refreshed 2026-10-09 to merged-main shinobi commit
``57bb5de3d8cc5c752e60d0efd7fd8a1bb66ae5af``, which includes the shared
output-family implementation from PR #195, the string constraint implementation
and offload fixes from PR #197, and finite derived-read, presence and nullability
support from PR #198. The source and native qualification date remains
2026-10-08.

Sources and declarations
------------------------

The cab's filename rules are transcribed from `WSClean v3.6
io/imagefilename.h
<https://gitlab.com/aroffringa/wsclean/-/blob/v3.6/io/imagefilename.h>`_.
The `v3.6 imaging implementation
<https://gitlab.com/aroffringa/wsclean/-/blob/v3.6/main/wsclean.cpp>`_ and
`settings validation
<https://gitlab.com/aroffringa/wsclean/-/blob/v3.6/main/settings.cpp>`_ confirm
availability and the combination of XY/YX into XY real and imaginary files.
Relevant defaults and CLI spelling are checked against the container's
``wsclean -help`` and `v3.6 commandline.cpp
<https://gitlab.com/aroffringa/wsclean/-/blob/v3.6/main/commandline.cpp>`_:
``-channels-out 1``, ``-intervals-out 1``, ``-pol I``, and ``-niter 0``.
Polarization lists are emitted as a single comma-separated argument.

``image``, ``dirty``, ``residual`` and ``model`` carry time, frequency,
polarization and component coordinates. ``psf`` is shared across
polarizations and carries only time and frequency. Channel indices are
integers; the MFS aggregate is the string ``mfs`` and exists only for
multiple output channels. Singletons omit their filename suffix, even
for a singleton polarization other than I. ``source_list`` is an optional
family with no dimensions and the fixed ``{prefix}-sources.txt`` path.

All family rules are optional; unavailable products return resolved empty
families. Normal capture excludes unchanged leftovers. Continuation explicitly
accepts existing model members so stale-output clearing preserves the models
it reads. Prediction and dry runs reserve no family products. Supplementary
outputs remain harvested without being assigned a family.

The scalar ``*_mfs`` fields are removed. Consumers select from the family,
for example ``image.select(time=0, frequency="mfs", polarization="Q",
component="real")``; see :doc:`../concepts/authoring`.

Native checks
-------------

The twelve checked-in opt-in cases use copies of a tiny native MS with a DATA
column, four linear correlations, four channels and multiple timesteps:

* Eight combinations of one/two channels, one/two intervals, and singleton Q
  or I/Q imaging. Every family member matches an actual emitted file.
* XX/XY/YX/YY imaging with two channels and ``-gridder wstacking``. WSClean
  emits XY and XYi, and no independent YX file. Image and dirty families each
  have twelve members; PSF has three.
* PSF-only imaging returns one PSF and empty image families.
* No-dirty imaging returns an image and PSF with an empty dirty family.
* One cleaning iteration with ``-beam-size 60`` and ``-save-source-list``
  emits image, dirty, model, residual, PSF and source list.

Every case also verifies a cache hit with the saved member table, then a
cache miss and repair after deleting a recorded PSF member. Run them with
an existing small fixture and Docker available:

.. code-block:: console

   DOSHO_WSCLEAN_TEST_MS=/absolute/path/to/tiny.ms \
     uv run --locked --extra run pytest -q tests/test_wsclean.py -k native_36

Three additional native probes passed: sandboxed two-channel/two-interval
I/Q imaging (twelve images, twelve dirty images and six PSFs); continued
cleaning using an existing model; and prediction that preserves its model
input while returning empty output families. Unit tests additionally verify
that a family declaration change invalidates a cached result and that stale
clearing preserves prediction and continuation inputs.

The native product/cache tests deliberately remove the strict MS contract
from a test copy of the document. They qualify output naming and capture,
not the MS mutation/cache profile. The production document retains its
``List[MSv2]`` writer contract unchanged, covered by the dataset declaration
tests. Full CLI schema refresh, restoration and reuse modes, primary-beam
products and direction-dependent PSF families remain separate audit work.

Declared model inputs and joint continuation
--------------------------------------------

The production cab declares finite model reads using WSClean 3.6's
``PredictModelFileSuffix()`` in ``main.h``. Facet-beam correction selects
``-model-fpb.fits``; otherwise beam gridding, an a-term configuration or
facet solutions select ``-model-pb.fits``; the remaining modes select
``-model.fits``. Prediction and continuation read channel models, including
XY's imaginary component, and never read MFS model aggregates. Only these
selected continuation inputs accept existing output members. MFS models
and ordinary model outputs under beam modes are newly captured products.

These declarations use shinobi's shared derived-read prerequisite. Readonly
models contribute physical fingerprints before cache lookup and are staged
into relative sandboxes without being republished as products. Continuation
uses the same strict snapshot group for the MS and existing model files;
resuming a logical step selects its original predecessor. Explicit null
values for filename/mode controls are refused rather than silently dropping
an input or output contract.

Additional Docker probes exercised the unmodified production strict cab:
prediction reused an unchanged model and missed after an external model edit;
continuation updated the MS and model together and then reused the committed
result. A two-polarization, two-channel, two-interval probe also passed
prediction invalidation and continuation reuse with eight declared model inputs.
Saved-flag restoration similarly missed after a saved version changed.
The earlier output-only native tests retain their narrower qualification.
These probes do not qualify every beam/facet imaging combination.
