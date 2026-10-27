# Contributing to dosho

Thanks for your interest in contributing! **dosho** ("a shinobi's tool
bag") is the native cab repository for
[shinobi](https://github.com/shinobi-dosho/stimela-ninja) (Stimela Ninja).
It's early software, so the most valuable contributions right now are new tool ports, bug reports, focused fixes, tests,
documentation, and feedback on the design.

Everyone taking part is expected to follow the
[Code of Conduct](https://github.com/shinobi-dosho/dosho/blob/main/CODE_OF_CONDUCT.md).

## Scope and philosophy

Every tool must contain a single executable, a Cab's `command`
or a `@dosho.pystep` function. No other tool attribute/section
will be executed, i.e, no `exec()/eval()` executions or
dynamic parameter creation at loadtime. Tools must be fully defined
when they are authored. The `ParamPattern` construct should be more
than enough for most cases, and anything beyond that should be
configured in the Python recipe's logic. See
[authoring guide](https://dosho.readthedocs.io/en/latest/concepts/authoring.html)
for the design rationale and tool formats, and the checklist below before
porting a new tool or changing `dosho/_builder.py` or `dosho/registry.py`.

Our core philosophy: **avoid unnecessary complexity like the plague**.

## Ways to contribute

- **Port a new tool** -- follow [Before adding a cab](https://github.com/shinobi-dosho/dosho/blob/main/CONTRIBUTING.md#before-adding-a-cab).
  Every ported tool needs a test that checks real CLI/schema shape, not
  just that the object constructs without error.
- **Report bugs** and request features via
  [issues](https://github.com/shinobi-dosho/dosho/issues).
- **Improve documentation** under `docs/` or the docstrings that feed the
  API reference.
- **Sizable change/addition** -- if you're considering a larger change,
  opening an issue to discuss it first is a great way to align before
  writing code.

## Before adding a cab

Use the real tool's `--help` and documentation as the source of truth. For a
Python function wrapper, check the actual function signature. Cross-check a
matching cult-cargo definition when available, but do not copy it blindly.
Never import or execute an external tool's schema-generation code when loading
a cab. Describe parameters statically; leave unsupported fields out until a
real pipeline needs them.

Put a binary tool's definition in `src/dosho/documents/<name>.yaml`, or a
`@dosho.pystep` function in the relevant `src/dosho/cabs/` module. Register it in
`src/dosho/cab_index.yaml` and add its exported attribute to
`src/dosho/cabs/__init__.py`. Use the existing image manifest and shared schema
helpers. Add a test that checks representative arguments or recipe wiring
against the real tool's interface, then regenerate the catalogue as described
under [Documentation](https://github.com/shinobi-dosho/dosho/blob/main/CONTRIBUTING.md#documentation).

## Development setup

The project uses [uv](https://docs.astral.sh/uv/).

### Testing with Shinobi

Dosho's lock resolves independently of Shinobi. Integration tests require an
explicit candidate checkout or wheel of Shinobi; it is deliberately absent
from Dosho's dependency graph:

```bash
uv sync --locked --extra validation --group dev
bash .github/scripts/install-pair.sh /path/to/candidate/stimela-ninja
uv run --no-sync pytest -q -o pythonpath=
```

The helper builds both wheels, installs them together with their runtime
dependencies, and verifies each version and installed package origin. Temporary
files stay under `.work-cache/pair`. Run integration tests with
`uv run --no-sync` so a subsequent sync cannot remove the explicit candidate.
Clearing pytest's configured `pythonpath` checks the installed wheels.
CI pairs every push to main and every pull request with
Shinobi main, verifying each installed version against its own source checkout
plus package origin. Reusable and manually dispatched CI accept a `ninja-ref`
override for a specific branch, tag, or commit. Independent core CI requires no
companion framework; the publication workflow also requires the full paired
tests and docs to pass.

### The pre-commit hook

Enabling it is the only setup step that is not `uv`'s job -- git will
not let a repository turn on an executable hook by itself, which is why
`git config core.hooksPath .githooks` is manual; skip it and you simply get no hook.

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
   `uv run --no-sync python docs/_ext/cab_catalog.py`.

Any other commit skips both in milliseconds. `git commit --no-verify`
bypasses the hook when you genuinely need to.

## Testing

```bash
uv run --no-sync pytest -q -o pythonpath=
```

Every ported tool's test round-trips a representative param set through
`shinobi.policies.build_argv` (for a runnable `Cab`) or checks its
`inputs_model`/`Recipe` wiring (for a pystep) against the real tool's
known CLI/signature shape -- most tools here (`casatasks`, `casaplotms`,
CASA in general) aren't installed in the test environment, so tests never
actually dispatch/execute them.

Standalone schema and argv behavior belongs in `dosho.validation`, whose
tests require no Shinobi installation. Run the independent core selection
from `.github/workflows/ci.yml` after `uv sync --locked --extra validation
--group dev`. For integration tests, install the candidate wheel pair first;
`-o pythonpath=` checks the installed wheels rather than importing `src/`.

## Code style

- **Lint must be clean**: `uv run --no-sync ruff check .` should report no errors. Ruff runs at
  `line-length = 100` with the rule set selected in `pyproject.toml`.
- `ruff format` is available and uses the same line width if you'd like
  autoformatting.
- Use **type hints** and write **docstrings** on public API — they render into
  the Sphinx API reference via autodoc.
- Match the surrounding code's naming, comment density, and idiom.

## Documentation

The build reads Dosho cab declarations and Python function annotations.
The docs group supplies all dependencies; Shinobi is not needed:

```bash
uv run --python 3.12 --locked --group docs sphinx-build -E -n -W --keep-going -b html docs docs/_build/html
open docs/_build/html/index.html
```

CI builds with `-W`, so a warning is a failure.

## Pull requests

1. Branch off `main` and keep PRs **small and focused** — one logical change per
   PR is much easier to review.
2. Make sure `uv run --no-sync pytest -q -o pythonpath=` and `uv run --no-sync ruff check .` pass locally, and that docs build if you
   touched public API.
3. Push and open a PR against `main`. Reference any related issue
   (e.g. "Closes #12").
4. **CI must be green.** The independent `core` job tests catalogue/validation
   and lint without Shinobi. Every push to `main` and every PR also runs the
   full paired suite on Python 3.11/3.12 against Shinobi `main`. The separate
   docs job builds without Shinobi. Reusable and manually dispatched CI accept a `ninja-ref` override
   for a specific branch, tag, or commit. `publish.yml` reuses this complete
   CI workflow, so core tests, paired tests, and docs must pass before upload.

### Publishing container images before merge

Image publication is a separate human action. Pushes and merges do not publish
release images. Wait for PR reviews and checks, mark the PR ready for review,
and dispatch the existing `images.yml` workflow **on protected `main`**:

```bash
gh workflow run images.yml --ref main \
  -f pr_number=YOUR_PR_NUMBER -f head_sha=FULL_40_CHARACTER_HEAD_SHA \
  -f override_unreviewed=false
```

The Actions UI offers the same inputs. The publisher must be present on
protected `main` before dispatch. Image PRs can publish before merge by
dispatching the trusted workflow on `main` with the candidate PR's exact
head SHA.
The trusted workflow, gate and CLI are pinned to that dispatch's `main` SHA.
A separate candidate checkout supplies only the YAML manifest, Dockerfiles and
build contexts. Candidate Python, workflows and dependency files never run on
the credential-bearing host. A new PR commit requires a new dispatch after its
reviews and checks pass. A rerun by a different actor is rejected; that human
should make a fresh dispatch.

A run fails before any GHCR login if the dispatcher is not a human repository
collaborator with write access, the PR is a fork, closed, draft, conflicted,
targets another branch, or its head moves. Dispatching from a candidate branch
is rejected; the workflow must run on `main`. GitHub's `reviewDecision` must be
`APPROVED`, including configured reviewer counts, code owners and stale review
rules. A repository administrator may set `override_unreviewed=true` to allow
`REVIEW_REQUIRED` (including partial approvals); this never overrides
`CHANGES_REQUESTED`, unknown review state, failed checks or pending checks.

The gate independently requires a successful `.github/workflows/ci.yml`
pull-request run for this exact PR/head and successful `test (3.11)`,
`test (3.12)` and `docs` jobs. It also checks the latest other workflow runs,
check runs and commit status contexts for that SHA; older successes cannot hide
new failures or pending reruns. Publisher workflow runs and their check suites
are excluded so a failed publication can be retried. Skipped, neutral, unknown
and API-error results fail closed.
This explicit publication gate applies even when the branch ruleset has no
required CI contexts. Unrelated manual or dev workflows need not be triggered.

Each publishing job repeats the gate and checkout SHA checks before GHCR login.
The trusted CLI validates candidate path containment (including symlink escapes),
release names/tags and the fixed `ghcr.io/shinobi-dosho` namespace; deployment
image overrides do not affect its plan or builds. The trusted gate runs again
before every registry-writing command, including each staged platform push and
final manifest creation. A change during an already running `buildx --push`
command cannot stop the exact internal registry write; revalidation happens
immediately before launching that command. `build-plan --missing-only` selects
absent release tags, builds bases before tools and skips existing tags. All bases
stage their platforms sequentially, so the final release manifest has a separate
gate after the builds complete. Tools retain sequential build/prune settings
with the single-platform CASA6 exception. Runs are serialized without
cancelling a publisher already running. The separate `images-verify.yml`
retains Monday registry checks; `images-dev.yml` and PyPI's `publish.yml` have
their own release processes.

### Commit messages

Write clear, descriptive commit messages explaining *why* a change is made. No
formal convention (Conventional Commits, sign-off/DCO, or CLA) is required.

If a coding assistant helped with a commit, end its message with a plain-text
trailer naming the assistant and model:

```text
Assisted-by: <LLM> <MODEL>
```

Use no email address or assistant `Co-authored-by:` trailer. Pull request
descriptions carry no assistant trailer, badge or generated-by notice; they
describe the change and its validation.

## Versioning and releases

The project follows [Semantic Versioning](https://semver.org/). **Contributors
don't cut releases** — that's a maintainer task. The maintainer bumps `version`
in `pyproject.toml` and publishes a GitHub Release, which triggers the publish
workflow to build and upload to PyPI.

## Repository protection

The active `main` branch ruleset lives in GitHub repository settings.
[`.github/main-ruleset.json`](https://github.com/shinobi-dosho/dosho/blob/main/.github/main-ruleset.json) records that policy;
committing the file does not apply or update the setting. If the repository is
recreated and has no ruleset, an admin can apply it once from the repository
root:

```bash
gh api -X POST "repos/$(gh repo view --json nameWithOwner --jq .nameWithOwner)/rulesets" \
  --input .github/main-ruleset.json
```

Check for an existing ruleset before running this command, because `POST`
creates another one rather than updating the current rule.

## License

By contributing, you agree that your contributions are licensed under the
project's [Apache License 2.0](https://github.com/shinobi-dosho/dosho/blob/main/LICENSE).

You are responsible for ensuring that you have the right to submit your
contribution under this licence, including any necessary employer or
third-party permissions. Do not submit confidential, proprietary, or
otherwise restricted material that you are not authorised to release.
The project's open-source terms apply irrespective of contributors'
employment or institutional affiliations. See [NOTICE](https://github.com/shinobi-dosho/dosho/blob/main/NOTICE).
