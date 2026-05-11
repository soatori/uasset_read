"""蓝图变量提取模块 — 从属性数据中提取蓝图变量、函数、事件元数据。

独立模块（per D-02），可被属性解析和蓝图图解析共同使用。
Phase 30: 属性解析模块。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Dict, Any, Optional

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.object_resources import ObjectExport
    from uasset_read.serializers.package_summary import PackageFileSummary

from uasset_read.models.blueprint import BlueprintVariable, BlueprintMetadata
from uasset_read.models.properties import PropertyValue
from uasset_read.models.core import FEdGraphPinType

# CPF_* flag bit constants (inline, do NOT import from constants.py)
CPF_Edit = 0x00000001
CPF_EditConst = 0x00000002
CPF_BlueprintVisible = 0x00000004
CPF_BlueprintReadOnly = 0x00000010
CPF_Net = 0x00000020
CPF_Transient = 0x00000040
CPF_BlueprintAssignable = 0x00000100
CPF_RepNotify = 0x10000000
CPF_SaveGame = 0x02000000


def _map_property_flags(flags: int) -> Dict[str, bool]:
    """将 CPF_* 位标志映射到 BlueprintVariable 布尔属性。"""
    return {
        "is_edit_anywhere": bool(flags & CPF_Edit),
        "is_edit_instance_only": bool(flags & CPF_EditConst),
        "is_blueprint_readable": bool(flags & CPF_BlueprintVisible),
        "is_blueprint_read_only": bool(flags & CPF_BlueprintReadOnly),
        "is_net": bool(flags & CPF_Net),
        "is_replicated": bool(flags & CPF_Net),
        "is_transient": bool(flags & CPF_Transient),
        "is_blueprint_assignable": bool(flags & CPF_BlueprintAssignable),
        "is_rep_notify": bool(flags & CPF_RepNotify),
        "is_save_game": bool(flags & CPF_SaveGame),
    }


def _flags_to_labels(flags: int) -> List[str]:
    """将 CPF_* 位标志转换为可读标签列表。"""
    labels = []
    if flags & CPF_Edit:
        labels.append("EditAnywhere")
    if flags & CPF_EditConst:
        labels.append("EditConst")
    if flags & CPF_BlueprintVisible:
        labels.append("BlueprintVisible")
    if flags & CPF_BlueprintReadOnly:
        labels.append("BlueprintReadOnly")
    if flags & CPF_Net:
        labels.append("Net")
    if flags & CPF_Transient:
        labels.append("Transient")
    if flags & CPF_BlueprintAssignable:
        labels.append("BlueprintAssignable")
    if flags & CPF_RepNotify:
        labels.append("RepNotify")
    if flags & CPF_SaveGame:
        labels.append("SaveGame")
    return labels


def _extract_pin_type_from_property(prop: PropertyValue) -> FEdGraphPinType:
    """从 PropertyValue 提取 FEdGraphPinType 类型信息。"""
    value = prop.value

    # StructProperty: 查找 pin_category, pin_subcategory 等字段
    if isinstance(value, dict):
        pin_category = value.get("pin_category", "")
        pin_subcategory = value.get("pin_subcategory", "")
        pin_subcategory_object = value.get("pin_subcategory_object")
        container_type = value.get("container_type", 0)

        # 处理 StructValue 对象（高级属性容器）
        from uasset_read.models.properties import StructValue
        if hasattr(prop, "type") and prop.type == "StructProperty":
            if isinstance(value, dict):
                pin_category = value.get("PinCategory", value.get("pin_category", ""))
                pin_subcategory = value.get("PinSubcategory", value.get("pin_subcategory", ""))
                if "PinSubcategoryObject" in value:
                    pin_subcategory_object = value["PinSubcategoryObject"]
                elif "pin_subcategory_object" in value:
                    pin_subcategory_object = value["pin_subcategory_object"]

        return FEdGraphPinType(
            pin_category=pin_category,
            pin_subcategory=pin_subcategory,
            pin_subcategory_object=pin_subcategory_object,
            container_type=container_type,
        )

    # 简单类型映射
    type_mapping = {
        "BoolProperty": FEdGraphPinType(pin_category="bool"),
        "IntProperty": FEdGraphPinType(pin_category="int"),
        "Int64Property": FEdGraphPinType(pin_category="int64"),
        "FloatProperty": FEdGraphPinType(pin_category="float"),
        "DoubleProperty": FEdGraphPinType(pin_category="double"),
        "StrProperty": FEdGraphPinType(pin_category="string"),
        "NameProperty": FEdGraphPinType(pin_category="name"),
        "TextProperty": FEdGraphPinType(pin_category="text"),
        "ObjectProperty": FEdGraphPinType(pin_category="object"),
        "ClassProperty": FEdGraphPinType(pin_category="class"),
        "ArrayProperty": FEdGraphPinType(pin_category="array"),
        "StructProperty": FEdGraphPinType(pin_category="struct"),
        "MapProperty": FEdGraphPinType(pin_category="map"),
        "SetProperty": FEdGraphPinType(pin_category="set"),
        "EnumProperty": FEdGraphPinType(pin_category="byte", pin_subcategory="enum"),
        "ByteProperty": FEdGraphPinType(pin_category="byte"),
        "DelegateProperty": FEdGraphPinType(pin_category="delegate"),
        "MulticastDelegateProperty": FEdGraphPinType(pin_category="multicast_delegate"),
        "InterfaceProperty": FEdGraphPinType(pin_category="interface"),
        "WeakObjectProperty": FEdGraphPinType(pin_category="weak_object"),
        "LazyObjectProperty": FEdGraphPinType(pin_category="lazy_object"),
        "SoftObjectProperty": FEdGraphPinType(pin_category="soft_object"),
        "SoftClassProperty": FEdGraphPinType(pin_category="soft_class"),
    }

    if isinstance(value, str) and prop.type in type_mapping:
        return type_mapping[prop.type]

    return FEdGraphPinType(pin_category=prop.type if hasattr(prop, "type") else "unknown")


def extract_blueprint_variables(properties: List[PropertyValue]) -> List[BlueprintVariable]:
    """从已解析的属性数据中提取蓝图变量。

    遍历 PropertyValue 列表，识别变量相关的属性（包含名称、类型、分类、
    标志位等信息），并将其转换为 BlueprintVariable 实例。

    Args:
        properties: 已解析的属性值列表

    Returns:
        BlueprintVariable 实例列表
    """
    variables: List[BlueprintVariable] = []

    if not properties:
        return variables

    # 查找变量描述属性
    # UE 蓝图变量通常在属性中以特定模式出现
    # 我们遍历所有属性，识别可能的变量定义
    for prop in properties:
        prop_name = prop.name
        prop_value = prop.value

        # 跳过终止标记和系统属性
        if prop_name in ("None", "NoneProperty"):
            continue

        # 检测是否为蓝图变量描述属性
        # 变量通常带有类型信息和默认值
        var_type = _extract_pin_type_from_property(prop)

        # 从属性名推断分类
        category = ""
        if hasattr(prop, "type") and prop.type in ("StructProperty", "ObjectProperty"):
            if isinstance(prop_value, dict):
                category = prop_value.get("Category", prop_value.get("category", ""))

        # 提取属性标志位
        property_flags = 0
        if isinstance(prop_value, dict):
            property_flags = prop_value.get("property_flags", prop_value.get("PropertyFlags", 0))

        # 检查是否为组件变量
        is_component = False
        if hasattr(prop, "type") and prop.type in ("ObjectProperty", "ClassProperty"):
            type_name = var_type.pin_subcategory or var_type.pin_category
            component_keywords = ["Component", "SceneComponent", "ActorComponent"]
            is_component = any(kw in type_name for kw in component_keywords)

        # 构建 BlueprintVariable
        flag_mapping = _map_property_flags(property_flags)
        flags_labels = _flags_to_labels(property_flags)

        # 提取默认值
        default_value = None
        if isinstance(prop_value, dict):
            default_value = prop_value.get("default_value", prop_value.get("DefaultValue"))
        else:
            default_value = prop_value

        # 提取元数据
        metadata = {}
        meta_class = ""
        edit_condition = ""
        if isinstance(prop_value, dict):
            for key, val in prop_value.items():
                if key.lower().startswith("meta"):
                    metadata[key] = str(val)
            meta_class = prop_value.get("meta_class", prop_value.get("MetaClass", ""))
            edit_condition = prop_value.get("edit_condition", prop_value.get("EditCondition", ""))

        # 推断变量类型的额外属性
        is_blueprint_writable = flag_mapping.get("is_blueprint_readable", False) and not flag_mapping.get("is_blueprint_read_only", False)

        var = BlueprintVariable(
            var_name=prop_name,
            var_type=var_type,
            category=category,
            property_flags=property_flags,
            default_value=default_value,
            is_component=is_component,
            metadata=metadata,
            flags_labels=flags_labels,
            edit_condition=edit_condition,
            meta_class=meta_class,
            **flag_mapping,
            is_blueprint_writable=is_blueprint_writable,
        )
        variables.append(var)

    return variables


def parse_component_transform(properties: List[PropertyValue]) -> Dict[str, Any]:
    """从已解析的属性数据中提取组件变换属性。

    识别并提取 RelativeLocation、RelativeRotation、RelativeScale3D、
    Mobility 等组件变换相关的属性。

    Args:
        properties: 已解析的属性值列表

    Returns:
        包含变换组件的字典，可能的键：
        - relative_location: {X, Y, Z}
        - relative_rotation: {Pitch, Yaw, Roll}
        - relative_scale3d: {X, Y, Z}
        - mobility: str
    """
    transform: Dict[str, Any] = {}

    for prop in properties:
        prop_name = prop.name
        prop_value = prop.value

        if prop_name == "RelativeLocation":
            transform["relative_location"] = _extract_vector(prop_value)
        elif prop_name == "RelativeRotation":
            transform["relative_rotation"] = _extract_rotator(prop_value)
        elif prop_name == "RelativeScale3D":
            transform["relative_scale3d"] = _extract_vector(prop_value)
        elif prop_name == "RelativeTranslation":
            transform["relative_translation"] = _extract_vector(prop_value)
        elif prop_name == "Mobility":
            transform["mobility"] = _extract_mobility(prop_value)

    return transform


def _extract_vector(value: Any) -> Dict[str, float]:
    """从属性值中提取 Vector 结构 {X, Y, Z}。"""
    if isinstance(value, dict):
        # 直接从字典提取
        x = value.get("X", value.get("x", 0.0))
        y = value.get("Y", value.get("y", 0.0))
        z = value.get("Z", value.get("z", 0.0))
        return {"X": float(x), "Y": float(y), "Z": float(z)}
    return {"X": 0.0, "Y": 0.0, "Z": 0.0}


def _extract_rotator(value: Any) -> Dict[str, float]:
    """从属性值中提取 Rotator 结构 {Pitch, Yaw, Roll}。"""
    if isinstance(value, dict):
        pitch = value.get("Pitch", value.get("pitch", 0.0))
        yaw = value.get("Yaw", value.get("yaw", 0.0))
        roll = value.get("Roll", value.get("roll", 0.0))
        return {"Pitch": float(pitch), "Yaw": float(yaw), "Roll": float(roll)}
    return {"Pitch": 0.0, "Yaw": 0.0, "Roll": 0.0}


def _extract_mobility(value: Any) -> str:
    """从属性值中提取 Mobility 枚举值。"""
    if isinstance(value, dict):
        return value.get("value", value.get("name", str(value)))
    if isinstance(value, str):
        return value
    return str(value) if value is not None else "Static"


def extract_blueprint_metadata(
    properties: List[PropertyValue],
    export_map: List[Any]
) -> BlueprintMetadata:
    """综合变量提取和通用元数据，构建 BlueprintMetadata 实例。

    检测蓝图标识、提取父类、调用变量提取，函数和事件列表暂为空
    （由 Phase 31 填充）。

    Args:
        properties: 已解析的属性值列表
        export_map: 导出表条目列表

    Returns:
        BlueprintMetadata 实例
    """
    # 检测是否为蓝图：检查 export_map 中的类名
    is_blueprint = False
    parent_class = None

    for export in export_map:
        if hasattr(export, "object_name"):
            obj_name = export.object_name
            if "BP_" in obj_name or "Blueprint" in obj_name:
                is_blueprint = True
        if hasattr(export, "class_index"):
            # 尝试从 class_index 推断父类
            pass

    # 从属性中提取父类信息
    for prop in properties:
        if prop.name in ("ParentClass", "ParentClassProperty", "SuperClass"):
            parent_class = str(prop.value) if prop.value else None

    # 提取变量
    variables = extract_blueprint_variables(properties)

    return BlueprintMetadata(
        is_blueprint=is_blueprint,
        parent_class=parent_class,
        variables=variables,
        functions=[],   # Phase 31 will populate
        events=[],      # Phase 31 will populate
    )
