# Project Constraints

## Core Constraints

- **Editor-saved/unbaked assets only** — Baked assets have graph data stripped
- **Read-only** — Parse only; no modification or writing
- **Zero runtime dependencies** — No third-party packages in `dependencies` (PAK optional dependencies go in `optional-dependencies`)
- **No `pip install`** — Run directly via `python run.py`; `pip install pytest` in CI is for testing only
- **UE source reference required** — Format understanding must trace back to UE C++ source; no guessing binary formats
- **Temp files in `temp/`** — Scripts, intermediate output, debug logs, test artifacts

## Design Constraints

- **Unified status model** — All output formats use `success | partial | failed`; legacy `fail`/`error` not allowed
- **Export-level status validation** — `parse_status` must be an `ExportParseStatus` enum value
- **UE-style load lifecycle** — Execution order: `link() → preload(idx) × N → post_load()`; no calling post_load before export parsing
- **Class serialization strategy** — Register via `class_serialization_strategy.py`; no hardcoded class names in the core pipeline
- **Payload offset defaults** — Use `SerialOffset/SerialSize` (aligned with UE LinkerLoad.cpp:4793); ScriptSerialization offsets are diagnostic only
- **Opaque class marking** — `OPAQUE_CLASS_PAYLOAD` must set both instance and export `parse_status`
- **No backward compatibility** — Project is in rapid iteration; APIs and internals may be freely refactored without maintaining legacy compatibility layers
- **Dead code cleanup** — Remove dead code, legacy aliases, and deprecated interfaces in the same commit; no deprecated markers or transition periods
- **Minimal implementation** — Implement in the simplest way possible; avoid over-abstraction, redundant wrappers, and unnecessary complexity

## Test Organization

- **Root `tests/` holds 6 test files** — 5 benchmark tests + 1 sample test (`tests/samples/`)
- **Benchmark test changes require confirmation** — Before modifying any benchmark test file, explain the changes and get user approval
- **New tests go in domain subdirectories** — Place tests in the appropriate subdirectory under `tests/` (core, kismet, iostore, etc.) based on the code they exercise
- **`tests/samples/` stores only `.uasset` sample files** — No Python test code in this directory

