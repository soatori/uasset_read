"""
uasset_read - Unreal Engine .uasset 文件解析器

模块化重构版本 v5.1 — src layout，零依赖，分层架构

公共API通过__all__控制，初始阶段导出常量和异常类。
"""
__version__ = "5.1.0"

# 导出常量模块
from .constants import (
    PACKAGE_FILE_TAG,
    PACKAGE_FILE_TAG_SWAPPED,
    UE5_VERSION_MIN,
    LEGACY_FILE_VERSION_MIN,
    LEGACY_FILE_VERSION_MAX,
    MAX_NAME_COUNT,
    MAX_IMPORT_COUNT,
    MAX_EXPORT_COUNT,
    MAX_CUSTOM_VERSIONS,
    MMAP_THRESHOLD,
    MAX_PROPERTY_COUNT,
    PROPERTY_TAG_COMPLETE_TYPE_NAME,
    # 图解析边界常量（Phase 31）
    MAX_PINS_PER_NODE,
    MAX_NODES_PER_GRAPH,
    MAX_LINKEDTO_PER_PIN,
    # PropertyTag 标志（Phase 30）
    PROP_TAG_NONE,
    PROP_TAG_HAS_ARRAY_INDEX,
    PROP_TAG_HAS_PROPERTY_GUID,
    PROP_TAG_HAS_EXTENSIONS,
    PROP_TAG_HAS_BINARY_OR_NATIVE,
    PROP_TAG_BOOL_TRUE,
    PROP_TAG_SKIPPED_SERIALIZE,
    # 版本阈值
    VER_UE4_STRUCT_GUID_IN_PROPERTY_TAG,
    VER_UE4_PROPERTY_GUID_IN_PROPERTY_TAG,
    # 控制流/事件类型集合
    CONTROL_FLOW_NODES,
    START_EVENT_TYPES,
    BRANCH_TYPE_MAP,
    # Package Flags
    PKG_Cooked,
    PKG_UnversionedProperties,
    PKG_FilterEditorOnly,
    # UE5 版本常量
    UE5_SCRIPT_SERIALIZATION_OFFSET,
    UE5_PROPERTY_TAG_EXTENSION,
    UE5_PROPERTY_TAG_COMPLETE_TYPE_NAME,
    UE5_REMOVE_OBJECT_EXPORT_PACKAGE_GUID,
    UE5_TRACK_OBJECT_EXPORT_IS_INHERITED,
    UE5_OPTIONAL_RESOURCES,
    UE5_NAMES_REFERENCED_FROM_EXPORT_DATA,
    UE5_PAYLOAD_TOC,
    UE5_LARGE_WORLD_COORDINATES,
    UE5_FSOFTOBJECTPATH_REMOVE_ASSET_PATH_FNAMES,
    UE5_ADD_SOFTOBJECTPATH_LIST,
    UE5_DATA_RESOURCES,
    UE5_ASSETREGISTRY_PACKAGEBUILDDEPENDENCIES,
    UE5_METADATA_SERIALIZATION_OFFSET,
    UE5_VERSE_CELLS,
    UE5_PACKAGE_SAVED_HASH,
    UE5_OS_SUB_OBJECT_SHADOW_SERIALIZATION,
    UE5_IMPORT_TYPE_HIERARCHIES,
    # FrameworkObjectVersion
    FFRAMEWORK_OBJECT_VERSION_GUID,
    FFRAMEWORK_VERSION_ED_GRAPH_PIN_CONTAINER_TYPE,
    FFRAMEWORK_VERSION_PINS_STORE_FNAME,
    # UE5MainStreamVersion
    FUE5_MAINSTREAM_VERSION_GUID,
    FUE5_MAINSTREAM_VERSION_ED_GRAPH_PIN_SOURCE_INDEX,
    # ReleaseObjectVersion
    FRELEASE_OBJECT_VERSION_GUID,
    FRELEASE_VERSION_PIN_TYPE_UOBJECT_WRAPPER,
    # 辅助函数
    use_complete_type_name,
    # 输出配置
    FORMAT_CONFIG,
    # 导出其他常用常量（后续阶段按需添加）
)

# 导出异常类
from .exceptions import (
    UAssetError,
    VersionError,
    ErrorContext,
    ParseError,
)

# 导出 FArchive（二进制读取器）
from .archive import FArchive

# 导出序列化模块（Phase 28）
from .serializers import (
    PackageFileSummary, PackageIndex, ObjectImport, ObjectExport,
    EngineVersion, CustomVersion, GenerationInfo,
    read_package_summary, read_name_table,
    read_import_map, read_export_map, detect_blueprint,
    # 辅助函数
    build_imports_list,
    get_asset_class,
    resolve_class_name,
    detect_blueprint_generated_class,
    detect_circular_deps,
    # 图序列化（Phase 31）
    read_ue_graph, read_ue_graph_node, read_ue_graph_pin,
    read_ed_graph_pin_type, read_fmember_reference,
    create_node_from_archive,
    # 节点类型读取器（Phase 31）
    read_k2node_call_function,
    read_k2node_event,
    read_k2node_knot,
    read_edgraph_node_comment,
    read_k2node_enhanced_input,
)

# 导出核心数据模型（Phase 29）
from .models import (
    # 核心模型
    FEdGraphPinType,
    UEdGraphPin,
    UEdGraphNode,
    UEdGraph,
    FMemberReference,
    # 节点类型
    K2NodeCallFunction,
    K2NodeEvent,
    K2NodeKnot,
    EdGraphNodeComment,
    K2NodeEnhancedInputAction,
    # 结果
    ParseResult,
    StatusInfo,
    # 蓝图元数据
    BlueprintMetadata,
    BlueprintVariable,
    BlueprintFunction,
    BlueprintEvent,
    FunctionParameter,
    MulticastDelegate,
)

# 属性数据模型（Phase 30）
from .models import (
    PropertyTag,
    PropertyValue,
    AdvancedPropertyValue,
    StructValue,
    MapValue,
    SetValue,
    EnumValue,
    TextValue,
    DelegateValue,
)

# 解析器模块（Phase 30）
from .parsers import (
    parse_property_value,
    parse_properties_from_export,
    parse_bool_property,
    parse_int_property,
    parse_float_property,
    parse_str_property,
    parse_name_property,
    parse_object_property,
    parse_soft_object_property,
    parse_array_property,
    parse_struct_property,
    parse_map_property,
    parse_set_property,
    parse_enum_property,
    parse_text_property,
    parse_delegate_property,
    # 辅助函数（测试依赖）
    _extract_struct_type_from_tag,
    _extract_map_types_from_tag,
    _extract_set_type_from_tag,
    _extract_enum_type_from_tag,
)

# 蓝图模块（Phase 30）
from .blueprint import (
    extract_blueprint_variables,
    parse_component_transform,
    extract_blueprint_metadata,
)

# 图解析模块（Phase 31 Wave 3）
from .graph import (
    extract_blueprint_graphs,
    build_execution_flows,
    build_data_flows,
    build_connections_map,
    build_graphs_summary,
    format_graphs_json,
)

# 格式化模块（Phase 32 Wave 1-2）
from .formatters import (
    # JSON 格式化
    format_json_full,
    format_json_summary,
    format_exports_list,
    format_properties_list,
    format_blueprint_dict,
    # Text 格式化
    format_text_full,
    format_text_summary,
    # Markdown 格式化
    format_markdown,
    _build_mermaid_flowchart,
    # 辅助函数
    build_status_info,
    build_schema_info,
    resolve_fpackage_index,
    # Phase 31 re-export
    format_pin_ref,
    _derive_node_name,
)

# ============================================================================
# 兼容 shim（临时 stub，Phase 33 完成后移除）
# ============================================================================
# 以下函数/类等待 Phase 33 迁移：
# - parse_uasset → Phase 33（入口适配）
# - resolve_parent_class → Phase 33
# - VectorValue/RotatorValue → Phase 30 扩展（遗留）
# - format_variable_type → Phase 32 Wave 2 迁移到 helpers.py

# ============================================================================
# 兼容 shim（临时，Phase 33 完成后移除）
# 从旧版 uasset_read_legacy.py 重导出尚未迁移到 src/ 的函数
# ============================================================================
import importlib.util as _iu
import pathlib as _p
_legacy_path = _p.Path(__file__).parent.parent.parent / "uasset_read_legacy.py"
if _legacy_path.exists():
    _spec = _iu.spec_from_file_location("_legacy_uasset", _legacy_path)
    _legacy = _iu.module_from_spec(_spec)
    import sys as _sys
    _sys.modules["_legacy_uasset"] = _legacy
    _spec.loader.exec_module(_legacy)

    parse_uasset = _legacy.parse_uasset
    resolve_parent_class = _legacy.resolve_parent_class
    resolve_package_index_to_reference = _legacy.resolve_package_index_to_reference
    read_soft_object_paths = _legacy.read_soft_object_paths
    find_main_blueprint_generated_class = _legacy.find_main_blueprint_generated_class
    parse_property_flags_to_labels = _legacy.parse_property_flags_to_labels
    CPF_Edit = _legacy.CPF_Edit
    CPF_InstancedReference = _legacy.CPF_InstancedReference
    CPF_BlueprintVisible = _legacy.CPF_BlueprintVisible
    CPF_EditAnywhere = _legacy.CPF_EditAnywhere
    CPF_EditInstanceOnly = _legacy.CPF_EditInstanceOnly
    CPF_BlueprintReadWrite = _legacy.CPF_BlueprintReadWrite
    CPF_BlueprintReadOnly = _legacy.CPF_BlueprintReadOnly
    CPF_Transient = _legacy.CPF_Transient
    CPF_SaveGame = _legacy.CPF_SaveGame
    CPF_ExposeOnSpawn = _legacy.CPF_ExposeOnSpawn

    # Legacy shim compatibility: FEdGraphPinType field name migration
    # Old: pin_sub_category, pin_sub_category_object, is_weak_pointer, is_const
    # New: pin_subcategory, pin_subcategory_object, is_weak_pointer (removed is_const)
    def _make_format_variable_type_compatible(legacy_func):
        """Create compatibility wrapper for format_variable_type with new FEdGraphPinType dataclass"""
        def _format_variable_type_compatible(pin_type, name_map=None):
            """Compatibility wrapper for format_variable_type with new FEdGraphPinType dataclass"""
            # Handle both old FEdGraphPinType (dict-like) and new dataclass
            # New FEdGraphPinType has: pin_category, pin_subcategory, pin_subcategory_object, is_weak_pointer
            # Old FEdGraphPinType has: pin_category, pin_sub_category, pin_sub_category_object, is_weak_pointer, is_const

            # Create a compatibility shim that normalizes field access
            class _CompatPinType:
                def __init__(self, pt):
                    self._pt = pt

                @property
                def pin_category(self):
                    return getattr(self._pt, 'pin_category', '')

                @property
                def pin_sub_category(self):
                    # Try new name first (v6.0), fall back to old name
                    return getattr(self._pt, 'pin_subcategory',
                                 getattr(self._pt, 'pin_sub_category', ''))

                @property
                def pin_sub_category_object(self):
                    # Try new name first (v6.0), fall back to old name
                    return getattr(self._pt, 'pin_subcategory_object',
                                 getattr(self._pt, 'pin_sub_category_object', 0))

                @property
                def is_weak_pointer(self):
                    return getattr(self._pt, 'is_weak_pointer', False)

                @property
                def is_const(self):
                    # is_const removed in v6.0 - always return False
                    return False

                @property
                def container_type(self):
                    return getattr(self._pt, 'container_type', 0)

            compat_pin_type = _CompatPinType(pin_type)
            return legacy_func(compat_pin_type, name_map)

        return _format_variable_type_compatible

    format_variable_type = _make_format_variable_type_compatible(_legacy.format_variable_type)
    VectorValue = _legacy.VectorValue
    RotatorValue = _legacy.RotatorValue
    ScaleValue = _legacy.ScaleValue
    TransformValue = getattr(_legacy, "TransformValue", None)  # type: ignore
    parse_default_value = _legacy.parse_default_value
    parse_vector_value = _legacy.parse_vector_value
    parse_rotator_value = _legacy.parse_rotator_value
    parse_scale_value = _legacy.parse_scale_value
    format_transform_value = _legacy.format_transform_value
    read_blueprint_variable = _legacy.read_blueprint_variable
    read_property_tag = _legacy.read_property_tag
    extract_component_transforms = _legacy.extract_component_transforms
    del _iu, _p, _legacy_path, _spec, _legacy, _sys
else:
    # 旧文件已删除时的降级处理
    parse_uasset = None  # type: ignore
    resolve_parent_class = None  # type: ignore
    resolve_package_index_to_reference = None  # type: ignore
    read_soft_object_paths = None  # type: ignore
    find_main_blueprint_generated_class = None  # type: ignore
    parse_property_flags_to_labels = None  # type: ignore
    CPF_Edit = 0x0000000000000001
    CPF_InstancedReference = 0x0000000000080000
    CPF_BlueprintVisible = 0x0000000000000004
    CPF_EditAnywhere = 0x02000000
    CPF_EditInstanceOnly = 0x04000000
    CPF_BlueprintReadWrite = 0x00000100
    CPF_BlueprintReadOnly = 0x0000000000000010
    CPF_Transient = 0x0000000000002000
    CPF_SaveGame = 0x0000000001000000
    CPF_ExposeOnSpawn = 0x0001000000000000
    format_variable_type = None  # type: ignore
    VectorValue = None  # type: ignore
    RotatorValue = None  # type: ignore
    ScaleValue = None  # type: ignore
    TransformValue = None  # type: ignore
    parse_default_value = None
    parse_vector_value = None  # type: ignore
    parse_rotator_value = None  # type: ignore
    parse_scale_value = None  # type: ignore
    format_transform_value = None  # type: ignore
    read_blueprint_variable = None  # type: ignore
    read_property_tag = None  # type: ignore
    extract_component_transforms = None  # type: ignore

# 公共API导出控制（per D-09）
__all__ = [
    # 版本号
    "__version__",
    # 常量（基础）
    "PACKAGE_FILE_TAG",
    "PACKAGE_FILE_TAG_SWAPPED",
    "UE5_VERSION_MIN",
    "LEGACY_FILE_VERSION_MIN",
    "LEGACY_FILE_VERSION_MAX",
    "MAX_NAME_COUNT",
    "MAX_IMPORT_COUNT",
    "MAX_EXPORT_COUNT",
    "MAX_CUSTOM_VERSIONS",
    "MMAP_THRESHOLD",
    "MAX_PROPERTY_COUNT",
    "PROPERTY_TAG_COMPLETE_TYPE_NAME",
    # 常量（图解析边界）
    "MAX_PINS_PER_NODE",
    "MAX_NODES_PER_GRAPH",
    "MAX_LINKEDTO_PER_PIN",
    # 常量（PropertyTag 标志）
    "PROP_TAG_NONE",
    "PROP_TAG_HAS_ARRAY_INDEX",
    "PROP_TAG_HAS_PROPERTY_GUID",
    "PROP_TAG_HAS_EXTENSIONS",
    "PROP_TAG_HAS_BINARY_OR_NATIVE",
    "PROP_TAG_BOOL_TRUE",
    "PROP_TAG_SKIPPED_SERIALIZE",
    # 常量（版本阈值）
    "VER_UE4_STRUCT_GUID_IN_PROPERTY_TAG",
    "VER_UE4_PROPERTY_GUID_IN_PROPERTY_TAG",
    # 常量（控制流/事件类型集合）
    "CONTROL_FLOW_NODES",
    "START_EVENT_TYPES",
    "BRANCH_TYPE_MAP",
    # 常量（Package Flags）
    "PKG_Cooked",
    "PKG_UnversionedProperties",
    "PKG_FilterEditorOnly",
    # 常量（UE5 版本）
    "UE5_SCRIPT_SERIALIZATION_OFFSET",
    "UE5_PROPERTY_TAG_EXTENSION",
    "UE5_PROPERTY_TAG_COMPLETE_TYPE_NAME",
    "UE5_REMOVE_OBJECT_EXPORT_PACKAGE_GUID",
    "UE5_TRACK_OBJECT_EXPORT_IS_INHERITED",
    "UE5_OPTIONAL_RESOURCES",
    "UE5_NAMES_REFERENCED_FROM_EXPORT_DATA",
    "UE5_PAYLOAD_TOC",
    "UE5_LARGE_WORLD_COORDINATES",
    "UE5_FSOFTOBJECTPATH_REMOVE_ASSET_PATH_FNAMES",
    "UE5_ADD_SOFTOBJECTPATH_LIST",
    "UE5_DATA_RESOURCES",
    "UE5_ASSETREGISTRY_PACKAGEBUILDDEPENDENCIES",
    "UE5_METADATA_SERIALIZATION_OFFSET",
    "UE5_VERSE_CELLS",
    "UE5_PACKAGE_SAVED_HASH",
    "UE5_OS_SUB_OBJECT_SHADOW_SERIALIZATION",
    "UE5_IMPORT_TYPE_HIERARCHIES",
    # 常量（Framework/UE5MainStream/Release Version）
    "FFRAMEWORK_OBJECT_VERSION_GUID",
    "FFRAMEWORK_VERSION_ED_GRAPH_PIN_CONTAINER_TYPE",
    "FFRAMEWORK_VERSION_PINS_STORE_FNAME",
    "FUE5_MAINSTREAM_VERSION_GUID",
    "FUE5_MAINSTREAM_VERSION_ED_GRAPH_PIN_SOURCE_INDEX",
    "FRELEASE_OBJECT_VERSION_GUID",
    "FRELEASE_VERSION_PIN_TYPE_UOBJECT_WRAPPER",
    # 常量（辅助函数）
    "use_complete_type_name",
    # 输出配置
    "FORMAT_CONFIG",
    # 异常类
    "UAssetError",
    "VersionError",
    "ErrorContext",
    "ParseError",
    # FArchive
    "FArchive",
    # 序列化模块（Phase 28）
    "PackageFileSummary", "PackageIndex", "ObjectImport", "ObjectExport",
    "EngineVersion", "CustomVersion", "GenerationInfo",
    "read_package_summary", "read_name_table",
    "read_import_map", "read_export_map", "detect_blueprint",
    "build_imports_list", "get_asset_class", "resolve_class_name",
    "detect_blueprint_generated_class", "detect_circular_deps",
    # 图序列化（Phase 31）
    "read_ue_graph", "read_ue_graph_node", "read_ue_graph_pin",
    "read_ed_graph_pin_type", "read_fmember_reference", "create_node_from_archive",
    # 核心数据模型（Phase 29）
    "FEdGraphPinType",
    "UEdGraphPin",
    "UEdGraphNode",
    "UEdGraph",
    "FMemberReference",
    # 节点类型（Phase 29）
    "K2NodeCallFunction",
    "K2NodeEvent",
    "K2NodeKnot",
    "EdGraphNodeComment",
    "K2NodeEnhancedInputAction",
    # 结果（Phase 29）
    "ParseResult",
    "StatusInfo",
    # 蓝图元数据（Phase 29）
    "BlueprintMetadata",
    "BlueprintVariable",
    "BlueprintFunction",
    "BlueprintEvent",
    "FunctionParameter",
    "MulticastDelegate",
    # 属性数据模型（Phase 30）
    "PropertyTag",
    "PropertyValue",
    "AdvancedPropertyValue",
    "StructValue",
    "MapValue",
    "SetValue",
    "EnumValue",
    "TextValue",
    "DelegateValue",
    # 解析器模块（Phase 30）
    "parse_property_value",
    "parse_properties_from_export",
    "parse_bool_property",
    "parse_int_property",
    "parse_float_property",
    "parse_str_property",
    "parse_name_property",
    "parse_object_property",
    "parse_soft_object_property",
    "parse_array_property",
    "parse_struct_property",
    "parse_map_property",
    "parse_set_property",
    "parse_enum_property",
    "parse_text_property",
    "parse_delegate_property",
    # 辅助函数（测试依赖）
    "_extract_struct_type_from_tag",
    "_extract_map_types_from_tag",
    "_extract_set_type_from_tag",
    "_extract_enum_type_from_tag",
    # 蓝图模块（Phase 30）
    "extract_blueprint_variables",
    "parse_component_transform",
    "extract_blueprint_metadata",
    # 兼容 shim（临时导出，Phase 31-34 完成后移除）
    "parse_uasset",
    "resolve_parent_class",
    "resolve_package_index_to_reference",
    "extract_blueprint_graphs",
    "read_soft_object_paths",
    "find_main_blueprint_generated_class",
    "parse_property_flags_to_labels",
    # 格式化模块（Phase 32）
    "build_status_info",
    "build_execution_flows",
    "build_connections_map",
    "build_graphs_summary",
    "format_json_full",
    "format_json_summary",
    "format_exports_list",
    "format_properties_list",
    "format_blueprint_dict",
    "format_text_summary",
    "format_text_full",
    "format_markdown",
    "_build_mermaid_flowchart",
    "format_variable_type",
    "format_graphs_json",
    "resolve_fpackage_index",
    "format_pin_ref",
    "_derive_node_name",
    "build_schema_info",
    # 兼容 shim（遗留类型）
    "VectorValue",
    "RotatorValue",
    "ScaleValue",
    "TransformValue",
    "CPF_Edit",
    "CPF_InstancedReference",
    "CPF_BlueprintVisible",
    "CPF_EditAnywhere",
    "CPF_EditInstanceOnly",
    "CPF_BlueprintReadWrite",
    "CPF_BlueprintReadOnly",
    "CPF_Transient",
    "CPF_SaveGame",
    "CPF_ExposeOnSpawn",
    "parse_default_value",
    "parse_vector_value",
    "parse_rotator_value",
    "parse_scale_value",
    "format_transform_value",
    "read_blueprint_variable",
    "read_property_tag",
    "extract_component_transforms",
    # 节点类型读取器（测试依赖）
    "read_k2node_call_function",
    "read_k2node_event",
    "read_k2node_knot",
    "read_edgraph_node_comment",
    "read_k2node_enhanced_input",
]
