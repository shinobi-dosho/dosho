# Multi-architecture DDFacet and killMS images

**Milestone:** Linux AMD64 and ARM64 images for DDFacet 1.0.0.0 and killMS
3.3.0. killMS inherits DDFacet, so the parent must build and publish first.
Both use new immutable `-multiarch` tags. The shared dosho astronomy base
remains unchanged.

## Dependency boundary

DDFacet uses its own Ubuntu 24.04 image. KERN-10 does not supply its full
native stack, and putting this stack into `BASE_ASTRO` would make every Python
child pay for it. The Dockerfile builds SOFA, Blitz, CASAREST, MAKEMS,
MeqTrees-timba and LOFARBeam, then installs DDFacet with its existing beam,
killMS, alternate-backend and DFT extras. killMS adds its Python package on
top of that image. The pre-milestone DDFacet image occupied about 9.9 GB
unpacked on kudu; its virtual environment was about 3.2 GB, including about
1.8 GB of TensorFlow.

The old compiler alternatives named `x86_64-linux-gnu-*` directly. The
Dockerfile now gets the host GNU triplet from `dpkg-architecture`, retaining
GCC/G++/GFortran 11 for both architectures. Native source builds use at most
four compile jobs to fit a standard CI runner. The final stages run
`DDF.py --help` and `kMS.py --help` during the build, so each platform must
pass a runtime startup check before publication.

The first emulated ARM64 package install exposed a `numcodecs==0.15.1`
source-build issue: its CPU detector read the x86 host flags and passed
`-msse2` and `-mavx2` to the ARM compiler. The
[upstream setup script](https://github.com/zarr-developers/numcodecs/blob/v0.15.1/setup.py)
uses the presence of `CFLAGS` to skip those automatic flags; its explicit
SSE2/AVX2 switches also omit the corresponding x86 sources. The DDFacet
Dockerfile now preinstalls that version on ARM64 with generic `CFLAGS` and
both switches, before resolving DDFacet. This source wheel built successfully
under QEMU. The same preinstall is a no-op on AMD64.

## ARM64 NumPy ABI

The first ARM64 DDFacet run built and passed `DDF.py --help` but failed when
opening a MeasurementSet: `PycArray: failed to load the numpy API`. Rebuilding
`python-casacore` from source did not help. Its extension links Ubuntu's
`libcasa_python3.so.7`, which contains the `PycArray` converter and was built
against Ubuntu's NumPy 1.26.4; DDFacet's final virtual environment uses NumPy
2.1.3. Opening the same 98,568-row MS with NumPy 1.26.4 worked, but keeping
NumPy 1 would conflict with several of DDFacet's installed dependencies.

On ARM64, the Dockerfile now rebuilds the seven converter sources from the
matching [casacore 3.5.0 release](https://github.com/casacore/casacore/tree/v3.5.0/python/Converters)
against the final virtual environment's NumPy headers. It installs only
`libcasa_python3.so.7` under `/opt/venv/lib`, which is already preferred at runtime;
the other casacore libraries stay with Ubuntu. A version check rejects a
future Ubuntu casacore upgrade until this pairing is reviewed. Both platforms
create a small casacore table during the build: importing the module alone did
not call the failing NumPy API.

PyBDSF's ARM64 extension still prints a NumPy 1.x ABI error during import, even
though `import bdsf` exits successfully. The separate BDSF image pins NumPy 1
for its own compatibility reasons. The DDFacet image no longer treats a bare
PyBDSF import as a meaningful build check; the PyBDSF backend in DDFacet is
not qualified by this milestone.

## Publishing

DDFacet runs in the image workflow's base job; killMS runs in its dependent
tool job. Both enable QEMU and Buildx. The [standard Ubuntu GitHub runner](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
has 14 GB of storage. To avoid keeping two large platform snapshots at once,
the workflow builds and pushes architecture-specific staging tags one at a
time, prunes Buildx cache between them on that disposable runner, then
creates the public multi-platform manifest only if both builds succeed.
No registry publication has been run as part of this local milestone, so the
CI disk-capacity gate still needs an actual workflow run.

## Validation

The AMD64 release builds passed their Dockerfile help checks. A disposable
98,568-row, 116-channel, four-correlation MeasurementSet produced a DDFacet
dirty FITS image with 4,225 finite pixels and nonzero peak (14.768 Jy/beam).
With a matching one-source BBS catalog, killMS completed calibration and
wrote three time solutions for 37 stations; all 444 Jones-matrix values were
finite. Both runs used `docker run --shm-size=8g`. The image's default
64 MB Docker shared-memory mount filled and stalled the opt-in shinobi Docker
test on this dataset; the current backend has no shared-memory option. A
deployment running this workload needs a larger `/dev/shm` allocation.

The ARM64 release DDFacet image built with its table-opening and help
checks. On the 2,048-row subset it produced a dirty FITS image with 4,225
finite pixels and a 15.057 Jy/beam peak. A separate run on the full 98,568-row
MS completed under QEMU in 12m29s, also with 4,225 finite pixels and a
14.768 Jy/beam peak. The latter used the same converter rebuild in a derived
image; the former used the final rendered Dockerfile. Both used 8 GB of Docker
shared memory.

The ARM64 killMS 3.3.0 image built after removing an unused x86-only
`emmintrin.h` include from its source on ARM64. On a conformant 1,998-row
subset containing three complete 666-baseline time bins and 37 stations, it
completed one-source calibration and wrote 148 finite complex Jones values.
The full-size AMD64 results above remain the broader data-backed check; these
ARM64 runs do not qualify every beam, solver, DFT or multi-MS mode.
