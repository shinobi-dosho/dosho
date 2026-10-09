:orphan:

Output-family parameter audit
=============================

Checked 2026-10-07; source heads and release versions reconfirmed 2026-10-08.
This inventory records the pre-migration schema and findings supporting
:doc:`../design_output_families`. The implemented declarations and native
qualification are recorded in :doc:`output_family_migration`. Image pins remain
unchanged.
``DDF`` means DDFacet and ``sofia`` means the native ``sofia2`` cab.

Evidence and coverage
---------------------

:download:`Machine-readable inventory <output_family_parameters.json>` records all
540 parameter definitions: upstream names, explicit/documented types,
defaults, available choices, definition links at source lines, and current
dosho field/type matches. Definitions are linked rather than copied into a
second maintained catalogue. It is an audit snapshot, not loader input.

.. list-table::
   :header-rows: 1
   :widths: 16 15 15 18 36

   * - Tool
     - Image pin
     - Latest release
     - Source revision
     - Inventory
   * - QuartiCal
     - 0.2.5
     - 0.2.7
     - ``15c081e1`` (main)
     - 51 common parameters, 12 per-term attributes
   * - DDFacet
     - 1.0.0.0
     - 1.0.0.0
     - ``2fe05ab4`` (master and release)
     - 273 CLI options, one parset-only version field
   * - killMS
     - 3.3.0
     - 3.3.0
     - ``350f22c6`` (master and release)
     - 94 CLI options
   * - SoFiA-2
     - 2.7.0
     - 2.7.1
     - ``a7434d9f`` (master and release)
     - 109 control parameters

GitHub source was retrieved with ``gh api``. SoFiA's authoritative repository
is GitLab; its old GitHub mirror was not used as the current source.
The QuartiCal schemas on current main are identical to release 0.2.7.
SoFiA 2.7.0 and 2.7.1 have identical hard-coded parameter names/defaults.
The live SoFiA wiki was checked against the pinned source; its fetched
content hash is recorded in the inventory.

Extraction read YAML/CFG/C text and the Python AST as data. No external
package, schema generator, or upstream configuration parser was imported
or executed. The findings below describe that audit snapshot; the migration
record identifies the subsequent fixes and container checks.

Types need evidence, not automatic inference
--------------------------------------------

QuartiCal supplies explicit ``dtype`` metadata except for three string-valued
choice fields. The inventory records that omission and the default type.
Optionality, choices and element choices remain distinct metadata.

DDFacet has 90 explicit ``#type`` annotations and 184 untagged entries,
including the parset-only version field. Its parser accepts numbers and
lists for some untagged options. For example, ``Image.NPix`` and
``Image.Cell`` document scalar or two-element forms. The inventory retains
the absent upstream type and a separately labelled default-literal type;
it does not claim that a default determines the complete accepted type.
Existing dosho dtypes are recorded for comparison, not used as upstream
proof. ``Misc.ParsetVersion`` has ``#no_cmdline:1`` and is intentionally
absent from the cab's CLI fields.

killMS CLI token types come from literal ``add_option`` declarations in
``read_options``. String tokens are subsequently converted by its own
``FormatValue`` function; ``str`` in that parser table is therefore not proof
that the semantic value must stay a string. Defaults come from its parset.
Filesystem dtypes such as ``MS`` and ``File`` are dosho annotations of a
parameter's role, not literal CLI parser types.

SoFiA's wiki gives types and accepted values. Those are cross-checked against
``Parameter_get_bool/int/flt/str`` call sites and the source's inline help.
Some lists are transported as comma-separated strings, so the C getter type
and the public parameter type are both retained. Defaults come from
``Parameter_default`` in ``src/Parameter.c``: the template explicitly says
it is not the authoritative default table.

QuartiCal findings
------------------

Current common and per-term names remain the schema's dotted names, e.g.
``output.gain_directory``, ``solver.terms``, and ``K.time_interval``.

.. list-table::
   :header-rows: 1

   * - Parameter
     - Upstream type/default
     - Definition or output implication
   * - ``output.gain_directory``
     - ``URI``, ``gains.qc``
     - Local/S3 gain-store location. The cab's resolved output is currently
       ``Directory``, losing the declared input's storage semantics.
   * - ``solver.terms``
     - ``List[str]``, ``[G]``
     - Ordered user-named gain terms, also used for store group names.
   * - ``output.net_gains``
     - ``Optional[List[Any]]``
     - One term list or several term lists; writes named combined groups.
   * - ``output.compute_baseline_corrections``
     - ``bool``, false
     - Enables the additional ``BLCORR`` group in the same store.
   * - ``input_ms.group_by``
     - ``Optional[List[str]]``
     - Controls actual MS partitions; not a Cartesian filename dimension.
   * - ``<term>.time_interval``, ``<term>.freq_interval``
     - ``str``, ``"1"``
     - Counts or unit-bearing intervals inside solution arrays.
   * - ``solver.collapse_chain``
     - ``bool``, true
     - New relative to image 0.2.5; collapses the solver chain. Missing in cab.
   * - ``<term>.scalar``
     - ``bool``, false
     - New relative to image 0.2.5; scalar treatment for supported diagonal
       terms. Missing in the cab's parameter pattern.

The current gain-type choices also include ``delay_tec_and_offset`` and
``feed_flip``. Port their constraints only alongside the intended version
update. ``output.products`` and ``output.columns`` describe MS column writes;
they do not make each column an independently owned file-family member.

DDFacet findings
----------------

The current cab covers all 273 CLI names in the default parset; the remaining
field is internal version metadata. Coverage of names does not establish
complete types, choices, defaults, or product declarations.

Output controls are ``Output.Mode`` (Dirty/Clean/Predict/PSF),
``Output.Name`` (string prefix), ``Output.Images`` and ``Output.Also``
(image-code strings), ``Output.Cubes`` (cube-code string), and
``Output.StokesResidues`` (I/IQ/IV/QU/IQUV). Native flags use section/name
hyphens, e.g. ``--Output-Cubes``. ``RIME.PolMode`` controls Stokes content;
``Freq.NBand`` controls imaging frequency bands. These can change the
contents of one FITS cube rather than the number of output files.

The current scalar fields omit many valid products and intermediate cycles.
Harvesting ``{output_name}.*`` preserves captured files but does not provide
logical references for them. Families need representation and flux-scale
labels, actual saved cycle ordinals, and precise product-kind patterns.

killMS findings
---------------

The cab has the 94 parameter names under section-derived Python field names,
but its flag mapping is wrong for the current driver. The actual option
parser defines flat flags, e.g. ``--MSName``, ``--SkyModel``, ``--SolsDir``,
``--OutSolsName``, ``--SolverType``, ``--dt``, and ``--NChanSols``.
The cab/tests currently expect forms such as ``--VisData-MSName`` and
``--Solutions-OutSolsName``. This needs a separate CLI mapping correction
with real parser checks; the Python field names can remain stable.

``Solutions.SolsDir`` (CLI string, default None) controls the solutions root.
``Solutions.OutSolsName`` (CLI string, default empty) supplies the solution
name, otherwise the solver type is used. ``Solvers.dt`` (float, 30 minutes)
and ``Solvers.NChanSols`` (int, 1) control internal solution dimensions.
``Solvers.PolMode`` controls Jones representation. None requires a separate
file per time/frequency/polarization cell.

The existing directory output misses member-level solution/parset references
and has no resolved location when ``SolsDir`` is unset. The native driver
also accepts a text list of MSs for batch operation; that needs a distinct
input-contract audit before promising multi-MS family support in this cab.

SoFiA-2 findings
----------------

Nine current control parameters are missing from the cab:

.. list-table::
   :header-rows: 1

   * - Parameter
     - Documented type/default
     - Definition
   * - ``input.primaryBeam``
     - string, empty
     - Optional primary-beam cube; a file input.
   * - ``flag.cube``
     - string, empty
     - Optional integer flag cube; a file input.
   * - ``output.dataFormat``
     - string, ``fits``
     - FITS/HDF5 image and cube storage, with build-dependent fallback.
   * - ``output.writeLogFile``
     - bool, true
     - Writes pipeline log messages to a named output log.
   * - ``output.writePV``
     - bool, false
     - Per-source major/minor-axis PV products when cubelets are enabled.
   * - ``output.writeKarma``
     - bool, false
     - Catalogue source labels in ``_cat.ann`` annotation format.
   * - ``output.marginAperSpec``
     - int, -1
     - Spectral margin for aperture spectra; -1 uses the full spectral axis.
   * - ``output.showPreviewImage``
     - bool, false
     - Terminal image preview; not a new owned scientific output.
   * - ``output.writeDiagnosticPlot``
     - bool, true
     - Diagnostic plot output with ``_diagnostic.eps`` suffix.

All nine are present in the pinned 2.7.0 parameter table as well.
The current cab has no legacy ``input.pbeam`` field either.
Existing ``output.writeMoments`` also emits ``_snr`` maps where applicable;
the scalar output schema does not declare those. Cubelets include masked
and aperture spectra, SNR maps and optional PV products, not just subcubes.
Source IDs must come from the produced members, not a guessed source count.

Requested HDF5 falls back to FITS if the binary lacks HDF5 build support.
The published collection must preserve the actual format; an input value
alone cannot guarantee the filename extension. Two-dimensional data omits
some spectral products. No-source failure uses exit code 8 and cannot be
cached as successful merely because an output directory was created.

The cab intentionally supplies ``output.directory=.`` and
``output.filename=sofia`` instead of the tool's input-derived defaults.
Those deviations should stay documented and participate in normal validated
inputs. Enabling accurate output declarations does not require silently
changing them.

Authoritative sources
---------------------

* `QuartiCal common schema
  <https://github.com/ratt-ru/QuartiCal/blob/15c081e1eee83a17ac063aff4e590cd79aa26139/quartical/config/argument_schema.yaml>`_
  and `gain schema
  <https://github.com/ratt-ru/QuartiCal/blob/15c081e1eee83a17ac063aff4e590cd79aa26139/quartical/config/gain_schema.yaml>`_.
* `DDFacet default parset
  <https://github.com/saopicc/DDFacet/blob/2fe05ab4a3399ef44a631b6116608f21239e2a57/DDFacet/Parset/DefaultParset.cfg>`_
  and `option parser
  <https://github.com/saopicc/DDFacet/blob/2fe05ab4a3399ef44a631b6116608f21239e2a57/DDFacet/Parset/MyOptParse.py>`_.
* `killMS CLI definitions
  <https://github.com/saopicc/killMS/blob/350f22c67a4b769b2c105327116028e7b13a86fb/killMS/kMS.py#L83>`_,
  `token parser
  <https://github.com/saopicc/killMS/blob/350f22c67a4b769b2c105327116028e7b13a86fb/killMS/Parset/MyOptParse.py#L63>`_,
  and `default parset
  <https://github.com/saopicc/killMS/blob/350f22c67a4b769b2c105327116028e7b13a86fb/killMS/Parset/DefaultParset.cfg>`_.
* `SoFiA control-parameter docs
  <https://gitlab.com/SoFiA-Admin/SoFiA-2/-/wikis/SoFiA-2-Control-Parameters>`_,
  `hard-coded defaults
  <https://gitlab.com/SoFiA-Admin/SoFiA-2/-/blob/a7434d9f91605cd738f2b13cd31b1450304fbc11/src/Parameter.c#L515>`_,
  and `inline parameter definitions
  <https://gitlab.com/SoFiA-Admin/SoFiA-2/-/blob/a7434d9f91605cd738f2b13cd31b1450304fbc11/src/Help.c>`_.
