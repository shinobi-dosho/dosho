Read-only MS imaging and attached history
=========================================

Use ``dosho.get("wsclean-readonly")``, ``dosho.get("ddfacet-readonly")`` or
``dosho.get("quartical-readonly")``; the direct imports are
``dosho.cabs.wsclean_readonly``, ``ddfacet_readonly`` and ``quartical_readonly``.
The existing names retain their general write-capable behavior. Each new cab
uses strict local MSv2 READ access and ``writable: false``. Separate output and
scratch trees let independent readers overlap after their common producer.
Set the execution worker limit high enough and provision the native tools'
resources; graph independence alone does not establish actual overlap.

WSClean fixes reordering and ``no_update_model_required`` on, and prediction,
model-update requirements, ``no_reorder`` and imaging-weight storage off.
``temp_dir`` is required and must be outside every input MS. DDFacet emits
explicit empty ``Predict-ColName`` and ``Weight-OutColName`` arguments and
accepts only Clean, Dirty and PSF modes. External parsets are rejected.
QuartiCal fixes ``output.products`` and ``output.columns`` to empty lists and
``output.flags`` to false; it rejects external parsets and retains gain-store
and log destinations. Dynamic gain-term names are native identifiers, exclude
reserved configuration roots and cannot contain argument separators.

Fixed controls have validated defaults and matching implicit argv constants:
deferred inputs cannot replace their effective native values. Nonempty
QuartiCal output lists fail the shared ``max_length: 0`` constraint. Scratch
and products may not overlap protected inputs, including through symlinks.
Readonly output families still describe only observed products after execution.

``msutils-info``, ``msutils-summary``, ``msutils-flagstats`` and
``msutils-flags-list`` mark their MS path read-only. Their generic MS type
continues to support the formats accepted by each native command; it is not a
new strict MSv4 lifecycle contract. Flags-list declares an optional read of
its sibling ``.flagversions`` history.

Both ``msutils-flags-backup`` and ``msutils-flags-delete`` take an exclusive
strict READ reservation with ``exclusive: true`` on the associated MS and separately own the attached
``DirectoryBundle`` history. This intentionally blocks every concurrent MS
reader or writer while history changes. Their MS input is read-only, has no
mutable marker or echoed MS output, and skip caching is disabled. They grant
no schema/row/subtable changes. Backup declares FLAG
and FLAG_ROW reads and no column writes; delete declares no column reads or
writes. The reservation controls concurrency only; MS mounts remain read-only and
scientific mutation snapshots are not entered. Restore remains a writer. Delete
rejects empty, leading-dot and path-separator version names.

Audit inventory
---------------

* WSClean, DDFacet and QuartiCal: new guarded read-only variants; existing
  general variants retained.
* msutils info, summary, flagstats and flags list: read-only path markers.
* msutils flags backup/delete: exclusive associated-MS ownership, uncached
  attached-history mutation.
* CubiCal, killMS and mixed CASA tools: conservative declarations retained;
  no blanket read-only claim without qualifying their native modes.

Cab access identity records DatasetAccess/FITSAccess declarations and effective
read-only input metadata as ``cab-access-v1``. Frozen workers verify it before
execution; cache hits cannot erase an access-contract change. Output-only
product declarations remain separate, as do dataset states and worker sources.

An interrupted history operation can leave a partial sidecar requiring
inspection or manual repair. Existing owned-output and durable worker-attempt
rules prevent a failed/uncommitted result from authorizing downstream success;
scientific MS snapshots do not claim to restore that separate directory.
Planner hazard labels use the existing read/write reservation vocabulary;
exclusive READ is a strong reservation, not scientific write permission.
QuartiCal ``load_from`` gain stores are read-only sources. Its output gain
store and interpolation scratch must remain disjoint, including symlink aliases.
