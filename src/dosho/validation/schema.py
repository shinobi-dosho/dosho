"""Framework-neutral parameter metadata and argument policies."""

from __future__ import annotations

import re
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field, PrivateAttr, model_validator


class ParamMeta(BaseModel):
    """Per-field metadata a plain pydantic model can't express: the name
    the underlying tool actually expects (`nom_de_guerre`), a value always
    supplied by the cab itself rather than the caller (`implicit`),
    human-facing help (`info`), the cab dtype string (`dtype`, e.g.
    "File"/"MS") for a `ParamPattern` attr -- since a dynamically-named
    param has no declared field/type annotation for `path_fields` to
    inspect, this is how backends know to bind-mount its directory --
    `positional`: emitted as a bare value (no `--flag`), in
    field-declaration order, after every flagged/pattern-matched arg.
    `positional_head`: the same, but emitted *before* every flagged/
    pattern-matched arg instead of after -- real cult-cargo's own
    `cubical.yml` names this exact policy (`parset: {policies:
    {positional_head: true}}`) for a tool whose own CLI only recognises a
    leading bare token as a parset file to seed defaults from (CubiCal's
    `main.py`: `if len(sys.argv) > 1 and not sys.argv[1][0].startswith('-'):
    custom_parset_file = sys.argv[1]`); killMS's `kMS.py` has the identical
    `sys.argv[1]`-only check. A plain `positional` field there would always
    land after every `--flag`, which these two tools' own argv[1]-anchored
    parset detection can't see -- either raising ("Unexpected number of
    arguments", CubiCal) or silently not reading the parset at all
    (killMS, which never validates leftover-arg count). Setting both
    `positional` and `positional_head` on the same field is nonsensical;
    `positional_head` wins if both are set. Head positionals, like tail
    ones, are emitted in field-declaration order. -- and
    `repeat_as_tokens`: a list/tuple value is emitted as separate bare argv
    tokens (after the one flag occurrence, or as separate positional
    tokens) instead of joined into one comma-separated token -- real
    cult-cargo cabs express this as a per-field `policies: {repeat: list}`
    (see e.g. wsclean's `-size <w> <h>`/`-weight briggs <n>`, which need
    two separate argv tokens, not `"4096,4096"` as one).

    `write_path`: this string-typed input names a filesystem path the tool
    writes to. Two shapes, both covered: a *stem* products are built from
    (wsclean's `prefix`, ddfacet's `Output-Name`, which never exists as a
    file itself), and a *complete* path written directly (a cache directory,
    a logfile). It is a **declaration of intent only, and deliberately
    changes nothing about how the value is handled**. In particular it does
    not make the field a path: a path dtype here would be rewritten by
    `sandbox.absolutize_path_inputs` and the tool would then write outside
    the sandbox, which is precisely why the convention types these as
    strings (see `declared_output_dirs`). Mounting and pre-creation still
    come from the *output* side -- a path-typed output whose `implicit`
    template names this field, a `harvest` glob, or a `scratch` glob.

    What it buys is enforcement. That convention previously existed only as
    prose and authorial discipline: a write path nobody declared a target for
    produces no error, just products that stay inside the container or
    outside the harvest. Marking the field lets `Cab` check that something
    does declare it (see `Cab._write_path_declares_a_write_target`).

    A **path**-typed input may be marked too, and there it is the *only*
    thing that distinguishes the two identical-looking spellings of an
    output field that echoes a same-named input. ``mstransform`` takes
    ``outputvis`` and creates it; ``flagdata`` takes ``vis`` and rewrites
    the caller's own data; both declare that one name on `inputs_model` and
    on `outputs_model`, so `mutated_path_fields` -- and any other structural
    test -- sees one shape. Marking ``outputvis`` says which it is, and
    `sandbox.clear_stale_outputs` then clears the stale product before a
    re-run instead of leaving the tool to trip over it. The default (unmarked)
    is the safe reading: an echoed path is the caller's data and is never
    deleted. Note the marker still changes nothing about how the *value* is
    handled -- a path-typed one is anchored at the workspace by
    `sandbox.absolutize_path_inputs` exactly as before, which is what a
    complete destination path (as opposed to a stem) wants.

    `writable`: this path-typed input is one the tool must not modify
    (`writable: false`, cult-cargo/scabha's own key). The container
    backends bind-mount the directories a read-only input contributes
    `:ro`, and re-assert the input itself `:ro` at its own path when
    something writable shares that directory (`backends.container.bind_dir_modes`).
    `None` -- the default, and every Python-typed pystep input -- means
    unmarked, which is read as writable. Carried onto a declared field's
    `json_schema_extra` by the loaders (`readonly_path_fields` reads it
    from there, the same channel `abbreviation` rides); kept here as well
    because a `ParamPattern` attr has no declared model field for
    `readonly_path_fields` to inspect, and a dynamically-named input is
    exactly the case that wants the marker -- QuartiCal's
    `<term>.load_from` names a previous run's gain store, which the step
    reads and must not write back into.

    `choices`: the field's allowed values (cult-cargo/classic's `choices`
    key). A loader that sets this also narrows the field's real annotation
    on `inputs_model`/`outputs_model` to `typing.Literal[*choices]` (see
    `loaders._modelgen.narrow_choices`), so an out-of-set value fails
    pydantic validation the same way a wrong `dtype` would -- not merely
    documented in `info`. Kept here too (rather than only inferred from the
    model's own annotation) so a `ParamPattern` attr -- which has no
    declared model field for a dynamically-matched name -- can still carry
    it.

    `string_pattern`: a literal scalar string field's validation regex. Static
    loaders attach it to the generated pydantic annotation, preserving its
    JSON-schema pattern. Python authors use a constrained model field. It is
    not a path classifier, a dynamic attr validator, or executable cab code.

    `abbreviation`: a short single-dash CLI alias for the field's generated
    `--long-flag` (cult-cargo/classic's `abbreviation` key, e.g. simms'
    `ascii-sky` -> `-as`). Purely a `ninja run` convenience -- carried onto
    the field's `json_schema_extra` by the loaders so `clickutil.build_options`
    can emit the alias; it never affects the argv the tool actually receives
    (that still uses `nom_de_guerre`).

    On an *output* field, a string `implicit` containing `{name}`
    placeholders is resolved by `steps.dispatch._fill_outputs` as a
    `str.format` template against the step's prepared (validated) input
    values -- e.g. `implicit="{prefix}-MFS-image.fits"` derives a tool's
    output path from its own `prefix` input, without shinobi ever
    importing/executing the tool's own schema-generation code. A plain
    string with no `{...}` is used as a literal constant, same as on an
    input field.
    """

    nom_de_guerre: str | None = None
    implicit: Any = None
    info: str | None = None
    positional: bool = False
    positional_head: bool = False
    repeat_as_tokens: bool = False
    dtype: str | None = None
    min_length: int | None = Field(default=None, ge=0)
    max_length: int | None = Field(default=None, ge=0)
    choices: list[Any] | None = None
    nullable: bool | None = None
    string_pattern: str | None = None
    abbreviation: str | None = None
    write_path: bool = False
    writable: bool | None = None


class Policies(BaseModel):
    """How a cab's parameters are turned into command-line arguments.

    `key_value`/`repeat` mirror real cult-cargo cab-level policy keys
    verbatim (e.g. QuartiCal's `policies: {key_value: true, repeat: '[]',
    prefix: ''}`): `key_value=True` means a hydra-style single
    `name=value` argv token instead of two tokens (`--name`, `value`);
    `repeat="[]"` means a list value formats as one bracketed-literal
    token (`solver.terms=[K,G]`) instead of `list_sep`-joining. Distinct
    from a per-field `ParamMeta.repeat_as_tokens` (real per-field
    `policies: {repeat: list}`, e.g. wsclean's bare `-size 4096 4096`),
    which is a field-level override and takes precedence when set.

    `explicit_true`/`explicit_false` also mirror real cult-cargo cab-level
    policy keys verbatim (e.g. CubiCal's `policies: {explicit_true: true,
    explicit_false: false}`): by default a `True` boolean value emits as a
    bare flag (`--flag`, argparse `store_true`-style) and `False` is
    omitted entirely. Some real CLIs (CubiCal's own optparse-derived
    parser among them) instead expect every boolean option to always take
    an explicit value token -- passing a bare flag with no value corrupts
    parsing of everything after it, since the parser consumes the next
    token as that flag's value. `explicit_true=True` emits `--flag true`
    (two tokens, `"true"`/`"false"` lowercase) instead of a bare flag when
    the value is `True`; `explicit_false=True` does the same instead of
    omitting the flag when the value is `False`. Each direction is
    independent (CubiCal only needs `explicit_true`, never
    `explicit_false`), and this applies uniformly to declared fields and
    `ParamPattern`-matched dynamic ones (e.g. CubiCal's own
    per-Jones-term `g-solvable`).

    `true_token`/`false_token` are what those two tokens actually say.
    Lowercase `"true"`/`"false"` (the default) is what CubiCal's parser
    reads, but it is not universal: DDFacet and killMS share a parset
    reader (`DDFacet.Parset.ReadCFG`) that parses `"0"`/`"1"` as ints and
    `"True"`/`"False"` as bools, and leaves an unrecognised `"false"` as a
    *string* -- which, being non-empty, is truthy. `--Mask-Auto false`
    there switches the mask **on**. So the pair of tokens is a cab-level
    policy of its own (`policies: {explicit_true: true, explicit_false:
    true, true_token: '1', false_token: '0'}` for those two), alongside
    the `explicit_*` switches rather than instead of them: `explicit_*`
    decides *whether* a value token is emitted, these decide what it
    reads.

    They spell a boolean in *every* value position, not only after a flag:
    a `key_value` cab's single `name=value` token, a positional, an
    element of a joined or bracketed list, one occurrence of a repeated
    flag. Python's own `str(True)` is `"True"`, so a path that missed this
    emitted a spelling no policy ever asked for
    (`policies._scalar_token` is the one place that decides).
    """

    prefix: str = "--"
    replace: dict[str, str] = Field(default_factory=dict)
    list_sep: str = ","
    repeat_list: bool = False
    key_value: bool = False
    repeat: str | None = None
    explicit_true: bool = False
    explicit_false: bool = False
    true_token: str = "true"
    false_token: str = "false"

    def arg_name(self, name: str) -> str:
        """Build the CLI flag name for a parameter name.

        Args:
            name: The parameter's declared/matched name.

        Returns:
            `name` with each `replace` substitution applied, prefixed by
            `prefix` (e.g. `"--"`).
        """
        for old, new in self.replace.items():
            name = name.replace(old, new)
        return f"{self.prefix}{name}"


MetaT = TypeVar("MetaT", bound=ParamMeta)


class ParamSegment(BaseModel, Generic[MetaT]):
    """One level of a dotted/dashed dynamic-parameter name. A "shape"
    segment carries only `regex` -- soft validation, no metadata, for a
    level whose actual values can't be enumerated at cab-authoring time
    (e.g. a solver term name like QuartiCal's `K`/`G`). The "meta" segment
    -- always the last one in a `ParamPattern` -- carries `attrs`: the
    known, enumerable part, each value with its own ParamMeta.
    """

    regex: str | None = None
    attrs: dict[str, MetaT] | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> ParamSegment:
        if (self.regex is None) == (self.attrs is None):
            raise ValueError("ParamSegment needs exactly one of `regex` or `attrs`")
        return self


class ParamPattern(BaseModel, Generic[MetaT]):
    """A family of inputs whose names are `<segment><separator><segment>...`,
    e.g. QuartiCal's `K.type`/`G.time_interval` or cubical's `g1-solvable`/
    `g-time-int`. Matched as one anchored regex assembled from `segments`:
    exactly one segment is `attrs` (the known, enumerable part, each value
    with its own ParamMeta -- dtype/nom_de_guerre/info); every other segment
    is a `regex` (soft shape-validation of a level that can't be enumerated
    ahead of time). See AGENTS.md for the motivating tools.

    The `attrs` segment is usually last (cubical/QuartiCal: an
    unenumerable term name followed by a known attribute, `g1.solvable`),
    but doesn't have to be -- wsclean's dynamic output names are the
    opposite shape, a known/enumerable image type followed by an
    open-ended qualifier tail (`dirty.per-band`,
    `restored.i.per-interval.mfs`), so `attrs` there is the *first*
    segment. Only one segment may carry `attrs`; the rest must all be
    `regex`.

    A segment regex that should behave as an unconstrained "match anything"
    level (the old design's `prefix`) should be written lazily (`.+?`, not
    `.+`): with more than one registered attr, an eager `.+` prefers the
    *shortest* attr that completes an overall match, which is wrong when
    one attr is itself a suffix of another (e.g. "int" vs "time-int" with
    separator "-") -- `.+?` tries the shortest prefix first, which is
    exactly "prefer the longest/most specific attr".
    """

    separator: str = "."
    segments: list[ParamSegment[MetaT]]

    _compiled: re.Pattern = PrivateAttr()
    _attrs_index: int = PrivateAttr()

    @model_validator(mode="after")
    def _compile(self) -> ParamPattern:
        attrs_indices = [i for i, seg in enumerate(self.segments) if seg.attrs is not None]
        if len(attrs_indices) != 1:
            raise ValueError("a ParamPattern must have exactly one segment that carries `attrs`")
        object.__setattr__(self, "_attrs_index", attrs_indices[0])
        parts: list[str] = []
        for i, seg in enumerate(self.segments):
            group = f"seg{i}"
            if seg.attrs is not None:
                # Longest-first: makes a longer attr win over a shorter one
                # that's also a valid alternative at the same split point.
                alt = "|".join(re.escape(a) for a in sorted(seg.attrs, key=len, reverse=True))
                parts.append(f"(?P<{group}>{alt})")
            else:
                parts.append(f"(?P<{group}>{seg.regex})")
        pattern = re.escape(self.separator).join(parts)
        object.__setattr__(self, "_compiled", re.compile(f"^{pattern}$"))
        return self

    def matches(self, name: str) -> MetaT | None:
        """Check whether `name` matches this pattern and look up its metadata.

        Args:
            name: A dynamic parameter name to test, e.g. `"g1.solvable"`.

        Returns:
            The `ParamMeta` for the matched `attrs` segment value, or
            `None` if `name` doesn't match the compiled pattern.
        """
        m = self._compiled.fullmatch(name)
        if not m:
            return None
        return self.segments[self._attrs_index].attrs[m.group(f"seg{self._attrs_index}")]


def parameter_name(field_meta: dict[str, ParamMeta], field: str) -> str:
    """Resolve one tool-facing name using its declared metadata."""
    meta = field_meta.get(field)
    return (meta.nom_de_guerre if meta else None) or field


def match_patterns(patterns: list[ParamPattern[MetaT]], name: str) -> MetaT | None:
    """Return metadata from the first matching pattern, in declaration order."""
    for pattern in patterns:
        if (meta := pattern.matches(name)) is not None:
            return meta
    return None
