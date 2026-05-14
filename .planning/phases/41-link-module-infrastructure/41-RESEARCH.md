# Phase 41: link/ 模块基础设施 - Research

**Researched:** 2026-05-14
**Domain:** UE FLinkerLoad pattern replication, Python dataclass architecture
**Confidence:** HIGH

## Summary

This phase creates the three core classes for the `src/uasset_read/link/` module: `UObjectInstance` (object instance dataclass), `PackageLinker` (two-phase loading coordinator), and `LinkerParseResult` (return result class). The `UObjectInstance` class already has a skeleton implementation in `link/object_instance.py` with all core fields and 5 method stubs. `PackageLinker` and `LinkerParseResult` do not exist yet.

The phase replicates UE's FLinkerLoad two-phase loading pattern: `link()` reads header info and creates UObjectInstance shells (no property deserialization), then `preload(index)` lazily deserializes individual object properties on demand. This is the foundational infrastructure layer for v7.0 object graph reconstruction -- it does not modify existing serializers.

**Primary recommendation:** Use the existing `UObjectInstance` skeleton as-is (fields and methods are well-designed), create `PackageLinker` in `link/linker.py` and `LinkerParseResult` in `link/result.py`, follow existing project patterns for dataclasses and result types.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Object instance representation | Application/Parser | — | Pure data model, no I/O |
| Two-phase loading coordination | Application/Parser | FArchive (I/O) | Orchestrates header reads + lazy preload |
| Package index resolution | Application/Parser | — | Maps FPackageIndex to UObjectInstance |
| Outer tree building | Application/Parser | — | Constructs parent-child relationships |
| Parse result aggregation | Application/Parser | — | Returns structured result to caller |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `dataclasses` | 3.10+ | Data structure definition | Project convention — all models use `@dataclass` |
| Python stdlib `typing` | 3.10+ | Type annotations | Project convention — TYPE_CHECKING guards for circular imports |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Python stdlib `__future__` annotations | 3.10+ | Forward references in type hints | All new modules use `from __future__ import annotations` |

**Installation:** No new dependencies. Zero runtime dependency policy maintained.

**Version verification:** Python 3.14.3 confirmed on target machine. Project requires 3.10+ (uses `dataclass`, `TYPE_CHECKING`, `field(default_factory=...)`).

## UE FLinkerLoad Reference Patterns

### FLinkerLoad Two-Phase Loading

Unreal Engine's `FLinkerLoad` (source: `Runtime/CoreUObject/Private/UObject/LinkerLoad.cpp`) implements a strict two-phase loading pattern:

| UE FLinkerLoad | PackageLinker Correspondence |
|---|---|
| `Link()` | `link()` — read header, create UObjectInstance shells |
| `CreateExport(int32 Index)` | Internal shell creation (within `link()`) |
| `Preload(UObject* Object)` | `preload(index)` — lazy deserialize properties |
| `ImportMap` | `_import_objects` (UObjectInstance list) |
| `ExportMap` | `_export_objects` (UObjectInstance list) |
| `LinkerRoot` | `_root_objects` |
| `IndexToObject(FPackageIndex)` | `resolve_package_index(pkg_idx)` |
| `DependsMap` | Not in Phase 41 scope (later phase) |

### FLinkerLoad::Link() Pattern (Phase 1)

1. Read PackageFileSummary (already done by `read_package_summary()`)
2. Read NameMap (already done by `read_name_table()`)
3. Read ImportMap entries, create FObjectImport records (already done by `read_import_map()`)
4. Read ExportMap entries, create FObjectExport records (already done by `read_export_map()`)
5. **For each ExportMap entry**: call `CreateExport()` which:
   - Resolves `ClassIndex` to actual UClass (may require loading other packages)
   - Calls `StaticConstructObject_Internal()` to create a "skeleton" UObject
   - At this point, the object exists but **its properties have NOT been deserialized**
6. **For each ImportMap entry**: create a placeholder UObject (import objects are not serialized in this package)
7. Build outer tree relationships (parent-child via `OuterIndex`)

### FLinkerLoad::Preload() Pattern (Phase 2)

1. Seek to object's `SerialOffset` in the file
2. Read `SerialSize` bytes of serialized property data
3. Call `UObject::Serialize()` to deserialize properties
4. Object is now fully loaded and usable

### Why Two-Phase?
- Creates all object instances first so cross-references can be resolved
- Serializes property data knowing all objects already exist
- Supports lazy/asynchronous loading (preload only what's needed)
- Handles circular dependencies between objects

### Source References
- [FLinkerLoad API](https://dev.epicgames.com/documentation/unreal-engine/API/Runtime/CoreUObject/FLinkerLoad) — UE 5.7 official docs [CITED: dev.epicgames.com]
- [FLinkerLoad::Preload](https://dev.epicgames.com/documentation/unreal-engine/API/Runtime/CoreUObject/FLinkerLoad/Preload) — UE 5.7 official docs [CITED: dev.epicgames.com]
- [LinkerLoad.cpp source](https://github.com/donaldwuid/unreal_source_explained/blob/master/main/initialization.md) — CreateExport code snippet [CITED: github.com/donaldwuid]
- [UE5 .uasset file format analysis](https://www.cnblogs.com/bodong/p/17618007.html) — bodong's detailed analysis [CITED: cnblogs.com]

## Architecture Patterns

### Recommended Project Structure

```
src/uasset_read/link/
├── __init__.py            # Module exports (D-03: submodule import only)
├── object_instance.py     # UObjectInstance dataclass (EXISTING — needs no changes)
├── linker.py              # PackageLinker (NEW — two-phase loading)
└── result.py              # LinkerParseResult (NEW — result aggregation)
```

### Existing UObjectInstance Skeleton (VERIFIED from codebase)

The file `src/uasset_read/link/object_instance.py` already exists with a complete field layout and 5 method stubs. The fields are:

| Field | Type | Purpose |
|-------|------|---------|
| `package_index` | int | Encoded: positive=export, negative=import, 0=null |
| `object_name` | str | Object name (e.g. 'Default__MyBlueprint_C') |
| `object_class` | Optional[str] | Class name (e.g. 'BlueprintGeneratedClass', 'EdGraph') |
| `class_package` | Optional[str] | Package containing the class (e.g. '/Script/Engine') |
| `outer_index` | Optional[PackageIndex] | PackageIndex pointing to the Outer (parent) object |
| `is_import` | bool | True if from ImportMap, False if from ExportMap |
| `serial_offset` | int | Byte offset in file where serialized data starts |
| `serial_size` | int | Size of serialized data in bytes |
| `linker` | Optional[PackageLinker] | Reference to the owning PackageLinker |
| `outer` | Optional[UObjectInstance] | Resolved parent object |
| `serialized_properties` | List[Any] | Parsed property values (filled by preload) |
| `property_references` | Dict[str, UObjectInstance] | ObjectProperty values resolved to references |
| `_preloaded` | bool | Whether properties have been loaded |
| `_raw_export` | Optional[ObjectExport] | Reference to raw ObjectExport dataclass |
| `_raw_import` | Optional[ObjectImport] | Reference to raw ObjectImport dataclass |

Existing methods (all skeleton implementations):
- `is_export` (property) — returns `not self.is_import`
- `is_null` (property) — returns `self.package_index == 0`
- `get_full_name()` — builds UE object path: 'Outermost.Outer.Inner.ObjectName'
- `get_class_object()` — resolves class to UObjectInstance
- `get_template_object()` — resolves template (CDO) to UObjectInstance
- `get_children()` — delegates to `linker.get_children(self)`
- `ensure_preloaded()` — lazy loads if needed
- `__repr__()` — formatted string representation

### PackageLinker Design (NEW)

Based on the existing `UObjectInstance` skeleton and project patterns, `PackageLinker` needs:

**Constructor signature:**
```python
def __init__(
    self,
    archive: FArchive,
    summary: PackageFileSummary,
    name_map: List[str],
    import_map: List[ObjectImport],
    export_map: List[ObjectExport],
):
```

**Core internal state:**
| Field | Type | Purpose |
|-------|------|---------|
| `_archive` | FArchive | Binary reader (shared, not owned) |
| `_summary` | PackageFileSummary | File header data |
| `_name_map` | List[str] | Name table |
| `_import_objects` | List[UObjectInstance] | Import-side object instances |
| `_export_objects` | List[UObjectInstance] | Export-side object instances |
| `_root_objects` | List[UObjectInstance] | Top-level objects (no outer) |
| `_preload_cache` | Dict[int, bool] | Track which exports have been preloaded |

**Core methods:**
| Method | Return | Purpose |
|--------|--------|---------|
| `link()` | None | Phase 1: create UObjectInstance shells from ImportMap/ExportMap |
| `preload(index: int)` | None | Phase 2: deserialize properties for specific export |
| `resolve_package_index(pkg_idx: PackageIndex)` | Optional[UObjectInstance] | Map FPackageIndex to object |
| `get_children(obj: UObjectInstance)` | List[UObjectInstance] | Find objects whose outer is `obj` |
| `build_outer_tree()` | None | Resolve OuterIndex references to actual UObjectInstance objects |

**`link()` step-by-step algorithm:**
1. Create `_import_objects` list: iterate `import_map`, create `UObjectInstance` for each entry
2. Create `_export_objects` list: iterate `export_map`, create `UObjectInstance` for each entry
3. Set `linker` back-reference on all instances
4. Store `_raw_import` / `_raw_export` references on each instance
5. Call `build_outer_tree()` to resolve parent-child relationships
6. Collect `_root_objects` (objects with null outer_index)

**`preload(index)` step-by-step algorithm:**
1. Validate index bounds (0 <= index < len(export_map))
2. Check `_preload_cache` — skip if already loaded
3. Get `UObjectInstance` from `_export_objects[index]`
4. Seek to `instance.serial_offset` in archive
5. Call `parse_properties_from_export()` using the corresponding `ObjectExport` entry
6. Store results in `instance.serialized_properties`
7. Mark `_preloaded = True` and update `_preload_cache`

### LinkerParseResult Design (NEW)

Following the existing `ParseResult` pattern from `models/result.py`:

| Field | Type | Purpose |
|-------|------|---------|
| `summary` | Optional[PackageFileSummary] | File header |
| `name_map` | List[str] | Name table |
| `import_map` | List[ObjectImport] | Raw import entries |
| `export_map` | List[ObjectExport] | Raw export entries |
| `linker` | Optional[PackageLinker] | The PackageLinker instance |
| `root_objects` | List[UObjectInstance] | Top-level objects |
| `all_objects` | List[UObjectInstance] | All objects (imports + exports) |
| `errors` | List[str] | Error messages |
| `is_success` | bool | Success flag |
| `mmap_used` | bool | mmap usage flag |
| `mmap_warning` | Optional[str] | mmap warning message |

### Integration with Existing Pipeline

`parse_uasset_with_linker()` (to be created in Phase 42 in `parse_uasset.py`):
```
read_package_summary() → read_name_table() → read_import_map() → read_export_map()
→ PackageLinker(archive, summary, name_map, import_map, export_map)
→ linker.link()
→ LinkerParseResult(linker=linker, summary=..., ...)
→ return result
```

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Data structures | Custom classes with `__init__` | Python `@dataclass` | Project standard — all models use dataclass, includes `__repr__`, `__eq__`, field defaults |
| Result type | Ad-hoc dict/tuple returns | Dedicated `LinkerParseResult` dataclass | `ParseResult` pattern proven across 373 tests |
| Circular import guards | Runtime import tricks | `TYPE_CHECKING` + string annotations | Project standard — `object_instance.py` already uses this pattern |
| Package index resolution | Manual if/else chains everywhere | `resolve_package_index()` single method | Centralized logic prevents bugs with positive/negative/zero index encoding |
| Preload tracking | Boolean flags scattered across code | `_preload_cache` dict + `_preloaded` bool | `_preloaded` already defined in UObjectInstance skeleton |

## Runtime State Inventory

> This is a greenfield module creation phase (not rename/refactor/migration). No runtime state to migrate.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — verified: link/ module has no datastore | N/A |
| Live service config | None — purely code changes | N/A |
| OS-registered state | None — no OS registrations | N/A |
| Secrets/env vars | None — no secrets involved | N/A |
| Build artifacts | None — no installed packages or compiled artifacts | N/A |

## Common Pitfalls

### Pitfall 1: Circular Import Between link/ and serializers/
**What goes wrong:** `object_instance.py` imports `PackageIndex` from `serializers/object_resources.py`, but if `linker.py` imports from `serializers/` which then imports from `link/`, a circular import occurs.
**Why it happens:** PackageLinker needs to call `parse_properties_from_export()` from `parsers/`, which may import from `serializers/`, creating an indirect cycle.
**How to avoid:** Use `TYPE_CHECKING` guards for type-only imports (as `object_instance.py` already does). Runtime imports in `linker.py` should be inside methods, not at module level.
**Warning signs:** `ImportError: cannot import name` at module load time.

### Pitfall 2: FArchive Position State Corruption
**What goes wrong:** `PackageLinker.link()` and `preload()` share the same `FArchive` instance. If `link()` leaves the archive at an unexpected position, subsequent operations read from wrong offsets.
**Why it happens:** FArchive has no position save/restore mechanism. Any seek() changes global state.
**How to avoid:** Always `archive.seek()` explicitly before reading. Never assume current position. The existing `parse_uasset()` already does this correctly for each serializer call.
**Warning signs:** Properties parsed with garbage data, "exceeds file size" errors.

### Pitfall 3: PackageIndex Zero-Meaning-Null Confusion
**What goes wrong:** `PackageIndex(0)` means null, not "first import". Positive = export (1-based), negative = import (negative 1-based), zero = null.
**Why it happens:** Off-by-one errors when converting between PackageIndex and list indices.
**How to avoid:** Use existing `to_import_index()` (`-index - 1`) and `to_export_index()` (`index - 1`) methods. Always check `is_null` first.
**Warning signs:** `IndexError: list index out of range` at index -1, or resolving null references to actual objects.

### Pitfall 4: Import vs Export OuterIndex Resolution
**What goes wrong:** ImportMap entries have `outer_index` that can point to other imports, exports, or null. The resolution logic must handle all three cases.
**Why it happens:** Import outer resolution is often overlooked because imports are "placeholder" objects.
**How to avoid:** `resolve_package_index()` must handle: positive index → `_export_objects`, negative index → `_import_objects`, zero → None.
**Warning signs:** Outer tree has gaps, `get_full_name()` returns incomplete paths.

### Pitfall 5: Preload Re-entrancy
**What goes wrong:** Calling `preload()` on the same index twice causes double property parsing, wasting time and potentially appending duplicate entries to `serialized_properties`.
**Why it happens:** No guard against re-entry.
**How to avoid:** Check `_preloaded` flag at the start of `preload()`. Also check in `ensure_preloaded()`.
**Warning signs:** `serialized_properties` length doubles after multiple calls.

## Code Examples

### Pattern: TYPE_CHECKING guard for circular imports
```python
# Source: src/uasset_read/link/object_instance.py
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.serializers.object_resources import ObjectExport, ObjectImport, PackageIndex
    from uasset_read.link.linker import PackageLinker
```

### Pattern: Result dataclass with error tracking
```python
# Source: src/uasset_read/models/result.py (adapted)
from dataclasses import dataclass, field
from typing import Optional, List

@dataclass
class LinkerParseResult:
    linker: Optional["PackageLinker"] = None
    root_objects: List["UObjectInstance"] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    is_success: bool = False
```

### Pattern: FArchive with explicit seek before each read
```python
# Source: src/uasset_read/parse_uasset.py (existing pattern)
archive.seek(summary.export_offset)
export_map = read_export_map(archive, summary, name_map)
# Later:
archive.seek(export.serial_offset)
properties = parse_properties_from_export(export, archive, ...)
```

### Pattern: ParseResult-like result with success flag
```python
# Source: src/uasset_read/parse_uasset.py §147-167 (existing pattern)
result.is_success = len(result.errors) == 0
# In finally block:
if archive:
    archive.close()
return result
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Direct byte reading, flat data | Two-phase object graph | v7.0 (this phase) | Enables actual object references |
| PackageIndex → name string | PackageIndex → UObjectInstance | v7.0 (this phase) | Real object graph navigation |
| No Outer tree | Outer tree via build_outer_tree() | v7.0 (this phase) | Parent-child navigation |
| All-at-once parsing | Lazy preload() on demand | v7.0 (this phase) | Faster initial load, memory efficient |

**Deprecated/outdated:**
- `resolve_package_index_to_reference()` in `object_resources.py`: Returns `Dict[str, Any]` (name-only resolution). Being replaced by `PackageLinker.resolve_package_index()` which returns `Optional[UObjectInstance]` (actual object reference).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `UObjectInstance` skeleton in `object_instance.py` is the final design — no field additions needed | UObjectInstance Skeleton | LOW — fields are well-defined by UE FObjectExport/FObjectImport structure |
| A2 | `parse_properties_from_export()` can be reused directly in `preload()` without modification | PackageLinker preload() method | MEDIUM — may need to pass additional context (e.g., already-loaded name_map, import_map, export_map) |
| A3 | No new dependencies needed — all functionality achievable with Python stdlib + existing project code | Standard Stack | LOW — project has zero-dependency policy, all building blocks exist |
| A4 | `FArchive` can be safely shared between `link()` and `preload()` calls (single instance, no threading) | FArchive Position State Corruption pitfall | LOW — single-threaded context, explicit seek before each read |

## Open Questions (RESOLVED)

1. **Should `PackageLinker` own the FArchive or receive it as a parameter?**
   RESOLVED: Pass FArchive as a constructor parameter (it's needed for preload). The existing serializers have already consumed the header data, so `link()` can work from the parsed data alone.

2. **How should `preload()` handle version-specific property parsing?**
   RESOLVED: Store `summary`, `name_map`, `import_map`, `export_map` on `PackageLinker` as instance attributes — they're needed for property parsing and already passed to the constructor.

3. **Should `build_outer_tree()` be a separate method or part of `link()`?**
   RESOLVED: `build_outer_tree()` as a separate method called by `link()` internally. This allows testing the outer tree building independently and matches UE's separation of CreateExport and Outer resolution.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Runtime | ✓ | 3.14.3 | — |
| pytest | Testing | ✓ | installed via pip | — |
| Test assets (`.uasset` files) | Integration tests | ✓ | `E:\Develop\lib\UnrealEngine\Samples\FirstPerson` | Synthetic test files |
| Unreal Engine source | Reference only | ✗ (private GitHub) | — | Community documentation, bodong's analysis |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x |
| Config file | none — uses default pytest discovery |
| Quick run command | `python -m pytest tests/test_uasset_read.py -x` |
| Full suite command | `python -m pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| LINK-01 | UObjectInstance dataclass has all required fields | unit | `pytest tests/test_link_object_instance.py -x` | ❌ Wave 0 |
| LINK-02 | PackageLinker.link() creates correct number of UObjectInstance | unit | `pytest tests/test_link_linker.py::test_link_creates_instances -x` | ❌ Wave 0 |
| LINK-03 | resolve_package_index() handles positive/negative/zero indices | unit | `pytest tests/test_link_linker.py::test_resolve_package_index -x` | ❌ Wave 0 |
| LINK-04 | build_outer_tree() constructs correct parent-child relationships | unit | `pytest tests/test_link_linker.py::test_outer_tree -x` | ❌ Wave 0 |
| LINK-05 | preload(index) deserializes properties for specific export | unit | `pytest tests/test_link_linker.py::test_preload -x` | ❌ Wave 0 |
| LINK-06 | LinkerParseResult has correct structure and success flag | unit | `pytest tests/test_link_result.py -x` | ❌ Wave 0 |
| LINK-07 | Existing 373 tests pass (0 regression) | regression | `python -m pytest tests/ -v` | ✅ existing |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_link_*.py -x`
- **Per wave merge:** `python -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_link_object_instance.py` — covers LINK-01
- [ ] `tests/test_link_linker.py` — covers LINK-02 through LINK-05
- [ ] `tests/test_link_result.py` — covers LINK-06
- [ ] `src/uasset_read/link/__init__.py` — module exports
- [ ] `src/uasset_read/link/linker.py` — PackageLinker implementation
- [ ] `src/uasset_read/link/result.py` — LinkerParseResult implementation

## Security Domain

> `security_enforcement` is not set to false in config.json — validation is enabled.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes | FArchive.validate_offset(), validate_size() — already implemented |
| V6 Cryptography | no | — |

### Known Threat Patterns for this Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malformed .uasset file (crafted offsets) | Tampering | FArchive.validate_offset() — all seeks validated |
| Negative serial_size/serial_offset | Tampering | Validation in read_export_map() — already implemented |
| Out-of-bounds PackageIndex | Tampering | Bounds checking in resolve_package_index() — must implement |
| Re-entrancy during preload | Denial of Service | _preloaded flag guard — must implement |

## Sources

### Primary (HIGH confidence)
- `src/uasset_read/link/object_instance.py` — existing UObjectInstance skeleton (verified via Read tool)
- `src/uasset_read/serializers/object_resources.py` — PackageIndex, ObjectImport, ObjectExport definitions (verified via Read tool)
- `src/uasset_read/serializers/package_summary.py` — PackageFileSummary, read_package_summary, read_name_table (verified via Read tool)
- `src/uasset_read/parse_uasset.py` — parse_uasset() pipeline structure (verified via Read tool)
- `src/uasset_read/archive.py` — FArchive class (verified via Read tool)
- `src/uasset_read/models/result.py` — ParseResult pattern (verified via Read tool)
- `src/uasset_read/__init__.py` — module exports pattern (verified via Read tool)
- `.planning/milestones/v7.0-OBJECT-GRAPH.md` — v7.0 design doc (verified via Read tool)
- `.planning/phases/41-link-module-infrastructure/41-CONTEXT.md` — phase context and decisions (verified via Read tool)

### Secondary (MEDIUM confidence)
- [FLinkerLoad API documentation](https://dev.epicgames.com/documentation/unreal-engine/API/Runtime/CoreUObject/FLinkerLoad) — UE 5.7 official [CITED]
- [FLinkerLoad::Preload documentation](https://dev.epicgames.com/documentation/unreal-engine/API/Runtime/CoreUObject/FLinkerLoad/Preload) — UE 5.7 official [CITED]
- [CreateExport code snippet](https://github.com/donaldwuid/unreal_source_explained/blob/master/main/initialization.md) — GitHub mirror [CITED]
- [UE5 .uasset file format analysis](https://www.cnblogs.com/bodong/p/17618007.html) — bodong's technical blog [CITED]

### Tertiary (LOW confidence)
- FLinkerLoad::Link() exact step-by-step implementation details — UE source is private GitHub (EpicGames/UnrealEngine), requiring Epic account linkage [ASSUMED]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — Python stdlib dataclasses, no external dependencies
- Architecture: HIGH — existing codebase patterns verified via Read tool, UE patterns from official docs
- Pitfalls: HIGH — based on verified codebase analysis and known UE serialization behavior
- FLinkerLoad details: MEDIUM — official API docs available, but exact Link() implementation from private source

**Research date:** 2026-05-14
**Valid until:** 30 days (stable domain — UE file format and Python stdlib do not change frequently)
