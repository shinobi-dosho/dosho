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

Not because it is unimportant, and not because the cab is unfinished. The test
is whether the *upstream* gives dosho something dependable to model:

* a parameter schema that states its own types (DDFacet's and killMS's
  ``DefaultParset.cfg`` files carry almost no usable ``#type:`` tags, and
  ``str`` there means "a string on the command line", not "not a path");
* output names dosho can predict without executing the tool's own code
  (killMS mangles its own with ``reformat(MSName)``; DDFacet names an image
  family by letter code at run time).

Where those fail, the honest options are to keep adding per-gap patches for a
tool dosho does not control, or to state the limitation. dosho states it. If
your pipeline needs one of these modes, the fix belongs upstream -- or in an
explicit mount in your own run configuration, not in a dosho declaration that
guesses at the tool's behaviour.

Current list
------------

``ddfacet``
    DDFacet's write targets -- ``Output-Name``, ``Cache-Dir``,
    ``Cache-DirWisdomFFTW``, ``Montblanc-LogFile`` -- are string-typed and
    undeclared, because the ``Output-Images`` letter-code system names the
    image family at run time.

    **Fine:** a native run, or any run whose ``Output-Name`` is relative (it
    lands under the working directory, which is always mounted) or sits under a
    directory an input already mounts.

    **Not supported:** a *sandboxed* run harvests none of the images, since
    nothing declares them. A *containerised* run does not bind-mount an
    ``Output-Name`` pointing outside the working directory, so those images are
    written inside the container -- discarded on ``docker run --rm``, and a hard
    failure on apptainer's read-only image filesystem.

``killms``
    ``Solutions-SolsDir`` is string-typed and undeclared. killMS builds the
    solutions filename internally as ``reformat(MSName) + SolsName``, which no
    template can reproduce.

    **Fine:** leaving ``Solutions-SolsDir`` unset. The solutions then land
    inside the MS directory, which is already mounted as an input.

    **Not supported:** an explicit ``Solutions-SolsDir`` under a sandboxed run
    (nothing harvests it) or an absolute one outside the working directory
    under a containerised run (not mounted, so the solutions are written inside
    the container).

Working around it
-----------------

In order of preference:

#. Keep the write target relative, so it resolves under the working directory.
#. Point it inside a directory one of the step's real path-typed inputs already
   contributes -- an input's parent directory is mounted read-write.
#. Run the step natively, or with the sandbox off, and accept that the products
   land wherever the tool puts them.
