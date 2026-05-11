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
    # 导出其他常用常量（后续阶段按需添加）
)

# 导出异常类
from .exceptions import (
    UAssetError,
    VersionError,
    ErrorContext,
    ParseError,
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
)

# 公共API导出控制（per D-09）
__all__ = [
    # 版本号
    "__version__",
    # 常量
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
    # 异常类
    "UAssetError",
    "VersionError",
    "ErrorContext",
    "ParseError",
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
]