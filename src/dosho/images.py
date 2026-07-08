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
