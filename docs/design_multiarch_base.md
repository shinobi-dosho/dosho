# Multi-architecture image base: design and audit

**Status:** base proposed, 2026-10-15. The audit below describes the image
manifest before the task-only CASA change. A separate CASA tasks source-build
recipe now passes local AMD64 and emulated ARM64 import and `listobs`
checks on kudu. The first shared-base gate is a native ARM64 apt build with KERN-10 enabled. CASA
plotms is **deferred**.

## Goal and boundary

Publish native `linux/amd64` and `linux/arm64` variants under each supported
dosho image tag. Docker can then select the matching variant on each host.
Replace `kernsuite/base:10` with a dosho-owned Ubuntu 24.04 base that configures
KERN-10 as an apt source. KERN supplies packages where its builds are available;
the upstream KERN container image is no longer an inherited base.

This does not imply that every tool will immediately support ARM64. Every tag
*offered* for ARM64 needs a real ARM64 image, even when the application is mostly
Python. The narrow part of the work is bespoke native porting: most tools use
one shared pip Dockerfile, but their dependency wheels and commands still need
an ARM64 build and smoke test. A tag must never claim ARM64 merely because an
AMD64 image runs under emulation.

## What the repository uses today

At the audit snapshot, the [image manifest](../src/dosho/images.yaml) had 31 keys: 30 dosho-built
images and one deprecated external reference (`SIMMS_CLASSIC`). Of the built
images, 21 use [the shared pip template](../src/dosho/cargo/pip/Dockerfile)
and `BASE_ASTRO`. Those 21 images serve **51 YAML document cabs and 10
pysteps**, or 61 registered tools. The counts were checked from the manifest
and `src/dosho/documents/`; the pystep split comes from the image decorators
in `src/dosho/cabs/`.

The present [base Dockerfile](../src/dosho/cargo/base-astro/Dockerfile) inherits
`kernsuite/base:10`, installs `python3-pip`, `python3-venv`, `git`, and
`casacore-tools`, then installs `python-casacore`, `astropy`, `dask-ms[xarray]`,
`numpy`, `scipy`, and `omegaconf` into system Python. This is the starting
dependency inventory, not a requirement to put every one of those Python
packages into the replacement base. In particular, downstream packages impose
different NumPy and Python constraints.

| Group | Image keys | Registered tools | Audit finding |
| --- | --- | ---: | --- |
| Shared pip children | `SIMMS`, `FITSTOOLZ`, `MSUTILS`, `QUARTICAL`, `TRICOLOUR`, `CRYSTALBALL`, `OWLCAT`, `SHADEMS`, `MOSAIC_QUEEN`, `MOWJSUB`, `BREIZORRO`, `AIMFAST`, `EIDOS`, `SMOPS`, `AEGEAN`, `RM_TOOLS`, `RFINDER`, `PYDDI`, `SPIMPLE`, `TIGGER_LSM`, `BDSF` | 61 | No architecture-specific command in the common Dockerfile. Build every child for ARM64 and check wheels and actual commands. |
| C/C++ or apt tools | `WSCLEAN`, `AOFLAGGER`, `SOFIA2` | 4 | WSClean, IDG, EveryBeam, and SoFiA build native code; AOFlagger installs an apt binary. See their Dockerfiles under `src/dosho/cargo/`. |
| Older Python stacks | `CUBICAL`, `RAGAVI` | 3 | CubiCal requires Python 3.9 and compiles `sharedarray`; ragavi inherits `stimela/base:1.2.5` with Python 3.6. Its ARM64 availability is unverified. |
| CASA tasks | `CASA6` at audit; now `CASA_TASKS` | 57 | The pinned [`casatools==6.7.0.31` release](https://pypi.org/project/casatools/6.7.0.31/) has no Linux ARM64 wheel or PyPI source distribution, so the pip install cannot complete natively on ARM64. These are the CASA tools to prioritize. |
| CASA plotms, deferred | `CASA6` today | 1 | [The current Dockerfile](../src/dosho/cargo/casa6/Dockerfile) also extracts a specifically `x86_64` casaplotms AppImage. This is a separate optional package and a separate pystep; it need not gate the 57 tasks. |
| DDFacet stack | `DDFACET`, `KILLMS` | 2 | [DDFacet](../src/dosho/cargo/ddfacet/Dockerfile) hard-codes `x86_64` compiler alternatives and builds several native dependencies; KILLMS inherits it. |
| External, deprecated | `SIMMS_CLASSIC` | 1 | The manifest uses a `ref:`; dosho cannot build its ARM64 variant. |

`BASE_ASTRO` is an additional build image with no cab of its own. Thus the
table covers 129 registered tools across 30 built image tags plus one external
reference.

## Proposed base contract

1. Start from a multi-platform Ubuntu 24.04 image. Configure the KERN-10 Noble
   PPA with its published signing key and a `signed-by` apt source; verify the
   key against the fingerprint on the PPA page before use. Keep Ubuntu
   repositories available. Record which repository supplied each installed
   KERN-related package; enabling a PPA does not mean every requested package
   came from it.
2. Include only broadly reused **runtime** facilities: certificates, apt
   source configuration, the selected Python runtime, and casacore runtime
   libraries/data and other shared astronomy libraries once the child inventory
   proves reuse. Keep compilers, headers, `*-dev` packages, CMake, and tool
   sources in build stages or individual child images. Install apt packages
   without recommends and remove apt lists in the same layer.
3. Keep `python3` on one documented default (currently Ubuntu Noble's 3.12).
   Support older and newer Python minors explicitly, without changing that
   default through `update-alternatives`. A wide range of interpreters is useful
   only if children select the intended one and install their own packages for
   its ABI. The first implementation should measure the compressed size of
   preinstalling the versions actually used; if carrying all of them raises
   every child's pull size substantially, use versioned Python base variants
   or install an interpreter in the affected child. CubiCal's 3.9 and ragavi's
   3.6 are existing cases, not evidence that all 21 shared pip children need
   those runtimes. [uv can install multiple Python versions](https://docs.astral.sh/uv/concepts/python-versions/),
   but its binary and managed runtimes are a choice to validate, not a required
   part of the base.
4. Give each child an isolated Python environment and pinned application
   dependencies. Sharing one scientific site-packages across children risks
   conflicting pins: the current [BDSF manifest entry](../src/dosho/images.yaml)
   requests `numpy<2`, and [CASA6](../src/dosho/cargo/casa6/Dockerfile) pins
   `protobuf==3.20` and handles its own NumPy installation. The exact set of
   shared Python packages should follow measured reuse and compatible pins,
   not the current base's package list by default.
5. Publish a package inventory and per-architecture compressed-size report for
   the base. Compare the total bytes a representative child pulls with the old
   base, not just the base's layer count. A shared dependency saves registry
   storage and build time, but still travels with every child that inherits it.

The supported Python versions, shared runtime package list, and size ceiling
remain decisions to make from native builds and measurements. The base contract
does not include CASA measures data, Qt/AppImage files, WSClean's IDG/EveryBeam
build, or DDFacet's private source stack.

## KERN-10 package findings and gate

[KERN's installation instructions](https://kernsuite.info/installation/)
identify KERN-10 with Ubuntu 24.04 and its PPA. The accessible
[Launchpad PPA overview](https://launchpad.net/~kernsuite/+archive/ubuntu/kern-10)
lists two published source packages, `casacore` 3.6.1-1kern1 and
`casacore-data` 20250113-160001-5. It does **not** identify which binary
architectures were built. The live PPA `Release` and `Packages` indexes and
package build pages were inaccessible during this audit, so KERN-10 ARM64
coverage is **unverified**. Launchpad's [PPA documentation](https://ubuntu.com/docs/launchpad/user/reference/packaging/ppas/ppa/)
says ARM64 builds are not enabled by default. The broad
[KERN package catalog](https://kernsuite.info/packages/) is not proof that
those packages are published by this Noble PPA for ARM64.

| Package used by dosho | Evidence available | Native-build check |
| --- | --- | --- |
| `casacore-dev`, `casacore-tools`, `casacore-data` | KERN-10 lists the `casacore` and `casacore-data` sources; Ubuntu Noble also publishes [casacore tools](https://packages.ubuntu.com/noble/casacore-tools) and [development files](https://packages.ubuntu.com/noble/casacore-dev). | Inspect `apt-cache policy` and install on both architectures; record selected versions and library ABI. |
| `python3-casacore` | [Ubuntu Noble publishes it](https://packages.ubuntu.com/noble/python3-casacore); KERN uses the package name in its guide. | Check package origin and that Python can import it alongside the selected casacore libraries. |
| `aoflagger` | [Ubuntu Noble publishes an ARM64 build](https://packages.ubuntu.com/noble/arm64/aoflagger); it is not among the two sources shown on the PPA overview. | Install with the PPA enabled and run `aoflagger --version`; verify its casacore dependency resolves with the chosen version. |
| `wcslib-dev` | [Ubuntu Noble publishes ARM64](https://packages.ubuntu.com/noble/wcslib-dev). | Install as part of the WSClean native build, not by default in the runtime base. |

The first build gate is an AMD64 and native ARM64 Ubuntu Noble image that adds
the KERN-10 source, records `dpkg --print-architecture` and `apt-cache policy`
for those packages, installs them, runs `python3 -c 'import casacore.tables'`
and an installed casacore tool, and records the resolved versions. If KERN's
casacore binaries are absent on ARM64, test Ubuntu's casacore packages as an
explicit alternative; do not silently mix incompatible library versions.

## Publishing and verification implications

The current [CLI](../src/dosho/cli.py) uses host-architecture `docker build`,
`docker run`, then `docker push`. Its `_image_exists` check and the weekly
`verify` command accept an existing tag without inspecting its architectures.
The [release workflow](../.github/workflows/images.yml) builds on
`ubuntu-latest`; its base-first ordering remains useful. Multi-platform
publishing needs a manifest containing both variants and a verification check
for `linux/amd64` and `linux/arm64`. Existing release tags are treated as
immutable, so the transition requires new tags or an explicit, reviewed
exception to the immutability policy. Dev tags and their reported digest need
the same platform semantics.

For source-heavy tools, prefer native builders for each architecture. Docker
[documents](https://docs.docker.com/build/building/multi-platform/) that QEMU
emulation can be much slower for compilation. Build and test the base first,
then one representative pip child, then the remaining shared-template images.
An image should enter the ARM64 published set only after its command has run
on ARM64. Keep unsupported images out of a claimed two-platform manifest.

## Later designs

The **CASA tasks** require a Linux ARM64 `casatools` build; changing the base
alone does not provide one. The
pinned `casatasks` release is a
[`py3-none-any` wheel](https://pypi.org/project/casatasks/6.7.0.31/), but it
depends on the compiled `casatools` package. The latest
[`casatools` release](https://pypi.org/project/casatools/) still lists Linux
x86-64 and macOS ARM64 wheels, with no Linux ARM64 wheel. Bundled measures data
then needs runtime validation. [CASA's modular-install documentation](https://casadocs.readthedocs.io/en/v6.7.6/notebooks/introduction.html)
lists `casatasks` and `casaplotms` as separate installations and requires
`casadata` for task operation. Dosho's [task wrappers](../src/dosho/cabs/casatasks.py)
import functions from `casatasks`; its [plotms wrapper](../src/dosho/cabs/casaplotms.py)
imports from `casaplotms`. They shared one image at the audit snapshot. The new `CASA_TASKS` image
serves the 57 task wrappers; `CASA6` remains assigned to plotms.

There is a plausible source-build route. [CASA's own developer guide](https://open-bitbucket.nrao.edu/projects/CASA/repos/casa6/browse)
builds libsakura, casacore, CASA C++ (`casacpp`), a `casatools` wheel, and then
`casatasks` in that order. A native ARM64 builder could use a pinned CASA source
revision and matching dependency revisions, install the resulting ARM64
`casatools` wheel with the same-version `casatasks` package, and publish it
alongside an AMD64 build under one image tag. The guide documents Ubuntu
prerequisites tested on 22.04; it does not establish that this stack already
builds or passes scientific tests on Ubuntu 24.04 ARM64. Reusing KERN casacore
in that build also needs an explicit version and ABI check. A source build is
therefore a candidate implementation, not a verified ARM64 release path.

**Defer plotms.** The task-image design should omit `casaplotms`, Qt/AppImage
extraction, and plotms-specific runtime libraries. When plotms is revisited,
give its wrapper a separate image key rather than publishing one tag whose
capabilities differ between AMD64 and ARM64. The current plotms wrapper stays on `CASA6` and remains AMD64-only until
its own ARM64 route is qualified.

DDFACET needs a separate inventory of each native dependency and
architecture-specific compiler setup; KILLMS depends on that result. Those
plans follow the base package gate and are outside this design.
