"""Keep Tricolour noninteractive progress updates without a five-minute exit delay."""

from importlib.util import find_spec
from pathlib import Path

spec = find_spec("tricolour.apps.tricolour.app")
if spec is None or spec.origin is None:
    raise RuntimeError("Tricolour CLI module was not found")
path = Path(spec.origin)
source = path.read_text()
old = "ProgressBar(minimum=1, dt=5*60)"
new = "ProgressBar(minimum=300, dt=10)"
if source.count(old) != 1:
    raise RuntimeError("Tricolour progress bar source changed")
path.write_text(source.replace(old, new))
