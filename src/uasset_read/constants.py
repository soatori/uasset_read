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
MAX_CUSTOM_VERSIONS = 10_000       # Maximum custom version entries
MMAP_THRESHOLD = 50 * 1024 * 1024  # 50MB - switch to mmap above this
MAX_PROPERTY_COUNT = 10_000        # Property loop limit
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
PKG_FilterEditorOnly = 0x00000080      # Filter editor-only objects

# ============================================================================
# 蓝图图解析安全常量
# ============================================================================

MAX_PINS_PER_NODE = 1000               # 单节点最大引脚数
MAX_NODES_PER_GRAPH = 5000             # 单图最大节点数
MAX_LINKEDTO_PER_PIN = 100             # 单引脚最大连接数

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
UE5_IMPORT_TYPE_HIERARCHIES = 1017

# ============================================================================
# 更多 CustomVersion GUIDs
# ============================================================================
FUE5_MAINSTREAM_VERSION_GUID = "697DD581-E64F41AB-AA4A51EC-BEB7B628"
FRELEASE_OBJECT_VERSION_GUID = "9C54D522-A8264FBE-94210746-61B482D0"
FUE5RELEASESTREAM_OBJECT_VERSION_GUID = "D89B5E42-24BD4D46-8412ACA8-DF641779"

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
# 控制流节点集合（用于蓝图图解析）
# ============================================================================

CONTROL_FLOW_NODES = frozenset({
    "K2Node_IfThenElse",
    "K2Node_Switch",
    "K2Node_SwitchString",
    "K2Node_SwitchEnum",
    "K2Node_SwitchInteger",
    "K2Node_MacroInstance",
})

# ============================================================================
# 开始事件类型集合
# ============================================================================

START_EVENT_TYPES = frozenset({
    "K2Node_Event",
    "K2Node_EnhancedInputAction",
    "K2Node_VariableSet",
    "K2Node_CustomEvent"
})

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
CPF_BlueprintVisible = 0x0000000000000004
CPF_BlueprintReadOnly = 0x0000000000000010
CPF_Transient = 0x0000000000002000
CPF_EditConst = 0x0000000000020000
CPF_InstancedReference = 0x0000000000080000
CPF_Config = 0x0000000000004000
CPF_SaveGame = 0x0000000001000000
CPF_Deprecated = 0x0000000020000000
CPF_Protected = 0x0000080000000000
CPF_AdvancedDisplay = 0x0000040000000000
CPF_ExposeOnSpawn = 0x0001000000000000
CPF_EditAnywhere = 0x02000000
CPF_EditInstanceOnly = 0x04000000
CPF_BlueprintReadWrite = 0x00000100
CPF_DuplicateTransient = 0x00008000
CPF_NoClear = 0x00080000
CPF_ReferenceOnly = 0x00100000
CPF_BlueprintAssignable = 0x80000000
CPF_BlueprintCallable = 0x00004000
CPF_RepNotify = 0x10000000
CPF_Interp = 0x20000000
CPF_Net = 0x00000020
CPF_Replicated = 0x00100000
CPF_NonPIEDuplicateTransient = 0x00800000

# ============================================================================
# CLI退出代码
# ============================================================================

EXIT_SUCCESS = 0
EXIT_PARSE_ERROR = 1
EXIT_FILE_NOT_FOUND = 2
EXIT_ARGUMENT_ERROR = 3


