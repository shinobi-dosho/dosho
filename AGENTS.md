# dosho -- design conventions

`dosho` ("a shinobi's tool bag") is the native cab repository for shinobi
(stimela-ninja, Stimela 3.0). It exists because cult-cargo's YAML cab
format -- built for Stimela 2.0/scabha -- carries assumptions shinobi
deliberately refuses to support: `dynamic_schema` (a Python function
imported and *executed* at cab-load time to compute a real tool's schema),
package-scoped `_include` composition, and dtype coverage gaps that
silently degrade to `str`. Patching a compatibility loader around those
forever was costing more than it was saving. See stimela-ninja's own
`AGENTS.md` for the full design philosophy this repo inherits; this file
only states what's specific to authoring cabs here.

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

## Never import/execute a tool's own schema-generation code

Some real tools (wsclean, CubiCal, QuartiCal) only fully describe their own
CLI via a Python function that inspects other resolved parameter values at
run time. shinobi will never import and call that function -- see
stimela-ninja's "Never eval()/exec() a cab's `command`". Instead:

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

No image-building infrastructure here (no cult-cargo-style
bundle-manifest.md + Dockerfile tree) -- that machinery doesn't earn its
keep for a cab-schema repo. `src/dosho/images.py` is the single place
image references are pinned (reusing existing `quay.io/stimela2/*` images
where they already exist); bumping a tool's version is editing one
constant there. The repo's own git tag versions the cab set as a whole.

## Repo layout

```
src/dosho/
  __init__.py      # re-exports get(), list_cabs()
  registry.py       # registered (real, possibly hyphenated) name ->
                     # "dosho.cabs:<attribute>"; get()/list_cabs(),
                     # registered under the "shinobi.cabs" entry-point group
                     # -- for a caller that only knows the tool's name at
                     # *runtime* (the CLI, shinobi.cabs discovery)
  images.py         # pinned {tool: "quay.io/stimela2/<tool>:<tag>"} constants
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
against the matching cult-cargo YAML (if one exists) as a second source,
not copied from it blindly -- cult-cargo's own schema for the hard cases
(wsclean, cubical, quartical) is exactly what's being replaced. Every
ported tool gets a test: for a `Cab`, round-trip a representative param
set through `build_argv` and check the real CLI token shape; for a
pystep, check its `inputs_model` schema shape and that it wires into a
`Recipe` -- not just that the object constructs without error.
