# dosho as a data registry: static cabs, optional shinobi

**Status:** v3 — **partly implemented.** Steps 0, 1 and the comparator have
landed; §9 step 3 is the gate; §8.1 should be answered before §9 step 5.
**Context:** spans this repo and stimela-ninja (`shinobi`). §9 marks which steps
land where.

**Change log**

- **v2 → v3 (spike against the code).** Steps 0 and 1 shipped (dosho #42,
  stimela-ninja #76), the comparator shipped (dosho #44), and a spike on three
  representative cabs then found that §4.6's generator cannot work as written.
  Everything below was measured, not reasoned about.
  1. **`dtype` is not recoverable from a built `Cab`, and 16% of fields carry
     one that matters (§4.6).** `_modelgen.dtype_to_type` is many-to-one:
     `Path` ← `File`/`MS`/`Directory`/`URI`, `list[Path]` ←
     `List[File]`/`List[MS]`/`List[Directory]`. Measured across dosho's 42
     cabs: **1523 declared fields, 237 (16%) collapse to `Path`**. v2 said the
     generator "imports each of the 42 cabs and serializes it" -- that
     flattens every one of those 237 to whatever the emitter guesses.
  2. **The comparator cannot catch it.** Both sides are already `Path` by the
     time it looks, so a migration that silently turned every `MS` into `File`
     would pass the gate. The gate is weaker than v2 claimed, for exactly this
     one class of information, and no amount of improving the comparator fixes
     it.
  3. **Recording the dtype on `ParamMeta` does not rescue it -- tried, and it
     is architecturally impossible.** `field_meta` is one dict keyed by field
     name, built as `{**input_meta, **output_meta}` (`_builder.py:286`), so a
     field that is both an input and an output has a single `ParamMeta`. Three
     real cabs need two different dtypes for one name: `killms`
     `solutions_sols_dir` (`str` in, `Directory` out), `quartical-plotter`
     `output_path` (`str`/`Directory`), `spimple-binterp` `output_filename`
     (`str`/`File`). The attempt failed 20 tests, all from the output-side
     `ParamMeta` clobbering the input side's `nom_de_guerre`.
  4. **Reading the source instead is feasible, and that is now measured rather
     than hoped.** An AST pass over `src/dosho/cabs/*.py` resolves **42/42**
     `define_cab` calls and **1437 input fields with zero non-literal specs**.
     Every field dict is either a literal or a module-level name bound to one
     (`_FIELDS: dict[str, FieldSpec] = {...}` -- an `AnnAssign`, which the
     first version of the extractor missed).
  **Fixed:** §4.6 now generates from source, and the gate is two checks rather
  than one -- the comparator for everything the `Cab` knows, plus a direct
  string comparison of dtypes for the part it forgets. The second is nearly
  free once the generator reads source, because the document's dtypes are then
  the source's dtypes by construction.

- **v1 → v2 (review round 1).** Independent review attacked v1 against both
  trees. The goal survived; v1's proof mechanism, its API-preservation story and
  its arithmetic did not. In order of severity:
  1. **The gate could never open (§0, §4.6, §9 step 3).** v1 asserted that
     round-tripping could be proven by `assert loaded == original`, because
     "pydantic compares structurally". It does not, for this shape:
     `Scope.inputs_model` holds a *class object* built by `pydantic.create_model`
     (`_modelgen.py`), which returns a fresh class per call, so equality falls
     back to identity. Measured: **0 of 42** cabs compare equal to an
     identically-rebuilt copy. The gate as written fails every cab on day one
     whether or not the conversion is lossless. **Fixed:** §4.6 now specifies a
     structural comparator and treats *it* as the load-bearing artifact.
     Validated before writing: 42/42 equal when rebuilt, 0 false positives
     across all 861 distinct pairs.
  2. **`experimental` cannot be expressed as a document (§2, §4.7).** v1's
     "entire authoring surface" list stopped one line short of `_builder.py`'s
     real signature and missed `scratch` and `experimental`. The second is not
     merely a missing field: it drives a module-global side effect
     (`EXPERIMENTAL_CABS[name]`, `_builder.py:245`) that `registry.get()` reads
     on every lookup (`registry.py:101`). Nothing would populate it once ddfacet
     and killms are documents. **Fixed:** §4.7 carries it in the name index.
  3. **PEP 562 does not intercept submodule imports (§4.3).** Verified:
     `from pkg import X` reaches `__getattr__`; `import pkg.X` raises
     `ModuleNotFoundError` regardless. v1 discussed only the package-level case.
     **Fixed:** §4.3 states the real blast radius, which is narrower than review
     assumed — both *documented* import forms survive — and records the fallback.
  4. **The counts were wrong.** 42 `define_cab` and 68 pysteps by AST, not 43
     and 79; grep had counted docstring prose. 42 + 68 = 110, which reconciles
     with the `__all__` count v1 separately verified and then contradicted.
  5. **Step 0 is not free (§9).** `Scope.scratch` landed after the v0.1.0b4 tag,
     and CI resolves shinobi through the very redirect step 0 deletes — so
     deleting it drops CI to a release without `scratch`, silently degrading
     ddfacet/killms/casatasks. **Fixed:** step 0 now depends on a shinobi
     release.
  6. **Image resolution disagreed with itself** about whether key-based lookup
     arrives with the dialect (step 2) or the flip (step 4), and never said how
     the generator recovers a manifest key from an already-resolved reference.
     **Fixed:** §4.5.
  Smaller: §9 step 6 cited `docs/cab-format-rule` as though the `AGENTS.md` Core
  rule were already amended — it was a *branch*, not a file, and review was right
  that on the base commit the Core rule still banned this outright. It has since
  merged (PR #39), so the rule now reads "a cab definition is parameter
  configuration, not code" and this design is an instance of it rather than an
  exception; v2 is rebased onto that main. §4.3 conflated `__dir__` with
  `__all__` (`import *` consults `__all__`; `registry._entries()` reads it
  directly). §6 gains the image-resolution duplication review flagged. The
  mixed-module counterexample review used against §4.3 — `simms.py` carrying one
  `Cab` and three pysteps — is also gone: PR #40 gave pre-3.0 simms its own
  module, and no module in the tree now mixes the two.

---

## 0. Status

Today `dosho` cannot be installed without `shinobi`: `_builder.py` imports
`from shinobi import Cab` at module scope, and every cab module imports
`_builder`. This proposes inverting that — the binary-cab half of dosho becomes
static documents with no runtime dependency on anything, and `shinobi` becomes
the *optional* thing you add in order to load and run them.

The load-bearing claim, and the thing most worth attacking:

1. **A binary cab's Python definition and a static document are
   interconvertible without loss, and the two checks that prove it are between
   them sufficient (§4.6).** The claim is a test, not an argument. It is now
   two tests, because one is provably not enough: the comparator (shipped,
   dosho #44) covers everything the built `Cab` knows, and a direct dtype-string
   comparison covers the 16% of fields whose `dtype` the `Cab` has already
   forgotten by the time anything can compare them.

   Attack either half. Find two `Cab`s the comparator calls equal that behave
   differently. Find something a document cannot express that neither check
   would notice — `experimental` was one such (§4.7), `dtype` was the second
   (found by spike, and it invalidated v2's gate outright), and the interesting
   question is what the third is. The pattern to look for is information that
   exists in the Python source but not in the object the source builds.

Two things this deliberately does **not** claim:

- **Pysteps do not become data.** A pystep is a function with a body —
  `bdsf.py`'s `catalog` wraps `ctx.import_func("process_image", "bdsf")` in a
  typed signature and its own orchestration. They stay Python (§4.1), and they
  outnumber binary cabs 68 to 42.
- **This adds no orchestration surface.** The dialect describes one tool's
  parameters and nothing else: no composition, no expression language, no
  control flow. See `AGENTS.md`'s Core rule, which this design is an instance
  of rather than an exception to.

---

## 1. Problem

1. **A registry requires its consumer.** `dosho` depends on `stimela-ninja`
   (`pyproject.toml:16`), and redirects it to git main via `[tool.uv.sources]`
   (`:39-40`) so the two develop together. That redirect is what makes
   stimela-ninja unable to lock dosho in *any* dependency group: uv reports

   ```
   Requirements contain conflicting URLs for package `stimela-ninja`:
     - file:///…/stimela-ninja (editable)     ← the root project
     - git+https://…/stimela-ninja@main       ← dosho's redirect
   ```

   and since uv locks all dependency-groups together, that breaks `uv lock` for
   everyone, not just anyone wanting the examples. Verified by reproducing both
   halves: a bare A→B→A cycle locks in 7 ms; adding the redirect produces the
   error above. Deleting four lines fixes the *symptom* (§7.1) — the structural
   oddity is that a catalogue of tool definitions cannot be installed without
   the framework that runs them.

2. **A Python registry can only be consumed by Python.** Cab definitions are
   useful as *files* — fetched, diffed, pinned, served, vendored into an image.
   `ninja download --cult-cargo` exists because cult-cargo's definitions are
   data. dosho's are not.

3. **Import is eager.** `dosho/cabs/__init__.py` imports all 32 cab modules and
   constructs every `Cab` at package-import time; its own docstring records this
   as a deliberate, accepted tradeoff. §4.3 makes it lazy as a side effect.

## 2. What already exists (the spine)

- **The provider protocol** (`shinobi/cabs.py`): a package registers a module
  under the `shinobi.cabs` entry-point group exposing `get(name) -> Cab |
  StepRef` (raising `KeyError` to fall through to the next provider) and
  `list_cabs() -> list[str]`. Providers are `ep.load()`ed only when something
  asks, so discovery is already lazy across providers.
- **`dosho.registry`**: a `name -> "module:attr"` table resolved by
  `importlib.import_module` on demand (`registry.py:114-126`), plus
  `_NAME_OVERRIDES` for the ~25 tools whose registered name differs from their
  Python attribute name. Lazy per cab.
- **`dosho.cabs`**: the write-time API — `from dosho.cabs import wsclean`
  yields a `Cab`. 254 lines of re-exports. §4.3 must preserve this exactly.
- **`_builder.define_cab`**: the entire authoring surface, and therefore the
  exact list a dialect must cover — `name`, `command`, `image`, `fields`,
  `outputs`, `input_mutability`, `policies`, `input_patterns`,
  `output_patterns`, `flavour`, `wranglers`, `info`, `sandbox`, `harvest`,
  **`scratch`, `experimental`** (`_builder.py:155-172`), where a field is
  `FieldSpec = tuple[str, bool, Any] | tuple[str, bool, Any, ParamMeta]`. The
  last two are the ones v1 missed by stopping its citation two lines early, and
  `experimental` is not an ordinary field — see §4.7.
- **`shinobi.loaders` already exports `build_model` and `sanitize_unique`**
  (`loaders/__init__.py:14`) — the model construction `_builder` itself uses. A
  document loader reuses them unchanged rather than reimplementing anything.
- **shinobi already loads two foreign cab dialects** (`loaders/cultcargo`,
  `loaders/stimela_classic`). "Build a `Cab` from a document" is established
  machinery, not new.
- **`images.yaml` is already data**, with `images.py` resolving each key to a
  full reference and applying the `$DOSHO_IMAGES` / `$DOSHO_IMAGE_<KEY>`
  override chain. `AGENTS.md` already exempts it from any authoring-format
  argument.

## 3. Assumptions

- The 42 binary cabs are pure data. Asserted, not assumed — §9 step 3 proves it
  before anything depends on it.
- Pysteps stay Python, indefinitely.
- `shinobi` remains the only consumer that needs to *build* a `Cab`. Other
  consumers (a catalogue browser, a diff tool, CI) want the document.

## 4. Design

### 4.1 Two halves, split at the distribution boundary

| half | contents | depends on |
|---|---|---|
| **data** | the 42 binary cabs as documents, `images.yaml`, a generated name index (§4.7) | nothing |
| **code** | the 68 pysteps, `_builder` (if kept), the `dosho images` CLI | `shinobi` |

One repository, two distributions. Whether the code half is a separate
distribution or an extra of the same one is §8.1. Both halves register under
`shinobi.cabs`, so `shinobi.cabs.get(name)` keeps working across the seam and
callers never learn which half a tool came from — the property `dosho/cabs/
__init__.py` already promises.

### 4.2 The provider protocol gains a document form

`shinobi.cabs.get` currently calls `module.get(name)` and expects a live object.
Add an optional second entry:

```python
def get_document(name: str) -> tuple[str, str]:   # (dialect, raw text)
def list_cabs() -> list[str]:
```

`shinobi.cabs.get` tries `get_document` first, falls back to `get`, and builds
the `Cab` itself when it got a document. Existing providers that expose only
`get` keep working untouched — this is additive, and it is the whole shinobi-
side surface change.

Returning **raw text plus a dialect tag**, rather than a parsed mapping, is what
lets the data half depend on nothing at all: it never needs a YAML parser,
because it never parses. It reads a file and hands over bytes.

### 4.3 `from dosho.cabs import wsclean` keeps working, lazily

`dosho/cabs/__init__.py` becomes a PEP 562 module `__getattr__`:

```python
def __getattr__(name: str):
    doc = _lookup(name)  # index + file read, no shinobi
    from shinobi.cabs import build_document  # imported only now

    cab = build_document(*doc)
    globals()[name] = cab  # cache; __getattr__ won't fire again
    return cab
```

Three consequences, all good:

- The package-level write-time API is unchanged for anyone with shinobi
  installed.
- Without shinobi, `import dosho.cabs` still succeeds; only attribute access
  fails, and it fails with a message naming `pip install stimela-ninja` rather
  than a bare `ModuleNotFoundError` from an unrelated import.
- Import stops being eager. §1.3's accepted tradeoff disappears rather than
  being restated.

**What this does not cover, stated plainly: submodule imports.** PEP 562
intercepts attribute access on an already-imported module; it cannot intercept
`import dosho.cabs.wsclean`, which the import machinery resolves by looking for
a file. Verified — `from pkg import X` reaches `__getattr__`, `import pkg.X`
raises `ModuleNotFoundError` regardless of what `__getattr__` would have
returned. Once `wsclean.py` becomes a document, `from dosho.cabs.wsclean import
wsclean` breaks.

The blast radius is narrower than it first looks. `dosho/cabs/__init__.py`
advertises exactly two forms, and **both survive**: `from dosho.cabs import
wsclean` is package-level, and `from dosho.cabs.casatasks import listobs` names
a module with zero `define_cab` calls — pure pysteps, which stay Python. What
breaks is the undocumented form, submodule-importing one of the 42 binary cabs.

Treat that as a real but acceptable break, called out in the changelog. If it
bites, the fallback is generating one two-line shim module per binary cab
(`from dosho.cabs import wsclean as wsclean`) — cheap, mechanical, and it
restores the path exactly; it is not the default only because 42 generated files
exist to serve an interface nobody was told to use.

Two separate obligations, which v1 ran together: `__all__` must stay a plain
literal list — `from … import *` consults it, and `registry._entries()` reads it
directly (`registry.py:79-84`) — *and* `__dir__` should be defined for
completion. Neither substitutes for the other.

### 4.4 The dialect: one document, one cab, no composition

A new `shinobi.loaders.dosho`. It is the third dialect, and deliberately the
smallest of the three:

- **No `_include`, no `_use`, no package scoping.** cult-cargo's composition is
  the single largest source of complexity in `loaders/cultcargo.py` and the
  thing `AGENTS.md` names as a disqualifier.
- **No expression language.** `ParamMeta.implicit` stays plain `str.format`,
  exactly as `dispatch.py:649-651` resolves it today.
- **One file, one cab.** No merging, no inheritance, no ordering rules.

The document maps 1:1 onto `define_cab`'s parameters, so the dialect needs no
design of its own beyond a serialization of what already exists:

```yaml
name: breizorro
command: breizorro
image: BREIZORRO          # a key into images.yaml, not a resolved ref (§4.5)
flavour: binary
info: "mask creation and manipulation ..."
policies: {prefix: "--", repeat_list: ...}
inputs:
  restored-image: {dtype: File, required: false, info: "..."}
  threshold:      {dtype: float, required: false, default: 6.5, info: "..."}
outputs:
  outfile: {dtype: File, required: false}
input_patterns: [...]
output_patterns: [...]
input_mutability: {...}
wranglers: {...}
sandbox: null
harvest: [...]
```

Raw parameter names stay raw (`restored-image`), and `sanitize_unique` derives
the field name and `nom_de_guerre` exactly as `_builder._resolve` does now —
so the sanitisation rule lives in one place and cannot drift, per `AGENTS.md`'s
DRY section, which already records `cultcargo`/`worker_schema` drifting apart
on precisely this kind of shared rule.

### 4.5 Images: the manifest stays, resolution moves

A cab document names an image **key** (`image: WSCLEAN`), not a resolved
reference. The loader resolves it against `images.yaml` and applies the
`$DOSHO_IMAGES` / `$DOSHO_IMAGE_<KEY>` chain.

This fixes a current wart rather than porting it: `images.py`'s own docstring
notes overrides are applied at *import* time and a cab's `image` is baked when
the cab is constructed, "so they must be set before the process starts, not
toggled at runtime". Resolving at load time makes an override a per-run fact,
which is what a deployment override should have been.

The manifest ships in the data half. Resolution is loader-side, so the data half
still parses nothing.

**Key-based lookup arrives with the dialect (§9 step 2), not with the flip.** v1
left this ambiguous between two steps; it belongs to the dialect, because the
dialect is what defines `image:` as a key. The flip (step 4) then changes
nothing about images beyond deleting the Python that used to resolve them.

**The generator recovers the key from source, not from the resolved string.** A
cab module writes `images.BREIZORRO` (`breizorro.py:161`), so the key is
recoverable exactly by reading the `image=` argument's AST — no reverse-mapping
of resolved references, and therefore no sensitivity to whatever
`$DOSHO_IMAGES`/`$DOSHO_IMAGE_<KEY>` happened to be set when the generator ran.
A reverse map built from `images.py`'s constants is a useful cross-check, but it
is ambiguous whenever two keys resolve to one reference and must not be the
primary mechanism.

Consequently the §4.6 comparison runs on a **resolved** document — the loader
applies the manifest before the comparator sees the `Cab` — so both sides carry
a full reference and `image` compares like any other scalar.

### 4.6 Migration is generated from source, and proven by two checks

1. A one-off script reads `src/dosho/cabs/*.py` **as source** and serializes
   each cab to the dialect. Nobody hand-writes 42 documents -- and nobody
   imports them either, for the reason in "why source" below.
2. A golden test checks each document two ways, because one check cannot cover
   everything: the comparator against the Python cab it came from, **and** a
   direct comparison of the document's dtype strings against the source's.
3. Only once all 42 pass both does the document become the source of truth and
   the Python definitions get deleted.

**Why source, and not the imported cabs.** v2 said to import and serialize.
That silently discards `dtype`. `_modelgen.dtype_to_type` is many-to-one:

```
Path        <- File, MS, Directory, URI
list[Path]  <- List[File], List[MS], List[Directory]
list[int]   <- List[int], list:int        (spelling only; harmless)
```

Measured over dosho's 42 cabs: **1523 declared fields, of which 237 (16%)
collapse to `Path`**. Serializing from a built `Cab` cannot tell you which of
the four a field was, so it must guess, and every guess it gets wrong is a
tool's declared interface quietly rewritten.

Recording the dtype on `ParamMeta` looks like the fix and is not: `field_meta`
is `{**input_meta, **output_meta}` (`_builder.py:286`), one entry per field
*name*, so a field appearing on both sides gets one `ParamMeta`. Three cabs
need two dtypes for one name (`killms` `solutions_sols_dir` is `str` in and
`Directory` out; likewise `quartical-plotter` `output_path` and
`spimple-binterp` `output_filename`). Attempting it failed 20 tests, all from
the output-side meta clobbering the input side's `nom_de_guerre` -- which is a
pre-existing fragility in that merge, worth fixing on its own.

Reading source is feasible and measured: an AST pass resolves **42/42**
`define_cab` calls and **1437 input fields with zero non-literal specs**. Each
field dict is a literal or a module-level name bound to one -- note
`_FIELDS: dict[str, FieldSpec] = {...}` is an `AnnAssign`, not an `Assign`,
which the first extractor missed and which is the kind of detail that decides
whether this step works at all.

**Why two checks.** The comparator covers everything the built `Cab` knows,
which is most of it, and is already proven (dosho #44: 42/42 on rebuilds, 0
false positives across 861 pairs). It cannot cover `dtype`, because both sides
are `Path` before it looks. The second check closes exactly that gap and costs
almost nothing: if the generator emits the source's dtype strings verbatim,
comparing them back is string equality.

**Step 2 cannot use `==`, and this is the design's sharpest edge.** `Cab` is a
pydantic model whose `inputs_model`/`outputs_model` fields hold *class objects*
produced by `pydantic.create_model`, which returns a fresh class per call.
Equality on a field whose value is a class falls back to identity, so two
byte-identically-specified cabs never compare equal. Measured on the real tree:

```
binary Cabs in __all__              : 42
pydantic ==, rebuilt identically    : 0/42 equal
```

v1 asserted the opposite and made that assertion the gate. What is needed
instead is a structural comparator: everything except the two model fields via
`model_dump(exclude=...)`, and the models themselves by the shape
`create_model` was given —

```python
def model_shape(m):
    return {
        n: (f.annotation, f.default, f.is_required(), f.alias, f.json_schema_extra)
        for n, f in m.model_fields.items()
    }
```

Validated against the tree before being written here:

```
comparator, rebuilt identically     : 42/42 equal
comparator, distinct pairs          : 0 false positives out of 861
```

Annotations compare by value (`Literal["a","b"] == Literal["a","b"]`), so the
`choices` narrowing `_modelgen.narrow_choices` performs is covered, as are
`alias` (the `nom_de_guerre` sanitisation) and `json_schema_extra` (the
`abbreviation` short flags).

Note what this shifts. The comparator is now the load-bearing artifact: a
comparator that ignores a field silently blesses a lossy dialect. It must
therefore be *tested against known-unequal pairs*, not only known-equal ones —
the 861-pair sweep above is that test, and it belongs in the suite, not just in
this document.

A cab that cannot round-trip is a **finding**, not an obstacle to route around:
it means the dialect is missing something, or that cab is not pure data. §4.7 is
what happened the first time this question was asked seriously.

### 4.7 `experimental` is not a field, and needs the name index

`define_cab(..., experimental="reason")` does two things beyond storing a value:
it prefixes `info` with `"EXPERIMENTAL:"`, and it registers the reason in a
module-global `EXPERIMENTAL_CABS` (`_builder.py:245`) that `dosho.registry`
reads on every lookup to warn once per cab (`registry.py:101`). The first half
is data and survives serialization. The second is a Python side effect with no
document equivalent — once `ddfacet` and `killms` are documents, nothing
populates that dict and the warnings silently stop.

This is exactly the counterexample §0 invited, and it is the reason the data
half ships a **generated name index** rather than just a directory of documents.
The index already has to exist to answer `list_cabs()` without parsing anything
(§4.2); it carries one more column:

```
wsclean       wsclean.yml
ddfacet       ddfacet.yml     experimental="DDFacet support is limited by … "
```

`registry` reads the reason from the index — no shinobi, no parse, no import —
and warns exactly as it does today. `scratch`, the other parameter v1 missed, is
by contrast an ordinary list of paths and needs nothing special.

The general lesson is worth stating for whoever extends `define_cab` next: a
parameter that mutates module state, rather than describing the tool, is the one
shape this design cannot carry. There is currently one.

## 5. Invariants

1. The data half imports nothing at runtime — not `shinobi`, not `yaml`. It
   reads files and returns bytes (§4.2), and answers `list_cabs()` and the
   `experimental` warning from the generated index (§4.7).
2. `from dosho.cabs import X` returns an object equal to what it returns today,
   whenever shinobi is installed (§4.3).
3. No document carries executable content, an expression or substitution
   language, or composition semantics needing a resolver (`AGENTS.md` Core
   rule).
4. Pysteps are untouched. No pystep becomes a document.
5. Name sanitisation and model construction happen in exactly one place
   (`shinobi.loaders`), never reimplemented dosho-side.
6. The provider-protocol change is additive: a provider exposing only `get`
   behaves as it does today.
7. The comparator (§4.6) is tested against known-*unequal* pairs as well as
   known-equal ones. A comparator only ever shown to return `True` proves
   nothing.

## 6. Known weaknesses

1. **A third dialect is real, permanent maintenance**, and `AGENTS.md`'s DRY
   section documents that this project's dialects have already drifted apart
   once. Mitigated by the dialect being strictly smaller than the other two and
   by invariant 5, but not eliminated.
2. **Authoring loses Python's typing.** Free dtypes, completion and refactoring
   were the stated reason for choosing Python. A YAML author gets none of it.
   Partly answered by a JSON Schema (§8.2) and by the round-trip test, but this
   is a genuine regression in authoring ergonomics and should be weighed against
   the distribution win rather than waved at.
3. **The dependency win covers the smaller half by count** — 42 `define_cab`
   cabs against 68 pysteps, which together are exactly the 110 names
   `dosho.cabs` re-exports. By *value* it is likely the larger half (the binary cabs
   are the portable ones), but the count is the honest number.
4. **Version skew.** Two distributions from one repo can be installed at
   mismatched versions. Needs at minimum a compatibility assertion at load time.
5. **`dosho images build` stays in the code half**, so the image *build*
   tooling still depends on shinobi even though the manifest it reads is data.
   Acceptable, but it means "dosho is data-only" is true of the cab half, not of
   the repository.
6. **Two call sites will resolve manifest keys**: the `dosho images` CLI
   (code half) and the loader (§4.5). That is the same key→ref+override
   computation in two places — the precise shape `AGENTS.md`'s DRY section
   records `cultcargo` and `worker_schema` having already drifted into. It must
   ship as one shared implementation with both callers routed through it, and
   this design does not currently say where that implementation lives. Open.
7. **The comparator can bless a lossy dialect.** §4.6 shifts the load from
   pydantic onto code we write; a field it forgets to compare is a field the
   dialect may silently drop. Invariant 7 is the mitigation, not a cure. And
   there is at least one thing it *structurally* cannot check -- `dtype` --
   which is why §4.6's gate is two checks and not one.
8. **`field_meta`'s output-over-input merge is lossy** (`_builder.py:286`).
   `{**input_meta, **output_meta}` replaces whole `ParamMeta` objects, so any
   cab declaring output-side metadata for a name that is also an input silently
   drops that input's `nom_de_guerre`, `info` and the rest. No cab hits it
   today -- `test_killms` documents the hazard in a comment rather than
   guarding it -- but the spike hit it immediately, and an attribute-wise merge
   would remove the trap. Independent of this design; worth fixing regardless.
9. **28 of cubical's 37 pattern attrs carry no `dtype`**, including
   `load-from`, `xfer-from`, `save-to`, `fix-dirs`. `ParamMeta.dtype` is the
   *only* thing that marks a pattern-matched input as file-like
   (`sandbox.py:152`, `container.py:572` -- both consult it solely for names
   not in `path_fields`), so those are neither bind-mounted nor
   sandbox-anchored. If they are paths, that is a live bug, and it predates
   this design. Worth checking before the migration bakes the current state
   into documents.

## 7. Alternatives considered and rejected

1. **Delete the `[tool.uv.sources]` redirect and stop there.** Cheapest fix,
   verified to work, and *not exclusive with this design* — it should probably
   happen regardless (§9 step 0). Rejected as a complete answer only because it
   leaves a registry that cannot be installed without its consumer.
2. **Keep Python cabs, make shinobi an optional dependency.** Does not work:
   every cab module imports `_builder`, which imports `shinobi` at module scope.
   Making the import lazy would mean each cab module deferring construction,
   i.e. rewriting all 42 anyway — with none of the distribution benefit.
3. **Reuse the cult-cargo dialect instead of defining one.** Rejected: it drags
   in `_include`/`_use` composition and package scoping, the things dosho exists
   to be free of, and `AGENTS.md` now names as disqualifiers.
4. **Convert pysteps too, as declarative `{package, func, kwargs}` entries.**
   Works for the thin `casatasks` pass-throughs, not for `bdsf`/`fitstoolz`/
   `simms`, which have real bodies. Splitting pysteps into "declarative enough"
   and "not" is where a dialect starts growing semantics. Rejected for now;
   revisit only if the thin wrappers become a maintenance problem in their own
   right.

## 8. Open questions

1. **Two distributions, or one with an extra?** Two (`dosho`, `dosho-pysteps`)
   makes the dependency boundary real and lets a site install cabs without
   Python-package tooling. One with `dosho[pysteps]` is simpler to release and
   keeps a single version. *Leaning: two, built from one repo — the boundary is
   the point.*
2. **Does the dialect get a JSON Schema?** It costs a file and buys editor
   validation for authors, partly answering §6.2. *Leaning: yes, generated from
   the same source as the loader so they cannot disagree.*
3. **Does `ninja download` learn to fetch dosho bundles?** The machinery exists
   for cult-cargo. Out of scope here, but the data half is what makes it
   possible, and it is a large part of why this is worth doing.
4. **What becomes of `define_cab`?** Deleted, or kept in the code half as an
   authoring aid that *emits* a document? *Leaning: keep it, emitting — it is
   how §4.6's generator works, and it preserves a typed authoring path for
   anyone who wants one.*

## 9. Implementation order

0. **[shinobi] Cut a release carrying `Scope.scratch`, then [dosho] drop the
   `[tool.uv.sources]` redirect** (§7.1). v1 called the deletion "independent,
   tiny, not gated on anything". It is not: `scratch` landed after the v0.1.0b4
   tag, and dosho's CI resolves shinobi *through the redirect*
   (`.github/workflows/ci.yml`, `uv sync --group dev`). Deleting it drops CI to
   the released 0.1.0b4, which has no `Scope.scratch` — so `ddfacet`, `killms`
   and `casatasks` silently degrade from a real bind-mount to the
   warning-only path, in exactly the two cabs already flagged as fragile.
   Sequence it: release shinobi ≥ the scratch commit, bump dosho's constraint,
   *then* delete the redirect. Still independent of steps 1-6.
1. **[shinobi] Provider protocol** -- **done** (stimela-ninja #76):
   `get_document` tried before `get`, plus `build_document(dialect, text)`.
   Additive; no dosho change. Note it is *not* a prerequisite for the gate --
   it is what step 4 needs at runtime. The gate needs step 2 and step 3 only.
2. **[shinobi] `loaders/dosho.py`**: the dialect, reusing `build_model` /
   `sanitize_unique`. Tested against hand-written fixtures before any migration.
3. **[dosho] The comparator, then the source-reading generator, then the
   golden test** over all 42 cabs, with Python still the source of truth.
   - The comparator is **done** (dosho #44), with its own tests: 42/42 on
     rebuilt cabs *and* 0 false positives across the 861 distinct pairs, before
     it was trusted to judge a single document.
   - The generator reads `src/dosho/cabs/*.py` as source (§4.6). The AST pass is
     measured feasible: 42/42 calls, 1437 input fields, zero non-literal specs.
   - The golden test runs **both** checks per cab (§4.6).

   **This is the gate.** If any cab fails either check, stop and reassess -- do
   not route around it, and do not loosen a check to make it pass. Depends on
   step 2 for the loader; independent of step 1.
4. **[dosho] Flip the source of truth**: documents become canonical, Python cab
   definitions deleted, `dosho/cabs/__init__.py` becomes `__getattr__`/`__dir__`
   (§4.3), image resolution moves loader-side (§4.5).
5. **[dosho] Split the distributions**, drop `stimela-ninja` from the data
   half's dependencies. Answer §8.1 first.
6. **[both] Docs**: `docs/concepts/authoring.rst` and shinobi's
   `docs/concepts/cabs.rst` for the new dialect. `AGENTS.md`'s Core rule is
   already done — PR #39 replaced the blanket "no YAML authoring path" ban with
   "a cab definition is parameter configuration, not code", which is what makes
   this design permissible in the first place. It was a genuine prerequisite,
   not a formality.

Steps 1–2 are useful on their own — a document-shaped provider protocol is a
better protocol whether or not dosho ever uses it. Step 0 is independent of them
but is now a two-part sequence, not a four-line deletion.

The order above is not the dependency order, and a reviewer of v1 was right to
ask. The gate (step 3) needs step 2's loader and nothing else; step 1 is for
step 4's runtime resolution. Read it as: **2 and 3 gate the design, 1 and 0 are
independent, 4 and 5 follow.**

Two prerequisites are already satisfied: the Core rule (PR #39, above), and the
absence of any module mixing a `Cab` with a pystep — PR #40 gave pre-3.0 simms
its own module, which was the last one, and a mixed module is the single shape
that cannot follow either half of the split.
