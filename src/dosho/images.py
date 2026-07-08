"""Pinned container image references, one constant per tool. The single
place a cab's image tag is bumped -- no image-building infrastructure
here (see AGENTS.md), just reuse of existing published images.
"""

# Tags cross-checked against cult-cargo's bundle-manifest.md (as of the
# cult-cargo `add-classic-cabs` branch) -- reusing the same published
# images, not building new ones.
WSCLEAN = "quay.io/stimela2/wsclean:3.6-haswell-cc0.2.1"
CUBICAL = "quay.io/stimela2/cubical:1.6.4-cc0.2.1"
QUARTICAL = "quay.io/stimela2/quartical:0.2.5-cc0.2.1"
AOFLAGGER = "quay.io/stimela2/aoflagger:cc0.2.1"
TRICOLOUR = "quay.io/stimela2/tricolour:cc0.2.1"
CRYSTALBALL = "quay.io/stimela2/crystalball:cc0.2.1"
OWLCAT = "quay.io/stimela2/owlcat:cc0.2.1"
SHADEMS = "quay.io/stimela2/shadems:cc0.1.3"
RAGAVI = "quay.io/stimela2/ragavi:cc0.2.1"
SOFIA2 = "quay.io/stimela2/sofia2:cc0.2.1"
# The real, tested tag caracal2's own common/casatasks.py pins (not the
# generic cult-cargo-manifest default) -- casatasks/casaplotms pysteps
# both use this image.
CASA6 = "quay.io/stimela2/casa6:6.7-cc0.2.1"
SIMMS = "quay.io/stimela2/simms:cc0.2.1"
# The old (pre-3.0) simms command has its own separate image -- a
# genuinely different tool from simms 3.0's skysim/telsim, not just a
# version bump.
SIMMS_CLASSIC = "quay.io/stimela2/simms-classic:cc0.2.1"
MOSAIC_QUEEN = "quay.io/stimela2/mosaic-queen:cc0.2.1"
