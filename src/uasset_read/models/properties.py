"""Property data classes — PropertyTag, PropertyValue and advanced property containers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PropertyTypeName:
    """Recursive FPropertyTypeName node."""
    name: str
    children: list[PropertyTypeName] = field(default_factory=list)

    @property
    def inner_count(self) -> int:
        return len(self.children)

    def child(self, index: int) -> PropertyTypeName | None:
        if 0 <= index < len(self.children):
            return self.children[index]
        return None

    def to_parts(self) -> list[tuple[str, int]]:
        parts: list[tuple[str, int]] = [(self.name, len(self.children))]
        for child in self.children:
            parts.extend(child.to_parts())
        return parts


@dataclass
class PropertyTag:
    """PropertyTag structure (PROP-01). From PropertyTag.h lines 37-105."""
    name: str                         # Property name (FName)
    type: str                         # Type name string (e.g. "IntProperty")
    size: int                         # Serialized data size (bytes)
    array_index: int = 0              # Array element index (default 0)
    flags: int = 0                    # EPropertyTagFlags bit flags
    property_guid: bytes | None = None  # 16 bytes GUID (when HasPropertyGuid)
    bool_val: int = 0                 # BoolProperty value (BoolTrue flag)
    override_operation: int | None = None  # EOverriddenPropertyOperation (u8)
    experimental_overridable_logic: int | None = None  # bExperimentalOverridableLogic (u8)
    serialize_type: str = "Property"  # Property / Skipped / BinaryOrNative
    type_name: PropertyTypeName | None = None  # Recursive FPropertyTypeName
    tag_data: Any | None = None     # PropertyType from mapping system
    enum_type: str | None = None   # ByteProperty/EnumProperty enum type (extracted from FPropertyTypeName)
    type_parts: list[tuple[str, int]] = field(default_factory=list)  # Complete FPropertyTypeName nodes
    struct_type: str | None = None  # StructProperty struct type name
    inner_type: str | None = None   # Array/Set inner type
    inner_type_struct: str | None = None  # Array/Set inner StructProperty struct type
    key_type: str | None = None     # Map key type
    key_type_struct: str | None = None  # Map key StructProperty struct type
    value_type: str | None = None   # Map value type
    value_type_struct: str | None = None  # Map value StructProperty struct type
    tag_start_offset: int | None = None  # PropertyTag start read position (archive.tell())
    value_start_offset: int | None = None  # Property value start position (after tag read)
    value_end_offset: int | None = None  # Property value expected end position (value_start + size)
    size_exceeded: bool = False  # True when tag.size exceeds remaining bytes (tolerant mode)


@dataclass
class PropertyValue:
    """Property value container (D-08/D-09)."""
    name: str
    type: str
    value: Any = None
    array_index: int = 0


@dataclass
class SoftObjectPathValue:
    """Unified SoftObject/LazyObject/AssetObject parse result."""
    raw_kind: str
    asset_path: str = ""
    sub_path: str = ""
    package_index: int | None = None
    guid: str | None = None
    property_type: str = "SoftObjectPath"
    index: int | None = None  # SoftObjectPathList index (UE5.7+)
    error: str | None = None  # Out-of-bounds and other diagnostic info


class AdvancedPropertyValue:
    """Advanced property value base class (D-07a). All advanced property dataclasses inherit this.

    Note: Not a dataclass — property_type field is defined in each subclass,
    with default values set directly to avoid field ordering issues in dataclass
    inheritance (CR-13).
    """
    pass


@dataclass
class StructValue(AdvancedPropertyValue):
    """StructProperty value container (D-01a)."""
    struct_type: str
    fields: dict[str, Any] = field(default_factory=dict)
    raw_size: int | None = None
    parse_status: str = "success"
    property_type: str = "StructProperty"


@dataclass
class MapValue(AdvancedPropertyValue):
    """MapProperty value container (D-02a)."""
    key_type: str
    value_type: str
    entries: list[dict[str, Any]] = field(default_factory=list)
    property_type: str = "MapProperty"


@dataclass
class SetValue(AdvancedPropertyValue):
    """SetProperty value container (D-03a)."""
    element_type: str
    elements: list[Any] = field(default_factory=list)
    property_type: str = "SetProperty"


@dataclass
class EnumValue(AdvancedPropertyValue):
    """EnumProperty value container (D-04a)."""
    enum_type: str
    value_name: str
    property_type: str = "EnumProperty"


@dataclass
class TextValue(AdvancedPropertyValue):
    """TextProperty value container (D-05a)."""
    namespace: str = ""
    key: str = ""
    source_string: str = ""
    property_type: str = "TextProperty"


@dataclass
class DelegateValue(AdvancedPropertyValue):
    """DelegateProperty value container (D-06a)."""
    object_ref: int
    function_name: str
    property_type: str = "DelegateProperty"
