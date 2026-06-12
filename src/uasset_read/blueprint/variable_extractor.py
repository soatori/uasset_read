"""蓝图变量提取模块 — 从属性数据中提取蓝图变量、函数、事件元数据。

独立模块（per D-02），可被属性解析和蓝图图解析共同使用。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Dict, Any, Optional

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.object_resources import ObjectExport
    from uasset_read.serializers.package_summary import PackageFileSummary

from uasset_read.models.blueprint import BlueprintVariable, BlueprintMetadata, BlueprintFunction, BlueprintEvent
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

# 延迟导入子模块（避免循环导入）
def _get_types():
    from ._variable_types import (
        map_pin_category_to_cpp_type,
        map_property_flags,
        extract_pin_type_from_property,
    )
    return map_pin_category_to_cpp_type, map_property_flags, extract_pin_type_from_property


def _get_functions():
    from .function_extractor import (
        extract_functions_from_bpgc_properties,
        extract_functions_from_graphs,
        build_events_from_functions,
        deduplicate_functions,
    )
    return (
        extract_functions_from_bpgc_properties,
        extract_functions_from_graphs,
        build_events_from_functions,
        deduplicate_functions,
    )


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
    "None",
    "NoneProperty",
})


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


def extract_blueprint_variables(properties: List[PropertyValue]) -> List[BlueprintVariable]:
    """从已解析的属性数据中提取蓝图变量。"""
    map_pin_category_to_cpp_type, map_property_flags, extract_pin_type_from_property = _get_types()

    variables: List[BlueprintVariable] = []

    if not properties:
        return variables

    for prop in properties:
        prop_name = prop.name
        prop_value = prop.value

        if prop_name == "NewVariables" and isinstance(prop_value, list):
            variables.extend(_extract_blueprint_variable_descriptions(prop_value, map_property_flags))
            continue

        if prop_name in BLUEPRINT_METADATA_PROPERTY_NAMES:
            continue

        var_type = extract_pin_type_from_property(prop)

        category = ""
        if isinstance(prop_value, dict):
            category = prop_value.get("Category", prop_value.get("category", ""))

        property_flags = 0
        if isinstance(prop_value, dict):
            property_flags = prop_value.get("property_flags", prop_value.get("PropertyFlags", 0))

        is_component = False
        if hasattr(prop, "type") and prop.type in ("ObjectProperty", "ClassProperty"):
            type_name = var_type.pin_subcategory or var_type.pin_category
            component_keywords = ["Component", "SceneComponent", "ActorComponent"]
            is_component = any(kw in type_name for kw in component_keywords)

        flag_mapping = map_property_flags(property_flags)
        flags_labels = _flags_to_labels(property_flags)

        default_value = None
        if isinstance(prop_value, dict):
            default_value = prop_value.get("default_value", prop_value.get("DefaultValue"))
        else:
            default_value = prop_value

        metadata = {}
        meta_class = ""
        edit_condition = ""
        if isinstance(prop_value, dict):
            for key, val in prop_value.items():
                if key.lower().startswith("meta"):
                    metadata[key] = str(val)
            meta_class = prop_value.get("meta_class", prop_value.get("MetaClass", ""))
            edit_condition = prop_value.get("edit_condition", prop_value.get("EditCondition", ""))

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


def _extract_blueprint_variable_descriptions(items: List[Any], map_property_flags) -> List[BlueprintVariable]:
    """展开 FBPVariableDescription 结构体。"""
    variables: List[BlueprintVariable] = []
    for item in items:
        fields = item.fields if isinstance(item, StructValue) else item if isinstance(item, dict) else None
        if not fields:
            continue
        var_name = fields.get("VarName") or fields.get("var_name")
        if not var_name:
            continue
        property_flags = int(fields.get("PropertyFlags") or fields.get("property_flags") or 0)
        flag_mapping = map_property_flags(property_flags)
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
    if isinstance(value, StructValue) and value.struct_type == "Guid":
        fields = value.fields
        a = int(fields.get("A", 0))
        b = int(fields.get("B", 0))
        c = int(fields.get("C", 0))
        d = int(fields.get("D", 0))
        def _u32_to_bytes(v: int) -> bytes:
            return v.to_bytes(4, byteorder='little')
        raw = _u32_to_bytes(a) + _u32_to_bytes(b) + _u32_to_bytes(c) + _u32_to_bytes(d)
        return _format_guid_bytes(raw)

    if isinstance(value, dict) and value.get("kind") == "binary_or_native_property":
        raw = value.get("raw_data")
        if isinstance(raw, bytes) and len(raw) == 16:
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
    """综合变量提取和通用元数据，构建 BlueprintMetadata 实例。"""
    from uasset_read.parsers.property_parser import parse_properties_from_export
    from .function_extractor import (
        extract_functions_from_bpgc_properties,
        extract_functions_from_graphs,
        build_events_from_functions,
        deduplicate_functions,
    )

    if export is None or export.serial_size <= 0:
        return None, None

    try:
        properties = parse_properties_from_export(
            export, archive, summary, name_map, export_map, import_map,
        )
    except Exception:
        return None, None

    if not properties:
        return None, None

    variables = extract_blueprint_variables(properties)

    parent_class = None
    for prop in properties:
        if prop.name in ("ParentClass", "ParentClassProperty", "SuperClass"):
            if prop.value and isinstance(prop.value, dict):
                if prop.value.get('raw_index'):
                    parent_class = prop.value.get('raw_index')
                elif prop.value.get('resolved'):
                    parent_class = prop.value.get('resolved')
                elif prop.value.get('object_name'):
                    object_name = prop.value.get('object_name')
                    class_package = prop.value.get('class_package', '')
                    if class_package:
                        parent_class = f"{class_package}.{object_name}"
                    else:
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
                            parent_class = object_name
            break

    if not parent_class and hasattr(export, 'super_index'):
        if linker is not None:
            from uasset_read.serializers.object_resources import resolve_parent_class_with_linker as _rpc
            parent_name, warn = _rpc(export.super_index, linker)
        else:
            from uasset_read.serializers.object_resources import resolve_parent_class as _rpc
            parent_name, warn = _rpc(export.super_index, import_map, export_map)
        if parent_name:
            parent_class = parent_name

    if parent_class:
        obj_name = getattr(export, 'object_name', '') or ''
        bp_name = obj_name.replace('_C', '').replace('Default__', '')
        if bp_name and bp_name in parent_class:
            parent_class = None

    functions_bpgc = extract_functions_from_bpgc_properties(properties) if properties else []
    functions_graph = extract_functions_from_graphs(graphs) if graphs else []
    functions = deduplicate_functions(functions_bpgc, functions_graph)
    events = build_events_from_functions(functions)

    meta = BlueprintMetadata(
        is_blueprint=True,
        parent_class=parent_class,
        variables=variables,
        functions=functions,
        events=events,
    )
    return meta, None


def parse_property_flags_to_labels(flags: int) -> List[str]:
    """将 CPF_* 位标志转换为可读标签列表。"""
    labels = []

    if flags & CPF_Edit:
        if flags & CPF_EditConst:
            labels.append("EditConst")
        else:
            labels.append("EditAnywhere")

    if flags & CPF_BlueprintVisible:
        if flags & CPF_BlueprintReadOnly:
            labels.append("BlueprintReadOnly")
        else:
            labels.append("BlueprintReadWrite")

    if flags & CPF_InstancedReference:
        labels.append("InstancedReference")

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
    """从 blueprint export 读取 FBPVariableDescription。"""
    var = BlueprintVariable(
        var_name=archive.read_name(name_map)
    )

    var.var_guid = _read_guid(archive)

    var.var_type = read_ed_graph_pin_type(archive, name_map, summary)

    var.friendly_name = archive.read_fstring()

    from . import _ftext
    var.category = _ftext.read_ftext(archive, summary)

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

    var.flags_labels = parse_property_flags_to_labels(var.property_flags)

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

    var.edit_condition = var.metadata.get('EditCondition', '')
    var.meta_class = var.metadata.get('MetaClass', '')
    var.edit_category = var.metadata.get('Category', '')
    var.edit_widget = var.metadata.get('EditWidget', '')

    default_str = archive.read_fstring()
    var.default_value = parse_default_value(default_str, var.var_type)

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
