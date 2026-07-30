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
test is whether the *upstream* is one dosho can depend on: a parameter schema
that states its own types, and output names dosho can predict without executing
the tool's own code. Where that fails, every gap an audit turns up is a patch
dosho would carry forever for a tool it does not control, and the burden
accumulates quietly. dosho states the limitation instead.

Both cabs below have their I/O fully declared -- products as output fields and
``harvest`` globs, caches and logs as ``scratch`` (mounted, never rescued into
your workspace). **Nothing is silently lost.** What is left in each case is a
wiring limitation, plus the standing expectation that an upstream release may
move the schema under the cab.

Current list
------------

``ddfacet``
    ``DefaultParset.cfg`` carries no usable ``#type:`` tags, so every path had
    to be classified from its help text, and ``Output-Images`` letter codes name
    the image family at run time.

    **Declared:** the apparent- and intrinsic-flux restored images, residuals,
    models, the dirty image, the PSF and the ``.DicoModel`` are output fields
    with resolved templates; ``harvest=["{output_name}.*"]`` covers the rest of
    the family; ``scratch`` covers ``Cache-Dir`` and ``Montblanc-LogFile``.

    **The residual:** individual per-major-cycle images (``.mask00``,
    ``.Taylor0.00``) are harvested but cannot be wired as an ``OutputRef``, since
    only the tool knows which codes a given run emits. ``Cache-DirWisdomFFTW`` is
    undeclared because its ``~/.fftw_wisdom`` default is HOME-relative, and
    shinobi resolves a relative declaration against the working directory, not
    ``$HOME``; in the default case it needs no declaration, since
    ``run_as_host_user`` sets HOME to the mounted workdir.

``killms``
    ``DefaultParset.cfg`` declares almost no types, and killMS builds its own
    output filename internally as ``reformat(MSName) + SolsName``.

    **Declared:** ``Solutions-SolsDir`` as an output, so the solutions directory
    is mounted and harvested wherever it points; ``ImageSkyModel-DDFCacheDir`` as
    ``scratch``.

    **The residual:** the ``.sols.npz`` path cannot be named, so a downstream
    step wires the solutions *directory* plus the solution name -- which is what
    DDFacet's ``DDESolutions-SolsDir`` / ``DDESolutions-DDSols`` want anyway, so
    this costs nothing for the pipeline shape these two are used in.

Working around it
-----------------

There is no longer a data-loss mode to work around: point ``Output-Name``,
``Solutions-SolsDir``, ``Cache-Dir``, ``Montblanc-LogFile`` or
``ImageSkyModel-DDFCacheDir`` wherever you like and the directory is mounted.
What remains is wiring: if a pipeline needs to depend on a product no field
names -- a per-major-cycle debug image, or the ``.sols.npz`` itself -- pass the
*directory* to the next step and let it find the file, the way DDFacet already
consumes killMS's solutions.

The one exception is ``Cache-DirWisdomFFTW``: if you point it at an absolute
path outside the working directory, mount that directory yourself.
