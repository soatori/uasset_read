<!-- generated-by: gsd-doc-writer -->
# Architecture

## System Overview

**uasset_read** is a Python 3.10+ library that parses Unreal Engine `.uasset` binary files, enabling AI agents and developers to read Blueprint data without running the UE editor. It implements the same `FArchive` binary-reading pattern used by Unreal Engine's internal serialization system, supporting both UE4 and UE5 formats (with full UE5.7+ coverage including versioned properties, custom versions, `script_serial_offset`, and serialization control extensions).

The project follows a **layered pipeline architecture**: raw bytes flow through five stages — binary reading, header/metadata deserialization, data model instantiation, property/graph parsing, and output formatting. Each layer depends only on the layers beneath it, producing a clean separation of concerns and enabling targeted testing at every level. The library has **zero runtime dependencies** — all serialization is handled by Python's built-in `struct` and `mmap` modules.

```
.uasset file
    │
    ▼
┌──────────────┐
│  FArchive    │  Binary reader with byte-swapping, mmap, boundary validation
└──────┬───────┘
       │ raw bytes + typed reads (i32, u32, fstring, name...)
       ▼
┌──────────────────┐
│  Serializers     │  PackageFileSummary, ImportMap, ExportMap, PropertyTag, Graph
└──────┬───────────┘
       │ dataclasses (summary, name_map, imports, exports)
       ▼
┌──────────────────┐
│  Data Models     │  UEdGraph → UEdGraphNode → UEdGraphPin, property values
└──────┬───────────┘
       │ parsed structures + blueprint metadata
       ▼
┌──────────────────┐
│  Parsers         │  14 property type parsers + dispatcher
└──────┬───────────┘
       │ typed property values
       ▼
┌──────────────────┐
│  Formatters      │  JSON / Text / Markdown / Mermaid output
└──────────────────┘
```

## Data Flow Pipeline

A typical parse operation proceeds through these stages:

1. **File open** — `FArchive` opens the `.uasset` file, detects size, and activates `mmap` for files >= `MMAP_THRESHOLD` (16 MB). Byte-order is determined by the file header tag.
2. **Header parsing** — `read_package_summary()` reads the `PackageFileSummary` (tag, legacy version, UE5 version, total header size, custom versions, package flags). `read_name_table()` builds the name string index.
3. **Import/Export maps** — `read_import_map()` and `read_export_map()` deserialize the `FObjectImport` and `FObjectExport` tables, resolving names via the name map and encoding parent/child relationships through `PackageIndex`.
4. **Property deserialization** — For each export with `serial_size > 0`, `parse_properties_from_export()` seeks to the property start, reads `PropertyTag` entries until `Name == "None"`, and dispatches each tag to the appropriate type parser. UE5.10+ uses `script_serial_offset` for the property start; older versions use `serial_offset` directly.
5. **Blueprint metadata extraction** — If the package contains a Blueprint Generated Class, `extract_blueprint_metadata()` traverses exports to locate the main BPGC, then extracts variables, functions, events, and component information.
6. **Graph extraction** — `extract_blueprint_graphs()` reads `UEdGraph` exports (EventGraphs, function graphs), deserializing nodes (`K2Node_CallFunction`, `K2Node_Event`, `K2Node_Knot`, `K2Node_EnhancedInputAction`) and their pins with `LinkedTo` connections.
7. **Dependency analysis** — `build_imports_list()` builds the dependency list, `detect_circular_deps()` checks for circular import chains, and `read_soft_object_paths()` extracts soft references.
8. **Output formatting** — The `ParseResult` is passed to a formatter (`format_json_full`, `format_text_full`, `format_markdown`) for structured output.

Two entry points orchestrate this pipeline:

| Function | Module | Description |
|----------|--------|-------------|
| `parse_uasset()` | `parse_uasset.py` | Standard single-pass parsing, returns `ParseResult` |
| `parse_uasset_with_linker()` | `parse_uasset.py` | Two-stage parsing with `PackageLinker`, returns `LinkerParseResult` |

## Layered Architecture

### Layer 1: Binary Reading (`archive.py`)

`FArchive` is the foundational binary reader, mirroring Unreal Engine's `FArchive` class. It provides:

- **Typed reads**: `read_u8/i32/u32/i64/u64/f32/f64/bool/fstring/name` with automatic byte-swapping
- **Memory mapping**: `mmap` for files >= 16 MB, with graceful fallback to standard file I/O
- **Boundary validation**: `validate_offset()`, `validate_size()`, and read-size checks prevent out-of-bounds access
- **Byte-order detection**: Set via `set_byte_swapping()` after reading the file header tag (`PACKAGE_FILE_TAG` vs `PACKAGE_FILE_TAG_SWAPPED`)

All higher layers pass through `FArchive` for every byte read. No other module opens files directly.

### Layer 2: Serializers (`serializers/`)

Serializers convert raw bytes from `FArchive` into Python dataclasses. They know nothing about parsing logic or output formatting.

| File | Exports | Purpose |
|------|---------|---------|
| `package_summary.py` | `PackageFileSummary`, `read_package_summary`, `read_name_table` | File header: version info, name table, custom versions |
| `object_resources.py` | `PackageIndex`, `ObjectImport`, `ObjectExport`, `read_import_map`, `read_export_map`, `detect_blueprint`, `resolve_class_name` | Import/Export tables, package index encoding, blueprint detection |
| `property_tags.py` | `read_property_tag` | PropertyTag deserialization (name, type, size, flags) |
| `graph.py` | `read_ue_graph`, `read_ue_graph_node`, `read_ue_graph_pin`, `read_ed_graph_pin_type`, `read_k2node_*` | Blueprint graph container/node/pin deserialization |
| `object_resources.py` | `find_main_blueprint_generated_class`, `read_soft_object_paths`, `detect_circular_deps` | Blueprint class discovery, soft reference extraction |

### Layer 3: Data Models (`models/`)

Data models are pure Python dataclasses with no I/O logic. They represent the semantic structure of parsed data.

**Core graph hierarchy:**
```
UEdGraph (graph container)
├── nodes: List[UEdGraphNode]
│   ├── pins: List[UEdGraphPin]
│   │   ├── pin_type: FEdGraphPinType
│   │   └── linked_to_objects: List[UObjectInstance]
│   └── class_name: str
└── graph_guid: str
```

**Property model hierarchy:**
```
PropertyTag (metadata: name, type, size, flags)
PropertyValue (name, type, value, array_index)
├── StructValue
├── MapValue
├── SetValue
├── EnumValue
├── TextValue
└── DelegateValue
```

**Specialized node types** (`node_types.py`):
| Class | UE Equivalent | Purpose |
|-------|--------------|---------|
| `K2NodeCallFunction` | `UK2Node_CallFunction` | Function call nodes with `FMemberReference` |
| `K2NodeEvent` | `UK2Node_Event` | Event entry points |
| `K2NodeKnot` | `UK2Node_Knot` | Graph knots (wire routing) |
| `K2NodeEnhancedInputAction` | `UK2Node_EnhancedInputAction` | Enhanced Input action binding |
| `EdGraphNodeComment` | `UEdGraphNode_Comment` | Comment box nodes |

**Result containers:**
- `ParseResult` — Standard parse result (summary, maps, properties, blueprint, graphs, errors)
- `LinkerParseResult` — Extended result with `PackageLinker`, `all_objects`, `root_objects`

**Transform value classes** (`transforms.py`):
- `VectorValue`, `RotatorValue`, `ScaleValue` — Typed numeric representations
- `format_transform_value()` — Human-readable formatting

### Layer 4: Parsers (`parsers/`)

The parser layer converts raw serialized properties into typed Python values. It uses a **dispatcher pattern** with lazy-loaded handler functions.

**Dispatch mechanism** (`property_parser.py`):

```
PropertyTag.type ──→ handler lookup ──→ typed parse function
   "BoolProperty"      parse_bool_property(tag, archive)
   "IntProperty"       parse_int_property(tag, archive)
   "StructProperty"    parse_struct_property(tag, archive, name_map, ...)
   "MapProperty"       parse_map_property(tag, archive, name_map, ...)
   ...
```

Each of the 14 type parsers (`property_types.py`) handles one or more property types:

| Parsers | Handles |
|---------|---------|
| `parse_bool_property` | `BoolProperty` |
| `parse_int_property` | `IntProperty`, `Int64Property`, `Int16Property`, `Int8Property`, `ByteProperty` |
| `parse_float_property` | `FloatProperty`, `DoubleProperty` |
| `parse_str_property` | `StrProperty` |
| `parse_name_property` | `NameProperty` |
| `parse_object_property` | `ObjectProperty` |
| `parse_soft_object_property` | `SoftObjectProperty` |
| `parse_array_property` | `ArrayProperty` |
| `parse_struct_property` | `StructProperty` |
| `parse_map_property` | `MapProperty` |
| `parse_set_property` | `SetProperty` |
| `parse_enum_property` | `EnumProperty` |
| `parse_text_property` | `TextProperty` |
| `parse_delegate_property` | `DelegateProperty` |

The main loop (`parse_properties_from_export`) handles: property start calculation (UE5 version-aware), serialization control extensions, tag reading, dispatch, boundary validation (seek to `start + tag.size`), and graceful error recovery (damaged properties produce `Warning` entries instead of crashing).

### Layer 5: Blueprint Processing (`blueprint/`)

Extracts semantic meaning from parsed properties:

| File | Function | Purpose |
|------|----------|---------|
| `variable_extractor.py` | `extract_blueprint_variables`, `read_blueprint_variable`, `parse_property_flags_to_labels` | Blueprint variable extraction with CPF flag interpretation |
| `transform_parser.py` | `extract_component_transforms`, `parse_vector/rotator/scale_value` | Component transform extraction (RelativeLocation, RelativeRotation, RelativeScale3D) |
| `component_extractor.py` | `extract_components` | Component property extraction (Phase 48) |
| `__init__.py` | `extract_blueprint_metadata`, `parse_component_transform` | High-level entry points |

### Layer 6: Graph Analysis (`graph/`)

Processes parsed graph data into flow and connection structures:

| File | Function | Purpose |
|------|----------|---------|
| `parser.py` | `extract_blueprint_graphs` | Entry point: reads all UEdGraph exports |
| `flow_builder.py` | `build_execution_flows`, `build_data_flows`, `build_connections_map`, `build_graphs_summary`, `format_graphs_json` | Flow analysis and formatting |

### Layer 7: Formatters (`formatters/`)

Convert `ParseResult` into human-readable or machine-consumable output:

| File | Exports | Purpose |
|------|---------|---------|
| `json_formatter.py` | `format_json_full`, `format_json_summary`, `format_exports_list`, `format_properties_list`, `format_blueprint_dict` | JSON output with optional `_schema` annotations |
| `text_formatter.py` | `format_text_full`, `format_text_summary` | YAML-style text output |
| `markdown_formatter.py` | `format_markdown`, `_build_mermaid_flowchart` | Markdown with Mermaid diagram support |
| `helpers.py` | `build_status_info`, `build_schema_info`, `resolve_fpackage_index` | Utility functions for schema resolution and status building |

### Layer 8: Object Linking (`link/`)

The `link/` module implements UE's `FLinkerLoad` pattern for two-stage object graph reconstruction. See the dedicated section below.

## Module Dependency Graph

```
                    cli.py
                      │
                      ▼
              parse_uasset.py ◄──┐
                      │          │
          ┌───────────┼──────────┤
          ▼           ▼          ▼
      archive.py   serializers/  link/
          │           │          │
          │           ▼          │
          │        models/ ──────┘
          │           │
          │           ▼
          │        parsers/
          │           │
          │           ▼
          │       blueprint/
          │           │
          │           ▼
          │        graph/
          │           │
          ▼           ▼
      constants.py  formatters/
          ▲
          │
      exceptions.py
```

Dependency direction (top to bottom): `cli` depends on `parse_uasset`, which depends on `archive`, `serializers`, `parsers`, `blueprint`, `graph`, and `link`. Circular dependencies are avoided through **lazy imports** (functions like `_get_parse_functions()` and inline `import` statements inside methods).

## Key Design Decisions

### FArchive Pattern

The library mirrors Unreal Engine's `FArchive` binary-reading approach rather than using `struct.unpack` on entire buffers. This provides:

- **Sequential reading** with automatic position tracking
- **Byte-swapping** for cross-platform compatibility (little-endian vs big-endian `.uasset` files)
- **Boundary validation** at every read operation
- **Memory efficiency** via `mmap` for large files (>16 MB)

This design choice directly enables the same serialization logic that UE's own `FArchive` uses, making it easier to port new UE features as the engine evolves.

### Zero Runtime Dependencies

The library uses only Python standard library modules (`struct`, `mmap`, `dataclasses`, `argparse`, `json`). This simplifies installation (`pip install -e .`), eliminates supply-chain risk, and ensures compatibility across Python 3.10+ environments. Development dependencies (pytest, pytest-cov) are optional via `[dev]` extras.

### src Layout

Source code lives in `src/uasset_read/` following the Python src-layout convention. This prevents accidental imports from the source directory during development (the installed package is imported instead), ensuring tests run against the installed code. The `pyproject.toml` configures this via:

```toml
[tool.setuptools]
package-dir = {"" = "src"}
```

### Flat Public API

The top-level `__init__.py` re-exports 100+ symbols through a single `__all__` list. Callers use `from uasset_read import X` rather than navigating submodules. This reduces import friction for AI agents and simplifies the API surface.

### Graceful Degradation (Tolerant Mode)

Both `FArchive` and the property parser support `tolerant` mode (enabled by default). When enabled:
- Negative property sizes are accepted without raising `ParseError`
- Oversized property tags are accepted
- Damaged properties produce `Warning` entries instead of aborting
- Unknown property types return `None` rather than crashing

This is critical for parsing real-world `.uasset` files that may contain editor-only data or version-specific quirks.

## PackageLinker: Two-Stage Object Graph Reconstruction

`PackageLinker` implements Unreal Engine's `FLinkerLoad` pattern for reconstructing the object graph from ImportMap and ExportMap entries. This enables cross-object reference resolution that single-pass parsing cannot achieve.

### Why Two-Stage?

In UE packages, objects reference each other through `FPackageIndex` — an encoded integer where positive values point to exports, negative to imports, and zero means null. During single-pass parsing, these indices remain as raw integers because the target objects may not yet be constructed. The two-stage approach solves this:

1. **Stage 1 (`link()`)**: Create lightweight `UObjectInstance` shells for all imports and exports, then resolve `Outer` references to build the parent-child tree.
2. **Stage 2 (`preload(index)`)**: On demand, seek to an export's serialized data and deserialize its properties, populating the `UObjectInstance.serialized_properties` field.

### Phase 1: Object Shell Creation

```
PackageLinker.link()
├── _create_import_instances()
│   └── For each ObjectImport: create UObjectInstance with:
│       - package_index = -(idx + 1)  (negative = import)
│       - object_name, object_class, class_package from name_map
│       - outer_index (unresolved PackageIndex)
│       - is_import = True
│
├── _create_export_instances()
│   └── For each ObjectExport: create UObjectInstance with:
│       - package_index = idx + 1  (positive = export)
│       - object_name from name_map
│       - object_class via resolve_class_name(class_index)
│       - serial_offset, serial_size from export
│       - is_import = False
│
├── build_outer_tree()
│   └── For all objects: resolve outer_index → UObjectInstance
│       via resolve_package_index()
│
└── _collect_root_objects()
    └── Objects with null outer_index are roots
```

### Phase 2: Lazy Property Loading

```
PackageLinker.preload(index)
1. Check _preload_cache — skip if already loaded
2. Seek to UObjectInstance.serial_offset
3. Call parse_properties_from_export() with the raw ObjectExport
4. Store results in UObjectInstance.serialized_properties
5. Mark _preloaded = True
```

### UObjectInstance

Each `UObjectInstance` is a dataclass representing one object in the graph:

```python
@dataclass
class UObjectInstance:
    # Identity
    package_index: int          # Encoded: +export, -import, 0=null
    object_name: str            # e.g. "Default__MyBlueprint_C"
    object_class: Optional[str] # e.g. "BlueprintGeneratedClass"
    class_package: Optional[str] # e.g. "/Script/Engine"

    # References
    outer_index: PackageIndex   # Unresolved parent reference
    outer: UObjectInstance      # Resolved parent (set by build_outer_tree)

    # Serialization
    is_import: bool
    serial_offset: int
    serial_size: int

    # Lazy-loaded
    serialized_properties: List[Any]       # Filled by preload()
    property_references: Dict[str, UObjectInstance]  # Resolved object refs

    # Convenience
    linker: PackageLinker       # Back-reference to owner
```

Key methods:
- `get_full_name()` — Returns the full UE path: `"Outermost.Outer.Inner.ObjectName"`
- `get_class_object()` — Resolves the object's class to another `UObjectInstance`
- `get_template_object()` — Resolves the Class Default Object (CDO)
- `get_children()` — Returns all objects whose `Outer` is this object
- `ensure_preloaded()` — Triggers `preload()` if not already loaded

### Resolution Flow

```
PackageIndex(index=5)  ──→  is_export=True  ──→  _export_objects[4]  ──→  UObjectInstance
PackageIndex(index=-3) ──→  is_import=True  ──→  _import_objects[2]   ──→  UObjectInstance
PackageIndex(index=0)  ──→  is_null=True    ──→  None
```

### Linker-Enhanced Parsing

When `parse_properties_from_export()` receives a `linker` parameter, it resolves `ObjectProperty` values to full `UObjectInstance` references instead of raw `PackageIndex` integers. Similarly, `UEdGraphPin.from_archive_with_linker()` resolves `default_object`, `linked_to`, `sub_pins`, `parent_pin`, and `ref_pass_through` to actual object instances.

### Entry Point

```python
result = parse_uasset_with_linker(path, preload_all=False)
# result.linker       — PackageLinker instance
# result.all_objects  — List[UObjectInstance] (imports + exports)
# result.root_objects — List[UObjectInstance] (no parent)
# result.linker.preload(0)  — Load properties for first export
```

## Data Model Hierarchy

### Blueprint Graph Model

```
UEdGraph                        # Top-level graph container (EventGraph, FunctionGraph)
├── graph_name: str             # "MyBlueprint_EventGraph"
├── graph_class: str            # "EdGraph"
├── schema: str                 # "K2Schema"
├── graph_guid: str             # Unique identifier
├── b_editable: bool            # Whether the graph is editable
└── nodes: List[UEdGraphNode]
    └── UEdGraphNode            # Base node class
        ├── node_guid: str      # Unique node identifier
        ├── node_pos_x/y: int   # Position in graph editor
        ├── node_comment: str   # Node comment
        ├── class_name: str     # e.g. "K2Node_CallFunction"
        ├── pins: List[UEdGraphPin]
        └── node_data: Any      # Specialized data (K2NodeCallFunction, etc.)
            └── UEdGraphPin
                ├── pin_id: str           # Unique pin identifier
                ├── pin_name: str         # Display name
                ├── direction: int        # Input/Output
                ├── pin_type: FEdGraphPinType
                │   ├── pin_category: str    # "exec", "bool", "float", "object"...
                │   ├── pin_subcategory: str # "object", "class", etc.
                │   ├── pin_subcategory_object: int  # FPackageIndex
                │   ├── container_type: int  # None/Array/Map/Set
                │   └── is_reference: bool   # By-ref parameter
                ├── default_value: str    # Literal default value
                ├── default_object: int   # FPackageIndex for default object
                ├── default_object_ref: UObjectInstance  # Resolved (linker)
                ├── linked_to_objects: List[UObjectInstance]  # Resolved connections
                ├── sub_pins_objects: List[UObjectInstance]   # Sub-pin connections
                ├── hidden: bool          # UI visibility
                └── advanced_view: bool   # Advanced property flag
```

### Property Model

```
PropertyTag              # Metadata about a property
├── name: str            # "RelativeLocation", "bHidden", ...
├── type: str            # "StructProperty", "BoolProperty", ...
├── size: int            # Serialized size in bytes
├── array_index: int     # Array element index (0 for non-arrays)
└── flags: int           # PropertyTag flags (UE5 extensions)

PropertyValue            # Parsed property value
├── name: str            # Property name
├── type: str            # Property type
├── value: Any           # Parsed value (type-specific)
└── array_index: int     # Array element index
```

### Blueprint Metadata Model

```
BlueprintMetadata
├── parent_class: str           # "Actor", "UserWidget", ...
├── variables: List[BlueprintVariable]
│   ├── name: str
│   ├── var_type: str           # "bool", "int", "float", object class...
│   ├── default_value: str
│   ├── flags: List[str]        # ["CPF_Edit", "CPF_BlueprintVisible", ...]
│   └── tooltips: str
├── functions: List[BlueprintFunction]
│   ├── name: str
│   ├── parameters: List[FunctionParameter]
│   └── return_type: str
├── events: List[BlueprintEvent]
│   ├── name: str               # "ReceiveBeginPlay", "EventTick"...
│   └── delegate: MulticastDelegate
└── components: List[str]       # Component class names
```

## Extension Points

### Adding a New Property Parser

1. Add a `parse_X_property(tag, archive, ...)` function to `parsers/property_types.py`
2. Register it in `_get_parse_functions()` in `parsers/property_parser.py`:
   ```python
   "XProperty": parse_X_property,
   ```
3. Add a dataclass to `models/properties.py` if the type needs a custom value representation
4. Export from `parsers/__init__.py` and the top-level `__init__.py`
5. Add tests in `tests/`

The dispatcher automatically routes `PropertyTag.type == "XProperty"` to the new handler. Unknown types silently return `None` (tolerant mode).

### Adding a New K2Node Type

1. Add a dataclass to `models/node_types.py` (e.g., `K2Node_MyCustom`)
2. Add a `read_k2node_my_custom(archive, ...)` function to `serializers/graph.py`
3. Register in the `create_node_from_archive()` dispatcher in `serializers/graph.py`
4. Export from `serializers/__init__.py`, `models/__init__.py`, and the top-level `__init__.py`

### Adding a New Formatter

1. Create a new file in `formatters/` (e.g., `yaml_formatter.py`)
2. Implement the formatting function(s) accepting a `ParseResult` argument
3. Export from `formatters/__init__.py` and the top-level `__init__.py`
4. (Optional) Add a CLI flag in `cli.py` by extending `create_parser()` and the output routing in `main()`

### Adding Blueprint Metadata Extraction

Extend `blueprint/` with new extractors. The `extract_blueprint_metadata()` function in `blueprint/__init__.py` serves as the high-level entry point. New extractors should:
- Accept an export, archive, import/export maps, and optional linker
- Return typed data from `models/blueprint.py`
- Handle errors gracefully (catch `ParseError`, log to result.errors)

## File Organization

```
src/uasset_read/
├── __init__.py          # Public API: 100+ symbols via __all__
├── __main__.py          # python -m uasset_read entry point
├── archive.py           # FArchive: binary reader, mmap, byte-swapping
├── cli.py               # argparse CLI entry (uasset-read command)
├── constants.py         # UE constants: versions, flags, limits, format config
├── exceptions.py        # UAssetError, VersionError, ParseError, ErrorContext
├── parse_uasset.py      # Main pipeline: parse_uasset(), parse_uasset_with_linker()
│
├── serializers/         # Raw bytes → dataclasses
│   ├── __init__.py
│   ├── package_summary.py   # PackageFileSummary, read_package_summary, read_name_table
│   ├── object_resources.py  # PackageIndex, ObjectImport/Export, map readers, helpers
│   ├── property_tags.py     # read_property_tag
│   └── graph.py             # UEdGraph/node/pin serializers, K2Node readers
│
├── models/              # Pure dataclasses (no I/O)
│   ├── __init__.py
│   ├── core.py          # UEdGraph, UEdGraphNode, UEdGraphPin, FEdGraphPinType, FMemberReference
│   ├── node_types.py    # K2NodeCallFunction, K2NodeEvent, K2NodeKnot, K2NodeEnhancedInputAction
│   ├── properties.py    # PropertyTag, PropertyValue, StructValue, MapValue, etc.
│   ├── blueprint.py     # BlueprintMetadata, BlueprintVariable, BlueprintFunction, etc.
│   ├── transforms.py    # VectorValue, RotatorValue, ScaleValue
│   └── result.py        # ParseResult, StatusInfo
│
├── parsers/             # Property value dispatch and type handlers
│   ├── __init__.py
│   ├── property_parser.py   # parse_property_value(), parse_properties_from_export()
│   └── property_types.py    # 14 type-specific parse_X_property() functions
│
├── blueprint/           # Blueprint semantic extraction
│   ├── __init__.py
│   ├── variable_extractor.py  # Variable extraction, CPF flag parsing
│   ├── transform_parser.py    # Component transforms (Vector/Rotator/Scale)
│   └── component_extractor.py # Component property extraction (Phase 48)
│
├── graph/               # Blueprint graph analysis
│   ├── __init__.py
│   ├── parser.py        # extract_blueprint_graphs()
│   └── flow_builder.py  # Execution/data flow, connections, summary
│
├── link/                # FLinkerLoad-style object graph reconstruction
│   ├── __init__.py
│   ├── linker.py        # PackageLinker: link() + preload()
│   ├── object_instance.py  # UObjectInstance dataclass
│   └── result.py        # LinkerParseResult
│
└── formatters/          # Output formatting
    ├── __init__.py
    ├── json_formatter.py     # JSON output (full, summary, exports, blueprint dict)
    ├── text_formatter.py     # YAML-style text output
    ├── markdown_formatter.py # Markdown + Mermaid diagrams
    └── helpers.py            # Status, schema info, package index resolution
```

Tests live in `tests/` with 520+ test cases across 20+ test modules. The test suite covers archive behavior, serialization, parsing, blueprint extraction, graph analysis, linker functionality, output formatting, boundary conditions, and error handling.
