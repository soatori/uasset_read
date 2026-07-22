"""属性数据类 — PropertyTag, PropertyValue 及高级属性值容器。

等价迁移 uasset_read.py 第 1294-1427 行。
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PropertyTypeName:
    """递归 FPropertyTypeName 节点。"""
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
    """PropertyTag 结构（PROP-01）。来自 PropertyTag.h lines 37-105."""
    name: str                         # 属性名（FName）
    type: str                         # 类型名字符串（如 "IntProperty")
    size: int                         # 序列化数据大小（字节）
    array_index: int = 0              # 数组元素索引（默认 0）
    flags: int = 0                    # EPropertyTagFlags 标志位
    property_guid: bytes | None = None  # 16 bytes GUID（HasPropertyGuid 时）
    bool_val: int = 0                 # BoolProperty 值（BoolTrue 标志位）
    override_operation: int | None = None  # EOverriddenPropertyOperation (u8)
    experimental_overridable_logic: int | None = None  # bExperimentalOverridableLogic (u8)
    serialize_type: str = "Property"  # Property / Skipped / BinaryOrNative
    type_name: PropertyTypeName | None = None  # 递归 FPropertyTypeName
    tag_data: Any | None = None     # 映射系统提供的 PropertyType
    enum_type: str | None = None   # ByteProperty/EnumProperty 的枚举类型（从 FPropertyTypeName 提取）
    type_parts: list[tuple[str, int]] = field(default_factory=list)  # 完整 FPropertyTypeName 节点
    struct_type: str | None = None  # StructProperty 的结构体类型名
    inner_type: str | None = None   # Array/Set 内层类型
    inner_type_struct: str | None = None  # Array/Set 内层 StructProperty 的结构体类型
    key_type: str | None = None     # Map key 类型
    key_type_struct: str | None = None  # Map key StructProperty 的结构体类型
    value_type: str | None = None   # Map value 类型
    value_type_struct: str | None = None  # Map value StructProperty 的结构体类型
    tag_start_offset: int | None = None  # PropertyTag 开始读取位置（archive.tell()）
    value_start_offset: int | None = None  # Property value 开始位置（tag 读取后）
    value_end_offset: int | None = None  # Property value 期望结束位置（value_start + size）
    size_exceeded: bool = False  # True when tag.size exceeds remaining bytes (tolerant mode)


@dataclass
class PropertyValue:
    """属性值容器（D-08/D-09）。"""
    name: str
    type: str
    value: Any = None
    array_index: int = 0


@dataclass
class SoftObjectPathValue:
    """统一 SoftObject/LazyObject/AssetObject 解析结果。"""
    raw_kind: str
    asset_path: str = ""
    sub_path: str = ""
    package_index: int | None = None
    guid: str | None = None
    property_type: str = "SoftObjectPath"
    index: int | None = None  # SoftObjectPathList 索引（UE5.7+）
    error: str | None = None  # 越界等诊断信息


class AdvancedPropertyValue:
    """高级属性值基类（D-07a）。所有高级属性 dataclass 继承此基类。

    Note: 非 dataclass — property_type 字段定义在各子类中，
    直接设置默认值避免 dataclass 继承时的字段顺序问题（CR-13）。
    """
    pass


@dataclass
class StructValue(AdvancedPropertyValue):
    """StructProperty 值容器（D-01a）。"""
    struct_type: str
    fields: dict[str, Any] = field(default_factory=dict)
    raw_size: int | None = None
    parse_status: str = "success"
    property_type: str = "StructProperty"


@dataclass
class MapValue(AdvancedPropertyValue):
    """MapProperty 值容器（D-02a）。"""
    key_type: str
    value_type: str
    entries: list[dict[str, Any]] = field(default_factory=list)
    property_type: str = "MapProperty"


@dataclass
class SetValue(AdvancedPropertyValue):
    """SetProperty 值容器（D-03a）。"""
    element_type: str
    elements: list[Any] = field(default_factory=list)
    property_type: str = "SetProperty"


@dataclass
class EnumValue(AdvancedPropertyValue):
    """EnumProperty 值容器（D-04a）。"""
    enum_type: str
    value_name: str
    property_type: str = "EnumProperty"


@dataclass
class TextValue(AdvancedPropertyValue):
    """TextProperty 值容器（D-05a）。"""
    namespace: str = ""
    key: str = ""
    source_string: str = ""
    property_type: str = "TextProperty"


@dataclass
class DelegateValue(AdvancedPropertyValue):
    """DelegateProperty 值容器（D-06a）。"""
    object_ref: int
    function_name: str
    property_type: str = "DelegateProperty"
