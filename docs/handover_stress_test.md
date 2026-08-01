# Handover: the cab documents, before a pipeline stress test

**State:** dosho `dacd8f5`, stimela-ninja `489af96`. Both green, nothing open.
**Next:** run a real caracal pipeline against this. Then release.

---

## What changed

dosho's 43 binary cabs are no longer Python. They are YAML documents under
`src/dosho/documents/`, loaded by `shinobi.loaders.yaml_cab` and served through
`dosho.registry`. The 68 pysteps are still Python, because a pystep is a
function with a body and cannot be data.

shinobi is now the `dosho[run]` extra rather than a dependency. `import dosho`
loads zero shinobi modules; `dosho.cabs.<tool>` and `dosho.get(...)` need the
extra and say so if it is absent.

`docs/design_data_registry.md` is the design, and its §9 lists the five steps,
all of which are done. What follows is only what matters for testing it.

## Why a stress test is the right next thing

The migration was gated on a round-trip: serialise each cab, load it back,
compare. That gate closed at 43/43, and it was rigorous about the thing it
measured -- every field, every `FieldInfo` attribute, `model_config`, patterns,
dtypes checked against source separately because the built `Cab` forgets them.

**It measured structural equivalence of `Cab` objects, and nothing else.** It
never ran a cab. Everything downstream of construction is untested against
document-built cabs:

* `build_argv` -- flags, positionals, `nom_de_guerre` names, list joining,
  `repeat_as_tokens`, the `positional_head` cases cubical and killMS need;
* container bind mounts -- `declared_output_dirs`, `path_fields`, and the
  `write_path` inputs that mount nothing themselves;
* sandbox anchoring and `harvest` -- whether products come back;
* `scratch` -- whether caches are mounted and *not* rescued;
* output filling -- `implicit` templates resolving against real inputs;
* pattern-matched inputs actually reaching a tool as argv.

Two of those were already found broken *after* the gate said 43/43 (see
"What the gate missed" below), which is the honest reason to distrust it as
evidence of anything but structural equality.

## What to run, and what to watch

A pipeline that touches all four shapes is worth more than a long one that
touches one. In rough priority:

**1. wsclean.** The `write_path` case: `prefix` is a string input, deliberately
not a path, and nothing mounts it. The write target is declared by the output
side (`implicit: "{prefix}-dirty.fits"`). Watch that products land on the host
and not inside the container, especially with an *absolute* prefix outside the
working directory. This is the single most likely thing to be wrong.

**2. cubical or quartical.** The pattern case. Their inputs models carry
`extra="allow"` so dynamically-named parameters (`g1-solvable`,
`K.time_interval`) validate at all. Pass some. If they are rejected, the cab
lost its patterns or its extra policy -- shipped broken once already, see
below.

**3. A CASA task and a simms step.** The pysteps, which did *not* change shape
but are now imported lazily through the registry rather than eagerly at
`import dosho.cabs`. Watch that `ctx.import_func` still resolves inside the
container.

**4. ddfacet or killMS.** The experimental warning should fire exactly once per
name per process, and their `scratch` declarations should mount without being
harvested.

**Also worth a glance:** every image reference. Documents name images by
manifest key (`image: WSCLEAN`), resolved at load time through
`registry.loader_options()` so `$DOSHO_IMAGES` overrides still apply. An
unresolved key reaches the runtime as a bare image name and fails at pull time.
`tests/test_documents.py` asserts every document resolves to something with a
`/` or `:` in it, but only the real runtime proves the reference is right.

## What is verified, and how

| property | evidence |
|---|---|
| 43 documents build to `Cab`s identical to the Python they replaced | the round-trip gate, before the Python was deleted |
| every declared dtype survives, including the 236 file-like ones | compared against source, which the built `Cab` cannot express |
| documents load, resolve images, declare a dtype per parameter | `tests/test_documents.py`, per document |
| index and documents agree about what exists | same |
| `import dosho` needs no shinobi | measured in a subprocess; also installed into a clean venv by hand |
| `dosho.cabs.<tool>` without shinobi fails with a message naming `dosho[run]` | same |
| the comparator notices every field attribute pydantic defines | mutation sweep, `tests/test_cab_compare.py` |

## What the gate missed

Both found by using its output rather than reading it, and both fixed before
the Python was deleted. They are the reason to treat a green suite as a floor:

* **`dtype`.** `dtype_to_type` is many-to-one -- `Path` covers
  File/MS/Directory/URI -- so a built `Cab` cannot say which a field was. 237
  of 1523 declared fields (16%) collapse. The comparator could not see the loss
  because both sides were already `Path`. Fixed by generating from source and
  checking dtypes as strings.
* **`model_config["extra"]`.** A cab with input patterns needs `extra="allow"`
  or it rejects every dynamic parameter it exists for. The comparator compared
  `model_fields` and not `model_config`, so cubical and quartical passed 43/43
  while being unusable. Found by dosho's own cubical test.

A deliberate sweep afterwards found eight further attributes the comparator
ignored (`title`, `frozen`, `exclude`, `repr`, `deprecated`, `examples`,
`serialization_alias`, `validation_alias`) plus the model class name. None were
reachable from the dialect, which is exactly why a hand-written list stays
wrong quietly. It is generic over `FieldInfo.__slots__` now.

## Before testing

caracal2 pins both projects to git `main` but its lock names older commits, so
a test run picks up whatever the lock says rather than what is described here.
Refresh it first:

```
uv lock --upgrade-package stimela-ninja --upgrade-package dosho
```

Worth checking the pins afterwards: at the time of writing caracal2's lock held
dosho at PR #53 -- ten commits back, before the registry flip, the deletion and
the extra -- and stimela-ninja at `0.1.0b4`, which does not satisfy caracal2's
own `>=0.1.0b5`. uv does not re-check a version constraint against a
git-pinned rev, so that contradiction is silent.

## The release, after

**dosho needs a version bump, and it is not cosmetic.** dosho still declares
`0.1.0b3`, which is also what PyPI has published since 26 July. Those two are
materially different packages:

| | PyPI `0.1.0b3` | git main, also `0.1.0b3` |
|---|---|---|
| cabs | 43 Python modules | 43 YAML documents |
| shinobi | hard dependency | `[run]` extra |
| `import dosho` | 29 shinobi modules | zero |

So `dosho>=0.1.0b3` is satisfied by either. Today the `[tool.uv.sources]` git
entry decides which; drop it and a consumer silently falls back to July's
package. `0.1.0b4` clears it; a case can be made for `0.1.0c1`, since
`dosho.cabs` changed shape and a dependency became optional.

Release process is the one stimela-ninja uses: bump `pyproject.toml`, tag **the
bump commit** (tagging before it is what broke the 0.1.0b5 release -- the
workflow's version guard caught it), push the tag.

Once released, caracal2 can pin `dosho>=0.1.0b4` and mean it, and the git
source becomes a development convenience rather than the only thing keeping it
off a stale package.

## Open, not blocking

* **`docs/design_remote_venv.md` §8.1 is answerable now.** It asked whether a
  real recipe repo keeps a lock, since that decides whether
  `ninja run --remote --venv sync` serves anyone. caracal2 has a committed
  `uv.lock` and pins dosho and stimela-ninja as ordinary git dependencies, so
  option (a) -- a recipe-side lock -- is not merely viable but already the
  case. Options (b) and (c) can be dropped, and §4.2's "look for a lock beside
  the target file" should probably look at the recipe repo's root instead.
* **`ninja run --remote` venv provisioning** (steps 2-5 of that design) is
  otherwise unstarted. Step 1, the shell precedence fix, shipped as
  stimela-ninja #85.
* **`cab_index.yaml` is hand-maintained.** Adding a cab means adding its entry:
  `attr` always, `document` for a binary cab, `module`/`symbol` for a pystep,
  `experimental` if it is. `tests/test_documents.py` checks it against both the
  documents and the modules, so a mistake fails rather than silently hides a
  tool.
