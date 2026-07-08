# Contributing to dosho

Thanks for your interest in contributing! **dosho** ("a shinobi's tool
bag") is the native cab repository for
[shinobi](https://github.com/SpheMakh/stimela-ninja) (stimela-ninja,
Stimela 3.0). It's early software, so the most valuable contributions
right now are new tool ports, bug reports, focused fixes, tests,
documentation, and feedback on the design.

## Scope and philosophy

Every tool is authored directly in Python -- no YAML dialect, no
`dynamic_schema`-style code execution at load time. See
**[`AGENTS.md`](https://github.com/caracal-pipeline/dosho/blob/main/AGENTS.md)**
for the full design rationale and tool-authoring conventions; read it
before porting a new tool or touching `dosho/_builder.py`/
`dosho/registry.py`. If you're considering a larger change, opening an
issue to discuss it first is a great way to align before writing code.

## Ways to contribute

- **Port a new tool** -- see `AGENTS.md`'s "Before adding a cab" section.
  Every ported tool needs a test that checks real CLI/schema shape, not
  just that the object constructs without error.
- **Report bugs** and request features via
  [issues](https://github.com/caracal-pipeline/dosho/issues).
- **Improve documentation** under `docs/` or the docstrings that feed the
  API reference.

## Development setup

The project uses [uv](https://docs.astral.sh/uv/). Clone this repo next
to a `stimela-ninja` checkout (`[tool.uv.sources]` in `pyproject.toml`
points at the local sibling path):

```bash
git clone https://github.com/SpheMakh/stimela-ninja.git
git clone https://github.com/caracal-pipeline/dosho.git
cd dosho
uv sync --group dev
uv run pytest
uv run ruff check .
```

## Testing

```bash
uv run pytest -q
```

Every ported tool's test round-trips a representative param set through
`shinobi.policies.build_argv` (for a `Cab`) or checks its
`inputs_model`/`Recipe` wiring (for a pystep) against the real tool's
known CLI/signature shape -- most tools here (`casatasks`, `casaplotms`,
CASA in general) aren't installed in the test environment, so tests never
actually dispatch/execute them.

## Documentation

```bash
uv sync --group docs
uv run sphinx-build -b html docs docs/_build/html
open docs/_build/html/index.html
```
