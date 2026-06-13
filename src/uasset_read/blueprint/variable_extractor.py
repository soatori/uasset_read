"""蓝图变量提取模块 — 从属性数据中提取蓝图变量、函数、事件元数据。

独立模块（per D-02），可被属性解析和蓝图图解析共同使用。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Dict, Any, Optional

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.object_resources import ObjectExport
    from uasset_read.serializers.package_summary import PackageFileSummary

from uasset_read.models.blueprint import BlueprintVariable, BlueprintMetadata, BlueprintFunction, BlueprintEvent, FunctionParameter
from uasset_read.models.properties import PropertyValue, StructValue
from uasset_read.models.core import FEdGraphPinType
from uasset_read.parsers.property_types import parse_default_value
from uasset_read.serializers.graph import read_ed_graph_pin_type
from uasset_read.constants import (
    CPF_Edit, CPF_EditConst, CPF_BlueprintVisible, CPF_BlueprintReadOnly,
    CPF_Transient, CPF_BlueprintAssignable, CPF_RepNotify, CPF_SaveGame,
    CPF_Net, CPF_InstancedReference, CPF_Config, CPF_Deprecated,
    CPF_Protected, CPF_AdvancedDisplay, CPF_ExposeOnSpawn, CPF_EditAnywhere,
    CPF_EditInstanceOnly, CPF_BlueprintReadWrite, CPF_DuplicateTransient,
    CPF_NoClear, CPF_ReferenceOnly, CPF_BlueprintCallable, CPF_Interp,
    CPF_Replicated, CPF_NonPIEDuplicateTransient,
)


# ============================================================================
# Pin Category 到 C++ 类型映射
# ============================================================================

_PIN_CATEGORY_TO_CPP_TYPE = {
    # 基本类型
    "real": "float",
    "double": "double",
    "float": "float",
    "int": "int32",
    "int32": "int32",
    "int64": "int64",
    "byte": "uint8",
    "bool": "bool",
    "boolean": "bool",
    # 字符串类型
    "string": "FString",
    "name": "FName",
    "text": "FText",
    # 结构体类型
    "struct": "FStruct",
    "vector": "FVector",
    "rotator": "FRotator",
    "transform": "FTransform",
    "vector2d": "FVector2D",
    "linearcolor": "FLinearColor",
    "guid": "FGuid",
    # 对象类型
    "object": "UObject*",
    "class": "UClass*",
    "widget": "UWidget*",
    # 特殊类型
    " wildcard": "Wildcard",
    "exec": "void",
    "delegate": "void",
    "multicastdelegate": "void",
}


def _map_pin_category_to_cpp_type(pin_category: str) -> str:
    """将 pin_category 映射到 C++ 类型。

    Args:
        pin_category: Pin 类型名称（如 "real", "object", "struct"）

    Returns:
        C++ 类型字符串
    """
    # 精确匹配
    if pin_category in _PIN_CATEGORY_TO_CPP_TYPE:
        return _PIN_CATEGORY_TO_CPP_TYPE[pin_category]

    # 大小写不敏感匹配
    lower_category = pin_category.lower()
    for key, value in _PIN_CATEGORY_TO_CPP_TYPE.items():
        if key.lower() == lower_category:
            return value

    # 如果是对象类型路径（以 /Script/ 开头），直接返回
    if pin_category.startswith("/Script/"):
        return pin_category

    # 默认返回原始类型名
    return pin_category


# Blueprint 资产元数据属性名称（不是用户定义的变量）
BLUEPRINT_METADATA_PROPERTY_NAMES = frozenset({
    "BlueprintDescription",
    "ParentClass",
    "ParentClassProperty",
    "SuperClass",
    "BlueprintGuid",
    "BlueprintCategory",
    "BlueprintType",
    "IsBlueprintBase",
    "KismetSchemaDeprecationWarning",
    "NativeParent",
    "ObjectArchitecture",
    "ObjectParentClass",
    "SupportedClasses",
    "HiddenCategories",
    "ModulesToIgnoreInReloadAndBlueprints",
    "None",  # 终止标记
    "NoneProperty",
})


def _map_property_flags(flags: int) -> Dict[str, bool]:
    """将 CPF_* 位标志映射到 BlueprintVariable 布尔属性。"""
    return {
        "is_edit_anywhere": bool(flags & CPF_EditAnywhere),
        "is_edit_instance_only": bool(flags & CPF_EditInstanceOnly),
        "is_blueprint_readable": bool(flags & CPF_BlueprintReadWrite),
        "is_blueprint_read_only": bool(flags & CPF_BlueprintReadOnly),
        "is_net": bool(flags & CPF_Net),
        "is_replicated": bool(flags & CPF_Replicated),
        "is_transient": bool(flags & CPF_Transient),
        "is_blueprint_assignable": bool(flags & CPF_BlueprintAssignable),
        "is_rep_notify": bool(flags & CPF_RepNotify),
        "is_save_game": bool(flags & CPF_SaveGame),
    }


def _flags_to_labels(flags: int) -> List[str]:
    """将 CPF_* 位标志转换为可读标签列表。"""
    labels = []
    if flags & CPF_EditAnywhere:
        labels.append("EditAnywhere")
    if flags & CPF_EditConst:
        labels.append("EditConst")
    if flags & CPF_BlueprintReadWrite:
        labels.append("BlueprintReadWrite")
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

    if isinstance(value, str) and getattr(prop, 'type', None) in type_mapping:
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

        if prop_name == "NewVariables" and isinstance(prop_value, list):
            variables.extend(_extract_blueprint_variable_descriptions(prop_value))
            continue

        # 跳过终止标记、系统属性和蓝图元数据属性
        if prop_name in BLUEPRINT_METADATA_PROPERTY_NAMES:
            continue

        # 检测是否为蓝图变量描述属性
        # 变量通常带有类型信息和默认值
        var_type = _extract_pin_type_from_property(prop)

        # 从属性值提取分类
        category = ""
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


def _extract_blueprint_variable_descriptions(items: List[Any]) -> List[BlueprintVariable]:
    """Expand FBPVariableDescription structs from UBlueprint.NewVariables."""
    variables: List[BlueprintVariable] = []
    for item in items:
        fields = item.fields if isinstance(item, StructValue) else item if isinstance(item, dict) else None
        if not fields:
            continue
        var_name = fields.get("VarName") or fields.get("var_name")
        if not var_name:
            continue
        property_flags = int(fields.get("PropertyFlags") or fields.get("property_flags") or 0)
        flag_mapping = _map_property_flags(property_flags)
        flags_labels = _flags_to_labels(property_flags)
        category = _text_or_string(fields.get("Category") or fields.get("category"))
        default_value = fields.get("DefaultValue", fields.get("default_value"))
        rep_condition = fields.get("ReplicationCondition", fields.get("replication_condition", 0))
        var = BlueprintVariable(
            var_name=str(var_name),
            var_type=_extract_var_type_from_description(fields.get("VarType")),
            category=category,
            property_flags=property_flags,
            default_value=default_value,
            metadata=_metadata_from_description(fields.get("MetaDataArray")),
            flags_labels=flags_labels,
            **flag_mapping,
            is_blueprint_writable=flag_mapping.get("is_blueprint_readable", False)
            and not flag_mapping.get("is_blueprint_read_only", False),
        )
        var.var_guid = _guid_from_description(fields.get("VarGuid"))
        var.friendly_name = str(fields.get("FriendlyName") or fields.get("friendly_name") or "")
        var.rep_notify_func = str(fields.get("RepNotifyFunc") or fields.get("rep_notify_func") or "")
        var.replication_condition = _replication_condition_value(rep_condition)
        variables.append(var)
    return variables


def _extract_var_type_from_description(value: Any) -> FEdGraphPinType:
    if isinstance(value, StructValue):
        fields = value.fields
    elif isinstance(value, dict) and value.get("kind") == "binary_or_native_property":
        return FEdGraphPinType(pin_category=str(value.get("type") or "StructProperty"))
    elif isinstance(value, dict):
        fields = value
    else:
        return FEdGraphPinType(pin_category="unknown")
    return FEdGraphPinType(
        pin_category=str(fields.get("PinCategory") or fields.get("pin_category") or "unknown"),
        pin_subcategory=str(fields.get("PinSubCategory") or fields.get("PinSubcategory") or fields.get("pin_subcategory") or ""),
        container_type=int(fields.get("ContainerType") or fields.get("container_type") or 0),
    )


def _guid_from_description(value: Any) -> str:
    # StructValue(Guid, {A:int, B:int, C:int, D:int}) — StructProperty 解析结果
    if isinstance(value, StructValue) and value.struct_type == "Guid":
        fields = value.fields
        a = int(fields.get("A", 0))
        b = int(fields.get("B", 0))
        c = int(fields.get("C", 0))
        d = int(fields.get("D", 0))
        # 每个 uint32 按小端序转为 4 字节
        def _u32_to_bytes(v: int) -> bytes:
            return v.to_bytes(4, byteorder='little')
        raw = _u32_to_bytes(a) + _u32_to_bytes(b) + _u32_to_bytes(c) + _u32_to_bytes(d)
        return _format_guid_bytes(raw)

    if isinstance(value, dict) and value.get("kind") == "binary_or_native_property":
        raw = value.get("raw_data")
        if isinstance(raw, bytes) and len(raw) == 16:
            return _format_guid_bytes(raw)
    # #143: struct_binary_decoded 格式的 Guid
    if isinstance(value, dict) and value.get("kind") == "struct_binary_decoded":
        if value.get("struct_type") == "Guid":
            fields = value.get("fields", {})
            a = int(fields.get("A", 0))
            b = int(fields.get("B", 0))
            c = int(fields.get("C", 0))
            d = int(fields.get("D", 0))
            raw = (
                a.to_bytes(4, byteorder="little")
                + b.to_bytes(4, byteorder="little")
                + c.to_bytes(4, byteorder="little")
                + d.to_bytes(4, byteorder="little")
            )
            return _format_guid_bytes(raw)
    if isinstance(value, bytes) and len(value) == 16:
        return _format_guid_bytes(value)
    if isinstance(value, str):
        return value
    return ""


def _format_guid_bytes(data: bytes) -> str:
    return (
        f"{data[0]:02x}{data[1]:02x}{data[2]:02x}{data[3]:02x}-"
        f"{data[4]:02x}{data[5]:02x}-"
        f"{data[6]:02x}{data[7]:02x}-"
        f"{data[8]:02x}{data[9]:02x}-"
        f"{data[10]:02x}{data[11]:02x}{data[12]:02x}{data[13]:02x}{data[14]:02x}{data[15]:02x}"
    )


def _text_or_string(value: Any) -> str:
    if hasattr(value, "source_string"):
        return str(value.source_string)
    return str(value or "")


def _metadata_from_description(value: Any) -> Dict[str, str]:
    metadata: Dict[str, str] = {}
    if isinstance(value, list):
        for item in value:
            fields = item.fields if isinstance(item, StructValue) else item if isinstance(item, dict) else {}
            key = fields.get("Key") or fields.get("Name") or fields.get("key")
            if key:
                metadata[str(key)] = str(fields.get("Value") or fields.get("value") or "")
    return metadata


def _replication_condition_value(value: Any) -> int:
    if isinstance(value, int):
        return value
    if hasattr(value, "value_name"):
        text = str(value.value_name)
        if text.endswith("COND_None"):
            return 0
    return 0


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
    """从属性值中提取 Vector 结构 {X, Y, Z}。

    支持 StructValue dataclass 和 dict 类型。
    """
    fields: Dict[str, Any] = {}
    if isinstance(value, StructValue):
        fields = value.fields
    elif isinstance(value, dict):
        fields = value

    if fields:
        x = fields.get("X", fields.get("x", 0.0))
        y = fields.get("Y", fields.get("y", 0.0))
        z = fields.get("Z", fields.get("z", 0.0))
        return {"X": float(x), "Y": float(y), "Z": float(z)}
    return {"X": 0.0, "Y": 0.0, "Z": 0.0}


def _extract_rotator(value: Any) -> Dict[str, float]:
    """从属性值中提取 Rotator 结构 {Pitch, Yaw, Roll}。

    支持 StructValue dataclass 和 dict 类型。
    """
    fields: Dict[str, Any] = {}
    if isinstance(value, StructValue):
        fields = value.fields
    elif isinstance(value, dict):
        fields = value

    if fields:
        pitch = fields.get("Pitch", fields.get("pitch", 0.0))
        yaw = fields.get("Yaw", fields.get("yaw", 0.0))
        roll = fields.get("Roll", fields.get("roll", 0.0))
        return {"Pitch": float(pitch), "Yaw": float(yaw), "Roll": float(roll)}
    return {"Pitch": 0.0, "Yaw": 0.0, "Roll": 0.0}


def _extract_mobility(value: Any) -> str:
    """从属性值中提取 Mobility 枚举值。"""
    if isinstance(value, dict):
        return value.get("value", value.get("name", str(value)))
    if isinstance(value, str):
        return value
    return str(value) if value is not None else "Static"


def _extract_functions_from_bpgc_properties(properties: List[Any]) -> List[BlueprintFunction]:
    """Primary path: Extract functions from BPGC export properties.

    Looks for UbergraphFunction and FunctionList properties in BPGC exports.
    These are FPackageIndex references that resolve to function names.
    """
    functions: List[BlueprintFunction] = []
    for prop in properties:
        prop_name = getattr(prop, 'name', '')
        if prop_name == "UbergraphFunction":
            func_name = _resolve_property_to_function_name(prop.value)
            if func_name:
                functions.append(BlueprintFunction(name=func_name))
        elif prop_name == "FunctionList" and isinstance(prop.value, (list, tuple)):
            for item in prop.value:
                func_name = _resolve_property_to_function_name(item)
                if func_name:
                    functions.append(BlueprintFunction(name=func_name))
    return functions


def _resolve_property_to_function_name(value: Any) -> Optional[str]:
    """Resolve a property value to a function name string."""
    if value is None:
        return None
    if isinstance(value, str) and value and value != "None":
        # UE path format: /Game/Path/To/PackageName.ClassName
        # First extract after last '/', then after last '.'
        raw = value.split('/')[-1] if '/' in value else value
        return raw.split('.')[-1] if '.' in raw else raw
    if isinstance(value, dict):
        obj_name = value.get('object_name') or value.get('resolved') or value.get('raw_index')
        if obj_name and obj_name != "None":
            raw = str(obj_name)
            return raw.split('.')[-1] if '.' in raw else raw
    if hasattr(value, 'object_name'):
        name = getattr(value, 'object_name', None)
        if name and name != "None":
            raw = str(name)
            return raw.split('.')[-1] if '.' in raw else raw
    return None


def _extract_functions_from_graphs(graphs) -> List[BlueprintFunction]:
    """从图的 K2Node_FunctionEntry 和 K2Node_Event 节点提取函数元数据（Fallback 路径）。

    遍历图列表，查找 K2Node_FunctionEntry / K2Node_Event 节点，
    从 node_data 和 pins 提取函数签名。
    """
    if not graphs:
        return []
    functions: List[BlueprintFunction] = []
    for graph in graphs:
        for node in getattr(graph, 'nodes', []):
            class_name = getattr(node, 'class_name', '')
            if class_name not in ("K2Node_FunctionEntry", "K2Node_Event"):
                continue

            nd = node.node_data or {}
            if not isinstance(nd, dict):
                continue

            is_event_node = class_name == "K2Node_Event"

            # 提取函数名
            func_name = "Unknown"
            if is_event_node:
                er = nd.get("event_reference")
                if er and hasattr(er, 'member_name'):
                    mn = er.member_name
                    func_name = mn.split('/')[-1] if '/' in mn else mn
                    if func_name == "None":
                        func_name = nd.get("custom_function_name", "Unknown")
                elif nd.get("custom_function_name"):
                    func_name = nd["custom_function_name"]
            else:
                fr = nd.get("function_reference")
                if fr and hasattr(fr, 'member_name'):
                    func_name = fr.member_name if fr.member_name != "None" else "Unknown"
                else:
                    func_name = nd.get("function_name", nd.get("custom_function_name", "Unknown"))

            # 从 pins 提取参数和返回值
            parameters: List[FunctionParameter] = []
            return_type = ""

            for pin in getattr(node, 'pins', []):
                pin_dir = getattr(pin, 'direction', '')
                pin_type_obj = getattr(pin, 'pin_type', None)
                pin_type_name = ""
                if pin_type_obj and hasattr(pin_type_obj, 'pin_category'):
                    pin_type_name = getattr(pin_type_obj, 'pin_category', '') or ""
                elif isinstance(pin_type_obj, dict):
                    pin_type_name = pin_type_obj.get("pin_category", pin_type_obj.get("category", ""))

                if isinstance(pin_dir, int):
                    is_output = pin_dir == 1
                    is_input = pin_dir == 0
                else:
                    is_output = pin_dir == "EGPD_Output"
                    is_input = pin_dir == "EGPD_Input"

                # 跳过执行流 pin（exec）和委托 pin
                if pin_type_name.lower() in ("exec", "delegate", "multicastdelegate"):
                    continue

                pin_name = getattr(pin, 'pin_name', '')
                pin_name_lower = pin_name.lower()

                if not is_event_node and is_output:
                    # FunctionEntry: 输出引脚中含 "return" 的是返回值，其余是输出参数
                    if "return" in pin_name_lower:
                        if return_type == "":
                            return_type = _map_pin_category_to_cpp_type(pin_type_name)
                    else:
                        cpp_type = _map_pin_category_to_cpp_type(pin_type_name)
                        parameters.append(FunctionParameter(
                            name=pin_name,
                            param_type=cpp_type,
                            is_input=False,
                            is_output=True,
                        ))
                elif is_input:
                    # 输入引脚作为参数（排除 self/target）
                    if pin_name_lower in ("self", "target", "worldcontext"):
                        continue
                    cpp_type = _map_pin_category_to_cpp_type(pin_type_name)
                    parameters.append(FunctionParameter(
                        name=pin_name,
                        param_type=cpp_type,
                        is_input=True,
                        is_output=False,
                    ))
                elif is_output and is_event_node:
                    # K2Node_Event 输出引脚（非 exec/delegate）= 事件参数
                    cpp_type = _map_pin_category_to_cpp_type(pin_type_name)
                    parameters.append(FunctionParameter(
                        name=pin_name,
                        param_type=cpp_type,
                        is_input=False,
                        is_output=True,
                    ))

            func = BlueprintFunction(
                name=func_name,
                return_type=return_type,
                parameters=parameters,
            )
            # 标记事件节点
            if is_event_node:
                func.is_blueprint_implementable_event = True
                if nd.get("b_override_function", False):
                    func.is_blueprint_event = True
            functions.append(func)
    return functions


def extract_blueprint_metadata(
    export,
    archive,
    import_map,
    export_map,
    name_map,
    summary,
    linker=None,
    graphs=None,
) -> tuple:
    """综合变量提取和通用元数据，构建 BlueprintMetadata 实例。

    等价迁移 uasset_read.py §6100-6220。
    从指定的 export 读取属性并提取蓝图元数据。

    Args:
        export: ObjectExport 条目（通常是 BPGC）
        archive: FArchive 实例
        import_map: 导入表
        export_map: 导出表
        name_map: 名称表
        summary: PackageFileSummary
        linker: PackageLinker 实例（可选，用于更精确的父类解析）
        graphs: UEdGraph 列表（可选，用于从 K2Node_FunctionEntry 提取函数）

    Returns:
        Tuple[BlueprintMetadata | None, str | None] — (元数据, 警告)
    """
    from uasset_read.parsers.property_parser import parse_properties_from_export

    if export is None or export.serial_size <= 0:
        return None, None

    # 解析 export 属性
    try:
        properties = parse_properties_from_export(
            export, archive, summary, name_map, export_map, import_map,
        )
    except Exception:
        return None, None

    if not properties:
        return None, None

    # 提取变量
    variables = extract_blueprint_variables(properties)

    # 提取父类信息
    parent_class = None
    for prop in properties:
        if prop.name in ("ParentClass", "ParentClassProperty", "SuperClass"):
            # 修复: 不使用 str(prop.value)，而是提取实际值
            # prop.value 可能是 ObjectProperty 实例 (dict 格式)
            if prop.value and isinstance(prop.value, dict):
                # 如果 dict 中有 raw_index/resolved，使用它
                if prop.value.get('raw_index'):
                    parent_class = prop.value.get('raw_index')
                elif prop.value.get('resolved'):
                    parent_class = prop.value.get('resolved')
                elif prop.value.get('object_name'):
                    # 从 object_name 构建 UE 路径
                    object_name = prop.value.get('object_name')
                    # 如果有 class_package，构建完整路径
                    class_package = prop.value.get('class_package', '')
                    if class_package:
                        # 典型格式: /Script/Engine.ClassName
                        parent_class = f"{class_package}.{object_name}"
                    else:
                        # 尝试从 object_name 推断（常见引擎类）
                        # 对于 Character/Pawn/Actor 等，使用 /Script/Engine 前缀
                        common_engine_classes = [
                            "Character", "Pawn", "Actor", "ActorComponent",
                            "SceneComponent", "Object", "Interface", "UserWidget",
                            "HUD", "PlayerController", "GameModeBase", "GameMode",
                            "Controller", "PlayerCameraManager", "PawnMovementComponent",
                            "CharacterMovementComponent", "SpringArmComponent",
                            "CameraComponent", "SkeletalMeshComponent", "StaticMeshComponent",
                            "BoxComponent", "SphereComponent", "CapsuleComponent",
                            "AudioComponent", "ParticleSystemComponent",
                            "WidgetComponent", "ChildActorComponent",
                            "Blueprint", "BlueprintGeneratedClass",
                        ]
                        if object_name in common_engine_classes:
                            parent_class = f"/Script/Engine.{object_name}"
                        else:
                            # 未知类，使用 object_name 作为父类名
                            parent_class = object_name

    # 推断父类（从 export 的 super_index）
    if not parent_class and hasattr(export, 'super_index'):
        if linker is not None:
            from uasset_read.serializers.object_resources import resolve_parent_class_with_linker as _rpc
            parent_name, warn = _rpc(export.super_index, linker)
        else:
            from uasset_read.serializers.object_resources import resolve_parent_class as _rpc
            parent_name, warn = _rpc(export.super_index, import_map, export_map)
        if parent_name:
            parent_class = parent_name

    # Merge primary BPGC path + fallback graph path
    functions_bpgc = _extract_functions_from_bpgc_properties(properties) if properties else []
    functions_graph = _extract_functions_from_graphs(graphs) if graphs else []
    # Deduplicate by name
    seen_names = set()
    functions: List[BlueprintFunction] = []
    for func in functions_bpgc + functions_graph:
        if func.name not in seen_names:
            seen_names.add(func.name)
            functions.append(func)
    events: List[BlueprintEvent] = []
    for f in functions:
        if f.is_blueprint_implementable_event or f.is_blueprint_event:
            events.append(BlueprintEvent(
                name=f.name,
                event_type="Override" if f.is_blueprint_event else "Event",
                function_flags=f.function_flags,
                is_blueprint_event=f.is_blueprint_event,
                is_blueprint_implementable_event=f.is_blueprint_implementable_event,
                parameters=f.parameters,
            ))

    meta = BlueprintMetadata(
        is_blueprint=True,
        parent_class=parent_class,
        variables=variables,
        functions=functions,
        events=events,
    )
    return meta, None


def parse_property_flags_to_labels(flags: int) -> List[str]:
    """将 CPF_* 位标志转换为可读标签列表。

    等价迁移 uasset_read.py §4775-4827。
    包含语义映射：CPF_Edit → EditAnywhere/EditConst,
    CPF_BlueprintVisible → BlueprintReadWrite/BlueprintReadOnly。
    """
    labels = []

    # Edit 标志（互斥模式）
    if flags & CPF_Edit:
        if flags & CPF_EditConst:
            labels.append("EditConst")
        else:
            labels.append("EditAnywhere")

    # 蓝图可见性标志（互斥）
    if flags & CPF_BlueprintVisible:
        if flags & CPF_BlueprintReadOnly:
            labels.append("BlueprintReadOnly")
        else:
            labels.append("BlueprintReadWrite")

    # 组件引用标志
    if flags & CPF_InstancedReference:
        labels.append("InstancedReference")

    # 其他标志
    if flags & CPF_Protected:
        labels.append("Protected")
    if flags & CPF_ExposeOnSpawn:
        labels.append("ExposeOnSpawn")
    if flags & CPF_Config:
        labels.append("Config")
    if flags & CPF_Transient:
        labels.append("Transient")
    if flags & CPF_SaveGame:
        labels.append("SaveGame")
    if flags & CPF_Deprecated:
        labels.append("Deprecated")
    if flags & CPF_BlueprintAssignable:
        labels.append("BlueprintAssignable")
    if flags & CPF_BlueprintCallable:
        labels.append("BlueprintCallable")
    if flags & CPF_RepNotify:
        labels.append("RepNotify")
    if flags & CPF_Interp:
        labels.append("Interp")
    if flags & CPF_Net:
        labels.append("Net")
    if flags & CPF_Replicated:
        labels.append("Replicated")

    return labels


def read_blueprint_variable(
    archive,
    name_map: List[str],
    summary,
) -> BlueprintVariable:
    """
    从 blueprint export 读取 FBPVariableDescription（BLUE-03）。
    
    参考 UE C++ FBPVariableDescription::Serialize() 实现

    序列化顺序:
    1. VarName (FName)
    2. VarGuid (FGuid - 16 bytes) — 跳过
    3. VarType (FEdGraphPinType)
    4. FriendlyName (FString)
    5. Category (FText — 简化为 FString)
    6. PropertyFlags (uint64)
    7. RepNotifyFunc (FName) — 跳过
    8. ReplicationCondition (uint8) — 跳过
    9. MetaDataArray (TArray)
    10. DefaultValue (FString)
    """
    var = BlueprintVariable(
        var_name=archive.read_name(name_map)
    )

    var.var_guid = _read_guid(archive)

    # VarType (FEdGraphPinType)
    var.var_type = read_ed_graph_pin_type(archive, name_map, summary)

    # FriendlyName (FString)
    var.friendly_name = archive.read_fstring()

    # Category (FText) — 简化为 FString
    var.category = archive.read_fstring()

    var.property_flags = archive.read_u64()

    var.rep_notify_func = archive.read_name(name_map)

    var.replication_condition = archive.read_u8()

    meta_count = archive.read_i32()
    var.metadata = {}
    for _ in range(meta_count):
        key = archive.read_name(name_map)
        value = archive.read_fstring()
        if key:
            var.metadata[key] = value

    # 解析 PropertyFlags 为可读标签
    var.flags_labels = parse_property_flags_to_labels(var.property_flags)

    # 解析属性标志为布尔字段
    flags = var.property_flags
    var.is_edit_anywhere = bool(flags & CPF_EditAnywhere)
    var.is_edit_instance_only = bool(flags & CPF_EditInstanceOnly)
    var.is_blueprint_read_only = bool(flags & CPF_BlueprintReadOnly)
    var.is_blueprint_readable = bool(flags & CPF_BlueprintReadWrite)
    var.is_blueprint_writable = bool(flags & CPF_BlueprintReadWrite) and not bool(flags & CPF_BlueprintReadOnly)
    var.is_transient = bool(flags & CPF_Transient)
    var.is_duplicate_transient = bool(flags & CPF_DuplicateTransient)
    var.is_save_game = bool(flags & CPF_SaveGame)
    var.is_no_clear = bool(flags & CPF_NoClear)
    var.is_reference_only = bool(flags & CPF_ReferenceOnly)
    var.is_blueprint_assignable = bool(flags & CPF_BlueprintAssignable)
    var.is_blueprint_callable = bool(flags & CPF_BlueprintCallable)
    var.is_rep_notify = bool(flags & CPF_RepNotify)
    var.is_interp = bool(flags & CPF_Interp)
    var.is_expose_on_spawn = bool(flags & CPF_ExposeOnSpawn)
    var.is_net = bool(flags & CPF_Net)
    var.is_replicated = bool(flags & CPF_Replicated)
    var.is_non_pi_ed_duplicate_transient = bool(flags & CPF_NonPIEDuplicateTransient)

    # 提取元数据字段
    var.edit_condition = var.metadata.get('EditCondition', '')
    var.meta_class = var.metadata.get('MetaClass', '')
    var.edit_category = var.metadata.get('Category', '')
    var.edit_widget = var.metadata.get('EditWidget', '')

    default_str = archive.read_fstring()
    var.default_value = parse_default_value(default_str, var.var_type)

    # 组件变量识别（双重验证）
    type_str = ""
    if var.var_type:
        if var.var_type.pin_subcategory and var.var_type.pin_subcategory.lower() != "none":
            type_str = var.var_type.pin_subcategory
        elif var.var_type.pin_category:
            type_str = var.var_type.pin_category

    is_component_by_name = isinstance(type_str, str) and "Component" in type_str
    is_component_by_flag = (var.property_flags & CPF_InstancedReference) != 0
    var.is_component = is_component_by_name or is_component_by_flag

    return var


def _read_guid(archive) -> str:
    data = archive.read_bytes(16) if hasattr(archive, "read_bytes") else archive.read(16)
    return (
        f"{data[0]:02x}{data[1]:02x}{data[2]:02x}{data[3]:02x}-"
        f"{data[4]:02x}{data[5]:02x}-"
        f"{data[6]:02x}{data[7]:02x}-"
        f"{data[8]:02x}{data[9]:02x}-"
        f"{data[10]:02x}{data[11]:02x}{data[12]:02x}{data[13]:02x}{data[14]:02x}{data[15]:02x}"
    )
