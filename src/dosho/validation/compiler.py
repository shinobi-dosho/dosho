"""Static scabha cab parsing, composition and parameter compilation."""

from __future__ import annotations

import functools
import re
import warnings
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from .compiled import (
    CabSpec,
    CompiledCab,
    CompiledParamMeta as ParamMeta,
    ParamPattern,
    ParamSegment,
)
from .exceptions import CabLoadError
from .modelgen import (
    COMMON_LEAF_KEYS,
    DtypeError,
    ResolutionCycleGuard,
    TypeBinding,
    build_model,
    contain_include,
    deep_merge,
    length_constraints,
    merge_field_meta,
    normalize_required_default,
    resolve_directive,
    resolve_package_root,
    resolve_use,
    sanitize_unique,
    validate_choices,
    validate_nullable,
)
from .schema import Policies


def load_file(
    path: str | Path,
    *,
    package_roots: dict[str, Path] | None = None,
    images: dict[str, str] | None = None,
) -> dict[str, CabSpec]:
    """Load a YAML cab definition file into inert `CabSpec` records.

    Args:
        path: Path to the YAML cab definition file.
        package_roots: Mapping of package name to filesystem root, used to
            resolve `_include` directives that reference other packages.
        images: Mapping of image *key* to full reference. See `loads`.

    Returns:
        A dict mapping cab name to its parsed `CabSpec` record. Call
        `compile_cab` to build parameter models and formatting metadata.

    Raises:
        CabLoadError: If composition cannot be resolved, including an
            ``_include`` or ``_use`` cycle. Cycle errors name the closed path.
    """
    path = Path(path)
    roots = package_roots or {}
    raw = _load_raw(path.resolve(), roots)
    resolved = resolve_use(raw, raw, error=CabLoadError)
    cabs_section = resolved.get("cabs", resolved)
    return {name: parse_document(name, spec, images=images) for name, spec in cabs_section.items()}


def loads(
    text: str,
    *,
    package_roots: dict[str, Path] | None = None,
    images: dict[str, str] | None = None,
) -> dict[str, CabSpec]:
    """Parse cab defs from a YAML string. Supports ``_use`` (resolved
    against the document itself) and package-scoped ``_include`` (resolved
    against `package_roots`), but not a plain relative-path ``_include``,
    since there's no base directory to resolve a relative file path against.

    ``images`` maps an image *key* to its full reference, for a document that
    names images symbolically (``image: WSCLEAN``) rather than by a baked-in
    reference. Caller-supplied for the same reason ``package_roots`` is:
    shinobi has no manifest of its own and will not go looking for one. A cab
    repository passes its own -- dosho's `images.yaml` is exactly this -- so a
    deployment's overrides still decide the reference at load time instead of
    it being fixed when the document was written.

    An image string absent from the mapping is left alone, because a
    literal reference is the older and still-valid form (cult-cargo's files
    carry ``quay.io/stimela2/...`` directly). A key that is simply misspelled
    therefore reaches the runtime as an image name and fails there -- loudly,
    at pull time, which is the safe direction: the alternative rejects every
    legitimate bare name (``ubuntu``) to catch a typo.

    Raises:
        CabLoadError: If composition cannot be resolved, including an
            ``_include`` or ``_use`` cycle. Cycle errors name the closed path.
    """
    roots = package_roots or {}
    raw = yaml.safe_load(text) or {}
    raw = resolve_directive(
        raw, "_include", lambda entry: _include_entry_to_dict(entry, None, roots)
    )
    resolved = resolve_use(raw, raw, error=CabLoadError)
    cabs_section = resolved.get("cabs", resolved)
    return {name: parse_document(name, spec, images=images) for name, spec in cabs_section.items()}


_PKG_INCLUDE_RE = re.compile(r"^\((?P<pkg>[\w.]+)\)(?P<rest>.*)$")
_INCLUDE_CYCLES = ResolutionCycleGuard("_include")


def _resolve_package_root(dotted: str, package_roots: dict[str, Path]) -> Path:
    """This dialect's `CabLoadError`-flavoured `resolve_package_root`. See
    that helper (and this module's docstring) for why `importlib` is never
    involved.
    """
    return resolve_package_root(dotted, package_roots, error=CabLoadError)


def _include_entry_to_dict(
    entry: Any,
    base_dir: Path | None,
    package_roots: dict[str, Path],
    containment_root: Path | None = None,
) -> dict[str, Any]:
    """One `_include` list entry -> its fully-loaded (and itself
    recursively `_include`-resolved) dict. Three real shapes:
    - plain relative path string (`"base.yml"`), only valid with a `base_dir`
    - combined package+path string (`"(cultcargo.genesis.cubical)schema.yaml"`)
    - package + file-list dict (`{"(cultcargo)": ["genesis/cult-cargo-base.yml"]}`)

    `containment_root` is the package root the enclosing include chain
    entered through (`None` at the top level, where a plain relative include
    is unconstrained). Every package-scoped hop sets it to its own package
    root and every file below that hop is checked against it -- see
    `_modelgen.contain_include`.
    """
    if isinstance(entry, str):
        if m := _PKG_INCLUDE_RE.match(entry):
            if not m.group("rest"):
                raise CabLoadError(f"package-scoped _include {entry!r} has no filename")
            pkg_dir = _resolve_package_root(m.group("pkg"), package_roots)
            target = contain_include(
                pkg_dir / m.group("rest"), pkg_dir, entry=entry, error=CabLoadError
            )
            return _load_raw(target, package_roots, pkg_dir)
        if base_dir is None:
            raise CabLoadError(
                f"relative-path _include {entry!r} has no base directory to resolve against (loads() only supports package-scoped _include entries)"
            )
        target = base_dir / entry
        if containment_root is not None:
            target = contain_include(target, containment_root, entry=entry, error=CabLoadError)
        return _load_raw(target.resolve(), package_roots, containment_root)
    if isinstance(entry, dict) and len(entry) == 1:
        ((key, files),) = entry.items()
        if (m := _PKG_INCLUDE_RE.match(key)) and not m.group("rest"):
            pkg_dir = _resolve_package_root(m.group("pkg"), package_roots)
            merged: dict[str, Any] = {}
            for f in files if isinstance(files, list) else [files]:
                target = contain_include(pkg_dir / f, pkg_dir, entry=f, error=CabLoadError)
                merged = deep_merge(merged, _load_raw(target, package_roots, pkg_dir))
            return merged
    raise CabLoadError(f"unsupported _include entry {entry!r}")


def _load_raw(
    path: Path, package_roots: dict[str, Path], containment_root: Path | None = None
) -> dict[str, Any]:
    """Read, parse, and recursively `_include`-resolve one file. Cached
    (keyed on the resolved path, `package_roots`, and the active
    `containment_root`, all three of which change how the file's own nested
    includes resolve) for the same reason as
    `worker_schema._load_include_file`: a cab library commonly has many
    files `_include`-ing the same shared base (cult-cargo's own
    `cult-cargo-base.yml`/`vars` files) or `_use`-ing each other, so without
    this every referencing file re-reads and re-parses it from disk. Safe
    to cache: `resolve_directive`/`deep_merge` never mutate their inputs, so
    the same returned dict can be reused (and further deep_merged from,
    which always builds a new dict) by every caller. `package_roots` is
    turned into a hashable, order-independent key since a plain dict can't
    be an `lru_cache` argument directly.
    """
    path = path.resolve()
    with _INCLUDE_CYCLES.enter(path, error=CabLoadError):
        return _load_raw_cached(path, tuple(sorted(package_roots.items())), containment_root)


@functools.cache
def _load_raw_cached(
    path: Path, roots_key: tuple[tuple[str, Path], ...], containment_root: Path | None
) -> dict[str, Any]:
    package_roots = dict(roots_key)
    data = yaml.safe_load(path.read_text()) or {}
    return resolve_directive(
        data,
        "_include",
        lambda entry: _include_entry_to_dict(entry, path.parent, package_roots, containment_root),
    )


# shinobi-native per-field keys. They must be here as well as read in
# `_collect`: `_is_section` decides leaf-vs-section by whether a mapping has
# *any* known param-spec key, so a spec carrying only a new key would
# otherwise be mistaken for a nested CLI section and vanish.
_SHINOBI_LEAF_KEYS = {"write_path", "mutable"}

_LEAF_SPEC_KEYS = (
    COMMON_LEAF_KEYS | {"nom_de_guerre", "mkdir", "element_choices"} | _SHINOBI_LEAF_KEYS
)


def parse_document(
    name: str, spec: dict[str, Any], *, images: dict[str, str] | None = None
) -> CabSpec:
    """Capture one composed static document; never import its schema hooks."""
    return CabSpec(name=name, document=spec, images=images or {})


def compile_cab(
    spec: CabSpec, *, type_bindings: Mapping[str, TypeBinding] | None = None
) -> CompiledCab:
    """Compile parameter models with explicit caller-supplied dtype bindings."""
    try:
        return _build_cab(spec.name, spec.document, {}, spec.images, type_bindings=type_bindings)
    except DtypeError as exc:
        raise CabLoadError(f"cab '{spec.name}': {exc}") from exc


def _build_cab(
    name: str,
    spec: dict[str, Any],
    package_roots: dict[str, Path],
    images: dict[str, str] | None = None,
    *,
    type_bindings=None,
) -> CompiledCab:
    cache = spec.get("cache")
    if cache is not None and not isinstance(cache, bool):
        raise CabLoadError(f"cab '{name}': 'cache' must be true, false or null")
    image = spec.get("image")
    if isinstance(image, dict):
        image = image.get("name")
    # A symbolic key resolves through the caller's mapping; anything else is
    # already a reference (see `loads`).
    if images and isinstance(image, str):
        image = images.get(image, image)

    flavour = spec.get("flavour", "binary")
    if isinstance(flavour, dict):
        flavour = flavour.get("kind", "binary")

    if "command" not in spec:
        raise CabLoadError(f"cab '{name}' has no 'command' (check its _use references)")

    if spec.get("dynamic_schema"):
        warnings.warn(
            f"cab '{name}' uses dynamic_schema ({spec['dynamic_schema']!r}), which "
            "Dosho doesn't resolve -- it's a dotted reference to a Python function "
            "that would need importing and calling to get the real schema. Any static "
            "'inputs:'/'outputs:' present are used as-is, but may be incomplete "
            "relative to the tool's actual interface. Check whether dosho (the native "
            "shinobi cab repository) already has a real port of this cab.",
            stacklevel=2,
        )

    policies_spec = spec.get("policies") or {}
    wranglers = ((spec.get("management") or {}).get("wranglers")) or {}

    in_fields, field_meta, input_mutability = _collect(spec.get("inputs") or {})
    out_fields, out_meta, _out_mutability = _collect(spec.get("outputs") or {})
    out_meta = _drop_output_writable(name, out_meta)

    in_choices = {field: meta.choices for field, meta in field_meta.items() if meta.choices}
    out_choices = {field: meta.choices for field, meta in out_meta.items() if meta.choices}

    # Field hints that ride `json_schema_extra` rather than the annotation,
    # because their consumer reads the *model*, not `field_meta`:
    # `abbreviation` is a CLI-only alias, so `clickutil.build_options` can emit
    # a `-<abbrev>` short flag; `writable` is the read-only-mount marker
    # `steps.schema.readonly_path_fields` looks for (which is how a cab's
    # `writable: false` reaches `bind_dir_modes` at all). Both only meaningful
    # on inputs -- outputs are neither CLI options nor bind-mounted read-only.
    in_extras: dict[str, dict[str, Any]] = {}
    for field, meta in field_meta.items():
        extra: dict[str, Any] = {}
        if meta.abbreviation:
            extra["abbreviation"] = meta.abbreviation
        if meta.writable is not None:
            extra["writable"] = meta.writable
        if extra:
            in_extras[field] = extra

    input_patterns = _param_patterns(spec.get("input_patterns"), cab=name, key="input_patterns")
    inputs_model = build_model(
        f"{name}_Inputs",
        in_fields,
        type_bindings=type_bindings,
        choices=in_choices,
        lengths={
            field: {
                key: getattr(meta, key)
                for key in ("min_length", "max_length")
                if getattr(meta, key) is not None
            }
            for field, meta in field_meta.items()
            if meta.min_length is not None or meta.max_length is not None
        },
        nullable={
            field: meta.nullable for field, meta in field_meta.items() if meta.nullable is not None
        },
        error=CabLoadError,
        extras=in_extras,
        string_patterns={
            field: meta.string_pattern
            for field, meta in field_meta.items()
            if meta.string_pattern is not None
        },
        allow_extra=bool(input_patterns),
    )
    outputs_model = build_model(
        f"{name}_Outputs",
        out_fields,
        type_bindings=type_bindings,
        choices=out_choices,
        lengths={
            field: {
                key: getattr(meta, key)
                for key in ("min_length", "max_length")
                if getattr(meta, key) is not None
            }
            for field, meta in out_meta.items()
            if meta.min_length is not None or meta.max_length is not None
        },
        nullable={
            field: meta.nullable for field, meta in out_meta.items() if meta.nullable is not None
        },
        error=CabLoadError,
        string_patterns={
            field: meta.string_pattern
            for field, meta in out_meta.items()
            if meta.string_pattern is not None
        },
    )
    return CompiledCab(
        name=name,
        command=spec["command"],
        info=spec.get("info"),
        image=image,
        flavour=flavour,
        policies=Policies(**policies_spec),
        # `allow_extra` when the cab has input patterns, matching
        # `dosho._builder.define_cab`. A pattern exists precisely to accept
        # names no field declares -- cubical's `g1-solvable`, QuartiCal's
        # `K.time_interval` -- so without it the model rejects every value the
        # pattern was written to match, and the pattern silently does nothing.
        inputs_model=inputs_model,
        outputs_model=outputs_model,
        framework_declarations={
            key: spec[key]
            for key in ("dataset_accesses", "fits_accesses", "derived_reads")
            if key in spec
        },
        # Output metas merged over input ones, the same way
        # `dosho._builder.define_cab` composes them, so a cab built from a
        # document and the same cab built in Python agree. Without the output
        # half an `implicit` output template is silently dropped: nothing
        # resolves the output's value, and `declared_output_dirs` finds no
        # write directory to mount, which is how a tool's products end up
        # inside the container. `merge_field_meta` merges a dual-declared
        # name attribute-wise instead of replacing the whole `ParamMeta`:
        # the sharp edge that used to be inherited here dropped the input
        # side's `write_path` for exactly the fields that carry it.
        field_meta=merge_field_meta(field_meta, out_meta),
        wranglers=wranglers,
        input_mutability=input_mutability,
        input_patterns=input_patterns,
        output_patterns=_param_patterns(
            spec.get("output_patterns"), cab=name, key="output_patterns"
        ),
        sandbox=spec.get("sandbox"),
        harvest=list(spec.get("harvest") or []),
        scratch=list(spec.get("scratch") or []),
        cache=cache,
    )


def _is_section(value: dict) -> bool:
    """A non-empty dict under `inputs:`/`outputs:` is a stimela2-style
    section (to be flattened into dotted `section.param` field names, e.g.
    cubical's `data: {ms: {...}, column: {...}}` -> `data.ms`/`data.column`)
    rather than a leaf param spec, when none of its own top-level keys look
    like a known param-spec key. An empty dict is always a (minimal) leaf
    spec, never an empty section -- this preserves the existing bare `key:`
    (implicit `{}`) leaf convention.
    """
    return bool(value) and not (set(value) & _LEAF_SPEC_KEYS)


def _param_patterns(raw: Any, *, cab: str, key: str) -> list[ParamPattern]:
    """Read `input_patterns:`/`output_patterns:` into `ParamPattern`s.

    A pattern is a `separator` plus an ordered list of `segments`; each segment
    is either a `regex` (a level that cannot be enumerated) or `attrs` (the
    known level, each attr a param spec in its own right). `ParamPattern`'s own
    validator enforces the real rule -- exactly one segment carries `attrs` --
    so this only has to produce the shape and let it complain.

    Errors name the cab and the key, because a pattern is the one part of a cab
    a reader cannot check by eye against the tool's `--help`.
    """
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise CabLoadError(
            f"cab '{cab}': '{key}' must be a list of patterns, got {type(raw).__name__}"
        )
    patterns: list[ParamPattern] = []
    for i, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise CabLoadError(
                f"cab '{cab}': '{key}[{i}]' must be a mapping, got {type(entry).__name__}"
            )
        segments_raw = entry.get("segments")
        if not isinstance(segments_raw, list) or not segments_raw:
            raise CabLoadError(f"cab '{cab}': '{key}[{i}]' needs a non-empty 'segments' list")
        segments: list[ParamSegment] = []
        for j, seg in enumerate(segments_raw):
            if not isinstance(seg, dict):
                raise CabLoadError(
                    f"cab '{cab}': '{key}[{i}].segments[{j}]' must be a mapping, got {type(seg).__name__}"
                )
            attrs_raw = seg.get("attrs")
            if attrs_raw is None:
                segments.append(ParamSegment(regex=seg.get("regex")))
                continue
            if not isinstance(attrs_raw, dict):
                raise CabLoadError(
                    f"cab '{cab}': '{key}[{i}].segments[{j}].attrs' must be a mapping, got {type(attrs_raw).__name__}"
                )
            # An attr always gets a ParamMeta, even an empty one. Unlike a
            # declared field, where an all-default meta carries no information
            # and is dropped, the *set of attr names* is what the pattern
            # matches on -- dropping an empty one would delete the attr.
            attrs = {
                name: _param_meta(spec or {}, with_dtype=True) for name, spec in attrs_raw.items()
            }
            segments.append(ParamSegment(attrs=attrs))
        try:
            patterns.append(ParamPattern(separator=entry.get("separator", "."), segments=segments))
        except ValueError as exc:
            raise CabLoadError(
                f"cab '{cab}': '{key}[{i}]' is not a valid pattern -- {exc}"
            ) from exc
    return patterns


_DEFAULT_PARAM_META = ParamMeta()


def _drop_output_writable(cab: str, out_meta: dict[str, ParamMeta]) -> dict[str, ParamMeta]:
    """Take `writable` off the *output* side of a cab's metas.

    `writable` describes an input the tool must not modify. It says nothing
    about an output -- a declared product is written by definition. Real
    cult-cargo documents still put `writable: true` on one (casa's
    `flagman.save` marks its `flagversions-table` output, caracal2's
    `caracal_base.yaml` its `output` directory), so the key is accepted there
    and dropped rather than refused.

    Dropping it is not cosmetic. Output metas merge *over* input ones
    (`merge_field_meta`, so an output's `implicit` wins), and
    `readonly_path_fields` reads `field_meta` -- so a `writable` left on the
    output side of a dual-declared name (`vis` on both, the echo idiom) would
    decide the mount mode of the *input* that never asked for it: a cab saying
    nothing about its input would get it mounted `:ro`, or one that marked its
    input read-only would have that silently overridden.

    `writable: false` on an output is refused instead of dropped: it declares
    a product the tool may not write, which nothing can honour, and no real
    document writes it.
    """
    contradictions = sorted(field for field, meta in out_meta.items() if meta.writable is False)
    if contradictions:
        raise CabLoadError(
            f"cab '{cab}': output(s) {', '.join(repr(f) for f in contradictions)} are marked `writable: false`. "
            f"An output is a product the tool writes -- marking it unwritable is a contradiction, and shinobi "
            f"will not quietly ignore it. Drop the key, or move it to the same-named *input* if what you meant "
            f"is that the tool must not modify the file it was given."
        )
    stripped = {
        field: (meta.model_copy(update={"writable": None}) if meta.writable is not None else meta)
        for field, meta in out_meta.items()
    }
    # An output spec whose only content was `writable` is left saying nothing,
    # and `_collect` never stores a meta that says nothing -- so neither does
    # this, or the cab would carry a default `ParamMeta` its Python-authored
    # equivalent does not have.
    return {field: meta for field, meta in stripped.items() if meta != _DEFAULT_PARAM_META}


def _param_meta(
    value: dict[str, Any], *, nom_de_guerre: str | None = None, with_dtype: bool = False
) -> ParamMeta:
    """Build a `ParamMeta` from a param-spec mapping.

    Shared by declared fields and by `ParamPattern` attrs, which are the same
    shape -- an attr is a param spec that happens to name part of a pattern
    rather than a whole field. Keeping one reader means a key added for one is
    understood by the other, which is the drift `AGENTS.md` warns about for
    these loaders.

    `with_dtype` is the one asymmetry, and it is not cosmetic. A declared
    field's dtype lives in its model annotation, so repeating it here would
    put something on `field_meta` that the Python-authored equivalent does not
    have -- every field of every cab would then differ on a round trip. A
    pattern attr has no model field at all, which is exactly why
    `ParamMeta.dtype` exists (see its docstring): it is the only way a backend
    can tell a dynamically-named input is file-like.
    """
    if with_dtype and value.get("string_pattern") is not None:
        raise CabLoadError(
            "string_pattern is supported only on literal fields, not dynamic parameter attrs"
        )
    if with_dtype and any(value.get(key) is not None for key in ("min_length", "max_length")):
        raise CabLoadError(
            "length constraints are supported only on literal fields, not dynamic parameter attrs"
        )
    policies = value.get("policies") or {}
    return ParamMeta(
        nom_de_guerre=nom_de_guerre,
        implicit=value.get("implicit"),
        framework_family=value.get("family"),
        info=value.get("info"),
        positional=bool(policies.get("positional", False)),
        positional_head=bool(policies.get("positional_head", False)),
        repeat_as_tokens=policies.get("repeat") == "list",
        choices=validate_choices(value.get("choices"), error=CabLoadError),
        **length_constraints(value, error=CabLoadError),
        nullable=validate_nullable(value, error=CabLoadError),
        string_pattern=value.get("string_pattern"),
        dtype=value.get("dtype") if with_dtype else None,
        write_path=bool(value.get("write_path", False)),
        pass_to_command=value.get("pass_to_command", True),
        abbreviation=value.get("abbreviation"),
        # Tri-state: absent stays unmarked rather than collapsing to `true`,
        # so what the cab actually said survives the load -- `worker_schema`
        # carries either explicit value the same way. Both read as writable;
        # only an explicit `false` earns a `:ro` mount.
        writable=None if value.get("writable") is None else bool(value["writable"]),
    )


def _collect(
    raw: dict[str, Any],
    *,
    _prefix: str = "",
    _seen: dict[str, str] | None = None,
) -> tuple[dict[str, tuple[str, bool, Any]], dict[str, ParamMeta], dict[str, str]]:
    """Split a cult-cargo inputs/outputs mapping into modelgen field specs
    and per-field ParamMeta (nom_de_guerre/implicit/info/positional/
    repeat_as_tokens). Recurses into stimela2-style CLI-section nesting
    (`data: {ms: {...}}`), flattening into dotted field names (`data.ms`).
    """
    fields: dict[str, tuple[str, bool, Any]] = {}
    metas: dict[str, ParamMeta] = {}
    mutability: dict[str, str] = {}
    seen = _seen if _seen is not None else {}
    for key, value in raw.items():
        if value is not None and not isinstance(value, dict):
            raise CabLoadError(
                f"expected a param spec mapping, got {value!r} -- this usually means an "
                "unsupported nested _include, which shinobi doesn't resolve without a "
                "package_roots entry (see this module's docstring)"
            )
        value = value or {}  # noqa: PLW2901 -- normalize an empty YAML parameter
        dotted_key = f"{_prefix}.{key}" if _prefix else key
        if _is_section(value):
            sub_fields, sub_metas, sub_mut = _collect(value, _prefix=dotted_key, _seen=seen)
            fields.update(sub_fields)
            metas.update(sub_metas)
            mutability.update(sub_mut)
            continue
        field = sanitize_unique(dotted_key, seen)
        implicit = value.get("implicit")
        required = bool(value.get("required", False)) and implicit is None
        fields[field] = (str(value.get("dtype", "str")), required, value.get("default"))
        # the tool's real flag name: an explicit nom_de_guerre, else the
        # original (unsanitised) param name if sanitising changed it.
        nom = value.get("nom_de_guerre") or (dotted_key if dotted_key != field else None)
        if value.get("mutable"):
            mutability[field] = "mutable"
        meta = _param_meta(value, nom_de_guerre=nom)
        # Only carry a meta that says something. Compared against the default
        # rather than testing each attribute: the old form was a long boolean
        # chain that had to be edited every time `ParamMeta` gained a field,
        # and was one edit behind more than once.
        if meta != _DEFAULT_PARAM_META:
            metas[field] = meta
    return fields, metas, mutability


# Description uses the same field normalization as compilation, without binding
# scientific/runtime types to misleading stand-ins.
def describe_cab(spec: CabSpec):
    """Describe normalized parameter data without constructing runtime types.

    This validates data-level rules, not dtype bindings or execution contracts.
    Only compilation with trusted bindings can establish runtime validity.
    """
    from .description import CabDescription, ParameterDescription

    def fields(raw):
        names = {}
        values, metas, mutability = _collect(raw or {}, _seen=names)
        descriptions = {}
        for name, (dtype, required, default) in values.items():
            meta = metas.get(name, ParamMeta())
            normalized_required, normalized_default = normalize_required_default(
                required, default, nullable=meta.nullable, error=CabLoadError
            )
            descriptions[name] = ParameterDescription(
                name=name,
                original_name=names[name],
                dtype=dtype,
                required=normalized_required,
                default=normalized_default,
                meta=meta,
                mutability=mutability.get(name),
            )
        return descriptions

    image = spec.document.get("image")
    if isinstance(image, dict):
        image = image.get("name")
    return CabDescription(
        name=spec.name,
        command=spec.document.get("command"),
        info=spec.document.get("info"),
        image=spec.images.get(image, image),
        inputs=fields(spec.document.get("inputs")),
        outputs=fields(spec.document.get("outputs")),
        input_patterns=_param_patterns(
            spec.document.get("input_patterns"), cab=spec.name, key="input_patterns"
        ),
        output_patterns=_param_patterns(
            spec.document.get("output_patterns"), cab=spec.name, key="output_patterns"
        ),
        framework_declarations={
            key: spec.document[key]
            for key in ("dataset_accesses", "fits_accesses", "derived_reads")
            if key in spec.document
        },
    )


def build_document(dialect: str, text: str, name: str | None = None, **options) -> CabSpec:
    """Resolve a static dialect and select one neutral definition by name."""
    if dialect in ("yaml_cab", "dosho-cab-v1"):
        definitions = loads(text, **options)
    elif dialect == "stimela-classic":
        from .classic import parse_classic

        # Classic JSON is self-contained. Historically this dialect ignored
        # shared provider image/root options; preserve that loader contract.
        definition = parse_classic(text)
        definitions = {definition.name: definition}
    else:
        raise CabLoadError(
            f"unknown cab dialect {dialect!r} (known: yaml_cab, stimela-classic, dosho-cab-v1)"
        )
    if name is not None:
        if name in definitions:
            return definitions[name]
        raise CabLoadError(f"{dialect} document defines {sorted(definitions)!r}, not {name!r}")
    if len(definitions) == 1:
        return next(iter(definitions.values()))
    raise CabLoadError(
        f"{dialect} document defines {sorted(definitions)!r}; no name was given to choose between them"
    )
