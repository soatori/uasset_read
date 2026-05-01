# Phase 3: Blueprint Extraction - Pattern Map

**映射日期:** 2026-05-01
**文件分析:** 2 (1 修改, 1 创建)
**找到类比:** 2 / 2

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `uasset_read.py` (modify) | model/utility | file-I/O | `uasset_read.py` (self-reference) | exact |
| `tests/test_blueprint_extraction.py` (create) | test | transform | `tests/test_property_parsing.py` | exact |

## Pattern Assignments

### `uasset_read.py` - Blueprint Dataclasses (model, file-I/O)

**Analog:** `uasset_read.py` lines 377-405 (PropertyTag dataclass)

**Dataclass pattern** (lines 377-391):
```python
@dataclass
class PropertyTag:
    """
    PropertyTag structure (PROP-01).

    From PropertyTag.h lines 37-105:
    FPropertyTag contains property meta info.
    """
    name: str                         # Property name (FName)
    type: str                         # Type name string (e.g., "IntProperty")
    size: int                         # Serialized data size (bytes)
    array_index: int = 0              # Array element index (default 0)
    flags: int = 0                    # EPropertyTagFlags flags
    property_guid: Optional[bytes] = None  # 16 bytes GUID (HasPropertyGuid)
    bool_val: int = 0                 # BoolProperty value (BoolTrue flag)
```

**Apply to:** FEdGraphPinType, BlueprintVariable, BlueprintMetadata dataclasses

---

### `uasset_read.py` - FArchive Read Methods (utility, file-I/O)

**Analog:** `uasset_read.py` lines 163-249 (FArchive type methods)

**Read methods pattern** (lines 163-196):
```python
def read_u8(self) -> int:
    """Read unsigned 8-bit integer (byte-order independent)."""
    return struct.unpack('<B', self.read(1))[0]

def read_i32(self) -> int:
    """Read signed 32-bit integer (supports byte swapping)."""
    fmt = '>' if self._byte_swapping else '<'
    return struct.unpack(fmt + 'i', self.read(4))[0]

def read_u64(self) -> int:
    """Read unsigned 64-bit integer (supports byte swapping)."""
    fmt = '>' if self._byte_swapping else '<'
    return struct.unpack(fmt + 'Q', self.read(8))[0]
```

**Apply to:** read_ed_graph_pin_type(), read_blueprint_variable() - 使用现有 FArchive 方法

---

### `uasset_read.py` - Version-Aware Parsing (utility, file-I/O)

**Analog:** `uasset_read.py` lines 829-845 (use_complete_type_name)

**Version detection pattern** (lines 829-845):
```python
def use_complete_type_name(legacy_version: int, ue5_version: int) -> bool:
    """
    Determine whether to use complete TypeName format (PROP-09).

    UE5 >= PROPERTY_TAG_COMPLETE_TYPE_NAME (1000) uses complete TypeName.
    UE4 always uses old format (short name + separate fields).

    Args:
        legacy_version: LegacyFileVersion (-2 to -9)
        ue5_version: UE5 version number

    Returns:
        True for UE5 new format, False for UE4 old format
    """
    if legacy_version <= -8 and ue5_version >= PROPERTY_TAG_COMPLETE_TYPE_NAME:
        return True
    return False
```

**Apply to:** FEdGraphPinType 版本检查 (FFrameworkObjectVersion thresholds)

---

### `uasset_read.py` - Property Dispatch Pattern (utility, transform)

**Analog:** `uasset_read.py` lines 1183-1224 (parse_property_value)

**Type dispatch pattern** (lines 1203-1224):
```python
def parse_property_value(
    tag: PropertyTag,
    archive: FArchive,
    name_map: List[str],
    export_map: List[ObjectExport]
) -> any:
    """Dispatch property value parsing."""
    type_dispatch = {
        "BoolProperty": lambda t, a, n, e: parse_bool_property(t, a),
        "IntProperty": lambda t, a, n, e: parse_int_property(t, a),
        "FloatProperty": lambda t, a, n, e: parse_float_property(t, a),
        "StrProperty": lambda t, a, n, e: parse_str_property(t, a),
        "NameProperty": lambda t, a, n, e: parse_name_property(t, a, n),
        "ObjectProperty": lambda t, a, n, e: parse_object_property(t, a),
        "ArrayProperty": lambda t, a, n, e: parse_array_property(t, a, n, e),
    }

    parser = type_dispatch.get(tag.type)
    if parser:
        return parser(tag, archive, name_map, export_map)

    # Unknown type: skip (D-26)
    return None
```

**Apply to:** parse_default_value() - 基于 PinCategory 分发

---

### `uasset_read.py` - ExportReader Pattern (utility, file-I/O)

**Analog:** `uasset_read.py` lines 1109-1180 (parse_properties_from_export)

**Export reading pattern** (lines 1135-1169):
```python
def parse_properties_from_export(
    export: ObjectExport,
    archive: FArchive,
    summary: PackageFileSummary,
    name_map: List[str],
    export_map: List[ObjectExport]
) -> List[PropertyValue]:
    """Parse all properties from export entry."""
    archive.seek(export.serial_offset)
    properties: List[PropertyValue] = []

    while True:
        try:
            tag = read_property_tag(
                archive,
                name_map,
                summary.legacy_file_version,
                summary.file_version_ue5
            )

            # Termination marker: Name == "None"
            if tag.name == "None":
                break

            # Record start position for boundary validation
            start_pos = archive.tell()

            # Dispatch to type-specific parser
            value = parse_property_value(tag, archive, name_map, export_map)

            # Boundary validation: ensure correct position
            expected_end = start_pos + tag.size
            current_pos = archive.tell()
            if current_pos != expected_end:
                archive.seek(expected_end)

            properties.append(PropertyValue(
                name=tag.name,
                type=tag.type,
                value=value,
                array_index=tag.array_index
            ))

        except ParseError as e:
            # Single property failure: log and continue (D-25)
            properties.append(PropertyValue(
                name="ParseError",
                type="Error",
                value=str(e)
            ))
            continue

    return properties
```

**Apply to:** extract_blueprint_metadata() - seek 到 export.SerialOffset,解析蓝图结构

---

### `uasset_read.py` - FPackageIndex Resolution Pattern (utility, transform)

**Analog:** `uasset_read.py` lines 793-822 (get_asset_class)

**PackageIndex resolution pattern** (lines 793-822):
```python
def get_asset_class(
    export: ObjectExport,
    import_map: List[ObjectImport],
    export_map: List[ObjectExport]
) -> Optional[str]:
    """
    Identify asset type from export entry (CORE-06).

    Lookup class_index in import_map or export_map to get class name.
    """
    if export.class_index.is_import:
        # Get class name from import table
        import_idx = export.class_index.to_import_index()
        if 0 <= import_idx < len(import_map):
            return import_map[import_idx].class_name
    elif export.class_index.is_export:
        # Get class name from export table
        export_idx = export.class_index.to_export_index()
        if 0 <= export_idx < len(export_map):
            return export_map[export_idx].object_name

    return None
```

**Apply to:** resolve_parent_class(), resolve_pin_sub_category_object() - 相同 FPackageIndex → map lookup pattern

---

### `uasset_read.py` - Error Handling Pattern (utility, file-I/O)

**Analog:** `uasset_read.py` lines 56-73 (exception classes), lines 1249-1290 (parse_uasset)

**Partial result pattern** (lines 1269-1284):
```python
except VersionError as e:
    result.errors.append(str(e))
    result.is_success = False

except ParseError as e:
    result.errors.append(str(e))
    # Carry partial results
    if e.partial_result:
        for key, value in e.partial_result.items():
            if hasattr(result, key):
                setattr(result, key, value)
    result.is_success = False

except Exception as e:
    result.errors.append(f"Unexpected error: {str(e)}")
    result.is_success = False
```

**Apply to:** Blueprint extraction - 检测失败时在 ParseResult.errors 添加警告 (D-03)

---

### `tests/test_blueprint_extraction.py` - MockArchive Pattern (test, transform)

**Analog:** `tests/test_property_parsing.py` lines 40-58 (MockArchive)

**Mock archive pattern** (lines 40-58):
```python
class MockArchive(FArchive):
    """
    Mock FArchive for testing, reads from BytesIO.
    """

    def __init__(self, data: bytes):
        # Don't call parent __init__, directly set required attributes
        self._file = BytesIO(data)
        self._byte_swapping = False
        self._file_size = len(data)
        self._path = "mock"

    def close(self):
        self._file.close()


def create_mock_archive_with_data(data: bytes) -> MockArchive:
    """Create MockArchive instance."""
    return MockArchive(data)
```

**Apply to:** Blueprint extraction tests - 为 FEdGraphPinType、BlueprintVariable tests 重用 MockArchive

---

### `tests/test_blueprint_extraction.py` - Test Organization Pattern (test, transform)

**Analog:** `tests/test_property_parsing.py` lines 62-673 (test organization)

**Test grouping pattern** (lines 62-86):
```python
# ============================================================================
# Version Detection Tests (PROP-09)
# ============================================================================

def test_use_complete_type_name_ue5_above_threshold():
    """UE5 >= 1000 uses new format."""
    assert use_complete_type_name(-8, 1000) == True
    assert use_complete_type_name(-8, 1001) == True


# ============================================================================
# PropertyTag Structure Tests (PROP-01)
# ============================================================================

def test_property_tag_ue5_format_basic():
    """Test UE5 PropertyTag basic format parsing."""
```

**Apply to:** Blueprint tests - 按 BLUE-01 到 BLUE-06 requirement IDs 分组

---

### `tests/test_blueprint_extraction.py` - Binary Data Construction Pattern (test, transform)

**Analog:** `tests/test_property_parsing.py` lines 90-118 (struct.pack pattern)

**Binary data pattern** (lines 100-118):
```python
def test_property_tag_ue5_format_basic():
    """Test UE5 PropertyTag basic format parsing."""
    name_map = ["TestProperty"]

    # FName: index (u32=0) + number (u32=0)
    # FString: length (i32=12) + "IntProperty\0"
    # Size: i32=4
    # Flags: u8=0
    data = (
        struct.pack('<I', 0) +      # Name index
        struct.pack('<I', 0) +      # Name number
        struct.pack('<i', 12) +     # Type string length
        b"IntProperty\x00" +        # Type string (12 bytes with null)
        struct.pack('<i', 4) +      # Size
        struct.pack('<B', 0)        # Flags (none)
    )

    archive = create_mock_archive_with_data(data)
    tag = read_property_tag(archive, name_map, -8, 1000)

    assert tag.name == "TestProperty"
    assert tag.type == "IntProperty"
```

**Apply to:** FEdGraphPinType tests - 用 struct.pack 为 PinCategory、PinSubCategory、ContainerType 等构造二进制数据

---

## Shared Patterns

### FArchive Binary Reading
**Source:** `uasset_read.py` lines 163-249
**Apply to:** 所有蓝图解析函数
```python
# Use existing FArchive methods:
archive.read_name(name_map)      # FName
archive.read_fstring()           # FString
archive.read_i32()               # int32
archive.read_u8()                # uint8
archive.read_u64()               # uint64 (PropertyFlags)
archive.read(16)                 # GUID/hash bytes
```

### Dataclass Model Definition
**Source:** `uasset_read.py` lines 254-420
**Apply to:** FEdGraphPinType, BlueprintVariable, BlueprintMetadata
```python
@dataclass
class ModelName:
    """Description from UE source reference."""
    field1: str                    # FName resolved
    field2: int                    # Raw value
    optional_field: Optional[bytes] = None  # Optional
    default_field: int = 0         # Default value
```

### Partial Result + Warning Pattern
**Source:** `uasset_read.py` lines 407-420, 1269-1284
**Apply to:** Blueprint detection failure (D-03)
```python
# On detection/extraction failure:
result.errors.append(f"Blueprint detection warning: {reason}")
# Continue parsing, don't fail entire file
```

### FPackageIndex Resolution
**Source:** `uasset_read.py` lines 278-300, 793-822
**Apply to:** ParentClass resolution, PinSubCategoryObject resolution
```python
pkg_idx = PackageIndex(raw_i32_value)
if pkg_idx.is_import:
    idx = pkg_idx.to_import_index()
    if 0 <= idx < len(import_map):
        name = import_map[idx].object_name
elif pkg_idx.is_export:
    idx = pkg_idx.to_export_index()
    if 0 <= idx < len(export_map):
        name = export_map[idx].object_name
```

### Test Assertion Pattern
**Source:** `tests/test_property_parsing.py` lines 110-119, 246-267
**Apply to:** 所有蓝图提取测试
```python
# Direct value assertion
assert tag.name == "TestProperty"
assert tag.type == "IntProperty"

# Float assertion with tolerance
assert abs(value - 3.14) < 0.001

# Type dispatch assertion
assert isinstance(value, list)

# Unknown type returns None
assert value is None
```

## No Analog Found

No files without analog. All Phase 3 patterns map to existing Phase 1/2 patterns:

| File | Role | Data Flow | Analog |
|------|------|-----------|--------|
| All | various | various | Found in uasset_read.py or test_property_parsing.py |

## RESEARCH.md Code Patterns

Additional patterns from UE source code research (RESEARCH.md) to supplement analog patterns:

### FEdGraphPinType Serialization Order
**Source:** RESEARCH.md Pattern 2 (EdGraphPin.cpp verified)
```python
# Serialization order (from EdGraphPin.cpp lines 163-346):
1. PinCategory (FName)          -> archive.read_name(name_map)
2. PinSubCategory (FName)       -> archive.read_name(name_map)
3. PinSubCategoryObject (i32)   -> archive.read_i32()
4. ContainerType (u8)           -> archive.read_u8()
5. PinValueType (if Map)        -> skip for Phase 3
6. bIsReference (bool/u8)       -> archive.read_u8() != 0
7. bIsWeakPointer (bool/u8)     -> archive.read_u8() != 0
8. MemberReference (skip)       -> archive.read_i32() + read_name + read(16)
9. bIsConst (bool/u8)           -> archive.read_u8() != 0
10. bIsUObjectWrapper (bool/u8) -> archive.read_u8() != 0
```

### FBPVariableDescription Serialization Order
**Source:** RESEARCH.md Pattern 3 (Blueprint.h verified)
```python
# Serialization order (from Blueprint.h lines 200-256):
1. VarName (FName)              -> archive.read_name(name_map)
2. VarGuid (16 bytes)           -> archive.read(16) [skip]
3. VarType (FEdGraphPinType)    -> read_ed_graph_pin_type()
4. FriendlyName (FString)       -> archive.read_fstring()
5. Category (FText -> FString)  -> archive.read_fstring() [simplified]
6. PropertyFlags (u64)          -> archive.read_u64()
7. RepNotifyFunc (FName)        -> archive.read_name(name_map) [skip]
8. ReplicationCondition (u8)    -> archive.read_u8() [skip]
9. MetaDataArray (count + skip) -> archive.read_i32() + loop skip
10. DefaultValue (FString)      -> archive.read_fstring()
```

### DefaultValue Parsing Regex
**Source:** RESEARCH.md Code Examples (D-13/D-14/D-15/D-16)
```python
import re

def parse_default_value(value_str: str, var_type: FEdGraphPinType) -> any:
    """Parse DefaultValue string to Python native type."""
    if not value_str:
        return None

    # Vector format: keep as string (D-16)
    if value_str.startswith("(") and value_str.endswith(")"):
        return value_str

    category = var_type.pin_category.lower()

    # Boolean parsing
    if category in ("bool", "boolean"):
        if value_str.lower() in ("true", "1"):
            return True
        elif value_str.lower() in ("false", "0"):
            return False
        return value_str  # D-14: fallback

    # Integer parsing
    if category in ("int", "integer"):
        match = re.match(r'^-?\d+$', value_str)
        if match:
            return int(value_str)
        return value_str  # D-14: fallback

    # Float parsing
    if category in ("float", "real", "double"):
        match = re.match(r'^-?\d+\.?\d*$', value_str)
        if match:
            return float(value_str)
        return value_str  # D-14: fallback

    return value_str
```

### Type Name Formatting
**Source:** RESEARCH.md Code Examples (D-05/D-06/D-07)
```python
CONTAINER_TYPES = {
    0: "None",     # EPinContainerType::None
    1: "Array",    # EPinContainerType::Array
    2: "Set",      # EPinContainerType::Set
    3: "Map",      # EPinContainerType::Map
}

def format_pin_type_name(pin_type: FEdGraphPinType, name_map: List[str], import_map: List[ObjectImport]) -> str:
    """Format human-readable type name from FEdGraphPinType."""
    # Base element type (D-05: UE original names)
    element_type = pin_type.pin_category

    # D-07: Resolve PinSubCategoryObject for object types
    if pin_type.pin_sub_category_object != 0:
        pkg_idx = PackageIndex(pin_type.pin_sub_category_object)
        if pkg_idx.is_import:
            idx = pkg_idx.to_import_index()
            if 0 <= idx < len(import_map):
                element_type = f"{import_map[idx].object_name} Reference"

    # D-06: Add container prefix
    container_name = CONTAINER_TYPES.get(pin_type.container_type, "None")
    if container_name == "None":
        return element_type
    elif container_name == "Map":
        return f"Map[{element_type}]"  # Simplified for Phase 3
    else:
        return f"{container_name}[{element_type}]"
```

## Metadata

**Analog search scope:** `uasset_read.py`, `tests/test_property_parsing.py`, `tests/test_uasset_read.py`
**Files scanned:** 3
**Pattern extraction date:** 2026-05-01

**Key patterns identified:**
- All Phase 3 patterns have exact analogs in existing codebase
- FArchive read methods pattern reused directly (no new read methods needed)
- Dataclass pattern consistent with PropertyTag/PropertyValue
- ExportReader pattern applies to blueprint metadata extraction
- FPackageIndex resolution pattern applies to ParentClass and PinSubCategoryObject
- Test patterns from test_property_parsing.py directly applicable

**Integration points:**
- `parse_uasset()` extended to call `detect_blueprint()` and `extract_blueprint_metadata()`
- `ParseResult` extended with `blueprint: Optional[BlueprintMetadata]` field
- `get_asset_class()` reused for blueprint detection (D-01)