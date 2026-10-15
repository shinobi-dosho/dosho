# Multi-architecture image base: design and audit

**Status:** base implemented and tested locally, 2026-10-15. The audit below
describes the image manifest before the task-only CASA change. CASA tasks pass
local AMD64 and emulated ARM64 import and `listobs` checks on kudu. The shared
base is built on AMD64 and under ARM64 emulation on kudu; no registry tag has
been published. CASA plotms is **deferred**.

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

The earlier [base Dockerfile](../src/dosho/cargo/base-astro/Dockerfile)
inherited `kernsuite/base:10`. The implemented image starts from Ubuntu 24.04,
configures KERN-10 as a signed apt source, installs casacore tools, data and
Python bindings from that PPA, and adds the common Python astronomy stack in
`/opt/dosho/venv`. The venv exposes system site packages so it can use the apt
casacore binding without rebuilding it. Children install into the venv and can
override its packages; a different `python-casacore` wheel or source build must
be checked against the installed casacore C++ ABI. The base provides Python
3.12 only; old interpreter requirements stay with their children.

| Group | Image keys | Registered tools | Audit finding |
| --- | --- | ---: | --- |
| Shared pip children | `SIMMS`, `FITSTOOLZ`, `MSUTILS`, `QUARTICAL`, `TRICOLOUR`, `CRYSTALBALL`, `OWLCAT`, `SHADEMS`, `MOSAIC_QUEEN`, `MOWJSUB`, `BREIZORRO`, `AIMFAST`, `EIDOS`, `SMOPS`, `AEGEAN`, `RM_TOOLS`, `RFINDER`, `PYDDI`, `SPIMPLE`, `TIGGER_LSM`, `BDSF` | 61 | No architecture-specific command in the common Dockerfile. Build every child for ARM64 and check wheels and actual commands. |
| C/C++ or apt tools | `WSCLEAN`, `AOFLAGGER`, `SOFIA2` | 4 | WSClean and EveryBeam build native code, IDG and AOFlagger come from KERN-10 apt, and SoFiA builds from source. See [the native-tool milestone](design_multiarch_native_tools.md). |
| Older Python stacks | `CUBICAL`, `RAGAVI` | 3 | CubiCal requires Python 3.9 and compiles `sharedarray`; ragavi inherits `stimela/base:1.2.5` with Python 3.6. Its ARM64 availability is unverified. |
| CASA tasks | `CASA6` at audit; now `CASA_TASKS` | 57 | The pinned [`casatools==6.7.0.31` release](https://pypi.org/project/casatools/6.7.0.31/) has no Linux ARM64 wheel or PyPI source distribution, so the pip install cannot complete natively on ARM64. These are the CASA tools to prioritize. |
| CASA plotms, deferred | `CASA6` today | 1 | [The current Dockerfile](../src/dosho/cargo/casa6/Dockerfile) also extracts a specifically `x86_64` casaplotms AppImage. This is a separate optional package and a separate pystep; it need not gate the 57 tasks. |
| DDFacet stack | `DDFACET`, `KILLMS` | 2 | [DDFacet](../src/dosho/cargo/ddfacet/Dockerfile) hard-codes `x86_64` compiler alternatives and builds several native dependencies; KILLMS inherits it. |
| External, deprecated | `SIMMS_CLASSIC` | 1 | The manifest uses a `ref:`; dosho cannot build its ARM64 variant. |

`BASE_ASTRO` is an additional build image with no cab of its own. Thus the
table covers 129 registered tools across 30 built image tags plus one external
reference.

## Implemented base contract

- Ubuntu 24.04 provides the runtime; KERN-10 is a `signed-by` apt source. The
  build downloads its key from Ubuntu's keyserver and checks fingerprint
  `5711690ECBEB59BAC7D3CBF9813B0DC8B7D042E7` before using it. Apt uses
  HTTP for this repository because HTTPS certificate validation failed inside
  the build environment; signed apt metadata still authenticates packages.
  `APT::Update::Error-Mode=any` fails the build if the PPA cannot be refreshed.
- Runtime packages include Python 3.12, pip, venv, certificates, curl, wget,
  git, `casacore-tools`, `casacore-data`, and `python3-casacore`. Compilers,
  development headers, Qt, CASA measures data, and alternate interpreters stay
  out of the base. Apt runs without recommends and removes its package lists.
- `/opt/dosho/venv` is on `PATH` and includes system site packages. The base
  installs NumPy 1.x, Astropy 7.2.2, SciPy 1.17.1, OmegaConf 2.4.0 and
  `dask-ms[xarray]==0.2.21`. Dask 2024.6.0, xarray 2024.6.0 and pandas
  2.2.2 are pinned because current Dask removed an internal function that
  this `dask-ms` release imports. Astropy is pinned because the unpinned
  resolver selected different releases on AMD64 and ARM64.
  Children may install their own Python package versions in the venv; native
  bindings require an ABI check. The apt copy of `python3-casacore` stays
  available if a child does not override it.
- One Python interpreter keeps the base small. CubiCal's 3.9 and ragavi's 3.6
  need separate images or their own interpreter setup. A future shared Python
  variant needs evidence of enough reuse to justify every child's pull cost.

The local images are 211,850,643 bytes unpacked on AMD64 and 207,345,438
bytes on ARM64, compared with 634,327,575 bytes for the previous AMD64
`kern10` base. A `docker save | gzip -1` comparison gave 210,214,314
versus 631,725,376 bytes respectively. This is a local archive comparison,
not a registry pull-size measurement. Skipping pip bytecode compilation
removed roughly 26 MB and shortened the emulated ARM64 package install.
FITSTOOLZ built and ran its CLI on both architectures with the new base. On ARM64 it installs its required NumPy 2 over the apt NumPy 1;
`casacore.tables` still imports, but pip reports that the inherited
`dask-ms==0.2.21` declares `numpy<2`. FITSTOOLZ does not use dask-ms;
children needing both packages must select compatible versions and validate
their operations, not rely on this import smoke check alone.

## KERN-10 package findings

[KERN's installation instructions](https://kernsuite.info/installation/)
identify the Noble PPA. Its live
[Release file](https://ppa.launchpadcontent.net/kernsuite/kern-10/ubuntu/dists/noble/Release)
lists both `amd64` and `arm64`. The package indexes contain `casacore-tools`
3.7.1-1kern1, `python3-casacore` 3.7.1-1kern2 and `casacore-data`
20250826-160001-5 on both architectures. The local AMD64 and emulated ARM64
builds select the KERN packages from this PPA, rather than Ubuntu's copies.
The PPA also contains `aoflagger` 3.5.0-1kern1 on ARM64; its binary
passed a local version check in the native-tool milestone.

PyPI does not provide an ARM64 wheel for the current `python-casacore`
release. Installing the PPA's architecture-specific `python3-casacore` lets
ARM64 children use the binding without compiling it. A forced pip install of
`python-casacore==3.7.1` into the base venv succeeded on AMD64 while leaving
the apt package in place. A child that requires another version can install
into the venv, but an ARM64 source build needs
`casacore-dev` and a runtime import/ABI test in that child.

## Publishing and verification

`BASE_ASTRO` uses the new `noble-kern10` version and declares
`linux/amd64` and `linux/arm64`. The CLI uses Buildx to build/push both
platforms as one manifest, and its existence and verify checks inspect the
manifest's platforms. The image workflow installs QEMU and Buildx for this
base. Builds and runtime smoke tests on kudu use emulation for ARM64, as
requested; native ARM64 hardware has not been used. A local Buildx OCI export
contains both `linux/amd64` and `linux/arm64` image manifests under one index. The tag is not yet
published. Existing child tags are immutable and still contain their earlier
base layers. Each child needs its own new version and build before publication
against this base; only children validated on ARM64 should declare ARM64.

For source-heavy tools, native builders may be faster. Docker
[documents](https://docs.docker.com/build/building/multi-platform/) that QEMU
emulation can be much slower for compilation. Each child must pass an ARM64
command check before its manifest declares ARM64.

## Later designs

The **CASA tasks** needed a Linux ARM64 `casatools` build; changing this
shared base alone would not have provided one. The pinned `casatasks` release
is a
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

The separate CASA tasks milestone built `casatools` from source and passed
local AMD64 and emulated ARM64 import and `listobs` checks. That image does
not inherit `BASE_ASTRO`: it has its own source and dependency stack. Broader
scientific qualification remains separate from the shared-base work.

**Defer plotms.** The task-image design should omit `casaplotms`, Qt/AppImage
extraction, and plotms-specific runtime libraries. When plotms is revisited,
give its wrapper a separate image key rather than publishing one tag whose
capabilities differ between AMD64 and ARM64. The current plotms wrapper stays on `CASA6` and remains AMD64-only until
its own ARM64 route is qualified.

DDFACET needs a separate inventory of each native dependency and
architecture-specific compiler setup; KILLMS depends on that result. Those
plans follow the base package gate and are outside this design.
