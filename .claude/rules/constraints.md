# Project Constraints

## Core

- **Unbaked/editor-saved assets only** — Cooked assets have graph data stripped
- **Read-only** — Parse only; no modification or writing
- **Zero runtime dependencies** — No third-party packages in `dependencies` (PAK optional deps in `optional-dependencies`)
- **No `pip install`** — Run via `python run.py` directly; CI `pip install pytest` is test-only
- **UE source required** — Format understanding must trace to UE C++ source; no binary guessing
- **Temp files in `temp/`** — Scripts, intermediate output, debug logs, test artifacts

## v0.5.1 Constraints

- **Unified status model** — All output formats use `success | partial | failed`; no legacy `fail`/`error`
- **Export-level status validation** — `parse_status` must be an `ExportParseStatus` enum value
- **UE-style load lifecycle** — Execution order: `link() → preload(idx) × N → post_load()`; no post_load before export parsing
- **Class serialization strategy** — Registered via `class_serialization_strategy.py`; no hardcoded class names in core pipeline
- **Payload offset default** — Use `SerialOffset/SerialSize` (aligned with UE LinkerLoad.cpp:4793); ScriptSerialization offset kept as diagnostic only
- **Opaque class marking** — `OPAQUE_CLASS_PAYLOAD` must set both instance and export `parse_status`
