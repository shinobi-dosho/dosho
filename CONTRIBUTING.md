# Contributing to dosho

Thanks for your interest in contributing! **dosho** ("a shinobi's tool
bag") is the native cab repository for
[shinobi](https://github.com/shinobi-dosho/stimela-ninja) (stimela-ninja,
Stimela 3.0). It's early software, so the most valuable contributions
right now are new tool ports, bug reports, focused fixes, tests,
documentation, and feedback on the design.

## Scope and philosophy

Every tool must contain a single executable, a Cab's `command`
or a `@shinobi.pystep` function. No other tool attribute/section
will be executed, i.e, no `exec()/eval()` executions or
dynamic parameter creation at loadtime. Tools must be fully defined
when they are authored. The `ParamPattern` construct should be more
than enough for most cases, and anything beyond that should be
configured in the Python recipe's logic. See
**[`AGENTS.md`](https://github.com/shinobi-dosho/dosho/blob/main/AGENTS.md)**
for the full design rationale and tool-authoring conventions; read it
before porting a new tool or touching `dosho/_builder.py`/
`dosho/registry.py`.

Our core philosophy: **avoid unnecessary complexity like the plague**.

## Ways to contribute

- **Port a new tool** -- see `AGENTS.md`'s "Before adding a cab" section.
  Every ported tool needs a test that checks real CLI/schema shape, not
  just that the object constructs without error.
- **Report bugs** and request features via
  [issues](https://github.com/shinobi-dosho/dosho/issues).
- **Improve documentation** under `docs/` or the docstrings that feed the
  API reference.
- **Sizable change/addition** -- if you're considering a larger change,
  opening an issue to discuss it first is a great way to align before
  writing code.

## Development setup

The project uses [uv](https://docs.astral.sh/uv/). `stimela-ninja` is
published on PyPI, so a plain `uv sync` resolves it like any other
dependency:

```bash
git clone https://github.com/shinobi-dosho/dosho.git
cd dosho
uv sync --group dev
uv run pytest
uv run ruff check .

# enable the repo's pre-commit hook (once per clone)
git config core.hooksPath .githooks
```

If you're working against an unreleased `stimela-ninja` change, clone
it next to this repo and layer it in for the duration of a command with
`uv run --with-editable ../stimela-ninja -- <command>` instead.

### The pre-commit hook

Enabling it is the only setup step that is not `uv`'s job -- git will
not let a repository turn on an executable hook by itself, which is why
the `git config` above is manual; skip it and you simply get no hook.

`.githooks/pre-commit` is a tracked shell script (no `pre-commit`
framework, no separate pinned tool universe), and does two things, each
only when the commit actually touches the relevant files:

1. **staged Python** -- `ruff check` and `ruff format --check`, through
   `uv run`, so it is this project's own pinned `ruff` and agrees with
   CI's lint job by construction. A format failure is fixed with
   `uv run ruff format <file> && git add <file>`; the hook never rewrites
   files behind your back.
2. **cab sources** (`src/dosho/`, `docs/_ext/cab_catalog.py`) --
   regenerates `docs/reference/cabs.rst` from the live registry and fails
   the commit if the committed copy was stale, so you never hit the CI
   staleness error after a schema change: `git add` the regenerated file
   and commit again. To refresh it by hand at any time:
   `uv run python docs/_ext/cab_catalog.py`.

Any other commit skips both in milliseconds. `git commit --no-verify`
bypasses the hook when you genuinely need to.

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
