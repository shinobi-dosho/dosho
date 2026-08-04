# dosho -- design conventions

`dosho` ("a shinobi's tool bag") is the native cab repository for shinobi
(stimela-ninja, Stimela 3.0). cult-cargo and scabha did the real work of
cataloguing this ecosystem's tools first, and dosho's cab set leans on
that prior art throughout -- it's a new repository, not a rejection of
the old one. It exists because cult-cargo's YAML cab format -- built for
Stimela 2.0/scabha -- carries assumptions shinobi deliberately doesn't
carry forward: `dynamic_schema` (a Python function imported and
*executed* at cab-load time to compute a real tool's schema),
package-scoped `_include` composition, and dtype coverage gaps that
silently degrade to `str`. A compatibility loader could paper over those,
but maintaining one indefinitely was costing more than it was saving. See
stimela-ninja's own `AGENTS.md` for the full design philosophy this repo
inherits; this file only states what's specific to authoring cabs here.

## Core rule

**A cab definition is parameter configuration, not code.** A cab declares a
tool's schema -- parameter names, dtypes, defaults, required-ness, metadata,
policies, output patterns. That is declarative data, and a static format
(YAML/JSON) is a legitimate way to carry it; it is what those formats were
made for.

The line that matters is code vs. data, not Python vs. YAML. What must never
enter a cab definition, **in any format**:

- **Executable content.** cult-cargo's `dynamic_schema` -- a Python function
  imported and *executed* at cab-load time to compute a schema -- is the
  canonical example. See "Never import/execute an external Cab's own
  schema-generation code" below.
- **An expression or substitution language** (`=IFSET(...)`,
  `{recipe.name}-{info.suffix}`). `ParamMeta.implicit` is plain `str.format`
  against a step's own validated inputs, and deliberately nothing more.
- **Composition semantics needing their own resolver**, e.g. cult-cargo's
  package-scoped `_include` chains.

Do not over-read stimela-ninja's `AGENTS.md` here: its anti-YAML rule is scoped
to the **recipe/orchestration layer** throughout -- "Stimela 2.0's YAML-*recipe*
complexity" (L3), "not a return to YAML *orchestration* ... no expression
language or control-flow semantics" (L9), "that entire class of problem only
exists because YAML was the *orchestration* layer" (L13). Recipes are Python
because a DAG with wiring and control flow is a program. A cab's parameter table
is not, and that rule does not reach it.

**Today every cab is authored in Python**, as a `shinobi.Cab` object built in a
plain module under `src/dosho/cabs/` on shinobi's
`Cab`/`Policies`/`ParamMeta`/`ParamPattern` machinery -- see
`dosho._builder.define_cab` for the boilerplate-reduction helper. That is a
practical choice, not a prohibition: Python supplies dtypes, completion and
refactoring for free, and spares us maintaining a dialect and its loader. A
static YAML/JSON authoring path is permitted by the rule above, and would let
dosho ship as pure data with no shinobi dependency at all -- an open design
question, not a settled one. Whichever format a cab uses, the constraints above
bind it.

Not every tool can be a `Cab`, though, and the exception is genuinely code:
shinobi only ever executes
`flavour="binary"` cabs (real standalone executables, argv-built and
shelled out to). A tool that's actually a Python-package function call --
no standalone binary at all (CASA tasks are the running example:
`casatasks.listobs`, `casaplotms.plotms`) -- is instead a
`@shinobi.pystep`-decorated function (a `StepRef`, not a `Cab`), calling
`ctx.import_func("<task>", "<package>")` *inside the running container at
step-execution time*. That's architecturally distinct from -- and doesn't
violate -- "never import a cab package" below: the import happens at
execution time inside the container, on ordinary trusted Python the
pystep author wrote directly, not shinobi interpreting untrusted cab data
on the host at load time. Both shapes live side by side under
`src/dosho/cabs/`, and both are first-class for `Recipe.add_step` -- a
pipeline author (or `dosho.get(name)`) doesn't need to know or care which
one a given tool is. See `dosho/cabs/casatasks.py` for the pattern.

A pystep is a real function with a body, not a declarative pointer at a
published one -- `bdsf.py`'s `catalog` wraps `ctx.import_func("process_image",
"bdsf")` in a typed signature and its own orchestration. So pysteps stay Python
under any cab-format decision: the static-data rule above governs `Cab`
definitions, which is the half that *is* configuration. Note the balance when
weighing that decision -- pysteps currently outnumber binary cabs (79
`@shinobi.pystep` decorators against 43 `define_cab` calls), though most of the
former are thin `casatasks` pass-throughs.

## Never import/execute an external Cab's own schema-generation code

External cabs that generate parameters dynamically via embedded functions
are strictly forbidden, as are cabs whose plain-text source shinobi would
have to execute to make sense of -- see stimela-ninja's "Never
eval()/exec() a cab's `command`". Instead:

- **Per-instance dynamic parameter families** (CubiCal's `g1-solvable`,
  QuartiCal's `K.time_interval`, one family per caller-chosen term name)
  are expressed as a hand-authored `ParamPattern` -- transcribed once from
  the tool's own template/docs, not generated. This is static data, not
  code.
- **Dynamic output paths** (wsclean's `{prefix}-MFS-image.fits`-shaped
  outputs) are expressed as a `ParamMeta.implicit` string template,
  resolved by shinobi's `_fill_outputs` via plain `str.format` against a
  step's own validated inputs -- never eval, never an expression language.
  Only the handful of outputs a real pipeline actually wires as a
  dependency need a resolved `implicit` template; anything more exotic
  stays validation-only via `output_patterns`.

If a tool's dynamic behavior can't be expressed this way, don't invent a
new mechanism speculatively -- leave the field/output out and come back
when a real pipeline needs it (same "as small and boring as possible" gate
as stimela-ninja itself).

## YAML files use `.yaml`

Not `.yml`. One extension, chosen so nobody has to remember which file went
which way: `src/dosho/images.yaml` and every generated cab document under
`src/dosho/documents/` use it, and a new one should too.

Two exceptions, both because the name is not ours to pick. `.github/workflows/`
keeps `.yml` -- renaming those churns CI for nothing. And when prose refers to
an *upstream* file it uses that project's own spelling, so cult-cargo's
`cubical.yml` stays `cubical.yml`; renaming it in a sentence would be quietly
wrong about a file someone might go and look for.

## Container images

`src/dosho/images.yaml` is the **single source of truth** linking each cab to
its container image. It is a manifest: top-level `metadata` (`registry` =
`ghcr.io/shinobi-dosho`, `bundle_version`) plus an `images:` map keyed by the constant
cabs read (`images.WSCLEAN`, `images.CASA6`, ...). Each entry is either a
`ref:` (an existing published image, used verbatim -- the bootstrap state) or a
`build:` recipe (a dosho-built image, resolved to
`{registry}/{name}:{version}-{bundle_version}`). `src/dosho/images.py` loads
the manifest, resolves each entry to a full reference, and exposes it as a
module constant, so cab modules import it exactly as before -- plain data plus
resolution, which is exactly the shape the Core rule endorses.

**Provisioning overrides:** a deployment can repoint any image without editing
dosho, via (lowest→highest precedence) the manifest, a YAML file named by
`$DOSHO_IMAGES`, and per-tool `$DOSHO_IMAGE_<KEY>` env vars. Overrides are
applied at import time (a cab's `image` is baked when the cab is constructed),
so set them *before* the process starts.

The build/maintenance infrastructure around the manifest is landed: a
`dosho images` CLI (`list`/`build`/`push`/`build-plan`/`verify` -- see
`src/dosho/cli.py`), a `src/dosho/cargo/` Dockerfile tree (a shared
`pip/Dockerfile` template for pip-installable tools on `BASE_ASTRO`, plus a
dedicated per-tool dir where a tool needs one -- e.g. an era-pinned
interpreter, as for `ragavi`/`cubical`), and the `images.yml` CI workflow
that rebuilds+pushes exactly the images a push touched (dependents of a
changed base included) to `ghcr.io/shinobi-dosho`, modelled on cult-cargo
and stimela-classic but with CI-automated push. Every tool is dosho-built
except the deprecated `SIMMS_CLASSIC` (kept as a `ref:` until removal);
bumping a tool is editing one manifest entry. Note any `images.yaml` edit
makes every image a rebuild *candidate* in CI (shared metadata like
`bundle_version` may have moved), but `build-plan --missing-only` filters
candidates to tags actually absent from the registry -- so editing one
entry's version rebuilds just that image, a `bundle_version` bump rebuilds
everything (every tag moved), and a no-op manifest edit builds nothing.

## Repo layout

```
src/dosho/
  __init__.py      # re-exports get(), list_cabs()
  registry.py       # registered (real, possibly hyphenated) name ->
                     # "dosho.cabs:<attribute>"; get()/list_cabs(),
                     # registered under the "shinobi.cabs" entry-point group
                     # -- for a caller that only knows the tool's name at
                     # *runtime* (the CLI, shinobi.cabs discovery)
  images.yaml       # image manifest: metadata (registry, bundle_version) +
                     # per-tool `build:` recipe (or `ref:` for external images)
  images.py         # loads images.yaml, exposes each key as a module constant
  cli.py            # `dosho images` build/push/plan/verify driver over the manifest
  cargo/            # Dockerfile templates: shared pip/ one + per-tool dirs
  _builder.py        # define_cab() helper over Cab(...) + shinobi.loaders.build_model
  cabs/
    __init__.py      # re-exports every tool-level object by name, so
                      # `from dosho.cabs import wsclean` works directly --
                      # the write-time-known counterpart to registry.py
    <tool>.py         # single-command tool: exports one object named after
                       # the tool itself (e.g. wsclean.py's `wsclean = ...`)
    <family>.py         # multi-command tool: one module-level object per
                          # sub-command (e.g. casatasks.py's `listobs`,
                          # `mstransform`, ...; simms.py's `skysim`/
                          # `telsim`/`primary_beam`). Sharing a *name* does
                          # not make two tools one family -- pre-3.0 simms
                          # is a different tool and has its own module,
                          # simms_classic.py.
tests/
  test_registry.py
  test_<tool>.py     # one per ported cab: round-trips a representative param
                      # set through build_argv and checks real CLI token shape
```

Registering a new tool touches two places: the module itself under
`cabs/`, and both `cabs/__init__.py` (direct-import re-export) and
`registry.py` (`_ENTRIES`, the runtime-lookup name -- which may differ
from the Python attribute name if the tool's real name isn't a valid
identifier, e.g. `"simms-skysim"` -> attribute `skysim`).

## Before adding a cab

Port from the real tool's own `--help`/docs (or, for a `@shinobi.pystep`
wrapper, the real Python package's own function signature), cross-checked
against the matching cult-cargo YAML (if one exists) as a useful second
source -- but not copied from it blindly, since cult-cargo's own schema
for the hard cases (wsclean, cubical, quartical) has the known gaps
dosho exists to close. Every
ported tool gets a test: for a `Cab`, round-trip a representative param
set through `build_argv` and check the real CLI token shape; for a
pystep, check its `inputs_model` schema shape and that it wires into a
`Recipe` -- not just that the object constructs without error.

## Attribution: commit trailers yes, PR trailers no

A commit made with an assistant's help records it as a trailer on the
**commit message**, in the form

```
Assisted-by: <AGENT> <MODEL>
```

-- e.g. `Assisted-by: Claude Opus 5`, or `Assisted-by: Codex GPT-5`. One
line, last in the message, after any `Co-authored-by:` for real people.
`Assisted-by:` rather than `Co-authored-by:` on purpose: co-authorship
attributes the work to a second author, which GitHub then shows as a
contributor, and that is not what happened. A human authored the commit
and is answerable for it; the trailer says what helped.

**Pull request descriptions carry no trailer at all** -- no
`Assisted-by:`, no "Generated with", no tool badge. A PR body is
review material: it exists to tell a reviewer what changed and why, and
what to check. Provenance already lives on every commit the PR contains,
where it is attached to the specific change rather than repeated once
per PR, so a trailer in the description is duplication in the one place
that has no room for it. Assistants default to adding one; delete it.

Neither form is a substitute for the message itself. A commit that
explains a decision badly does not improve by naming the model that
helped make it -- see the existing history for the standard: what
changed, what it deviates from and why, and what a reviewer should not
assume held still.
