# Core Architecture

## Pipeline

```text
.uasset → FArchive → Serializers → Parsers → ParseResult
                                      ↓
                          IR Builder → PackageIR → JSON/Markdown Renderers
```

Full pipeline: `parse_package()` → `ParseResult` → `build_package_ir()` → `PackageIR` → `renderer.render(ir, options)`. Renderers receive only IR, not `ParseResult`.

## Key Modules

- `archive.py`: FArchive binary reader layer; `parse_uasset.py`: parse entry point.
- `core/__init__.py`: `parse_single`, `parse_batch`, `diff_single`, shared by CLI and scripts.
- `ir_builder.py`, `models/ir.py`, `models/result.py`: Result-to-IR building and models.
- `objects/`: Cross-export UObject registration and reference resolution.
- `serializers/graph.py` → `graph/flow_builder.py` → `blueprint/` → `kismet/`: Blueprint graph and bytecode chain.
- `cpp_gen/`: Blueprint results to C++ class skeletons; `renderers/`: Output formats registered via `RENDERER_REGISTRY`.

## Status Model

- Package level: `success | partial | failed`
- Export-level status must pass `validate_parse_status()`
- `strict` stops on warning, `tolerant` (default) continues on error and marks `partial`
- `export_count > 300` auto-skips full blueprint parsing

## Important Functions

- `parse_single()` returns formatted string, accepts `tolerant=True` and other params
- `parse_package()` returns `ParseResult` object with errors/warnings attributes
- Batch tests should use `parse_package()` to access full error information
