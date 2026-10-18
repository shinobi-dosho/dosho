"""Adapt AIMFAST 1.3.4's Bokeh 2 calls and NumPy results.

Fail on changed upstream code so a version bump cannot silently skip the fix.
"""

from pathlib import Path

source = Path("/opt/dosho/venv/lib/python3.12/site-packages/aimfast/aimfast.py")
code = source.read_text()
for old, new, expected in (
    ("plot_width=", "width=", 6),
    ("plot_height=", "height=", 6),
    ("            hover.names = ['data']\n", "", 2),
    ("            hover.names = ['ratios']\n", "", 1),
    ("json.dump(data, f)", "json.dump(data, f, default=lambda value: value.tolist())", 1),
):
    count = code.count(old)
    if count != expected:
        raise RuntimeError(f"expected {expected} AIMFAST {old!r} call sites, found {count}")
    code = code.replace(old, new)
source.write_text(code)
