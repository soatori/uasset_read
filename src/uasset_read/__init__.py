"""
uasset_read - Unreal Engine .uasset 文件解析器

版本 0.5.0

Core / Extras 分层（详见 docs/architecture/core-extras-split.md）：
- Core: archive, constants, exceptions, core, parse_uasset, package,
  models, serializers, parsers, link — 基础解析管线
- Extras: graph, kismet, blueprint — 可选高级分析，
  可通过 ``from uasset_read.extras.graph import ...`` 访问

API 稳定性策略（详见 docs/api-stability.md）：
- 稳定根 API: __all__ 中列出的符号，面向外部使用者
- 子模块 API: parsers, serializers, graph, kismet, renderers 等
  通过 ``from uasset_read.serializers import ...`` 访问，不保证稳定
- 根模块仍导入大量内部符号（向后兼容），但它们不在 __all__ 中，
  使用者不应直接依赖
"""
__version__ = "0.5.0"

# ============================================================================
# 稳定根 API — 推荐入口
# ============================================================================

from .core import parse_single, parse_batch, list_formats, BatchResult
from .parse_uasset import parse_package, parse_uasset, parse_uasset_with_linker
from .models.result import ParseResult, StatusInfo
from .exceptions import UAssetError, VersionError, ErrorContext, ParseError
from .archive import FArchive

# IR 模型
from .models.ir import PackageIR, ExportIR, GraphIR, NodeIR, PinIR

# 稳定 API 别名（统一命名）
from .serializers.package_summary import PackageFileSummary as PackageSummary
from .serializers.object_resources import ObjectExport as ExportEntry
from .serializers.object_resources import ObjectImport as ImportEntry

# ============================================================================
# 常量（稳定）
# ============================================================================

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
    MAX_PINS_PER_NODE,
    MAX_NODES_PER_GRAPH,
    MAX_LINKEDTO_PER_PIN,
    PROP_TAG_NONE,
    PROP_TAG_HAS_ARRAY_INDEX,
    PROP_TAG_HAS_PROPERTY_GUID,
    PROP_TAG_HAS_EXTENSIONS,
    PROP_TAG_HAS_BINARY_OR_NATIVE,
    PROP_TAG_BOOL_TRUE,
    PROP_TAG_SKIPPED_SERIALIZE,
    CONTROL_FLOW_NODES,
    START_EVENT_TYPES,
    BRANCH_TYPE_MAP,
    PKG_Cooked,
    PKG_UnversionedProperties,
    PKG_FilterEditorOnly,
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
    FFRAMEWORK_OBJECT_VERSION_GUID,
    FFRAMEWORK_VERSION_ED_GRAPH_PIN_CONTAINER_TYPE,
    FFRAMEWORK_VERSION_PINS_STORE_FNAME,
    FUE5_MAINSTREAM_VERSION_GUID,
    FUE5_MAINSTREAM_VERSION_ED_GRAPH_PIN_SOURCE_INDEX,
    FRELEASE_OBJECT_VERSION_GUID,
    FRELEASE_VERSION_PIN_TYPE_UOBJECT_WRAPPER,
    FORMAT_CONFIG,
    CPF_Edit, CPF_BlueprintVisible, CPF_InstancedReference, CPF_EditAnywhere,
    CPF_EditInstanceOnly, CPF_BlueprintReadWrite, CPF_BlueprintReadOnly,
    CPF_Transient, CPF_SaveGame, CPF_ExposeOnSpawn,
)

# ============================================================================
# 子模块 API — 通过子模块访问更详细功能
# ============================================================================

# 序列化模块
from .serializers import (
    PackageFileSummary, PackageIndex, ObjectImport, ObjectExport,
    EngineVersion, CustomVersion, GenerationInfo,
    read_package_summary, read_name_table,
    read_import_map, read_export_map, detect_blueprint,
    build_imports_list, get_asset_class, resolve_class_name,
    detect_blueprint_generated_class, detect_circular_deps,
    validate_package_index,
    read_ue_graph, read_ue_graph_node, read_ue_graph_pin,
    read_ed_graph_pin_type, read_fmember_reference, create_node_from_archive,
    read_k2node_call_function,
    read_k2node_event,
    read_k2node_knot,
    read_edgraph_node_comment,
    read_k2node_enhanced_input,
    read_k2node_functionentry,
)

# 核心数据模型
from .models import (
    FEdGraphPinType, UEdGraphPin, UEdGraphNode, UEdGraph, FMemberReference,
    K2NodeCallFunction, K2NodeEvent, K2NodeKnot, EdGraphNodeComment,
    K2NodeEnhancedInputAction, K2NodeFunctionEntry,
    BlueprintMetadata, BlueprintVariable, BlueprintFunction,
    BlueprintEvent, FunctionParameter, MulticastDelegate,
    PropertyTag, PropertyTypeName, PropertyValue,
    SoftObjectPathValue, AdvancedPropertyValue, StructValue,
    MapValue, SetValue, EnumValue, TextValue, DelegateValue,
    PropertyFallback, StructFallback, GenericUObject,
    ExportParseStatus, FallbackReason, OffsetRangeDiagnostic,
)

# 映射模型
from .mappings import (
    TypeMappingsProvider, UsmapParser, JmapParser,
    TypeMappings, StructMapping, PropertyType, PropertyInfo,
)

# Class Handler Registry
from .parsers.class_registry import (
    ClassHandlerRegistry, ClassHandler, HandlerResult,
    FallbackPolicy, get_class_registry,
)

# 解析器模块
from .parsers import (
    parse_property_value, parse_properties_from_export,
    parse_bool_property, parse_int_property, parse_float_property,
    parse_str_property, parse_name_property, parse_object_property,
    parse_soft_object_property, parse_array_property, parse_struct_property,
    parse_map_property, parse_set_property, parse_enum_property,
    parse_text_property, parse_delegate_property,
    parse_uint16_property, parse_uint32_property, parse_uint64_property,
    parse_utf8_str_property, parse_weak_object_property, parse_lazy_object_property,
    parse_class_property, parse_soft_class_property, parse_asset_object_property,
    parse_multicast_delegate_property, parse_multicast_inline_delegate_property,
    parse_multicast_sparse_delegate_property, parse_interface_property,
    parse_field_path_property, parse_optional_property,
    parse_verse_string_property, parse_verse_class_property,
    parse_verse_function_property, parse_verse_dynamic_property,
    parse_verse_cell_property, parse_verse_value_property,
    parse_ansi_str_property, parse_double_property, parse_guid_property,
    CUSTOM_PROPERTY_HANDLERS, CustomPropertyContext,
    register_custom_property, handle_custom_property,
    get_struct_size,
    _extract_struct_type_from_tag, _extract_map_types_from_tag,
    _extract_set_type_from_tag, _extract_enum_type_from_tag,
    resolve_name_from_index, read_validated_count, make_enum_value,
    extract_inner_from_tag,
)

# 蓝图模块
from .blueprint import (
    extract_blueprint_variables, parse_component_transform,
    extract_blueprint_metadata, extract_components,
)

# 图解析模块
from .graph import (
    extract_blueprint_graphs, build_execution_flow_entries,
    build_data_flows, build_connections_map,
    build_graphs_summary, format_graphs_json, build_blueprint_node_index,
    build_execution_chains, format_pin_ref, _derive_node_name,
    write_pin_trace_report, is_function_graph, build_function_graphs,
    write_phase75_diagnostic,
)

# Kismet 字节码模块
from .kismet import (
    EExprToken, ECastToken, EScriptInstrumentationType,
    EBlueprintTextLiteralType, EAutoRtfmStopTransactMode,
    KismetExpression, KismetExpressionT, EXPR_CLASS_MAP,
    FKismetPropertyPointer, FFieldPath, FKismetArchive, USTRUCT_TYPES,
    reset_bpgc_cache, KismetTranslator, MathFunctionCleaner, TypeRegistry,
    line_cpp, UE_TYPE_MAP, FunctionBodyBuilder, to_function_body,
    StructuredControlFlow, StructuredBlock,
    extract_bytecode_bytes, parse_bytecode_stream, extract_and_parse,
    KismetDecompiledResult, decompile_uasset, decompile_single_function,
)


# 版本管理
from .versioning import VersionContainer, build_version_container, EUEVersion

# C++ 代码生成辅助
from .cpp_gen import sanitize_identifier

# Link 模块
from .link import PackageLinker, UObjectInstance, LinkerParseResult

# Pak 模块
from .pak import (
    PAK_FILE_MAGIC, PakFileVersion, ECompressionFlags,
    Flag_Encrypted, Flag_Deleted, MaxNumCompressionMethods, PAK_INFO_SIZES,
    FPakCompressedBlock, FPakEntry, FPakInfo, FPakDirectoryEntry, read_fstring,
    decompress_block, decompress_entry, PakFileReader,
)

# IoStore 容器系统
from .iostore import IoStoreReader, FIoChunkId, FIoOffsetAndSize

# Package 模块
from .package import (
    PackageBundle, PackageProvider, FileSystemPackageProvider,
    PakPackageProvider, IoStorePackageProvider, open_package_bundle,
)

# Raw 文件解析
from .raw import (
    RawFileResult, parse_raw_file, parse_json_descriptor,
    parse_ini_file, parse_locres, parse_locmeta, parse_audio_metadata,
)

# 变换数据类
from .models.transforms import VectorValue, RotatorValue, ScaleValue, format_transform_value

# 辅助函数
from .serializers.object_resources import (
    find_main_blueprint_generated_class, resolve_parent_class,
    resolve_class_name_with_linker, get_asset_class_with_linker,
    detect_blueprint_with_linker, resolve_parent_class_with_linker,
    read_soft_object_paths,
)
from .blueprint.transform_parser import (
    extract_component_transforms, parse_vector_value,
    parse_rotator_value, parse_scale_value,
)
from .serializers.property_tags import read_property_tag, parse_ctrl_flags, parse_ue511_ctrl_flags
from .parsers.property_types import parse_default_value, format_variable_type
from .blueprint.variable_extractor import read_blueprint_variable, parse_property_flags_to_labels

# ============================================================================
# 稳定公共 API — 仅包含推荐外部使用的符号
# ============================================================================
__all__ = [
    # 版本号
    "__version__",
    # 核心入口
    "parse_single",
    "parse_batch",
    "parse_package",
    "parse_uasset",
    "parse_uasset_with_linker",
    "list_formats",
    # 结果模型
    "ParseResult",
    "PackageSummary",
    "ExportEntry",
    "ImportEntry",
    "BatchResult",
    # IR 模型
    "PackageIR",
    "ExportIR",
    "GraphIR",
    "NodeIR",
    "PinIR",
    # 异常
    "UAssetError",
    "ParseError",
    "VersionError",
    # 高级工具
    "FArchive",
    "PackageBundle",
    "PackageLinker",
    "sanitize_identifier",
]
