# Multi-architecture native-tool images

**Milestone:** WSClean, AOFlagger, SoFiA-2 and chgcentre on AMD64 and ARM64.
The last is a binary from WSClean's source and already uses the `WSCLEAN`
image key; no fourth image or cab change is needed. All builds use the
Ubuntu 24.04 dosho base and KERN-10 as a signed apt source. On kudu, ARM64
is built and tested under QEMU, as chosen for this project.

| Image key | Cabs | Version and build route | Runtime image |
| --- | --- | --- | --- |
| `WSCLEAN` | `wsclean`, `chgcentre` | WSClean 3.6 and EveryBeam 0.7.4 from pinned source tags; KERN-10 `idg-dev` 1.2.0-2kern8 | dosho base, native runtime libraries and copied installed binaries |
| `AOFLAGGER` | `aoflagger` | KERN-10 `aoflagger` 3.5.0-1kern1 | dosho base plus signed apt package |
| `SOFIA2` | `sofia2` | SoFiA-2 2.7.0 from its pinned source tag | Ubuntu 24.04 with the compiled binary, wcslib and OpenMP runtime |

The [KERN-10 ARM64 package index](https://ppa.launchpadcontent.net/kernsuite/kern-10/ubuntu/dists/noble/main/binary-arm64/Packages.xz)
contains `idg-dev`, `aoflagger` and `wsclean` on ARM64. The PPA's WSClean
3.7 package is not used here: this cab is pinned to 3.6, and the PPA does
not publish an EveryBeam package. Building 3.6 with EveryBeam preserves the
beam capability expected of the existing dosho image. WSClean's CMake can
silently omit IDG or EveryBeam if discovery fails, so the Dockerfile checks
both positive configure messages before compilation. Source builds use
`PORTABLE=Yes` and four compile jobs to bound QEMU memory and CPU use.

Development headers, compilers and source trees stay in build stages.
SoFiA's final image does not inherit the Python astronomy stack; only its
build stage needs the KERN-configured base. AOFlagger's signed apt package
includes GUI libraries, so its runtime is larger than a command-line-only
build would be. The current cab runs the command-line executable.

## Validation

- Both architectures built on kudu. The ARM64 builds used Buildx with QEMU;
  each image ran with `docker run --platform linux/arm64`. WSClean 3.6 ran
  `wsclean --version` and `chgcentre` on both architectures. CMake found
  IDG and EveryBeam during each build, and the final image verifies that
  `wsclean --version` reports both as available. AOFlagger reported 3.5
  with `aoflagger --version`; SoFiA started with `sofia -h`.
- The combined Buildx publish path is enabled only for image keys whose
  `platforms` manifest entry names both targets. These local runtime checks
  establish that binaries start and their dynamic libraries resolve.
  Imaging, flagging and source-finding results still need representative
  datasets before scientific equivalence is claimed.
- Published tags are immutable. These recipes use new `-noble` variants;
  existing registry tags keep their previous contents until new tags are
  built and pushed.

## Other native stacks

CubiCal compiles SharedArray but needs its older Python 3.9 image; ragavi
needs Python 3.6. DDFacet and killMS share a larger C++/Python dependency
stack and remain their own later milestone. CASA tasks are already in their
separate source-built image. This group contains the remaining standalone
native executables in the current cab catalog; `wsclean-mp` has no dosho cab
and is not part of this image contract.
