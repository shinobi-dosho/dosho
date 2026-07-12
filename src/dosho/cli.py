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
        raise click.ClickException(f"image {key!r} is a `ref:` (external) -- dosho does not build it")
    return entry, manifest["metadata"]


def _tag(key: str, entry: dict[str, Any], metadata: dict[str, Any], registry: str | None) -> str:
    registry = registry or metadata["registry"]
    name = entry.get("name", key.lower())
    return f"{registry}/{name}:{entry['build']['version']}-{metadata['bundle_version']}"


def _render_dockerfile(entry: dict[str, Any], metadata: dict[str, Any], package: str | None) -> tuple[str, Path]:
    build = dict(entry["build"])
    if package:
        build["package"] = package
    dockerfile = _CARGO_DIR / build["dockerfile"]
    text = dockerfile.read_text()
    fmt = {**metadata, **build}
    return text.format(**fmt), dockerfile.parent


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
@click.option("--package", default=None, help="override the pip package/spec installed (e.g. a prerelease).")
@click.option("--force", is_flag=True, help="on --push, overwrite an already-published tag.")
@click.option("--dry-run", is_flag=True, help="render and print the Dockerfile + tag; do not build.")
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
