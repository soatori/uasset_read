"""
uasset_read - Unreal Engine .uasset 文件解析器

版本 dev-0.3.0 — CUE4Parse 核心对齐 (v14, Phase 76)

公共API通过__all__控制，初始阶段导出常量和异常类。
"""
__version__ = "dev-0.3.1"

# 导出常量模块
from .constants import (
    PACKAGE_FILE_TAG,
    PACKAGE_FILE_TAG_SWAPPED,
    UE5_VERSION_MIN,
    UE5_LEGACY_VERSION,
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
    read_k2node_functionentry,
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
    K2NodeFunctionEntry,
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
    # 新增属性类型解析函数
    parse_uint16_property,
    parse_uint32_property,
    parse_uint64_property,
    parse_utf8_str_property,
    parse_weak_object_property,
    parse_lazy_object_property,
    parse_class_property,
    parse_soft_class_property,
    parse_asset_object_property,
    parse_multicast_delegate_property,
    parse_multicast_inline_delegate_property,
    parse_multicast_sparse_delegate_property,
    parse_interface_property,
    parse_field_path_property,
    parse_optional_property,
    parse_verse_string_property,
    parse_verse_class_property,
    parse_verse_function_property,
    parse_verse_dynamic_property,
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

# 图解析模块（Phase 31 Wave 3, Phase 71）
from .graph import (
    extract_blueprint_graphs,
    build_execution_flows,
    build_data_flows,
    build_connections_map,
    build_graphs_summary,
    format_graphs_json,
    build_execution_chains,  # Phase 71
    format_pin_ref,
    _derive_node_name,
    build_execution_chains_from_flows,  # Phase 71 (N2C compat)
    write_pin_trace_report,
)

# 格式化模块（Phase 32 Wave 1-2）
# 主解析管线（Phase 33）
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
    # Blueprint 翻译参考文本
    format_blueprint_translation_text,
    format_blueprint_ue_text,
    # 辅助函数
    build_status_info,
    build_schema_info,
    resolve_fpackage_index,
)
# ============================================================================
from .parse_uasset import parse_uasset, parse_uasset_with_linker

# 变换数据类（Phase 33）
from .models.transforms import (
    VectorValue, RotatorValue, ScaleValue, format_transform_value,
)

# 辅助函数（Phase 33）
from .serializers.object_resources import (
    find_main_blueprint_generated_class,
    resolve_parent_class,
    resolve_class_name_with_linker,
    get_asset_class_with_linker,
    detect_blueprint_with_linker,
    resolve_parent_class_with_linker,
    read_soft_object_paths,
)
from .blueprint.transform_parser import (
    extract_component_transforms,
    parse_vector_value,
    parse_rotator_value,
    parse_scale_value,
    format_transform_value as _format_transform_value,
)
from .serializers.property_tags import read_property_tag, parse_ctrl_flags, parse_ue511_ctrl_flags
from .parsers.property_types import parse_default_value, format_variable_type
from .blueprint.variable_extractor import read_blueprint_variable, parse_property_flags_to_labels
from .constants import (
    CPF_Edit, CPF_BlueprintVisible, CPF_InstancedReference, CPF_EditAnywhere,
    CPF_EditInstanceOnly, CPF_BlueprintReadWrite, CPF_BlueprintReadOnly,
    CPF_Transient, CPF_SaveGame, CPF_ExposeOnSpawn,
)

# Kismet bytecode module (Phase 61)
from .kismet import (
    EExprToken, ECastToken, EScriptInstrumentationType,
    EBlueprintTextLiteralType, EAutoRtfmStopTransactMode,
    KismetExpression, KismetExpressionT,
    EXPR_CLASS_MAP,
    FKismetPropertyPointer, FFieldPath,
)

# Kismet C++ translator (Phase 63)
from .kismet import (
    KismetTranslator,
    MathFunctionCleaner,
    TypeRegistry,
    line_cpp,
    UE_TYPE_MAP,
    FunctionBodyBuilder,
    to_function_body,
    StructuredControlFlow,
    StructuredBlock,
)

# Kismet bytecode extractor (Phase 62)
from .kismet import (
    extract_bytecode_bytes,
    parse_bytecode_stream,
    extract_and_parse,
)

# Kismet decompilation pipeline (Phase 64)
from .kismet.result import KismetDecompiledResult
from .kismet.pipeline import decompile_uasset

# Agent translation pipeline (Phase 66)
from .agent.translator import AgentTranslationPipeline, translate_blueprint_to_cpp
from .agent.writer import CppFileWriter, write_cpp_class_files

# N2C intermediate format (Phase 70)
from .n2c import (
    N2CStruct, N2CGraph, N2CNode, N2CPin, N2CIdMapper,
    to_n2c_json, from_n2c_json,
    N2C_JSON_SCHEMA, validate_n2c_json,
)

# Export system (Phase Export)
from .exporter import (
    ExportOptions,
    IExporter,
    ExportValidationError,
    ExporterRegistry,
    export,
    BatchExporter,
    BatchExportResult,
)

# C++ code gen (Phase 56-58)
from .cpp_gen import (
    CppProperty, CppHeaderMeta, CppClassIR,
    format_cpp_class_json, format_cpp_header,
)

# Version management (Phase 76, COR-02)
from .versioning import (
    VersionContainer, build_version_container, EUEVersion,
)

# 以下函数等待后续 plan 完成后追加：
# read_property_tag, read_blueprint_variable,
# parse_property_flags_to_labels, parse_default_value,
# read_k2node_call_function, read_k2node_event, read_k2node_knot,
# read_edgraph_node_comment, read_k2node_enhanced_input
# 注：read_k2node_* 已在 serializers import 中导出

# 公共API导出控制（per D-09）
__all__ = [
    # 版本号
    "__version__",
    # 常量（基础）
    "PACKAGE_FILE_TAG",
    "PACKAGE_FILE_TAG_SWAPPED",
    "UE5_VERSION_MIN",
    "UE5_LEGACY_VERSION",
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
    # 常量（输出配置）
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
    "K2NodeFunctionEntry",
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
    # 新增属性类型解析函数
    "parse_uint16_property",
    "parse_uint32_property",
    "parse_uint64_property",
    "parse_utf8_str_property",
    "parse_weak_object_property",
    "parse_lazy_object_property",
    "parse_class_property",
    "parse_soft_class_property",
    "parse_asset_object_property",
    "parse_multicast_delegate_property",
    "parse_multicast_inline_delegate_property",
    "parse_multicast_sparse_delegate_property",
    "parse_interface_property",
    "parse_field_path_property",
    "parse_optional_property",
    "parse_verse_string_property",
    "parse_verse_class_property",
    "parse_verse_function_property",
    "parse_verse_dynamic_property",
    # 辅助函数（测试依赖）
    "_extract_struct_type_from_tag",
    "_extract_map_types_from_tag",
    "_extract_set_type_from_tag",
    "_extract_enum_type_from_tag",
    # 蓝图模块（Phase 30）
    "extract_blueprint_variables",
    "parse_component_transform",
    "extract_blueprint_metadata",
    # 主解析管线（Phase 33）
    "parse_uasset",
    "parse_uasset_with_linker",
    # 图解析辅助函数（Phase 33 — 依赖 Phase 31, Phase 71）
    "extract_blueprint_graphs",
    "build_execution_flows",
    "build_data_flows",
    "build_connections_map",
    "build_graphs_summary",
    "build_execution_chains",  # Phase 71
    "build_execution_chains_from_flows",  # Phase 71
    "write_pin_trace_report",
    # 格式化函数（Phase 33 — 依赖 Phase 32）
    "format_json_full",
    "format_json_summary",
    "format_exports_list",
    "format_properties_list",
    "format_blueprint_dict",
    "format_text_summary",
    "format_text_full",
    "format_markdown",
    "format_blueprint_translation_text",
    "format_blueprint_ue_text",
    "format_graphs_json",
    "build_schema_info",
    "resolve_fpackage_index",
    "format_pin_ref",
    "_derive_node_name",
    "_build_mermaid_flowchart",
    "build_status_info",
    # 辅助函数（Phase 33）
    "find_main_blueprint_generated_class",
    "resolve_parent_class",
    "resolve_class_name_with_linker",
    "get_asset_class_with_linker",
    "detect_blueprint_with_linker",
    "resolve_parent_class_with_linker",
    "read_soft_object_paths",
    "extract_component_transforms",
    "parse_vector_value",
    "parse_rotator_value",
    "parse_scale_value",
    "format_transform_value",
    "read_property_tag",
    "parse_ctrl_flags",
    "parse_ue511_ctrl_flags",
    "parse_property_flags_to_labels",
    "parse_default_value",
    "read_blueprint_variable",
    "format_variable_type",
    # CPF 常量（Phase 33）
    "CPF_Edit",
    "CPF_BlueprintVisible",
    "CPF_InstancedReference",
    "CPF_EditAnywhere",
    "CPF_EditInstanceOnly",
    "CPF_BlueprintReadWrite",
    "CPF_BlueprintReadOnly",
    "CPF_Transient",
    "CPF_SaveGame",
    "CPF_ExposeOnSpawn",
    # 变换数据类（Phase 33）
    "VectorValue",
    "RotatorValue",
    "ScaleValue",
    # 节点类型读取器（Phase 31 / 测试依赖）
    "read_k2node_call_function",
    "read_k2node_event",
    "read_k2node_knot",
    "read_edgraph_node_comment",
    "read_k2node_enhanced_input",
    "read_k2node_functionentry",
    # Kismet bytecode (Phase 61)
    "EExprToken",
    "ECastToken",
    "EScriptInstrumentationType",
    "EBlueprintTextLiteralType",
    "EAutoRtfmStopTransactMode",
    "KismetExpression",
    "KismetExpressionT",
    "EXPR_CLASS_MAP",
    "FKismetPropertyPointer",
    "FFieldPath",
    # Kismet translator (Phase 63)
    "KismetTranslator",
    "MathFunctionCleaner",
    "TypeRegistry",
    "line_cpp",
    "UE_TYPE_MAP",
    "FunctionBodyBuilder",
    "to_function_body",
    "StructuredControlFlow",
    "StructuredBlock",
    # Kismet bytecode extractor (Phase 62)
    "extract_bytecode_bytes",
    "parse_bytecode_stream",
    "extract_and_parse",
    # Kismet decompilation pipeline (Phase 64)
    "KismetDecompiledResult",
    "decompile_uasset",
    # Agent translation pipeline (Phase 66)
    "AgentTranslationPipeline",
    "translate_blueprint_to_cpp",
    "CppFileWriter",
    "write_cpp_class_files",
    # N2C intermediate format (Phase 70)
    "N2CStruct",
    "N2CGraph",
    "N2CNode",
    "N2CPin",
    "N2CIdMapper",
    "to_n2c_json",
    "from_n2c_json",
    "N2C_JSON_SCHEMA",
    "validate_n2c_json",
    # Export system (Phase Export)
    "ExportOptions",
    "IExporter",
    "ExportValidationError",
    "ExporterRegistry",
    "export",
    "BatchExporter",
    "BatchExportResult",
    # C++ code gen
    "CppProperty",
    "CppHeaderMeta",
    "CppClassIR",
    "format_cpp_class_json",
    "format_cpp_header",
    # Version management (Phase 76)
    "VersionContainer",
    "build_version_container",
    "EUEVersion",
]
