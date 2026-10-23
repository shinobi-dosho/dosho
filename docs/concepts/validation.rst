Schema validation and argv formatting
=====================================

Dosho owns cab parameter schemas, validation, scalar metadata, patterns,
policies and validated-parameter-to-argv formatting. Shinobi owns framework
annotations and declarations, DAG/wiring, execution, filesystems and dataset
lifecycle/recovery. Its mandatory dependency is ``dosho[validation]``; Dosho
validation never imports Shinobi.

The validation extra requires Pydantic 2.14 or newer, matching Shinobi's
minimum for threaded generic product-family handoffs. The currently tested Python 3.11–3.14 range is unchanged. Base catalogue access still needs neither Pydantic nor Shinobi.

The public ``dosho.validation`` API exposes ``CabSpec``, ``CompiledCab``,
``parse_document``, ``compile_cab``, ``build_argv``, ``build_model``,
``dtype_to_type``, ``TypeBinding``, ``ParamMeta``, ``Policies``, ``ParamPattern``
and ``ParamSegment``. It can be used independently:

.. code-block:: python

    from dosho.validation import parse_document, compile_cab, build_argv

    spec = parse_document("tool", {
        "command": "tool",
        "inputs": {"count": {"dtype": "int", "required": True}},
    })
    compiled = compile_cab(spec)
    values = compiled.inputs_model(count="4").model_dump()
    assert build_argv(compiled, values) == ["tool", "--count", "4"]

``build_model`` also creates reusable Pydantic input models for Python recipes;
no recipe language is introduced. Shinobi's compatibility helper supplies
explicit trusted bindings for MSv2/CasaTab/FITS/ProductFamily/DirectoryBundle.
Known framework dtypes without bindings are errors, including nested types.
Declarations for dataset accesses, FITS accesses, derived reads and families
are inert JSON until Shinobi validates its authoritative models. Dynamic
matched extras retain historical pass-through behavior.

Static YAML composition is safe data processing: ``_include`` containment and
cycles, ``_use`` merge precedence and warnings remain supported. Package roots
are explicit filesystem roots, never imports. ``dynamic_schema`` never runs;
non-binary commands are rejected before executable argv is returned.

Detached workers stage both packages and digest their combined source tree.
Shinobi's versioned cab cache identity separately records schema/formatter
contract versions and argument semantics. Frozen bundle version 3 verifies
those semantics without confusing them with dataset states or worker attempts.

Release gate
------------

Both projects target 0.2.0b1. Verify an exact local wheel pair first. Dosho's
independent lock contains no reverse framework dependency. Ninja's final
registry lock must wait for authorized publication of the Dosho beta; no local
paths, invented registry hashes or publication are part of this migration.

Provider documents carry the ``dosho-cab-v1`` dialect tag. Old Shinobi releases
reject it rather than silently substituting their earlier compiler. Lazy
runnable-object bridges require the matching adapter capability and provide
explicit installation guidance. Ordinary third-party ``yaml_cab`` documents
remain supported by the new adapter.

Automatic paired CI
-------------------

Dosho's core job covers validation, catalogue/image metadata, CLI,
publication authorization and version tests without Shinobi. Pushes to main
and pull requests also run the full paired cab suite on Python 3.11/3.12 and
build docs against Shinobi main. Reusable and manually dispatched CI default
``ninja-ref`` to ``main`` and accept an explicit branch, tag, or commit override.
Push and pull-request checkouts fall back to ``main`` because those events
have no workflow inputs. The publication workflow reuses the complete CI
workflow and requires core tests, paired tests, and docs to pass before upload.

Literal fields support ordinary Pydantic ``min_length`` and ``max_length``
constraints for strings and containers. Bounds must be nonnegative integers
and the minimum cannot exceed the maximum. Constrained defaults are validated
when constructing the model. These shared constraints also serve Shinobi's
worker configuration models; no cab-specific validation callback is loaded.
