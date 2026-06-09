"""
uasset_read常量定义

包含所有版本号、属性类型阈值、边界常量。
从uasset_read.py提取（per D-11）。
"""

# ============================================================================
# Package文件标签（来自UE源码）
# ============================================================================

PACKAGE_FILE_TAG = 0x9E2A83C1       # 正确字节序魔术标签
PACKAGE_FILE_TAG_SWAPPED = 0xC1832A9E  # 交换字节序魔术标签

# ============================================================================
# 版本常量
# ============================================================================

UE5_VERSION_MIN = 0                # UE5 版本最低值
UE5_LEGACY_VERSION = -9            # UE5.6+ 文件的 LegacyFileVersion 固定值
# -8: FileVersionUE5 字段加入, -7: 纹理分配信息移除, -6: 自定义版本序列化优化
UE5_LEGACY_VERSIONS = frozenset({-6, -7, -8, UE5_LEGACY_VERSION})  # 支持的 UE5 LegacyFileVersion

# ============================================================================
# CustomVersion GUIDs
# ============================================================================

FFRAMEWORK_OBJECT_VERSION_GUID = "CFFC743F-43B04480-939114DF-171D2073"

# ============================================================================
# 边界验证常量（防御性编程）
# ============================================================================

MAX_NAME_COUNT = 10_000_000        # Maximum name table entries
MAX_IMPORT_COUNT = 1_000_000       # Maximum import table entries
MAX_EXPORT_COUNT = 1_000_000       # Maximum export table entries
MAX_TOTAL_OBJECT_COUNT = 500_000   # Maximum import + export combined entries
MAX_CUSTOM_VERSIONS = 10_000       # Maximum custom version entries
MMAP_THRESHOLD = 50 * 1024 * 1024  # 50MB - switch to mmap above this
MAX_PROPERTY_COUNT = 10_000        # Property loop limit
MAX_RECURSION_DEPTH = 50           # 属性嵌套最大递归深度（防止恶意/畸形资产栈溢出）
MIN_UASSET_SIZE = 64               # 最小合法 .uasset 文件大小（字节）
                                      # 包含 Tag(4) + 版本字段(16~20) + LicenseeVer(4) + Hash(20) + HeaderSize(4) 的最小值
MAX_ARRAY_COUNT = 1_000_000       # Maximum ArrayProperty elements (per HIGH-07/35d-01)
MAX_FSTRING_LENGTH = 10_000_000   # 10 MB — FString maximum length (UTF-8/UTF-16)

# ============================================================================
# PropertyTag标志
# ============================================================================

PROP_TAG_NONE = 0x00
PROP_TAG_HAS_ARRAY_INDEX = 0x01      # ArrayIndex field present
PROP_TAG_HAS_PROPERTY_GUID = 0x02    # PropertyGuid field present
PROP_TAG_HAS_EXTENSIONS = 0x04       # Extension data
PROP_TAG_HAS_BINARY_OR_NATIVE = 0x08 # Binary/native serialize
PROP_TAG_BOOL_TRUE = 0x10            # Bool value is true
PROP_TAG_SKIPPED_SERIALIZE = 0x20    # Skipped serialize

# ============================================================================
# PropertyTag版本阈值
# ============================================================================

PROPERTY_TAG_COMPLETE_TYPE_NAME = 1012  # UE5 format switch threshold

# ============================================================================
# Package Flags
# ============================================================================

PKG_Cooked = 0x200                     # Package is cooked
PKG_UnversionedProperties = 0x2000     # Uses unversioned property serialization
PKG_FilterEditorOnly = 0x80000000      # Filter editor-only objects

# ============================================================================
# 蓝图图解析安全常量
# ============================================================================

MAX_PINS_PER_NODE = 1000               # 单节点最大引脚数
MAX_NODES_PER_GRAPH = 5000             # 单图最大节点数
MAX_LINKEDTO_PER_PIN = 100             # 单引脚最大连接数
MAX_FTEXT_CONSUMPTION = 10_240         # 10 KB — FText 解析安全网最大字节消耗
MAX_FTEXT_UTF16_LEN = 20_000           # 20 KB — FText/FString UTF-16 字节长度上限（UTF-16 码元对齐）

# ============================================================================
# 轻量容错解析阈值
# ============================================================================

LIGHTWEIGHT_TOLERANT_PARSE_THRESHOLD = 300  # export_count 超过此值时启用轻量容错解析

# ============================================================================
# FPropertyTypeName 最大节点数（UE 源码限制）
# ============================================================================

MAX_TYPENODE_NODES = 20                # FPropertyTypeName 最大节点数

# ============================================================================
# PropertyTag extension flags
# ============================================================================

PROP_EXT_SERIALIZE_CONTROL = 0x02  # SerializeControl bit in property extensions

# ============================================================================
# FPropertyTypeName type node read limit (relaxed from MAX_TYPENODE_NODES for complex nested types)
# ============================================================================

MAX_PROPERTY_TYPE_NODES = 50  # Max nodes in _read_property_type_name (relaxed from MAX_TYPENODE_NODES=20 for complex nested types)

# ============================================================================
# UE5版本常量（EUnrealEngineObjectUE5Version）
# ============================================================================

UE5_REMOVE_OBJECT_EXPORT_PACKAGE_GUID = 1005
UE5_TRACK_OBJECT_EXPORT_IS_INHERITED = 1006
UE5_OPTIONAL_RESOURCES = 1003
UE5_NAMES_REFERENCED_FROM_EXPORT_DATA = 1001
UE5_PAYLOAD_TOC = 1002
UE5_LARGE_WORLD_COORDINATES = 1004
UE5_FSOFTOBJECTPATH_REMOVE_ASSET_PATH_FNAMES = 1007
UE5_ADD_SOFTOBJECTPATH_LIST = 1008
UE5_DATA_RESOURCES = 1009
UE5_SCRIPT_SERIALIZATION_OFFSET = 1010
UE5_PROPERTY_TAG_EXTENSION = 1011
UE5_PROPERTY_TAG_COMPLETE_TYPE_NAME = PROPERTY_TAG_COMPLETE_TYPE_NAME  # alias (same value 1012)
UE5_ASSETREGISTRY_PACKAGEBUILDDEPENDENCIES = 1013
UE5_METADATA_SERIALIZATION_OFFSET = 1014
UE5_VERSE_CELLS = 1015
UE5_PACKAGE_SAVED_HASH = 1016
UE5_OS_SUB_OBJECT_SHADOW_SERIALIZATION = 1017
UE5_IMPORT_TYPE_HIERARCHIES = 1018

# ============================================================================
# UE4 版本常量（对应 EUnrealEngineObjectUE4Version）
# ============================================================================

UE4_ADDED_PACKAGE_SUMMARY_LOCALIZATION_ID = 516
UE4_ADD_STRING_ASSET_REFERENCES_MAP = 516
UE4_SERIALIZE_TEXT_IN_PACKAGES = 517
UE4_ADDED_SEARCHABLE_NAMES = 518
UE4_ADDED_PACKAGE_OWNER = 519
UE4_NON_OUTER_PACKAGE_IMPORT = 520
UE4_NAME_HASHES_SERIALIZED = 514  # VER_UE4_NAME_HASHES_SERIALIZED: 名称表条目后添加 4 字节哈希 (UE 4.14+)
UE4_LOAD_FOR_EDITOR_GAME = 364
UE4_COOKED_ASSETS_IN_EDITOR_SUPPORT = 484
UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS = 506
UE4_TemplateIndex_IN_COOKED_EXPORTS = 507
UE4_64BIT_EXPORTMAP_SERIALSIZES = 510

# ============================================================================
# 更多 CustomVersion GUIDs
# ============================================================================
FUE5_MAINSTREAM_VERSION_GUID = "697DD581-E64F41AB-AA4A51EC-BEB7B628"
FRELEASE_OBJECT_VERSION_GUID = "9C54D522-A8264FBE-94210746-61B482D0"
FUE5RELEASESTREAM_OBJECT_VERSION_GUID = "D89B5E42-24BD4D46-8412ACA8-DF641779"

# 子系统版本 GUIDs（扩展版本系统覆盖）
FBLUEPRINTS_OBJECT_VERSION_GUID = "B0D832E4-1F89-4D06-B39A-8F1B5E1B2A4B"
FCORE_OBJECT_VERSION_GUID = "371EC2EE-4CD7-4C38-AEB1-B7D6F539A54B"
FEDITOR_OBJECT_VERSION_GUID = "E4B068ED-F494-42E9-A231-DA0B0E4C5E56"
FANIM_OBJECT_VERSION_GUID = "29E575DD-E0A3-4682-9C20-D1CF1B5E8DEF"
FPHYSICS_OBJECT_VERSION_GUID = "78F01B33-BEA0-46A0-8BAF-6C4F4E23F8C1"
FRENDERING_OBJECT_VERSION_GUID = "645F75DB-7F54-4C64-A1E2-2F6F3B4B8A5E"

# ============================================================================
# FrameworkObjectVersion阈值
# ============================================================================

FFRAMEWORK_VERSION_ED_GRAPH_PIN_CONTAINER_TYPE = 15
FFRAMEWORK_VERSION_PINS_STORE_FNAME = 19

# ============================================================================
# FUE5MainStreamObjectVersion阈值
# ============================================================================

FUE5_MAINSTREAM_VERSION_ED_GRAPH_PIN_SOURCE_INDEX = 50

# ============================================================================
# FReleaseObjectVersion阈值
# ============================================================================

FRELEASE_VERSION_PIN_TYPE_UOBJECT_WRAPPER = 10

# ============================================================================
# FUE5ReleaseStreamObjectVersion Thresholds
# ============================================================================

FUE5RELEASESTREAM_VERSION_SERIALIZE_FLOAT_PIN_DEFAULTS_AS_SINGLE_PRECISION = 36

# ============================================================================
# 蓝图元数据键（UE 编辑器内部字段）
# ============================================================================

BLUEPRINT_METADATA_KEYS = frozenset({
    "BlueprintSystemVersion",
    "GeneratedClass",
    "SimpleConstructionScript",
    "bCanEverTick",
    "bCanEverRender",
    "bStartWithTickEnabled",
    "bReplicates",
    "NetUpdateFrequency",
    "MinNetUpdateFrequency",
    "NetPriority",
})

# ============================================================================
# 控制流节点集合（用于蓝图图解析）
# ============================================================================

CONTROL_FLOW_NODES = frozenset({
    "K2Node_IfThenElse",
    "K2Node_Switch",
    "K2Node_SwitchString",
    "K2Node_SwitchEnum",
    "K2Node_SwitchInteger",
    "K2Node_MacroInstance",
    # 循环类宏
    "K2Node_ForLoop",
    "K2Node_WhileLoop",
    "K2Node_DoOnce",
    # 多门控
    "K2Node_Sequence",
    "K2Node_MultiGate",
    # 选择
    "K2Node_Select",
    "K2Node_ExecutionSequence",
})

# ============================================================================
# 开始事件类型集合
# ============================================================================

START_EVENT_TYPES = frozenset({
    "K2Node_Event",
    "K2Node_EnhancedInputAction",
    "K2Node_VariableSet",
    "K2Node_CustomEvent",
    "K2Node_FunctionEntry",  # 函数图执行流起点
})

# ============================================================================
# 数据流边界节点集合
# ============================================================================

DATA_BOUNDARY_NODES = frozenset({
    "K2Node_FunctionEntry",  # 函数参数输出作为数据流起点
    "K2Node_VariableSet",    # 本地变量定义（边界）
})

# ============================================================================
# EnhancedInput TriggerEvent 引脚映射
# ============================================================================

ETRIGGER_EVENT_PIN_MAP = {
    "Started": "Started",
    "Triggered": "Ongoing",
    "Completed": "Completed",
    "Exited": "Exited",
}

# ============================================================================
# 分支类型映射
# ============================================================================

BRANCH_TYPE_MAP = {
    "K2Node_IfThenElse": "if_then_else",
    "K2Node_Switch": "switch",
    "K2Node_SwitchString": "switch_string",
    "K2Node_SwitchEnum": "switch_enum",
    "K2Node_SwitchInteger": "switch_integer",
    "K2Node_MacroInstance": "macro_instance",
    "K2Node_ForLoop": "for_loop",
    "K2Node_WhileLoop": "while_loop",
    "K2Node_DoOnce": "do_once",
    "K2Node_Sequence": "sequence",
    "K2Node_MultiGate": "multi_gate",
    "K2Node_Select": "select",
}

# ============================================================================
# 输出格式配置
# ============================================================================

FORMAT_CONFIG = {
    "pin_reference_mode": "name",
}

# ============================================================================
# 图类型映射
# ============================================================================

GRAPH_TYPE_MAP = {
    "EdGraph": "event",
    "UberEdGraph": "uber",
}

# ============================================================================
# CPF_* 属性标志位常量（Class Property Flags）
# 等价迁移 uasset_read.py §4711-4738
# ============================================================================

CPF_Edit = 0x0000000000000001
CPF_ConstParm = 0x0000000000000002
CPF_BlueprintVisible = 0x0000000000000004
CPF_ExportObject = 0x0000000000000008
CPF_BlueprintReadOnly = 0x0000000000000010
CPF_BlueprintAuthorityOnly = 0x0000000000000020
CPF_EditFixedSize = 0x0000000000000040
CPF_Parm = 0x0000000000000080
CPF_OutParm = 0x0000000000000100
CPF_ZeroConstructor = 0x0000000000000200
CPF_ReturnParm = 0x0000000000000400
CPF_Net = 0x0000000000000800
CPF_EditAnywhere = 0x0000000000001000
CPF_BlueprintReadWrite = 0x0000000000010000
CPF_Transient = 0x0000000000002000
CPF_Config = 0x0000000000004000
CPF_DisableEditOnTemplate = 0x0000000000008000
CPF_DuplicateTransient = 0x0000000000020000
CPF_NonPIEDuplicateTransient = 0x0000000000040000
CPF_EditConst = 0x0000000000080000
CPF_NoClear = 0x0000000000200000
CPF_ReferencePersisted = 0x0000000000400000
CPF_SaveGame = 0x0000000001000000
CPF_BlueprintAssignable = 0x0000000002000000
CPF_BlueprintCallable = 0x0000000004000000
CPF_BlueprintPure = 0x0000000008000000
CPF_BlueprintCompilerGenerated = 0x0000000010000000
CPF_NetSerialize = 0x0000000020000000
CPF_RepNotify = 0x0000000040000000
CPF_RepRetry = 0x0000000080000000
CPF_Interp = 0x0000000100000000
CPF_Constructed = 0x0000000200000000
CPF_Protected = 0x0000000400000000
CPF_AdvancedDisplay = 0x0000000800000000
CPF_AssetRegistrySearchable = 0x0000001000000000
CPF_ContainsInstancedReference = 0x0000002000000000
CPF_Deprecated = 0x0000004000000000
CPF_IsPlainOldData = 0x0000008000000000
CPF_NoDestructor = 0x0000010000000000
CPF_HasGetValueTypeHash = 0x0000020000000000
CPF_NativeAccessSpecifierPublic = 0x0000040000000000
CPF_NativeAccessSpecifierProtected = 0x0000080000000000
CPF_NativeAccessSpecifierPrivate = 0x0000100000000000
CPF_SkipSerialization = 0x0000200000000000
CPF_TextExportTransient = 0x0000400000000000
CPF_NonTransactional = 0x0000800000000000
CPF_Required = 0x0001000000000000
CPF_ExposeOnSpawn = 0x0002000000000000
CPF_PersistentInstance = 0x0004000000000000
CPF_TObjectPtr = 0x0008000000000000
CPF_UObjectWrapper = 0x0010000000000000
CPF_NaturalizePropertyIndex = 0x0020000000000000
CPF_InstancedReference = 0x0040000000000000

# 旧 API 名称保留为 UE5 标准语义别名，不再覆盖标准 CPF_* 值。
CPF_EditInstanceOnly = CPF_EditAnywhere
CPF_ReferenceOnly = CPF_ReferencePersisted
CPF_Replicated = CPF_Net

# ============================================================================
# CLI退出代码
# ============================================================================

EXIT_SUCCESS = 0
EXIT_PARSE_ERROR = 1
EXIT_FILE_NOT_FOUND = 2
EXIT_ARGUMENT_ERROR = 3


