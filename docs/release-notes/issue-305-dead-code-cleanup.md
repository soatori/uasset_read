# Issue #305 Dead-Code Cleanup and Migration Notes

**Date:** 2026-07-27

**Scope:** Verified unreachable definitions remaining after the earlier #305 cleanup commits

**Version metadata:** Unchanged

## What changed

The historical #305 inventory is not a deletion checklist. This pass rebuilt the
candidate matrix from the current source tree, tests, public exports, CLI paths,
module imports, and lazy/reflection-sensitive registration paths. It removes only
bindings that Python had already replaced at module or class creation time.

| Module | Removed unreachable source | Canonical implementation retained |
| --- | --- | --- |
| `blueprint.variable_extractor` | Earlier definitions of `_resolve_parent_class`, `_extract_and_merge_functions`, `_extract_events_from_functions`, `_extract_interfaces_from_props`, and `_extract_interfaces` | The final definitions previously selected by normal Python module loading |
| `ir_builder` | Earlier definitions of `_build_export_raw_ir`, `_build_export_diagnostics`, `_build_resolved_depends_map`, `_infer_bytecode_confidence`, `_extract_parameters_from_signature`, `_bind_implementations`, and `_bind_single_implementation`; the earlier duplicate `_EVENT_ALIASES` binding | The final definitions and alias table previously selected by normal Python module loading |
| `parsers.binary_or_native_handlers` | The earlier inline `_parse_struct_binary` implementation | The registered `_STRUCT_DECODERS` implementation bound in `BINARY_OR_NATIVE_HANDLERS` |
| `parsers.property_types` | The earlier table-driven `_try_fast_path_struct`, `_FAST_PATH_STRUCT_HANDLERS`, `_make_fp_vec3`, and its `_fp_*` helper family | The branch-based `_try_fast_path_struct` previously used by `parse_struct_property` |
| `renderers.markdown_renderer` | The earlier identical `MarkdownRenderer._render_export_properties` definition | The final identical method previously selected when the class was created |
| `cli` | The no-op `--tolerant` flag, whose value was never read | Tolerant mode remains the default; `--strict` remains the single switch that changes it |

This removes 16 shadowed same-scope bindings, the private helper family that
was reachable only through a shadowed function, and one public CLI flag with no
runtime consumer. No active parser or renderer call target changes.

## Public API migration

### Removed public CLI option

`--tolerant` is removed. It was always `True`, and no command path read
`args.tolerant`; all single, batch, diff, and package-list paths derive tolerant
mode from `not args.strict`.

Migration:

```text
# Before
python run.py Asset.uasset --tolerant

# After: tolerant mode is already the default
python run.py Asset.uasset

# To disable tolerant mode
python run.py Asset.uasset --strict
```

No public Python import, class, method, or function parameter is removed in this
pass.

The removed names were private implementation details. Code that directly
imports, monkey-patches, or source-inspects these underscore-prefixed helpers must
move to the supported paths:

- build IR through `uasset_read.ir_builder.build_package_ir`;
- parse properties through the public package parsing APIs;
- render Markdown through `MarkdownRenderer.render` or `render_to`.

Source-location assertions such as `co_firstlineno` will change because only one
definition remains. Runtime package parsing and rendered output retain the
previously active implementations.

## Retained API decisions

| Candidate | Decision | Current evidence |
| --- | --- | --- |
| `GameDirectoryProvider` | Retain | It is a documented independent provider API in `README.md`; lack of a main parser caller is not evidence that it is dead. |
| `parsers.asset_types` handlers | Retain | `get_class_registry()` lazily bootstraps optional modules; the runtime registry currently discovers 26 handlers. Static direct-call counts do not describe this path. |
| HexView rendering chain and `debug` exports | Retain | HexView is connected from CLI/config through archive recording, IR conversion, and JSON/Markdown rendering; `HexViewEntry`, `format_hex_view`, and `format_hex_dump` are explicit `debug.__all__` exports. |
| `graph.parser.extract_blueprint_graphs` | Retain | `pipeline.post_process` imports and calls it, and `graph.__all__` exports it. |
| `PackageLinker` / `UObjectInstance` helpers | Retain | Both classes are documented public link APIs. Removing methods solely because the repository has no direct caller would repeat the independent-API false positive. |
| Pak and IoStore models/helpers | Retain | Their package `__all__` lists define standalone container-reader APIs, including exported structure types and lookup helpers. |
| Versioning models and stream constants | Retain | `FPackageFileVersion` participates in `VersionContainer.file_version`; the stream table is active version lookup data. |
| Protocol-shaped `__exit__` parameters | Retain | Apparently unused exception arguments are required by the context-manager protocol and are not obsolete parameters. |

## Verification contract

`tests/test_dead_code_contract.py` rejects future same-scope rebinding and the
reintroduction of the removed shadow-only struct helper family. The release
acceptance loop also imports every discoverable package module, exercises the
lazy asset-handler registry, runs the full test suite and lint/compile checks,
checks CLI help/contracts, and parses representative tracked assets.
