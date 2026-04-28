# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python tool to parse Unreal Engine .uasset files, enabling AI agents to read blueprint content without UE Editor dependency. Focus on uncooked/editor-saved assets (contain full blueprint data).

## Current Status

**Phase 1 (Core Parsing): Complete** — Parser reads headers, name table, import/export maps. All tests pass.

Next phases (2-5) planned in `.planning/ROADMAP.md`.

## UE 5.7 Source Reference

UE 5.7 source at `./UnrealEngine` (read-only reference).

Key files for .uasset parsing:
- `PackageFileSummary.h` — File header structure
- `ObjectResource.h` — Import/Export structures
- `Archive.h` — FArchive pattern

## External Directories (Git-Excluded)

- `UnrealEngine/` — UE engine source reference (do not modify)
- `LyraStarterGame/` — Sample game assets (do not modify)

## Tech Stack

- **Language**: Python 3.10+ (match/case support, better type hints)
- **Dependencies**: Zero runtime dependencies — stdlib only
- **Parsing**: `struct` for binary, `mmap` for large files (planned)
- **Models**: `dataclasses` with `asdict()` → JSON
- **CLI**: `argparse`
- **Encoding**: UTF-8 only (UE 5.x standard)

## Architecture

Pipeline pattern mirroring UE's FArchive:

```
.uasset → FArchive (reader) → Deserializers → Dataclasses → Output (JSON/text)
```

Core components in `uasset_read.py`:
- `FArchive`: Binary reader with byte swapping, boundary validation
- `PackageFileSummary`: Header with offsets to NameTable/ImportMap/ExportMap
- `FPackageIndex`: Signed int encoding (>0 export, <0 import, 0 null)
- `FName`: NameMap index + instance number
- `ParseResult`: Container with partial results on error

## File Organization

- Source: `uasset_read.py` (single-file for Phase 1)
- Tests: `tests/` directory
- Docs: `docs/` or `.planning/`
- Planning: `.planning/` (GSD workflow files)

## Commands

```bash
# Parse a .uasset file
python -c "from uasset_read import parse_uasset; r = parse_uasset('file.uasset'); print(r)"

# Run all tests
python -m pytest tests/ -v

# Run single test
python -m pytest tests/test_uasset_read.py::test_package_summary_valid -v
```