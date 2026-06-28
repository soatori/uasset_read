---
title: IR Intermediate Representation
section: ir
---

# IR Intermediate Representation

IR (Intermediate Representation) is the unified data layer introduced in 0.4.1, positioned between `ParseResult` and renderers. Renderers only receive `PackageIR` and do not access `ParseResult`.

## Design Goals

1. **Decoupling**: Parsing logic and output format are completely independent
2. **Minimalism**: IR only retains data needed by renderers, removing redundancy
3. **Unification**: All renderers share the same data structure
4. **GUID Standardization**: All Node/Pin GUIDs are unified to 32-bit lowercase hex

## Data Types

All IR types are defined in `src/uasset_read/models/ir.py`.

### PackageHeaderIR

```python
@dataclass
class PackageHeaderIR:
    package_name: str          # Package name
    package_class: str         # Package class
    package_flags: int         # Package flags
    total_export_count: int    # Export count
    total_import_count: int    # Import count
    ue_version: str            # UE version
```

### PinIR

```python
@dataclass
class PinIR:
    pin_name: str              # Pin name
    pin_type: str              # Pin type
    pin_type_value: str | None # Pin type value
    linked_to: list[str]       # Connection targets
    direction: str             # Direction (input/output)
    default_value: str | None  # Default value
```

### NodeIR

```python
@dataclass
class NodeIR:
    node_guid: str             # Node GUID (32-bit lowercase hex)
    node_class: str            # Node class
    node_comment: str | None   # Comment
    pins: list[PinIR]          # Pins
    execution_flow: list[dict] # Execution flow
```

### GraphIR

```python
@dataclass
class GraphIR:
    graph_guid: str            # Graph GUID
    graph_name: str            # Graph name
    graph_class: str           # Graph class
    nodes: list[NodeIR]        # Node list
    execution_chains: list[list[str]]  # Execution chains
```

### PropertyIR

```python
@dataclass
class PropertyIR:
    name: str                  # Property name
    type: str                  # Property type
    value: Any                 # Property value
    array_index: int           # Array index
    guid: str | None           # Property GUID
```

### ExportIR

```python
@dataclass
class ExportIR:
    index: int                 # Export index
    object_name: str           # Object name
    object_class: str          # Object class
    serial_size: int           # Serialized size
    outer_index_resolved: str | None    # Outer index resolution
    super_index_resolved: str | None    # Parent index resolution
    parent_class: str | None   # Parent class
    properties: list[PropertyIR]  # Property list
    graphs: list[GraphIR]      # Graph list
    bulk_data: dict | None     # Bulk data
```

### BlueprintIR

```python
@dataclass
class BlueprintIR:
    parent_class: str | None           # Parent class
    functions: list[BlueprintFunctionIR]  # Function list
    events: list[BlueprintEventIR]     # Event list
    components: list[dict]             # Component list
```

### BlueprintFunctionIR / BlueprintEventIR

```python
@dataclass
class BlueprintFunctionIR:
    name: str                  # Function name
    return_type: str           # Return type
    parameters: list[dict]     # Parameter list

@dataclass
class BlueprintEventIR:
    name: str                  # Event name
    event_type: str            # Event type
    parameters: list[dict]     # Parameter list
```

### DecompiledFunctionIR

```python
@dataclass
class DecompiledFunctionIR:
    name: str                  # Function name
    signature: str             # Signature
    cpp_code: str              # C++ code
    parameters: list[dict]     # Parameter list
    return_type: str           # Return type
```

### ExecutionChainIR

```python
@dataclass
class ExecutionChainIR:
    event: str                 # Starting event
    chain: list[str]           # Execution chain
```

### LinkerSummaryIR

```python
@dataclass
class LinkerSummaryIR:
    has_linker: bool           # Whether linker exists
    import_paths: list[str]    # Import paths
    export_paths: list[str]    # Export paths
```

### VariableIR

```python
@dataclass
class VariableIR:
    name: str                  # Variable name
    type: str                  # Variable type
    default_value: str | None  # Default value
```

### PackageIR (Top-level Structure)

```python
@dataclass
class PackageIR:
    header: PackageHeaderIR                    # Package header
    name_map: list[str]                        # Name table
    imports: list[dict]                        # Import table
    exports: list[ExportIR]                    # Export table
    linker: LinkerSummaryIR | None             # Linker summary
    blueprint: BlueprintIR | None = None       # Blueprint metadata
    decompiled_functions: list[DecompiledFunctionIR] = field(default_factory=list)
    execution_chains: list[ExecutionChainIR] = field(default_factory=list)
    variables: list[VariableIR] = field(default_factory=list)
```

## IR Builder

The `build_package_ir(result)` function in `ir_builder.py` is responsible for constructing `PackageIR` from `ParseResult`.

```python
from uasset_read.ir_builder import build_package_ir

ir = build_package_ir(result)
```

## Data Flow

```
ParseResult (raw parsing result)
    ↓ build_package_ir()
PackageIR (unified intermediate representation)
    ↓ renderer.render()
Output String (final output)
```

**Related sections**: [[Renderer System]] · [[Parsing Pipeline]]
