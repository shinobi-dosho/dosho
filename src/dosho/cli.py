"""``dosho images`` -- build and publish dosho's container images from the
`images.yaml` manifest.

A small build driver modelled on cult-cargo's ``build-cargo``: for each
`build:` entry it renders the entry's Dockerfile (a ``str.format`` template
over the manifest's build vars) and shells out to Docker. Multi-platform entries use Buildx to build and
push one manifest list; other entries retain the single-host build/run/push path. `ref:` entries are external
images (used verbatim) and are not built here.

The resolved tag is ``{registry}/{name}:{version}-{bundle_version}`` (the same
reference `dosho.images.<KEY>` exposes to cabs), so a built+pushed image is
exactly what the cabs consume.

An entry may also declare a ``dev:`` block -- its `build:` vars overlaid to
install the tool from its development branch -- built with ``build --dev`` and
published to the mutable tag ``{registry}/{name}:dev``. Dev images are *not*
part of the release build plan (`build-plan` never selects them) and never
share a tag with a release, so the two publish paths cannot collide.
"""

from __future__ import annotations

import json
import re
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import click

from dosho import images as _images

_CARGO_DIR = Path(__file__).with_name("cargo")


@dataclass
class PublicationSource:
    manifest: dict[str, Any] | None = None
    cargo: Path | None = None
    pre_publish: tuple[str, ...] = ()


def _source() -> PublicationSource:
    ctx = click.get_current_context(silent=True)
    return (ctx.find_object(PublicationSource) if ctx else None) or PublicationSource()


def _manifest() -> dict[str, Any]:
    candidate = _source().manifest
    return candidate if candidate is not None else _images.manifest


def _load_source(root: Path) -> PublicationSource:
    """Read candidate configuration without importing candidate Python."""
    root = root.resolve(strict=True)
    manifest_path = (root / "src/dosho/images.yaml").resolve(strict=True)
    cargo = (root / "src/dosho/cargo").resolve(strict=True)
    if not manifest_path.is_relative_to(root) or not cargo.is_relative_to(root):
        raise click.ClickException("candidate manifest/cargo escapes source root")
    manifest = _images._load_manifest(manifest_path)
    metadata = manifest["metadata"]
    if metadata["registry"] != "ghcr.io/shinobi-dosho":
        raise click.ClickException("candidate release registry must be ghcr.io/shinobi-dosho")
    for key, entry in manifest["images"].items():
        if "build" not in entry:
            continue
        name = entry.get("name", key.lower())
        tag = f"{entry['build']['version']}-{metadata['bundle_version']}"
        if not re.fullmatch(r"[a-z0-9]+(?:[._-][a-z0-9]+)*", name):
            raise click.ClickException("invalid candidate image name")
        if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}", tag):
            raise click.ClickException("invalid candidate release tag")
        dockerfile = (cargo / entry["build"]["dockerfile"]).resolve(strict=True)
        if not dockerfile.is_relative_to(cargo):
            raise click.ClickException("candidate Dockerfile escapes cargo tree")
    for path in cargo.rglob("*"):
        if not path.resolve(strict=True).is_relative_to(cargo):
            raise click.ClickException("candidate context symlink escapes cargo tree")
    return PublicationSource(manifest=manifest, cargo=cargo)


def _registry_write(argv: list[str]) -> bool:
    return (
        argv[:2] == ["docker", "push"]
        or (argv[:3] == ["docker", "buildx", "build"] and "--push" in argv)
        or argv[:4] == ["docker", "buildx", "imagetools", "create"]
    )


def _image_exists(tag: str) -> bool:
    """True if `tag` already exists in its registry -- published image tags are
    treated as immutable, so `push` skips them unless `--force`.
    """
    return (
        subprocess.run(
            ["docker", "manifest", "inspect", tag],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,  # a missing tag is the answer, not an error
        ).returncode
        == 0
    )


def _image_has_platforms(tag: str, platforms: list[str]) -> bool:
    """Check an existing registry manifest's declared OS/architecture pairs."""
    if not platforms:
        return True
    proc = subprocess.run(
        ["docker", "buildx", "imagetools", "inspect", "--raw", tag],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode:
        return False
    try:
        manifest = json.loads(proc.stdout)
        present = {
            f"{item['platform']['os']}/{item['platform']['architecture']}"
            for item in manifest.get("manifests", [])
            if "platform" in item
        }
    except (KeyError, TypeError, ValueError):
        return False
    return set(platforms) <= present


def _build_keys(manifest: dict[str, Any]) -> list[str]:
    return [key for key, entry in manifest["images"].items() if "build" in entry]


# Repo-relative path whose change makes *every* build image a rebuild
# candidate: the manifest (metadata like bundle_version, or any entry's
# version/base, can move). CI pairs this with `build-plan --missing-only`,
# which then filters the candidates to tags actually absent from the
# registry -- so bumping one entry's version rebuilds just that image,
# while a bundle_version bump (every tag moves) still rebuilds the world.
# A CI workflow change is deliberately NOT here -- it orchestrates builds
# but can't change image contents, so it shouldn't force a full rebuild.
_GLOBAL_TRIGGERS = frozenset({"src/dosho/images.yaml"})
_CARGO_PREFIX = "src/dosho/cargo/"


def _affected_keys(manifest: dict[str, Any], changed_files: list[str]) -> set[str]:
    """The set of `build:` KEYs that must rebuild given `changed_files`
    (repo-relative paths from a push diff).

    A build image's context is its Dockerfile's parent dir under `cargo/`, so a
    change to *any* file in that dir (e.g. `casa6/casasiteconfig.py`, or the
    shared `pip/Dockerfile` used by many tools) invalidates every KEY built from
    it. Changing the manifest rebuilds everything. Finally, a changed base image
    transitively pulls in everything that builds `FROM` it.
    """
    images = manifest["images"]
    build = _build_keys(manifest)
    if _GLOBAL_TRIGGERS.intersection(changed_files):
        return set(build)

    # cargo subdir (first path component of each entry's dockerfile) -> its KEYs.
    subdir_keys: dict[str, set[str]] = {}
    for key in build:
        subdir = images[key]["build"]["dockerfile"].split("/", 1)[0]
        subdir_keys.setdefault(subdir, set()).add(key)

    affected: set[str] = set()
    for path in changed_files:
        if path.startswith(_CARGO_PREFIX):
            subdir = path[len(_CARGO_PREFIX) :].split("/", 1)[0]
            affected |= subdir_keys.get(subdir, set())

    # Base-DAG invalidation: rebuild dependents of any affected base, transitively.
    while True:
        grew = {
            key
            for key in build
            if images[key]["build"].get("base") in affected and key not in affected
        }
        if not grew:
            break
        affected |= grew
    return affected


def _run(argv: list[str], **kwargs: Any) -> None:
    hook = _source().pre_publish
    if hook and _registry_write(argv):
        subprocess.run(list(hook), check=True)
    click.echo(click.style("+ " + " ".join(argv), fg="cyan"))
    subprocess.run(argv, check=True, **kwargs)


def _get_build_entry(key: str) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = _manifest()
    imgs = manifest["images"]
    if key not in imgs:
        raise click.ClickException(f"no image {key!r} in the manifest (have: {', '.join(imgs)})")
    entry = imgs[key]
    if "build" not in entry:
        raise click.ClickException(
            f"image {key!r} is a `ref:` (external) -- dosho does not build it"
        )
    return entry, manifest["metadata"]


def _tag(
    key: str,
    entry: dict[str, Any],
    metadata: dict[str, Any],
    registry: str | None,
    dev: bool = False,
) -> str:
    if _source().manifest is not None and registry not in (None, "ghcr.io/shinobi-dosho"):
        raise click.ClickException("candidate publication registry cannot be overridden")
    registry = registry or metadata["registry"]
    name = entry.get("name", key.lower())
    if dev:
        # Deliberately outside the immutable {version}-{bundle} scheme: a dev
        # tag is a moving pointer at the tool's `main`, so it carries no version
        # to imply otherwise, and can never collide with a release tag.
        return f"{registry}/{name}:dev"
    return f"{registry}/{name}:{entry['build']['version']}-{metadata['bundle_version']}"


def _dev_entry(key: str, entry: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    """`entry` with its `dev:` block overlaid onto `build:` -- i.e. the same
    build recipe, but installing the tool from its development branch.

    `metadata.dev_deps` is appended to the result's `extra_deps` (see the
    manifest's comment on it): a tool built from its own `main` is written
    against its framework dependency's `main` too, which a plain `pip install`
    would resolve from PyPI instead.
    """
    dev = entry.get("dev")
    if dev is None:
        raise click.ClickException(
            f"image {key!r} has no `dev:` block in the manifest -- add one "
            f"(e.g. `dev: {{package: 'git+<repo>@main'}}`) to build a dev image for it"
        )
    build = {**entry["build"], **dev}
    pins = metadata.get("dev_deps", "")
    if pins:
        build["extra_deps"] = f"{build.get('extra_deps', '')} {pins}".strip()
    return {**entry, "build": build}


def _digest(tag: str) -> str | None:
    """The pushed image's `name@sha256:...` reference, or None if docker
    doesn't report one. Callers pin *this*, not the mutable `:dev` tag."""
    proc = subprocess.run(
        ["docker", "inspect", "--format", "{{index .RepoDigests 0}}", tag],
        capture_output=True,
        text=True,
        check=False,  # "no digest reported" is an answer the caller handles
    )
    return proc.stdout.strip() or None if proc.returncode == 0 else None


_OPTIONAL_TEMPLATE_VARS = ("pre_install", "post_install", "extra_deps", "pip_install_flags")


def _render_dockerfile(
    entry: dict[str, Any], metadata: dict[str, Any], package: str | None
) -> tuple[str, Path]:
    build = dict(entry["build"])
    if package:
        build["package"] = package
    fmt = {**metadata, **build}
    # `base: <KEY>` -- build FROM another dosho image; resolve it to a full ref
    # (via the same resolver cabs use) and expose it to the template as `base_image`.
    base_key = build.get("base")
    if base_key:
        fmt["base_image"] = _images._resolve_ref(
            base_key, _manifest()["images"][base_key], metadata
        )
    for var in _OPTIONAL_TEMPLATE_VARS:
        fmt.setdefault(var, "")
    dockerfile = (_source().cargo or _CARGO_DIR) / build["dockerfile"]
    return dockerfile.read_text().format(**fmt), dockerfile.parent


@click.group()
def main() -> None:
    """dosho tooling."""


@main.group()
@click.option(
    "--source-root",
    type=click.Path(path_type=Path, exists=True, file_okay=False),
    help="Read candidate manifest/cargo as data; run this installed CLI's trusted code.",
)
@click.option(
    "--pre-publish", default="", help="Trusted command to revalidate before every registry write."
)
@click.pass_context
def images(ctx: click.Context, source_root: Path | None, pre_publish: str) -> None:
    """Build and publish dosho's container images."""
    source = _load_source(source_root) if source_root else PublicationSource()
    source.pre_publish = tuple(shlex.split(pre_publish))
    ctx.obj = source


@images.command("list")
def images_list() -> None:
    """List every manifest image, its kind (ref/build), and resolved reference."""
    for key, entry in _manifest()["images"].items():
        kind = "build" if "build" in entry else "ref"
        ref = (
            _images._resolve_ref(key, entry, _manifest()["metadata"])
            if _source().manifest is not None
            else getattr(_images, key)
        )
        click.echo(f"{key:16} [{kind:5}] {ref}")


@images.command("build")
@click.argument("key")
@click.option("--push", "do_push", is_flag=True, help="push the image after building.")
@click.option("--no-cache", is_flag=True, help="build without the docker layer cache.")
@click.option("--network", default=None, help="Docker build network mode (e.g. host).")
@click.option(
    "--sequential-platforms",
    is_flag=True,
    help="on multi-platform --push, build each platform separately before creating the manifest.",
)
@click.option(
    "--prune-between-platforms",
    is_flag=True,
    help="with --sequential-platforms, clear Buildx cache between builds (isolated builders only).",
)
@click.option("--registry", default=None, help="override the manifest registry for the tag.")
@click.option(
    "--package", default=None, help="override the pip package/spec installed (e.g. a prerelease)."
)
@click.option("--force", is_flag=True, help="on --push, overwrite an already-published tag.")
@click.option(
    "--dev",
    is_flag=True,
    help="build the entry's `dev:` variant (the tool from its development "
    "branch) and tag it `{name}:dev`. The tag is mutable, so --push always "
    "overwrites it; the digest is printed afterwards, and consumers should pin "
    "that -- shinobi's step-cache key hashes the image *string*, so a moving "
    "tag would keep serving cache hits produced by the code you just changed.",
)
@click.option(
    "--dry-run", is_flag=True, help="render and print the Dockerfile + tag; do not build."
)
def images_build(
    key: str,
    do_push: bool,
    no_cache: bool,
    network: str | None,
    sequential_platforms: bool,
    prune_between_platforms: bool,
    registry: str | None,
    package: str | None,
    force: bool,
    dev: bool,
    dry_run: bool,
) -> None:
    """Build (and optionally --push) the image for KEY."""
    entry, metadata = _get_build_entry(key)
    if dev:
        entry = _dev_entry(key, entry, metadata)
    tag = _tag(key, entry, metadata, registry, dev)
    dockerfile, context = _render_dockerfile(entry, metadata, package)

    if dry_run:
        click.echo(f"# tag: {tag}\n# context: {context}\n{dockerfile}")
        return

    platforms = entry["build"].get("platforms", [])
    if prune_between_platforms and not sequential_platforms:
        raise click.ClickException("--prune-between-platforms requires --sequential-platforms")
    if sequential_platforms and not (do_push and platforms):
        raise click.ClickException("--sequential-platforms requires multi-platform --push")
    if do_push and platforms:
        # Publish the resolved tag only after every platform's Dockerfile
        # (including its runtime RUN check) succeeds. A local docker push
        # would publish just the host architecture under the shared tag.
        if not (force or dev) and _image_exists(tag):
            if _image_has_platforms(tag, platforms):
                click.echo(f"{tag} already published; skipping push (use --force to overwrite)")
                return
            raise click.ClickException(
                f"{tag} exists without all declared platforms; bump its version "
                "or use --force after reviewing the existing tag"
            )
        if sequential_platforms:
            # Large native stacks can exceed a standard CI runner's disk when
            # Buildx holds two unpacked platform snapshots at once. Staging
            # tags are published first; the public tag appears only after both
            # platform builds (and their Dockerfile RUN checks) succeed.
            staged_tags = []
            for index, platform in enumerate(platforms):
                staged = f"{tag}-{platform.rsplit('/', 1)[-1]}"
                build_argv = [
                    "docker",
                    "buildx",
                    "build",
                    "--platform",
                    platform,
                    "--push",
                    "-t",
                    staged,
                    "-f",
                    "-",
                ]
                if no_cache:
                    build_argv.append("--no-cache")
                if network:
                    build_argv += ["--network", network]
                build_argv.append(str(context))
                _run(build_argv, input=dockerfile.encode())
                staged_tags.append(staged)
                if prune_between_platforms and index < len(platforms) - 1:
                    _run(["docker", "buildx", "prune", "--all", "--force"])
            _run(["docker", "buildx", "imagetools", "create", "-t", tag, *staged_tags])
        else:
            build_argv = [
                "docker",
                "buildx",
                "build",
                "--platform",
                ",".join(platforms),
                "--push",
                "-t",
                tag,
                "-f",
                "-",
            ]
            if no_cache:
                build_argv.append("--no-cache")
            if network:
                build_argv += ["--network", network]
            build_argv.append(str(context))
            _run(build_argv, input=dockerfile.encode())
        if not _image_has_platforms(tag, platforms):
            raise click.ClickException(f"published {tag} lacks a declared platform")
        click.echo(click.style(f"built and pushed {tag} ({', '.join(platforms)})", fg="green"))
        return

    build_argv = ["docker", "build", "-t", tag, "-f", "-"]
    if no_cache:
        build_argv.append("--no-cache")
    if network:
        build_argv += ["--network", network]
    build_argv.append(str(context))
    _run(build_argv, input=dockerfile.encode())

    # sanity check: run the image's own CMD (e.g. `<tool> --help`).
    _run(["docker", "run", "--rm", tag])

    pushed = False
    if do_push:
        # A dev tag is mutable by design -- the immutability guard would skip
        # every push after the first, which is exactly the wrong behaviour here.
        pushed = _push(tag, force or dev)

    click.echo(click.style(f"built {tag}" + (" and pushed" if pushed else ""), fg="green"))
    if pushed and dev:
        digest = _digest(tag)
        click.echo(
            click.style(f"pin this digest, not the tag: {digest or '<unknown>'}", fg="yellow")
        )


@images.command("push")
@click.argument("key")
@click.option("--registry", default=None, help="override the manifest registry for the tag.")
@click.option("--force", is_flag=True, help="overwrite an already-published tag.")
@click.option("--dev", is_flag=True, help="push the `{name}:dev` tag (always overwrites).")
def images_push(key: str, registry: str | None, force: bool, dev: bool) -> None:
    """Push the already-built image for KEY (skips an already-published tag)."""
    entry, metadata = _get_build_entry(key)
    if entry["build"].get("platforms"):
        raise click.ClickException(
            f"{key} declares multiple platforms; use `dosho images build {key} --push`"
        )
    _push(_tag(key, entry, metadata, registry, dev), force or dev)


def _push(tag: str, force: bool) -> bool:
    """Push `tag`, unless it's already published and `force` is not set."""
    if not force and _image_exists(tag):
        click.echo(f"{tag} already published; skipping push (use --force to overwrite)")
        return False
    _run(["docker", "push", tag])
    return True


@images.command("build-keys")
@click.option("--dev", is_flag=True, help="list only KEYs that declare a `dev:` variant.")
def images_build_keys(dev: bool) -> None:
    """Print the JSON list of `build:` image KEYs (for a CI build matrix)."""
    manifest = _manifest()
    keys = _build_keys(manifest)
    if dev:
        keys = [k for k in keys if "dev" in manifest["images"][k]]
    click.echo(json.dumps(keys))


@images.command("build-plan")
@click.option(
    "--changed",
    multiple=True,
    metavar="PATH",
    help="Repo-relative changed file (repeatable). If given, restrict the plan "
    "to images affected by those changes plus dependents of any changed base.",
)
@click.option(
    "--missing-only",
    is_flag=True,
    help="Further restrict the plan to images whose resolved tag is absent "
    "from the registry (needs docker registry access). Published tags are "
    "immutable, so an existing tag never needs rebuilding: on a manifest "
    "change this turns the rebuild-everything candidate set into just the "
    "images whose tags moved (or were never built), and self-heals a "
    "deleted/corrupt registry entry.",
)
def images_build_plan(changed: tuple[str, ...], missing_only: bool) -> None:
    """Print JSON {bases, tools} -- base images (those referenced via `base:` by
    another entry) must build before the tools that build FROM them (for a
    two-stage CI build).

    Without `--changed`, plan every `build:` image. With `--changed`, plan only
    the images a push actually invalidated (see `_affected_keys`), so CI skips
    rebuilding unrelated (e.g. heavy) images.
    """
    manifest = _manifest()
    images_ = manifest["images"]
    build = _build_keys(manifest)
    keys = _affected_keys(manifest, list(changed)) if changed else set(build)

    if missing_only:
        present = {
            k
            for k in keys
            if _image_exists(_tag(k, images_[k], manifest["metadata"], None))
            and _image_has_platforms(
                _tag(k, images_[k], manifest["metadata"], None),
                images_[k]["build"].get("platforms", []),
            )
        }
        if present:
            click.echo(
                f"already published, excluded from plan: {', '.join(sorted(present))}",
                err=True,
            )
        keys -= present

    # A base is any KEY referenced via `base:`; it builds in the first stage.
    all_bases = {images_[k]["build"]["base"] for k in build if "base" in images_[k]["build"]}
    bases = sorted(all_bases & keys)
    tools = sorted(keys - all_bases)
    click.echo(json.dumps({"bases": bases, "tools": tools}))


@images.command("verify")
@click.argument("key", required=False)
def images_verify(key: str | None) -> None:
    """Check that `build:` image(s) exist in the registry (exit 1 if any are missing)."""
    manifest = _manifest()
    keys = [key] if key else _build_keys(manifest)
    missing = []
    for k in keys:
        entry = manifest["images"].get(k)
        if not entry or "build" not in entry:
            raise click.ClickException(f"{k!r} is not a build: image")
        tag = _tag(k, entry, manifest["metadata"], None)
        platforms = entry["build"].get("platforms", [])
        ok = _image_exists(tag) and _image_has_platforms(tag, platforms)
        click.echo(f"{'ok     ' if ok else 'MISSING'} {tag}")
        if not ok:
            missing.append(tag)
    if missing:
        raise click.ClickException(f"{len(missing)} image(s) missing from the registry")


if __name__ == "__main__":
    main()
