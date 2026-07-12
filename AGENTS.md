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

**Cabs are authored directly in Python, not parsed from a YAML dialect.**
Every tool is a `shinobi.Cab` object (or several) built in a plain Python
module under `src/dosho/cabs/`, using shinobi's existing
`Cab`/`Policies`/`ParamMeta`/`ParamPattern` machinery -- see
`dosho._builder.define_cab` for the boilerplate-reduction helper. There is
no YAML authoring path and none should be added: a YAML dialect is exactly
the kind of "grows its own semantics" surface stimela-ninja's `AGENTS.md`
warns against.

Not every tool can be a `Cab`, though: shinobi only ever executes
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

## Container images

`src/dosho/images.yaml` is the **single source of truth** linking each cab to
its container image. It is a manifest: top-level `metadata` (`registry` =
`ghcr.io/shinobi-dosho`, `bundle_version`) plus an `images:` map keyed by the constant
cabs read (`images.WSCLEAN`, `images.CASA6`, ...). Each entry is either a
`ref:` (an existing published image, used verbatim -- the bootstrap state) or a
`build:` recipe (a dosho-built image, resolved to
`{registry}/{name}:{version}-{bundle_version}`). `src/dosho/images.py` loads
the manifest, resolves each entry to a full reference, and exposes it as a
module constant, so cab modules import it exactly as before -- this is plain
data plus resolution, not a cab schema, so it doesn't fall under the "no YAML
authoring path" rule above.

**Provisioning overrides:** a deployment can repoint any image without editing
dosho, via (lowest→highest precedence) the manifest, a YAML file named by
`$DOSHO_IMAGES`, and per-tool `$DOSHO_IMAGE_<KEY>` env vars. Overrides are
applied at import time (a cab's `image` is baked when the cab is constructed),
so set them *before* the process starts.

dosho **is** growing image build/maintenance infrastructure (a `dosho images`
CLI + a `cargo/` Dockerfile tree + CI that builds and pushes to
`ghcr.io/shinobi-dosho`, with an auto-generated readthedocs catalog) so cabs, images,
registry, and docs stay linked off this one manifest -- modelled on cult-cargo
and stimela-classic but with CI-automated push. It lands incrementally; until a
tool is dosho-built, its manifest entry `ref:`s an existing image. Bumping a
tool is editing one manifest entry.

## Repo layout

```
src/dosho/
  __init__.py      # re-exports get(), list_cabs()
  registry.py       # registered (real, possibly hyphenated) name ->
                     # "dosho.cabs:<attribute>"; get()/list_cabs(),
                     # registered under the "shinobi.cabs" entry-point group
                     # -- for a caller that only knows the tool's name at
                     # *runtime* (the CLI, shinobi.cabs discovery)
  images.yaml       # pinned {tool: "quay.io/stimela2/<tool>:<tag>"} data
  images.py         # loads images.yaml, exposes each key as a module constant
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
                          # `telsim`/`simms_classic`)
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
