"""Pinned container image references, one constant per tool, loaded from
`images.yaml` -- the single place a cab's image tag is bumped. No
image-building infrastructure here (see AGENTS.md), just reuse of
existing published images.
"""

from pathlib import Path

import yaml

_DATA_PATH = Path(__file__).with_name("images.yaml")

with _DATA_PATH.open() as _f:
    _IMAGES = yaml.safe_load(_f)

globals().update(_IMAGES)

del _f, _DATA_PATH
