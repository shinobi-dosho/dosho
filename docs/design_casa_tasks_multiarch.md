# CASA tasks multi-architecture image

**Status (2026-10-15):** source-built AMD64 and ARM64 images pass the import check and `listobs` on the same small MeasurementSet on kudu. ARM64 was built under QEMU. A 2.1 GB local OCI archive at `/tmp/casa-tasks-multiarch.oci.tar` contains both platform manifests; no registry tag has been published.

## Scope

`CASA_TASKS` is a separate image for the 57 `casatasks` pysteps. The `casaplotms` pystep stays on the existing `CASA6` image; plotms remains deferred for ARM64. The task image does not carry Qt, FUSE, or the x86 AppImage. It starts from Ubuntu 24.04 and builds its own native CASA stack. KERN is an apt source for the future shared dosho base, not an inherited CASA base.

The image uses CASA source tag `6.7.0.31` at commit `01dc26b15daf69d07239bf0a4f059f7f374abbf6`, the casacore submodule selected by that commit, libsakura 5.2.1, a locally built `casatools` wheel, and published `casatasks==6.7.0.31`. Build dependencies stay in the first Docker stage; the runtime stage copies only the native libraries and Python environment, installs runtime libraries, and bakes CASA run and measures data. The final local images are 1,145,571,384 bytes on AMD64 and 1,062,671,925 bytes on ARM64 (Docker uncompressed sizes).

Four details from the first build matter for portability:

- libsakura 5.2.1 hard-codes `-m64` in its library CMake target. `libsakura.sh` removes that flag only on AArch64.
- The pinned CASA commit carries both `6.7.0.31` and `6.7.1.0` tags. Its detached-checkout version script otherwise makes a `6.7.1.0...dirty` wheel, which conflicts with the exact `casatools==6.7.0.31` dependency of `casatasks`. `wheel.sh` writes the release version metadata before packaging.
- CASA C++ needs `libprotobuf-dev` in addition to the gRPC packages.
- The source-built Python bindings need `libfftw3-single3` in the runtime image. The default command imports `listobs`, `gaincal`, and `table` on both platforms; scanning their native CASA libraries with `ldd` reports no missing libraries.

## Local build and checks on kudu

The manifest declares both target platforms. Local builds use the CLI's native single-platform `docker build` path; publication uses its Buildx multi-platform path. Kudu's default Docker build network cannot resolve NRAO Bitbucket, so local builds use host networking. This is a kudu environment workaround, not a source dependency.

```sh
uv run dosho images build CASA_TASKS --network host
docker run --rm ghcr.io/shinobi-dosho/casa-tasks:6.7.0.31-d0.1.0
```

For ARM64 emulation, kudu has Buildx and an ARM64 binfmt registration. The build command is:

```sh
uv run dosho images build CASA_TASKS --dry-run > /tmp/casa-tasks.Dockerfile
docker buildx build --platform linux/arm64 --network host --load \
  -t casa-tasks:arm64 -f /tmp/casa-tasks.Dockerfile src/dosho/cargo/casa-tasks
docker run --rm --platform linux/arm64 casa-tasks:arm64
```

The builder stage caps native compile jobs at 48, or the host's `nproc` value when lower. Under QEMU, compilation is substantially slower than the native AMD64 build. Both architecture variants passed the image command and `listobs` on the same 28 MB MeasurementSet mounted read-only. A local `docker buildx build --platform linux/amd64,linux/arm64 --output type=oci` export produced an index with both platforms. This validates packaging and a read-only task, not calibration or imaging results. Compare numerical outputs from a representative scientific task before release.

## Publication gate

The image CLI uses `docker buildx build --platform linux/amd64,linux/arm64 --push` for `CASA_TASKS`, after the Dockerfile runs its import smoke check on both platforms. It verifies the published manifest includes both architectures. `dosho images push CASA_TASKS` rejects a local single-platform image; `verify` and the missing-only build plan also require both manifest entries. The CI workflow installs QEMU and Buildx for this image. No tag has been published yet. Before release, compare numerical outputs from a representative calibration or imaging task on both platforms; the passing `listobs` task is a packaging and I/O check. An existing incomplete tag is never overwritten without `--force`.
