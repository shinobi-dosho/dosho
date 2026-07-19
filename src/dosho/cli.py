"""``dosho images`` -- build and publish dosho's container images from the
`images.yaml` manifest.

A small build driver modelled on cult-cargo's ``build-cargo``: for each
`build:` entry it renders the entry's Dockerfile (a ``str.format`` template
over the manifest's build vars) and shells out to ``docker build`` /
``docker run`` (a sanity check) / ``docker push``. `ref:` entries are external
images (used verbatim) and are not built here.

The resolved tag is ``{registry}/{name}:{version}-{bundle_version}`` (the same
reference `dosho.images.<KEY>` exposes to cabs), so a built+pushed image is
exactly what the cabs consume.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import click

from dosho import images as _images

_CARGO_DIR = Path(__file__).with_name("cargo")


def _image_exists(tag: str) -> bool:
    """True if `tag` already exists in its registry -- published image tags are
    treated as immutable, so `push` skips them unless `--force`.
    """
    return (
        subprocess.run(
            ["docker", "manifest", "inspect", tag],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        == 0
    )


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
    click.echo(click.style("+ " + " ".join(argv), fg="cyan"))
    subprocess.run(argv, check=True, **kwargs)


def _get_build_entry(key: str) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = _images.manifest
    imgs = manifest["images"]
    if key not in imgs:
        raise click.ClickException(f"no image {key!r} in the manifest (have: {', '.join(imgs)})")
    entry = imgs[key]
    if "build" not in entry:
        raise click.ClickException(
            f"image {key!r} is a `ref:` (external) -- dosho does not build it"
        )
    return entry, manifest["metadata"]


def _tag(key: str, entry: dict[str, Any], metadata: dict[str, Any], registry: str | None) -> str:
    registry = registry or metadata["registry"]
    name = entry.get("name", key.lower())
    return f"{registry}/{name}:{entry['build']['version']}-{metadata['bundle_version']}"


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
            base_key, _images.manifest["images"][base_key], metadata
        )
    for var in _OPTIONAL_TEMPLATE_VARS:
        fmt.setdefault(var, "")
    dockerfile = _CARGO_DIR / build["dockerfile"]
    return dockerfile.read_text().format(**fmt), dockerfile.parent


@click.group()
def main() -> None:
    """dosho tooling."""


@main.group()
def images() -> None:
    """Build and publish dosho's container images."""


@images.command("list")
def images_list() -> None:
    """List every manifest image, its kind (ref/build), and resolved reference."""
    for key, entry in _images.manifest["images"].items():
        kind = "build" if "build" in entry else "ref"
        click.echo(f"{key:16} [{kind:5}] {getattr(_images, key)}")


@images.command("build")
@click.argument("key")
@click.option("--push", "do_push", is_flag=True, help="push the image after building.")
@click.option("--no-cache", is_flag=True, help="build without the docker layer cache.")
@click.option("--registry", default=None, help="override the manifest registry for the tag.")
@click.option(
    "--package", default=None, help="override the pip package/spec installed (e.g. a prerelease)."
)
@click.option("--force", is_flag=True, help="on --push, overwrite an already-published tag.")
@click.option(
    "--dry-run", is_flag=True, help="render and print the Dockerfile + tag; do not build."
)
def images_build(
    key: str,
    do_push: bool,
    no_cache: bool,
    registry: str | None,
    package: str | None,
    force: bool,
    dry_run: bool,
) -> None:
    """Build (and optionally --push) the image for KEY."""
    entry, metadata = _get_build_entry(key)
    tag = _tag(key, entry, metadata, registry)
    dockerfile, context = _render_dockerfile(entry, metadata, package)

    if dry_run:
        click.echo(f"# tag: {tag}\n# context: {context}\n{dockerfile}")
        return

    build_argv = ["docker", "build", "-t", tag, "-f", "-"]
    if no_cache:
        build_argv.append("--no-cache")
    build_argv.append(str(context))
    _run(build_argv, input=dockerfile.encode())

    # sanity check: run the image's own CMD (e.g. `<tool> --help`).
    _run(["docker", "run", "--rm", tag])

    pushed = False
    if do_push:
        pushed = _push(tag, force)

    click.echo(click.style(f"built {tag}" + (" and pushed" if pushed else ""), fg="green"))


@images.command("push")
@click.argument("key")
@click.option("--registry", default=None, help="override the manifest registry for the tag.")
@click.option("--force", is_flag=True, help="overwrite an already-published tag.")
def images_push(key: str, registry: str | None, force: bool) -> None:
    """Push the already-built image for KEY (skips an already-published tag)."""
    entry, metadata = _get_build_entry(key)
    _push(_tag(key, entry, metadata, registry), force)


def _push(tag: str, force: bool) -> bool:
    """Push `tag`, unless it's already published and `force` is not set."""
    if not force and _image_exists(tag):
        click.echo(f"{tag} already published; skipping push (use --force to overwrite)")
        return False
    _run(["docker", "push", tag])
    return True


@images.command("build-keys")
def images_build_keys() -> None:
    """Print the JSON list of `build:` image KEYs (for a CI build matrix)."""
    click.echo(json.dumps(_build_keys(_images.manifest)))


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
    manifest = _images.manifest
    images_ = manifest["images"]
    build = _build_keys(manifest)
    keys = _affected_keys(manifest, list(changed)) if changed else set(build)

    if missing_only:
        present = {
            k for k in keys if _image_exists(_tag(k, images_[k], manifest["metadata"], None))
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
    manifest = _images.manifest
    keys = [key] if key else _build_keys(manifest)
    missing = []
    for k in keys:
        entry = manifest["images"].get(k)
        if not entry or "build" not in entry:
            raise click.ClickException(f"{k!r} is not a build: image")
        tag = _tag(k, entry, manifest["metadata"], None)
        ok = _image_exists(tag)
        click.echo(f"{'ok     ' if ok else 'MISSING'} {tag}")
        if not ok:
            missing.append(tag)
    if missing:
        raise click.ClickException(f"{len(missing)} image(s) missing from the registry")


if __name__ == "__main__":
    main()
