"""
uasset_read - Unreal Engine .uasset 文件解析器

版本 0.5.1.19

公共API通过__all__控制。
"""
__version__ = "0.5.1.19"

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
    # 图解析边界常量
    MAX_PINS_PER_NODE,
    MAX_NODES_PER_GRAPH,
    MAX_LINKEDTO_PER_PIN,
    # PropertyTag 标志
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
    # Package Flags (EPackageFlags)
    PKG_None,
    PKG_NewlyCreated,
    PKG_ClientOptional,
    PKG_ServerSideOnly,
    PKG_CompiledIn,
    PKG_ForDiffing,
    PKG_EditorOnly,
    PKG_Developer,
    PKG_UncookedOnly,
    PKG_Cooked,
    PKG_ContainsNoAsset,
    PKG_NotExternallyReferenceable,
    PKG_AccessSpecifierEpicInternal,
    PKG_UnversionedProperties,
    PKG_ContainsMapData,
    PKG_IsSaving,
    PKG_Compiling,
    PKG_ContainsMap,
    PKG_RequiresLocalizationGather,
    PKG_LoadUncooked,
    PKG_PlayInEditor,
    PKG_ContainsScript,
    PKG_DisallowExport,
    PKG_CookGenerated,
    PKG_DynamicImports,
    PKG_RuntimeGenerated,
    PKG_ReloadingForCooker,
    PKG_FilterEditorOnly,
    PKG_TransientFlags,
    PKG_InMemoryOnly,
    decode_package_flags,
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

# 导出序列化模块
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
    validate_package_index,
    # 图序列化
    read_ue_graph, read_ue_graph_node, read_ue_graph_pin,
    read_ed_graph_pin_type, read_fmember_reference,
    create_node_from_archive,
    # 节点类型读取器
    read_k2node_call_function,
    read_k2node_event,
    read_k2node_knot,
    read_edgraph_node_comment,
    read_k2node_enhanced_input,
    read_k2node_functionentry,
)

# 导出核心数据模型
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

from .mappings import (
    TypeMappingsProvider,
    UsmapParser,
    JmapParser,
    TypeMappings,
    StructMapping,
    PropertyType,
    PropertyInfo,
)

# 属性数据模型
from .models import (
    PropertyTag,
    PropertyTypeName,
    PropertyValue,
    SoftObjectPathValue,
    AdvancedPropertyValue,
    StructValue,
    MapValue,
    SetValue,
    EnumValue,
    TextValue,
    DelegateValue,
)

# Fallback 模型
from .models import (
    PropertyFallback,
    StructFallback,
    GenericUObject,
    ExportParseStatus,
    FallbackReason,
    OffsetRangeDiagnostic,
)

# Class Handler Registry
from .parsers.class_registry import (
    ClassHandlerRegistry,
    ClassHandler,
    HandlerResult,
    FallbackPolicy,
    get_class_registry,
)

# 解析器模块
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
    parse_verse_cell_property,
    parse_verse_value_property,
    parse_ansi_str_property,
    parse_double_property,
    parse_guid_property,
    # CustomProperty 注册表
    CUSTOM_PROPERTY_HANDLERS,
    CustomPropertyContext,
    register_custom_property,
    handle_custom_property,
    # 辅助函数（测试依赖）
    get_struct_size,
    _extract_struct_type_from_tag,
    _extract_map_types_from_tag,
    _extract_set_type_from_tag,
    _extract_enum_type_from_tag,
    # 共享辅助函数（parsers/utils.py）
    resolve_name_from_index,
    read_validated_count,
    make_enum_value,
    extract_inner_from_tag,
)

# 蓝图模块
from .blueprint import (
    extract_blueprint_variables,
    parse_component_transform,
    extract_blueprint_metadata,
    extract_components,
)

# 图解析模块
from .graph import (
    extract_blueprint_graphs,
    build_execution_flow_entries,
    build_data_flows,
    build_connections_map,
    format_graphs_json,
    build_execution_chains,
    format_pin_ref,
    _derive_node_name,
    build_function_graphs,
)

# Core API (parse_single, parse_batch, list_formats)
from .core import parse_single, parse_batch, list_formats, BatchResult
from .memory_safety import MemoryLimitExceeded, MemoryPolicy, ResourceLimits

# ============================================================================
from .parse_uasset import parse_package, parse_uasset, parse_uasset_with_linker
from .package import (
    PackageBundle,
    PackageProvider,
    FileSystemPackageProvider,
    PakPackageProvider,
    IoStorePackageProvider,
    open_package_bundle,
)
from .raw import (
    RawFileResult,
    parse_raw_file,
    parse_json_descriptor,
    parse_ini_file,
    parse_locres,
    parse_locmeta,
    parse_audio_metadata,
)

# 变换数据类
from .models.transforms import (
    VectorValue, RotatorValue, ScaleValue, format_transform_value,
)

# 辅助函数
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
)
from .serializers.property_tags import read_property_tag, parse_ctrl_flags, parse_ue511_ctrl_flags
from .parsers.property_types import parse_default_value, format_variable_type
from .blueprint.variable_extractor import read_blueprint_variable, parse_property_flags_to_labels
from .constants import (
    CPF_Edit, CPF_BlueprintVisible, CPF_InstancedReference,
    CPF_BlueprintReadOnly,
    CPF_Transient, CPF_SaveGame, CPF_ExposeOnSpawn,
)

# Kismet bytecode module
from .kismet import (
    EExprToken, ECastToken, EScriptInstrumentationType,
    EBlueprintTextLiteralType, EAutoRtfmStopTransactMode,
    KismetExpression, KismetExpressionT,
    EXPR_CLASS_MAP,
    FKismetPropertyPointer, FFieldPath,
    FKismetArchive,
    USTRUCT_TYPES,
    reset_bpgc_cache,
)

# Kismet C++ translator
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

# Kismet bytecode extractor
from .kismet import (
    extract_bytecode_bytes,
    parse_bytecode_stream,
    extract_and_parse,
)

# Kismet decompilation pipeline
from .kismet.result import KismetDecompiledResult
from .kismet.pipeline import decompile_uasset, decompile_single_function

# C++ code gen
from .cpp_gen import (
    CppProperty, CppHeaderMeta, CppClassIR,
    format_cpp_class_json, format_cpp_header,
    UE_TO_CPP_TYPE_MAP, ENGINE_CLASS_PATHS,
    ue_path_to_cpp_type, ue_package_path_to_cpp_class,
    infer_class_prefix, resolve_ue_type,
    CPF_TO_UPROPERTY_MAP, cpf_flags_to_uproperty_marks,
    extract_cpp_class_skeleton, extract_cpp_constructor,
    format_cpp_call_statements, CppCallParameter, CppMethodIR, CppCallStatement,
    CppStatement, CppCallStmt, CppAssignmentStmt, CppIfStmt,
    CppInlineExprStmt, CppReturnStmt, CppWhileStmt, CppRawStmt,
    kismet_to_cpp_body,
    format_cpp_default_value, format_cpp_transform,
    format_cpp_component_init, format_cpp_input_action_load,
    build_constructor_sections, format_cpp_constructor,
    sanitize_identifier,
)

# Version management
from .versioning import (
    VersionContainer, build_version_container, EUEVersion,
)

# Link module -- PackageLinker, UObjectInstance, LinkerParseResult
from .link import (
    PackageLinker, UObjectInstance, LinkerParseResult,
)

# Pak module
from .pak import (
    PAK_FILE_MAGIC, PakFileVersion, ECompressionFlags,
    Flag_Encrypted, Flag_Deleted, MaxNumCompressionMethods, PAK_INFO_SIZES,
    FPakCompressedBlock, FPakEntry, FPakInfo, FPakDirectoryEntry, read_fstring,
    decompress_block, decompress_entry,
    PakFileReader,
)

# IoStore 容器系统
from .iostore import IoStoreReader, FIoChunkId, FIoOffsetAndSize

# Bulk Data
from .bulk import FBulkDataHeader, BulkDataFlags

# UObject 类型体系
from .objects import UObject, ObjectTypeRegistry
from .objects.exports import UStaticMesh, USkeletalMesh, UTexture2D, UMaterial, UMaterialInstance

# 公共API导出控制（per D-09）
__all__ = [
    # 版本号
    "__version__",
    # Core API
    "parse_single",
    "parse_batch",
    "list_formats",
    "BatchResult",
    "MemoryPolicy",
    "ResourceLimits",
    "MemoryLimitExceeded",
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
    "PKG_None",
    "PKG_NewlyCreated",
    "PKG_ClientOptional",
    "PKG_ServerSideOnly",
    "PKG_CompiledIn",
    "PKG_ForDiffing",
    "PKG_EditorOnly",
    "PKG_Developer",
    "PKG_UncookedOnly",
    "PKG_Cooked",
    "PKG_ContainsNoAsset",
    "PKG_NotExternallyReferenceable",
    "PKG_AccessSpecifierEpicInternal",
    "PKG_UnversionedProperties",
    "PKG_ContainsMapData",
    "PKG_IsSaving",
    "PKG_Compiling",
    "PKG_ContainsMap",
    "PKG_RequiresLocalizationGather",
    "PKG_LoadUncooked",
    "PKG_PlayInEditor",
    "PKG_ContainsScript",
    "PKG_DisallowExport",
    "PKG_CookGenerated",
    "PKG_DynamicImports",
    "PKG_RuntimeGenerated",
    "PKG_ReloadingForCooker",
    "PKG_FilterEditorOnly",
    "PKG_TransientFlags",
    "PKG_InMemoryOnly",
    "decode_package_flags",
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
    # 序列化模块
    "PackageFileSummary", "PackageIndex", "ObjectImport", "ObjectExport",
    "EngineVersion", "CustomVersion", "GenerationInfo",
    "read_package_summary", "read_name_table",
    "read_import_map", "read_export_map", "detect_blueprint",
    "build_imports_list", "get_asset_class", "resolve_class_name",
    "detect_blueprint_generated_class", "detect_circular_deps",
    "validate_package_index",
    # 图序列化
    "read_ue_graph", "read_ue_graph_node", "read_ue_graph_pin",
    "read_ed_graph_pin_type", "read_fmember_reference", "create_node_from_archive",
    # 核心数据模型
    "FEdGraphPinType",
    "UEdGraphPin",
    "UEdGraphNode",
    "UEdGraph",
    "FMemberReference",
    # 节点类型
    "K2NodeCallFunction",
    "K2NodeEvent",
    "K2NodeKnot",
    "EdGraphNodeComment",
    "K2NodeEnhancedInputAction",
    "K2NodeFunctionEntry",
    # 结果
    "ParseResult",
    "StatusInfo",
    # 蓝图元数据
    "BlueprintMetadata",
    "BlueprintVariable",
    "BlueprintFunction",
    "BlueprintEvent",
    "FunctionParameter",
    "MulticastDelegate",
    # 映射模型
    "TypeMappingsProvider",
    "UsmapParser",
    "JmapParser",
    "TypeMappings",
    "StructMapping",
    "PropertyType",
    "PropertyInfo",
    # 属性数据模型
    "PropertyTag",
    "PropertyTypeName",
    "PropertyValue",
    "SoftObjectPathValue",
    "AdvancedPropertyValue",
    "StructValue",
    "MapValue",
    "SetValue",
    "EnumValue",
    "TextValue",
    "DelegateValue",
    # 解析器模块
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
    "parse_verse_cell_property",
    "parse_verse_value_property",
    "parse_ansi_str_property",
    "parse_double_property",
    "parse_guid_property",
    # CustomProperty 注册表
    "CUSTOM_PROPERTY_HANDLERS",
    "CustomPropertyContext",
    "register_custom_property",
    "handle_custom_property",
    # 辅助函数（测试依赖）
    "get_struct_size",
    "_extract_struct_type_from_tag",
    "_extract_map_types_from_tag",
    "_extract_set_type_from_tag",
    "_extract_enum_type_from_tag",
    # parsers/utils.py 辅助函数
    "resolve_name_from_index",
    "read_validated_count",
    "make_enum_value",
    "extract_inner_from_tag",
    # Fallback 模型
    "PropertyFallback",
    "StructFallback",
    "GenericUObject",
    "ExportParseStatus",
    "FallbackReason",
    # 诊断模型
    "OffsetRangeDiagnostic",
    # Class Handler Registry
    "ClassHandlerRegistry",
    "ClassHandler",
    "HandlerResult",
    "FallbackPolicy",
    "get_class_registry",
    # 蓝图模块
    "extract_blueprint_variables",
    "parse_component_transform",
    "extract_blueprint_metadata",
    "extract_components",
    # 主解析管线
    "parse_package",
    "parse_uasset",
    "parse_uasset_with_linker",
    "PackageBundle",
    "PackageProvider",
    "FileSystemPackageProvider",
    "PakPackageProvider",
    "IoStorePackageProvider",
    "open_package_bundle",
    "RawFileResult",
    "parse_raw_file",
    "parse_json_descriptor",
    "parse_ini_file",
    "parse_locres",
    "parse_locmeta",
    "parse_audio_metadata",
    # 图解析辅助函数
    "extract_blueprint_graphs",
    "build_execution_flow_entries",
    "build_data_flows",
    "build_connections_map",
    "format_graphs_json",
    "build_execution_chains",
    "format_pin_ref",
    "build_function_graphs",
    # 辅助函数
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
    # CPF 常量
    "CPF_Edit",
    "CPF_BlueprintVisible",
    "CPF_InstancedReference",
    "CPF_BlueprintReadOnly",
    "CPF_Transient",
    "CPF_SaveGame",
    "CPF_ExposeOnSpawn",
    # 变换数据类
    "VectorValue",
    "RotatorValue",
    "ScaleValue",
    # 节点类型读取器（测试依赖）
    "read_k2node_call_function",
    "read_k2node_event",
    "read_k2node_knot",
    "read_edgraph_node_comment",
    "read_k2node_enhanced_input",
    "read_k2node_functionentry",
    # Kismet bytecode
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
    "FKismetArchive",
    "USTRUCT_TYPES",
    "reset_bpgc_cache",
    # Kismet translator
    "KismetTranslator",
    "MathFunctionCleaner",
    "TypeRegistry",
    "line_cpp",
    "UE_TYPE_MAP",
    "FunctionBodyBuilder",
    "to_function_body",
    "StructuredControlFlow",
    "StructuredBlock",
    # Kismet bytecode extractor
    "extract_bytecode_bytes",
    "parse_bytecode_stream",
    "extract_and_parse",
    # Kismet decompilation pipeline
    "KismetDecompiledResult",
    "decompile_uasset",
    "decompile_single_function",
    # C++ code gen
    "CppProperty",
    "CppHeaderMeta",
    "CppClassIR",
    "format_cpp_class_json",
    "format_cpp_header",
    "UE_TO_CPP_TYPE_MAP",
    "ENGINE_CLASS_PATHS",
    "ue_path_to_cpp_type",
    "ue_package_path_to_cpp_class",
    "infer_class_prefix",
    "resolve_ue_type",
    "CPF_TO_UPROPERTY_MAP",
    "cpf_flags_to_uproperty_marks",
    "extract_cpp_class_skeleton",
    "extract_cpp_constructor",
    "format_cpp_call_statements",
    "CppCallParameter",
    "CppMethodIR",
    "CppCallStatement",
    # Statement IR
    "CppStatement",
    "CppCallStmt",
    "CppAssignmentStmt",
    "CppIfStmt",
    "CppInlineExprStmt",
    "CppReturnStmt",
    "CppWhileStmt",
    "CppRawStmt",
    # Body builder
    "kismet_to_cpp_body",
    "format_cpp_default_value",
    "format_cpp_transform",
    "format_cpp_component_init",
    "format_cpp_input_action_load",
    "build_constructor_sections",
    "format_cpp_constructor",
    "sanitize_identifier",
    # Version management
    "VersionContainer",
    "build_version_container",
    "EUEVersion",
    # Link module
    "PackageLinker",
    "UObjectInstance",
    "LinkerParseResult",
    # Pak module
    "PAK_FILE_MAGIC",
    "PakFileVersion",
    "ECompressionFlags",
    "Flag_Encrypted",
    "Flag_Deleted",
    "MaxNumCompressionMethods",
    "PAK_INFO_SIZES",
    "FPakCompressedBlock",
    "FPakEntry",
    "FPakInfo",
    "FPakDirectoryEntry",
    "read_fstring",
    "decompress_block",
    "decompress_entry",
    "PakFileReader",
    # IoStore 容器系统
    "IoStoreReader",
    "FIoChunkId",
    "FIoOffsetAndSize",
    # Bulk Data
    "FBulkDataHeader",
    "BulkDataFlags",
    # UObject 类型体系
    "UObject",
    "ObjectTypeRegistry",
    "UStaticMesh",
    "USkeletalMesh",
    "UTexture2D",
    "UMaterial",
    "UMaterialInstance",
]
