# Stack Recommendations

**Domain:** Python binary parser for Unreal Engine .uasset files
**Researched:** 2026-04-27

## Recommended Stack

| Component | Recommendation | Version | Rationale |
|-----------|---------------|---------|-----------|
| **Language** | Python | 3.10+ | User-specified; dataclasses (3.7+), typing improvements (3.10+), good binary parsing support |
| **Binary Parsing** | struct (built-in) + mmap | Built-in | No external dependencies needed; struct for typed unpacking, mmap for large files |
| **Data Models** | dataclasses | Built-in (3.7+) | Clean model definitions; asdict() for JSON serialization; type hints |
| **JSON Output** | json (built-in) + dataclasses.asdict | Built-in | Standard; no external dependencies; asdict() converts models directly |
| **CLI Interface** | argparse | Built-in | Simple command-line parsing; standard library; sufficient for single-file tool |
| **File Handling** | pathlib + open/mmap | Built-in | Cross-platform paths; streaming file access via mmap for large files |
| **Error Handling** | Custom exceptions + logging | Built-in | Structured errors; logging for debugging; graceful degradation |

## What NOT to Use

| Library | Why Avoid | Alternative |
|---------|-----------|-------------|
| **construct** | Adds complexity; slower than struct; learning curve for declarative syntax | Use struct.unpack directly with explicit offsets |
| **numpy** | Overkill for byte parsing; memory overhead; not designed for binary serialization | Use struct + mmap |
| **pydantic** | Adds dependency; validation overhead not needed for read-only parsing | Use plain dataclasses |
| **click/rich** | External dependencies; argparse sufficient for simple CLI | Use argparse + plain print |
| **pytest** (for runtime) | Not needed in runtime; testing is separate | Use for tests only |
| **lark/parser** | .uasset is binary, not text; no grammar parsing needed | Binary parsing with struct |
| **marshmallow** | Serialization overhead; not designed for binary formats | Use dataclasses + custom serialize |

## Python Version Requirements

**Minimum: Python 3.10**

Why 3.10+:
- `match/case` statements for type dispatch (cleaner than if/else chains)
- `ParamSpec` and `TypeVarTuple` for advanced typing (if needed)
- Better error messages (helpful for debugging binary parsing issues)
- `dataclasses` mature and stable (available since 3.7, well-tested by 3.10)

If 3.10 unavailable, 3.8+ works with if/else dispatch instead of match/case.

## Dependency Philosophy

**Zero runtime dependencies beyond Python standard library.**

Rationale:
- AI agents need simple installation (`pip install` or just `python uasset_read.py`)
- Standard library sufficient for binary parsing, JSON output, CLI
- Reduces maintenance burden (no version conflicts, no security updates)
- Single-file execution possible (`python uasset_read.py file.uasset`)

Testing dependencies (not shipped):
- `pytest` for unit tests
- `hypothesis` for property-based testing (optional)

## Core Stack Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Runtime Stack                            │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ argparse        CLI argument parsing                    ││
│  │ pathlib         File path handling                      ││
│  │ mmap            Memory-mapped file I/O                  ││
│  │ struct          Binary unpacking                        ││
│  │ dataclasses     Data model definition                   ││
│  │ json            JSON serialization                      ││
│  │ logging         Debug/error logging                     ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    Testing Stack                            │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ pytest          Unit test framework                     ││
│  │ hypothesis      Property-based testing (optional)       ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

## UE Source Reference Stack

The parser must align with Unreal Engine's serialization stack:

| UE Component | Python Equivalent | Source Path |
|--------------|-------------------|-------------|
| `FArchive` | `FArchive` base class | `Core/Public/Serialization/Archive.h` |
| `FArchiveState` | Archive state tracking | `Core/Public/Serialization/ArchiveState.h` |
| `FPackageFileSummary` | `PackageSummary` dataclass | `CoreUObject/Public/UObject/PackageFileSummary.h` |
| `FPackageIndex` | `PackageIndex` dataclass | `CoreUObject/Public/UObject/ObjectResource.h` |
| `FObjectImport` | `ObjectImport` dataclass | `CoreUObject/Public/UObject/ObjectResource.h` |
| `FObjectExport` | `ObjectExport` dataclass | `CoreUObject/Public/UObject/ObjectResource.h` |
| `FName` | Name table + index resolution | `Core/Public/UObject/NameTypes.h` |
| `FString` | Length-prefixed string reading | `Core/Public/Containers/UnrealString.h` |
| `FPropertyTag` | Property tag parsing | `CoreUObject/Public/UObject/PropertyTag.h` |

UE 5.7 source location: `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/`

## Version Handling Strategy

UE uses multiple version systems:

```python
# Version types to handle
EUnrealEngineObjectUE4Version  # 214-522+ (oldest to latest UE4)
EUnrealEngineObjectUE5Version  # 1000+ (UE5 versions)
FCustomVersionContainer        # GUID-based custom versions
LegacyFileVersion             # -2 to -9 (modern format indicators)
```

Parser must:
1. Read all version fields from PackageFileSummary
2. Maintain version compatibility matrix
3. Branch parsing logic based on version
4. Fail gracefully on unsupported versions

## Binary Parsing Patterns

### Pattern 1: struct.unpack with explicit byte order

```python
import struct

# Always use explicit byte order (< for little-endian, > for big-endian)
def read_u32(archive) -> int:
    return struct.unpack('<I', archive.read(4))[0]

def read_i32(archive) -> int:
    return struct.unpack('<i', archive.read(4))[0]

def read_f32(archive) -> float:
    return struct.unpack('<f', archive.read(4))[0]

def read_u64(archive) -> int:
    return struct.unpack('<Q', archive.read(8))[0]
```

### Pattern 2: Memory-mapped file for large assets

```python
import mmap
import os

def create_archive(path: str):
    file_size = os.path.getsize(path)
    if file_size > 100 * 1024 * 1024:  # > 100MB
        return MappedArchive(path)  # mmap-based
    return FileArchive(path)  # standard file handle
```

### Pattern 3: Version-aware serialization

```python
def read_package_summary(archive) -> PackageSummary:
    tag = read_u32(archive)
    
    # Check for byte swapping
    if tag == PACKAGE_FILE_TAG_SWAPPED:
        archive.set_byte_swapping(True)
        tag = PACKAGE_FILE_TAG
    
    # Version fields
    legacy_version = read_i32(archive)
    ue4_version = read_i32(archive) if legacy_version >= -8 else 0
    ue5_version = read_i32(archive) if legacy_version >= -8 else 0
    # ... continue with version-aware logic
```

## JSON Output Stack

```python
from dataclasses import dataclass, asdict
import json

@dataclass
class BlueprintInfo:
    name: str
    parent_class: str
    variables: list[VariableInfo]

@dataclass
class VariableInfo:
    name: str
    type: str
    default_value: str | None

def output_json(blueprint: BlueprintInfo) -> str:
    return json.dumps(asdict(blueprint), indent=2)
```

## Text Output Stack

```python
def output_text(blueprint: BlueprintInfo) -> str:
    lines = [
        f"Blueprint: {blueprint.name}",
        f"Parent Class: {blueprint.parent_class}",
        "",
        "Variables:",
    ]
    for var in blueprint.variables:
        lines.append(f"  - {var.name}: {var.type}")
        if var.default_value:
            lines.append(f"    Default: {var.default_value}")
    return "\n".join(lines)
```

## File Structure Recommendation

```
uasset_read/
├── uasset_read.py          # Main entry point (single-file version)
├── src/
│   ├── __init__.py
│   ├── archive.py          # FArchive base + implementations
│   ├── summary.py          # PackageFileSummary model + parser
│   ├── name_table.py       # Name table parsing
│   ├── import_export.py    # Import/Export map parsing
│   ├── properties.py       # Property tag + value parsing
│   ├── blueprint.py        # Blueprint-specific extraction
│   ├── output.py           # JSON/Text/Summary formatters
│   └── errors.py           # Custom exceptions
├── tests/
│   ├── test_archive.py
│   ├── test_summary.py
│   └── ...
└── pyproject.toml          # Project metadata (optional)
```

**Single-file version** (`uasset_read.py`) for simple deployment:
- All code in one file (~2000-3000 lines)
- Direct execution: `python uasset_read.py file.uasset`
- No package installation required

**Package version** (`src/` directory) for maintainability:
- Clean separation of concerns
- Testable components
- Importable: `from uasset_read import parse_uasset`

## Installation Patterns

### Pattern A: Single-file (zero install)

```bash
# Download single file
python uasset_read.py --json input.uasset > output.json
```

### Pattern B: pip install (package)

```bash
pip install uasset_read
python -m uasset_read --json input.uasset > output.json
```

### Pattern C: Importable module (for AI agents)

```python
from uasset_read import parse_uasset, BlueprintInfo

result = parse_uasset("path/to/file.uasset")
print(result.blueprint.variables)
```

## Performance Considerations

| Approach | Memory | Speed | When to Use |
|----------|--------|-------|-------------|
| FileArchive + read() | Low | Medium | Small files (<50MB) |
| MappedArchive + mmap | Very Low | Fast | Large files (>50MB) |
| Read entire file | High | Fast startup | Not recommended |

## Testing Stack

| Component | Purpose | Notes |
|-----------|---------|-------|
| `pytest` | Unit test framework | Required for development |
| `hypothesis` | Property-based testing | Optional; good for binary edge cases |
| Mock archives | Testing without real files | FMemoryArchive for test fixtures |
| Sample .uasset | Integration tests | Create simple UE project for test files |

## Security Considerations

- No untrusted input parsing (user provides files)
- Memory limits via file size checks
- No network access (standalone tool)
- No file modification (read-only)

## Confidence Levels

| Recommendation | Confidence | Reason |
|---------------|------------|--------|
| Python 3.10+ | HIGH | User-specified; standard library sufficient |
| Zero runtime deps | HIGH | Standard library covers all needs |
| struct + mmap | HIGH | Proven pattern for binary parsing |
| dataclasses | HIGH | Clean models; built-in JSON serialization |
| argparse | HIGH | Simple CLI; standard library |
| Version handling | MEDIUM | Complex but documented in UE source |
| Single-file version | MEDIUM | Good for deployment; may need refactoring for growth |

---

## Sources

- UE 5.7 Source: `D:/Program Files/Epic Games/Engine/UE_5.7/`
- Python docs: struct, mmap, dataclasses, argparse (official)
- CUE4Parse: Binary parsing patterns for UE formats
- FModel: Python-like architecture for UE asset parsing