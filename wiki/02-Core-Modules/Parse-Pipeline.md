---
title: Parse Pipeline
section: parse-pipeline
---

# Parse Pipeline

`parse_uasset.py` provides three entry functions, and `core.py` provides the new high-level API.

## New Core API (0.4.1+ Recommended)

<!-- data-api="parse_single" -->
```python
parse_single(file_path, format="json", tolerant=True, memory_policy=None, ...) -> str
```

Pure function entry point, no argparse/sys.exit/print. Internally handles: parsing -> IR construction -> rendering.

<!-- data-api="parse_batch" -->
```python
parse_batch(input_dir, format="json", output_dir=None, isolate_assets=True,
            memory_policy=None, ...) -> BatchResult
```

Batch-parse all `.uasset`/`.umap` files in a directory. By default, each top-level asset uses an isolated
spawn worker; parent asset linked reads are still completed within that worker. The parent process selects
RSS/timeout tiers based on file size, terminates the current worker if limits are exceeded, records the failure, and continues with subsequent assets.

<!-- data-api="list_formats" -->
```python
list_formats() -> list[str]
```

Returns all registered renderer format names.

## Legacy API (Backward Compatible)

<!-- data-api="parse_package" -->
```python
parse_package(path: str, tolerant: bool = True, include_parent_assets: bool = False, provider, mappings_path, game) -> ParseResult
```

<!-- data-api="parse_uasset" -->
```python
parse_uasset(...) -> ParseResult  # Delegates to parse_package
```

<!-- data-api="parse_uasset_with_linker" -->
```python
parse_uasset_with_linker(path: str, tolerant: bool = True, preload_all: bool = False, ...) -> LinkerParseResult
```

## Full Parse Flow (0.4.1+)

```
1. open_package_bundle() -> PackageBundle
2. bundle.open_archive() -> PackageArchive
3. read_package_summary() -> PackageFileSummary
4. build_version_container() -> VersionContainer
5. read_name_table() -> List[str]
6. read_import_map() -> List[ObjectImport]
7. read_export_map() -> List[ObjectExport]
8. parse_properties_from_export() (per export)
9. [linker only] PackageLinker.link() + post_load()
10. _post_process() -> Blueprint/Graph/Kismet/Components
11. build_package_ir() -> PackageIR          <- Added: IR construction
12. renderer.render(ir, options) -> str       <- Added: rendering
```

## Key Design

- **Three-layer architecture**: ParseResult -> PackageIR -> Renderers (parsing, data, and output are fully separated)
- **Core API**: parse_single/parse_batch are pure functions, shared by CLI/scripts/Skills
- **Tolerance-first**: Optional feature failures do not affect the main pipeline; errors are collected in result.errors
- **Provider abstraction**: Three sources — filesystem/pak/iostore
- **Automatic Linker selection**: parse_single automatically uses parse_uasset_with_linker for formats like json that require a linker

## Module Locations

| Module | Path | Description |
|--------|------|-------------|
| Legacy parse entry | `parse_uasset.py` | parse_package / parse_uasset / parse_uasset_with_linker |
| New Core API | `core.py` | parse_single / parse_batch / list_formats / BatchResult |
| IR Builder | `ir_builder.py` | build_package_ir: ParseResult -> PackageIR |
| IR Models | `models/ir.py` | PackageIR / ExportIR / GraphIR / NodeIR / PinIR, etc. |

> [!TIP]
> Related sections: [[FArchive]] · [[Serialization Module]] · [[Renderer System]] · [[IR Intermediate Representation]]
