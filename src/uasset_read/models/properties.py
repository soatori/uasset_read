"""属性数据类 — PropertyTag, PropertyValue 及高级属性值容器。

等价迁移 uasset_read.py 第 1294-1427 行。
Phase 30: 属性解析模块 (per MOD-06, MOD-09)。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.archive import FArchive


@dataclass
class PropertyTag:
    """PropertyTag 结构（PROP-01）。来自 PropertyTag.h lines 37-105."""
    name: str                         # 属性名（FName）
    type: str                         # 类型名字符串（如 "IntProperty")
    size: int                         # 序列化数据大小（字节）
    array_index: int = 0              # 数组元素索引（默认 0）
    flags: int = 0                    # EPropertyTagFlags 标志位
    property_guid: Optional[bytes] = None  # 16 bytes GUID（HasPropertyGuid 时）
    bool_val: int = 0                 # BoolProperty 值（BoolTrue 标志位）
    override_operation: Optional[int] = None  # EOverriddenPropertyOperation (u8)
    experimental_overridable_logic: Optional[int] = None  # bExperimentalOverridableLogic (u8)
    enum_type: Optional[str] = None   # ByteProperty/EnumProperty 的枚举类型（从 FPropertyTypeName 提取）


@dataclass
class PropertyValue:
    """属性值容器（D-08/D-09）。"""
    name: str
    type: str
    value: Any = None
    array_index: int = 0


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
    fields: Dict[str, Any] = field(default_factory=dict)
    property_type: str = "StructProperty"


@dataclass
class MapValue(AdvancedPropertyValue):
    """MapProperty 值容器（D-02a）。"""
    key_type: str
    value_type: str
    entries: List[Dict[str, Any]] = field(default_factory=list)
    property_type: str = "MapProperty"


@dataclass
class SetValue(AdvancedPropertyValue):
    """SetProperty 值容器（D-03a）。"""
    element_type: str
    elements: List[Any] = field(default_factory=list)
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
