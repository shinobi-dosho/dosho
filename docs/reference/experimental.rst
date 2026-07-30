Experimental cabs
=================

Most cabs in dosho are supported the same way: their inputs and outputs are
declared precisely enough that shinobi can bind-mount what a containerised run
needs, pre-create what a sandboxed run needs, and wire outputs into the next
step. A few tools do not permit that, and are marked **experimental** rather
than patched around indefinitely.

An experimental cab still runs, and runs correctly in the common case. What it
does not carry is a promise that every execution *mode* is covered. The marker
shows up in three places:

* ``ninja cabs list`` / ``ninja cabs show`` and the :doc:`cab catalog <cabs>`,
  where the cab's description begins with ``EXPERIMENTAL:``;
* a ``UserWarning`` the first time :func:`dosho.get` resolves the name, quoting
  the reason and the unsupported modes;
* this page.

Fetching one by direct import (``from dosho.cabs import ddfacet``) skips the
warning -- there is no hook to fire on an attribute access -- so the reason is
carried on the cab's own ``info`` as well.

Why a tool ends up here
-----------------------

Not because a tool is unimportant, and not because its cab is unfinished. The
test is whether some part of the tool's behaviour can't be declared at all --
where the honest options are to keep adding per-gap patches for an upstream
dosho does not control, or to state the limitation. dosho states it.

Both cabs below have their **products** declared and mounted like any other
cab. What is left in each case is narrower, and named on the cab itself.

Current list
------------

``ddfacet``
    Products are declared: the apparent- and intrinsic-flux restored images,
    residuals, models, the dirty image, the PSF and the ``.DicoModel`` are real
    output fields (source-verified against DDFacet's own
    ``ClassDeconvMachine.py``), and a ``harvest`` glob on ``Output-Name`` covers
    the rest of the letter-code family. So an ``Output-Name`` anywhere -- inside
    or outside the working directory -- is bind-mounted and harvested.

    **The residual:** DDFacet's *scratch* write targets, ``Cache-Dir``,
    ``Cache-DirWisdomFFTW`` and ``Montblanc-LogFile``, are deliberately left
    undeclared. Declaring them would make a sandboxed run rescue a cache tree
    into the caller's workspace, and shinobi has no way to say "mount this but
    do not harvest it". ``Cache-Dir`` defaults to living next to the MS, whose
    directory an input already mounts, so this only bites an explicitly-absolute
    cache directory elsewhere: under docker/podman it is written inside the
    container and lost -- a recompute, not a lost product -- and under
    apptainer's read-only image filesystem it fails the run.

    Per-major-cycle debug images (``.mask00``, ``.Taylor0.00``) are harvested but
    not wireable, since the letter codes name them at run time.

``killms``
    ``Solutions-SolsDir`` is declared, so the solutions directory is
    bind-mounted and harvested wherever it points.

    **The residual:** the ``.sols.npz`` file itself is not nameable -- ``kMS.py``
    builds it internally as ``reformat(MSName) + SolsName`` -- so a downstream
    step wires the *directory* plus the solution name rather than the file. In
    practice that is what DDFacet's ``DDESolutions-SolsDir`` /
    ``DDESolutions-DDSols`` want anyway, so this costs nothing for the pipeline
    shape these two are used in. ``ImageSkyModel-DDFCacheDir`` is undeclared for
    the same reason as DDFacet's ``Cache-Dir``.

Working around it
-----------------

In order of preference:

#. Leave the cache/log options unset, so they default next to the MS (whose
   directory is already mounted) or under the working directory.
#. Point one inside a directory the step's own path-typed inputs already
   contribute -- an input's parent directory is mounted read-write.
#. Run the step natively, or with the sandbox off, and accept that the scratch
   lands wherever the tool puts it.
