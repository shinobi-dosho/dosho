#!/usr/bin/env bash
# Explicit local candidates, never a reverse dependency or Git-source redirect.
set -euo pipefail
candidate=${1:?pass the compatible Shinobi candidate checkout}
mkdir -p .work-cache/pair/tmp
pair_wheels=$(mktemp -d "$PWD/.work-cache/pair/wheels.XXXXXXXX")
export NINJA_CANDIDATE="$candidate"
export TMPDIR="$PWD/.work-cache/pair/tmp"
export UV_CACHE_DIR="$PWD/.work-cache/pair/cache"
uv build --wheel --out-dir "$pair_wheels"
uv build --wheel --directory "$candidate" --out-dir "$pair_wheels"
uv pip install --reinstall "$pair_wheels"/*.whl
uv run --no-sync python - <<'CHECK'
import importlib.metadata as metadata
from pathlib import Path
import os
import tomllib
import dosho
import shinobi
for package, checkout in (("dosho", Path.cwd()), ("stimela-ninja", Path(os.environ["NINJA_CANDIDATE"]))):
    expected = tomllib.loads((checkout / "pyproject.toml").read_text())["project"]["version"]
    assert metadata.version(package) == expected
assert "site-packages" in str(Path(dosho.__file__))
assert "site-packages" in str(Path(shinobi.__file__))
from dosho.validation import build_model
assert build_model("Inputs", {"n": ("int", True, None)})(n="2").n == 2
CHECK
