# Architecture Patterns

**Domain:** Binary file parser for Unreal Engine .uasset files
**Researched:** 2026-04-27

## Recommended Architecture

The recommended architecture follows a **layered pipeline** pattern, mirroring Unreal Engine's own serialization architecture while adapting to Python idioms.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              OUTPUT LAYER                                   │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐  │
│  │   TextOutput    │  │   JsonOutput    │  │      SummaryOutput         │  │
│  │  (Human-readable)│  │ (Agent-parseable)│  │  (Condensed overview)      │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ▲
                                    │
┌─────────────────────────────────────────────────────────────────────────────┐
│                              MODEL LAYER                                    │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐  │
│  │   UObject       │  │   UBlueprint    │  │      FProperty            │  │
│  │   (Base class)  │  │   (Blueprint)   │  │   (Property types)        │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────────┘  │
│                                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐  │
│  │   FPackageIndex │  │   NameTable     │  │      ExportMap/ImportMap   │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ▲
                                    │
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DESERIALIZER LAYER                                │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                         AssetDeserializer                            │   │
│  │  - Reads NameTable, ImportMap, ExportMap                           │   │
│  │  - Dispatches to type-specific handlers                             │   │
│  │  - Resolves cross-references (FPackageIndex)                        │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌───────────────────┐  ┌───────────────────┐  ┌───────────────────────┐   │
│  │ BlueprintHandler  │  │  TextureHandler   │  │    ...other types    │   │
│  └───────────────────┘  └───────────────────┘  └───────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ▲
                                    │
┌─────────────────────────────────────────────────────────────────────────────┐
│                              READER LAYER                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                           BinaryReader                               │   │
│  │  - Low-level byte operations (read_u8, read_u32, read_f32, etc.)   │   │
│  │  - Endianness handling                                              │   │
│  │  - Stream position management                                        │   │
│  │  - Memory-mapped file support                                       │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌───────────────────┐  ┌───────────────────┐  ┌───────────────────────┐   │
│  │   FileReader      │  │   MemoryReader    │  │    PakReader         │   │
│  │  (file streams)   │  │  (bytes buffer)   │  │   (pak archives)     │   │
│  └───────────────────┘  └───────────────────┘  └───────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ▲
                                    │
┌─────────────────────────────────────────────────────────────────────────────┐
│                            INPUT LAYER                                      │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                           .uasset file                               │   │
│  │  [PackageFileSummary][NameTable][ImportMap][ExportMap][Payload]     │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| **BinaryReader** | Low-level byte reading, endianness, seeking | Input layer (reads from), Deserializer (serves) |
| **AssetDeserializer** | Orchestrates parsing, type dispatch, reference resolution | Reader (reads from), Model (creates), Handlers (dispatches to) |
| **TypeHandlers** | Type-specific parsing logic (Blueprint, Texture, etc.) | Deserializer (receives context), Model (creates) |
| **Models** | Structured data representation | Deserializer (created by), Output (served to) |
| **OutputFormatters** | Transform models to text/JSON/summary | Model (reads from) |

### Data Flow

```
.uasset file
    │
    ▼
BinaryReader.open(path)
    │
    ├─► read_package_summary() ─► PackageSummary model
    │
    ├─► read_name_table() ─► List[str] (NameMap)
    │
    ├─► read_import_map() ─► List[ObjectImport]
    │
    ├─► read_export_map() ─► List[ObjectExport]
    │
    ▼
AssetDeserializer.parse_exports()
    │
    ├─► resolve_export_type() ─► "Blueprint", "Texture", etc.
    │
    ├─► dispatch_to_handler(export_type)
    │       │
    │       └─► BlueprintHandler.parse(reader, context)
    │               │
    │               └─► Blueprint model (with nodes, properties, etc.)
    │
    ▼
OutputFormatter.format(model, format="text"|"json"|"summary")
    │
    ▼
Structured output (text/JSON/summary)
```

## Patterns to Follow

### Pattern 1: Archive/Reader Abstraction (from UE FArchive)

**What:** Abstract base class for all binary reading operations, inspired by UE's `FArchive` pattern.

**When:** Foundation of the entire parsing system.

**Example:**

```python
from abc import ABC, abstractmethod
from typing import BinaryIO, Optional
from dataclasses import dataclass

@dataclass
class ArchiveState:
    """Tracks parsing state, mirrors UE's FArchiveState."""
    position: int = 0
    is_error: bool = False
    engine_version: int = 0
    custom_versions: dict[int, int] = None

class FArchive(ABC):
    """
    Abstract base for binary reading, mirroring UE's FArchive pattern.
    Provides serialization-independent interface.
    """
    def __init__(self):
        self._state = ArchiveState(custom_versions={})

    @abstractmethod
    def read(self, size: int) -> bytes: ...
    @abstractmethod
    def seek(self, pos: int) -> None: ...
    @abstractmethod
    def tell(self) -> int: ...
    @abstractmethod
    def total_size(self) -> int: ...

    # Convenience methods for typed reading
    def read_u8(self) -> int:
        return int.from_bytes(self.read(1), 'little')

    def read_u32(self) -> int:
        return int.from_bytes(self.read(4), 'little')

    def read_u64(self) -> int:
        return int.from_bytes(self.read(8), 'little')

    def read_f32(self) -> float:
        return struct.unpack('<f', self.read(4))[0]

    def read_fstring(self) -> str:
        """Read UE FString (length-prefixed UTF-16 or UTF-8)."""
        length = self.read_i32()
        if length == 0:
            return ""
        if length < 0:
            # UTF-16 encoded
            data = self.read(-length * 2)
            return data.decode('utf-16-le').rstrip('\x00')
        else:
            # UTF-8 encoded
            data = self.read(length)
            return data.decode('utf-8').rstrip('\x00')

    def read_name(self, name_map: list[str]) -> str:
        """Read FName (index into name table)."""
        index = self.read_u32()
        number = self.read_u32()  # Instance number
        if 0 <= index < len(name_map):
            base = name_map[index]
            return f"{base}_{number}" if number > 0 else base
        return "None"

class FFileArchive(FArchive):
    """File-backed archive implementation."""

    def __init__(self, path: str):
        super().__init__()
        self._file = open(path, 'rb')

    def read(self, size: int) -> bytes:
        return self._file.read(size)

    def seek(self, pos: int) -> None:
        self._file.seek(pos)

    def tell(self) -> int:
        return self._file.tell()

    def total_size(self) -> int:
        pos = self._file.tell()
        self._file.seek(0, 2)
        size = self._file.tell()
        self._file.seek(pos)
        return size

class FMemoryArchive(FArchive):
    """Memory-backed archive for testing and nested archives."""

    def __init__(self, data: bytes):
        super().__init__()
        self._data = data
        self._pos = 0

    def read(self, size: int) -> bytes:
        result = self._data[self._pos:self._pos + size]
        self._pos += size
        return result

    def seek(self, pos: int) -> None:
        self._pos = pos

    def tell(self) -> int:
        return self._pos

    def total_size(self) -> int:
        return len(self._data)
```

### Pattern 2: Model-First with Dataclasses

**What:** Use Python dataclasses for structured data representation.

**When:** All model classes (PackageSummary, ObjectImport, ObjectExport, etc.).

**Example:**

```python
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class FPackageFileSummary:
    """Mirrors UE's FPackageFileSummary - package header."""
    tag: int  # PACKAGE_FILE_TAG = 0x9E2A83C1
    file_version_ue: int
    file_version_licensee: int
    custom_versions: dict[int, int]
    package_flags: int
    name_count: int
    name_offset: int
    export_count: int
    export_offset: int
    import_count: int
    import_offset: int
    total_header_size: int
    # ... other fields

@dataclass
class FObjectImport:
    """Mirrors UE's FObjectImport - external reference."""
    class_package: str  # Package name
    class_name: str     # Class name
    outer_index: int    # FPackageIndex to outer
    object_name: str    # Object name

@dataclass
class FObjectExport:
    """Mirrors UE's FObjectExport - object definition in package."""
    class_index: int       # FPackageIndex to class
    super_index: int       # FPackageIndex to superclass
    outer_index: int       # FPackageIndex to outer
    object_name: str       # Object name
    object_flags: int      # EObjectFlags
    serial_size: int       # Size of serialized data
    serial_offset: int     # Offset to serialized data

@dataclass
class FPackageIndex:
    """
    Mirrors UE's FPackageIndex.
    Index > 0: ExportMap[index - 1]
    Index < 0: ImportMap[-index - 1]
    Index = 0: null
    """
    index: int

    @property
    def is_import(self) -> bool:
        return self.index < 0

    @property
    def is_export(self) -> bool:
        return self.index > 0

    @property
    def is_null(self) -> bool:
        return self.index == 0

    def to_import_index(self) -> int:
        return -self.index - 1

    def to_export_index(self) -> int:
        return self.index - 1
```

### Pattern 3: Handler/Plugin Registry

**What:** Registry pattern for type-specific deserializers.

**When:** Extending support for new asset types.

**Example:**

```python
from typing import Protocol, TypeVar, Callable
from dataclasses import dataclass

T = TypeVar('T')

@dataclass
class ParseContext:
    """Context passed to all handlers during parsing."""
    archive: FArchive
    name_map: list[str]
    import_map: list[FObjectImport]
    export_map: list[FObjectExport]
    summary: FPackageFileSummary

class TypeHandler(Protocol[T]):
    """Protocol for type-specific handlers."""

    @staticmethod
    def can_handle(class_name: str, package_path: str) -> bool: ...

    def parse(self, ctx: ParseContext, export: FObjectExport) -> T: ...

# Global registry
_handler_registry: dict[str, type[TypeHandler]] = {}

def register_handler(asset_type: str):
    """Decorator to register a handler for an asset type."""
    def decorator(cls: type[TypeHandler]) -> type[TypeHandler]:
        _handler_registry[asset_type] = cls
        return cls
    return decorator

def get_handler(class_name: str) -> Optional[type[TypeHandler]]:
    """Get handler for a class name."""
    # Direct match
    if class_name in _handler_registry:
        return _handler_registry[class_name]
    # Pattern match (e.g., "BlueprintGeneratedClass" -> "Blueprint")
    for pattern, handler in _handler_registry.items():
        if pattern.lower() in class_name.lower():
            return handler
    return None

# Handler implementation example
@register_handler("Blueprint")
class BlueprintHandler:
    """Handles blueprint asset deserialization."""

    @staticmethod
    def can_handle(class_name: str, package_path: str) -> bool:
        return "Blueprint" in class_name or package_path.endswith("_BP.uasset")

    def parse(self, ctx: ParseContext, export: FObjectExport) -> 'Blueprint':
        ctx.archive.seek(export.serial_offset)
        # Parse blueprint-specific data
        return Blueprint(...)
```

### Pattern 4: Streaming for Large Files

**What:** Memory-mapped file access and chunked reading for large files.

**When:** Files > 100MB or when processing multiple files.

**Example:**

```python
import mmap
from contextlib import contextmanager

class FMappedArchive(FArchive):
    """Memory-mapped archive for large files."""

    def __init__(self, path: str):
        super().__init__()
        self._file = open(path, 'rb')
        self._mmap = mmap.mmap(
            self._file.fileno(),
            0,
            access=mmap.ACCESS_READ
        )

    def read(self, size: int) -> bytes:
        result = self._mmap[self._pos:self._pos + size]
        self._pos += size
        return result

    def seek(self, pos: int) -> None:
        self._pos = pos

    def tell(self) -> int:
        return self._pos

    def total_size(self) -> int:
        return len(self._mmap)

    def read_at(self, offset: int, size: int) -> bytes:
        """Random access without affecting position."""
        return self._mmap[offset:offset + size]

    def close(self):
        self._mmap.close()
        self._file.close()

# Factory function
def create_archive(path: str, use_mmap: bool = True) -> FArchive:
    """Create appropriate archive based on file size."""
    import os
    file_size = os.path.getsize(path)
    if use_mmap and file_size > 50 * 1024 * 1024:  # > 50MB
        return FMappedArchive(path)
    return FFileArchive(path)
```

### Pattern 5: Version-Aware Deserialization

**What:** Handle multiple UE versions with version-specific parsing branches.

**When:** Parsing .uasset from different UE versions.

**Example:**

```python
from enum import IntEnum
from typing import Callable

class UEVersion(IntEnum):
    """Key UE version milestones for serialization changes."""
    VER_4_0 = 400
    VER_4_14 = 414
    VER_4_22 = 422
    VER_4_25 = 425
    VER_4_27 = 427
    VER_5_0 = 500
    VER_5_1 = 510
    VER_5_2 = 520
    VER_5_3 = 530
    VER_5_4 = 540
    VER_5_5 = 550

# Custom versions (UE uses these for specific subsystems)
CUSTOM_VERSIONS = {
    0x7E7A3F3E: "CoreObjectVersion",
    0x12E8C3E4: "BlueprintVersion",
    0x4B4B2E28: "NiagaraVersion",
    # ... from UE source
}

class VersionedParser:
    """Handles version-specific parsing logic."""

    def __init__(self, engine_version: int, custom_versions: dict[int, int]):
        self.engine_version = engine_version
        self.custom_versions = custom_versions

    def should_read_fstring_as_utf8(self) -> bool:
        """UE 5.0+ uses UTF-8 by default."""
        return self.engine_version >= UEVersion.VER_5_0

    def should_use_new_guid_format(self) -> bool:
        """GUID serialization changed in 5.1."""
        return self.engine_version >= UEVersion.VER_5_1

    def get_custom_version(self, version_key: int) -> int:
        """Get custom version for a subsystem."""
        return self.custom_versions.get(version_key, 0)

# Usage in parser
def parse_property(ctx: ParseContext) -> Property:
    parser = VersionedParser(
        ctx.summary.file_version_ue,
        ctx.summary.custom_versions
    )

    # Version-specific logic
    if parser.should_read_fstring_as_utf8():
        value = ctx.archive.read_utf8_string()
    else:
        value = ctx.archive.read_utf16_string()
```

## Anti-Patterns to Avoid

### Anti-Pattern 1: Loading Entire File into Memory

**What:** `data = open(path, 'rb').read()` on multi-GB files.

**Why bad:** Memory exhaustion, slow startup, crashes on large files.

**Instead:** Use streaming or memory-mapped files.

```python
# BAD
with open(path, 'rb') as f:
    data = f.read()  # Loads entire file
    process(data)

# GOOD
with FMappedArchive(path) as archive:
    process_streaming(archive)  # Reads on demand
```

### Anti-Pattern 2: Hardcoded Offsets

**What:** `archive.seek(0x1234)` without reading headers first.

**Why bad:** UE format changes between versions; offsets become invalid.

**Instead:** Parse PackageFileSummary first, use its offsets.

```python
# BAD
archive.seek(0x1234)  # Magic number - breaks on different files

# GOOD
summary = read_package_summary(archive)
archive.seek(summary.export_offset)  # From actual header
```

### Anti-Pattern 3: Monolithic Parser

**What:** Single 2000-line `parse_uasset()` function.

**Why bad:** Unmaintainable, hard to test, hard to extend.

**Instead:** Separate concerns into Reader, Deserializer, Model, Output layers.

```python
# BAD
def parse_uasset(path):
    with open(path, 'rb') as f:
        # 2000 lines of everything mixed together
        pass

# GOOD
def parse_uasset(path):
    with FFileArchive(path) as archive:
        summary = read_package_summary(archive)
        name_map = read_name_table(archive, summary)
        imports = read_import_map(archive, summary, name_map)
        exports = read_export_map(archive, summary, name_map)

        ctx = ParseContext(archive, name_map, imports, exports, summary)

        for export in exports:
            handler = get_handler(export.class_name)
            if handler:
                yield handler.parse(ctx, export)
```

### Anti-Pattern 4: Ignoring Import Resolution

**What:** Only parsing exports without resolving import references.

**Why bad:** Blueprints reference parent classes, interfaces, types from other packages. Without resolution, you get incomplete data.

**Instead:** Build import resolution into the architecture.

```python
# GOOD - Import resolution built in
@dataclass
class ResolvedExport:
    export: FObjectExport
    resolved_class: Optional[str]  # From ImportMap or ExportMap
    resolved_super: Optional[str]  # Parent class
    resolved_outer: Optional[str]  # Containing object

def resolve_reference(
    index: FPackageIndex,
    imports: list[FObjectImport],
    exports: list[FObjectExport]
) -> Optional[str]:
    if index.is_import:
        imp = imports[index.to_import_index()]
        return f"{imp.class_package}.{imp.object_name}"
    elif index.is_export:
        exp = exports[index.to_export_index()]
        return exp.object_name
    return None
```

### Anti-Pattern 5: Tight Coupling to Output Format

**What:** Returning formatted strings directly from parser.

**Why bad:** Can't produce JSON, can't filter, can't test structure.

**Instead:** Return structured models, format separately.

```python
# BAD
def parse_blueprint(archive) -> str:
    return f"Blueprint: {name}\nNodes: {nodes}"

# GOOD
def parse_blueprint(archive) -> Blueprint:
    return Blueprint(name=name, nodes=nodes, ...)

# Then format:
class JsonOutput:
    def format(self, blueprint: Blueprint) -> str:
        return json.dumps(asdict(blueprint))

class TextOutput:
    def format(self, blueprint: Blueprint) -> str:
        return f"Blueprint: {blueprint.name}\nNodes: {len(blueprint.nodes)}"
```

## Scalability Considerations

| Concern | At 100 exports | At 10K exports | At 100K exports |
|---------|---------------|----------------|-----------------|
| **Memory** | Load all | Stream exports | mmap + lazy parse |
| **Startup** | Parse all headers | Parse summary only | Parse summary + lazy imports |
| **Output** | Full serialization | Paginated output | Stream to file |
| **Resolution** | Full import resolution | Cache resolved names | Lazy resolution on-demand |

### Lazy Parsing Strategy

For very large packages (e.g., large maps with many actors):

```python
class LazyExportIterator:
    """Iterate exports without parsing all at once."""

    def __init__(self, ctx: ParseContext, exports: list[FObjectExport]):
        self.ctx = ctx
        self.exports = exports
        self._parsed: dict[int, Any] = {}

    def get(self, index: int) -> Any:
        """Get export, parsing on first access."""
        if index not in self._parsed:
            export = self.exports[index]
            handler = get_handler(export.class_name)
            if handler:
                self._parsed[index] = handler.parse(self.ctx, export)
        return self._parsed.get(index)

    def __iter__(self):
        for i, export in enumerate(self.exports):
            yield self.get(i)
```

## Sources

- **Unreal Engine Source**: `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/CoreUObject/`
  - `Private/UObject/Package.cpp` - Package handling
  - `Private/Serialization/AsyncLoading.cpp` - Loading architecture
  - `Public/UObject/Linker.h` - Linker structure
  - `Public/UObject/LinkerLoad.h` - Package loading
  - `Public/UObject/PackageFileSummary.h` - File header structure
  - `Public/UObject/ObjectResource.h` - Import/Export structures
  - `Public/Serialization/Archive.h` - Archive abstraction

- **CUE4Parse Architecture**: [https://github.com/Fabian-Creostone/CUE4Parse](https://github.com/Fabian-Creostone/CUE4Parse)
  - FArchive pattern for C# implementation
  - Handler registry for type-specific parsing
  - Version-aware deserialization

- **FModel Architecture**: [https://github.com/4sval/FModel](https://github.com/4sval/FModel)
  - Layered architecture (Reader -> Deserializer -> Model -> Output)
  - CUE4Parse integration patterns

- **Python Binary Parsing**:
  - `struct` module for low-level parsing (built-in)
  - `dataclasses` for model representation (built-in)
  - `mmap` for memory-efficient large file handling (built-in)
  - Generator patterns for streaming

## Build Order Implications

Based on the architecture, recommended build order:

1. **Phase 1: Reader Layer**
   - `FArchive` base class
   - `FFileArchive` implementation
   - `FMemoryArchive` for testing
   - Low-level read methods (u8, u32, fstring, fname)

2. **Phase 2: Model Layer (Core)**
   - `FPackageFileSummary`
   - `FPackageIndex`
   - `FObjectImport` / `FObjectExport`
   - Name table structures

3. **Phase 3: Deserializer Layer (Core)**
   - `read_package_summary()`
   - `read_name_table()`
   - `read_import_map()`
   - `read_export_map()`
   - `ParseContext`

4. **Phase 4: Model Layer (Types)**
   - Base `UObject` model
   - `Blueprint` model
   - Property types (`FProperty`, `FArrayProperty`, etc.)

5. **Phase 5: Handler Layer**
   - Handler registry
   - `BlueprintHandler`
   - Other type handlers as needed

6. **Phase 6: Output Layer**
   - `TextOutput`
   - `JsonOutput`
   - `SummaryOutput`

7. **Phase 7: Performance & Polish**
   - `FMappedArchive` for large files
   - Lazy parsing
   - Version handling
   - Error recovery