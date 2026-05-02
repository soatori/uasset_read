"""
uasset_read.py - Unreal Engine .uasset 文件解析器

Phase 1: 核心解析器实现
- FArchive 基类和字节序处理
- PackageFileSummary、ObjectImport、ObjectExport 数据模型
- 名称表、导入表、导出表解析
- 版本验证和错误处理

基于 UE 5.7 源码参考：
- PackageFileSummary.h - 文件头结构
- ObjectResource.h - 导入/导出结构
- Archive.h - FArchive 模式
"""

import struct
import os
import re
import sys
import json
import argparse
import mmap
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, BinaryIO, Tuple, Any


# ============================================================================
# 常量定义（来自 UE 源码）
# ============================================================================

PACKAGE_FILE_TAG = 0x9E2A83C1       # 正确字节序魔术标签
PACKAGE_FILE_TAG_SWAPPED = 0xC1832A9E  # 交换字节序魔术标签
UE5_VERSION_MIN = 0                # UE5 版本最低值（接受任何 UE5 文件）
LEGACY_FILE_VERSION_MIN = -9       # LegacyFileVersion 范围下限
LEGACY_FILE_VERSION_MAX = -2       # LegacyFileVersion 范围上限

# Bounds validation constants (WR-01 mitigation)
MAX_NAME_COUNT = 10_000_000        # Maximum name table entries
MAX_IMPORT_COUNT = 1_000_000       # Maximum import table entries
MAX_EXPORT_COUNT = 1_000_000       # Maximum export table entries
MAX_CUSTOM_VERSIONS = 10_000       # Maximum custom version entries

# Memory-mapped file threshold (SAFE-03, D-01)
MMAP_THRESHOLD = 50 * 1024 * 1024  # 50MB - switch to mmap above this
MAX_PROPERTY_COUNT = 10_000        # D-09: property loop limit

# PropertyTag flags (PropertyTag.h lines 17-26)
PROP_TAG_NONE = 0x00
PROP_TAG_HAS_ARRAY_INDEX = 0x01      # ArrayIndex field present
PROP_TAG_HAS_PROPERTY_GUID = 0x02    # PropertyGuid field present
PROP_TAG_HAS_EXTENSIONS = 0x04       # Extension data (defer to Phase 3)
PROP_TAG_HAS_BINARY_OR_NATIVE = 0x08 # Binary/native serialize
PROP_TAG_BOOL_TRUE = 0x10            # Bool value is true
PROP_TAG_SKIPPED_SERIALIZE = 0x20    # Skipped serialize

# PropertyTag version thresholds (PropertyTag.cpp)
PROPERTY_TAG_COMPLETE_TYPE_NAME = 1000  # UE5 format switch threshold
VER_UE4_STRUCT_GUID_IN_PROPERTY_TAG = 500
VER_UE4_PROPERTY_GUID_IN_PROPERTY_TAG = 510

# Package Flags (ObjectMacros.h)
PKG_Cooked = 0x200                     # Package is cooked
PKG_UnversionedProperties = 0x2000     # Uses unversioned property serialization (Phase 11 GAP-01)
PKG_FilterEditorOnly = 0x00000080      # Filter editor-only objects (Phase 10 Gap #2)

# Phase 7: Blueprint Graph Parsing Safety Constants
MAX_PINS_PER_NODE = 1000               # 单节点最大引脚数（T-07-02-02）
MAX_NODES_PER_GRAPH = 5000             # 单图最大节点数（T-07-02-03）
MAX_LINKEDTO_PER_PIN = 100             # 单引脚最大连接数（T-07-02-04）

# UE5 Version Constants (EUnrealEngineObjectUE5Version)
UE5_NAMES_REFERENCED_FROM_EXPORT_DATA = 1001  # NAMES_REFERENCED_FROM_EXPORT_DATA
UE5_PAYLOAD_TOC = 1002                        # PAYLOAD_TOC
UE5_LARGE_WORLD_COORDINATES = 1004            # LARGE_WORLD_COORDINATES
UE5_FSOFTOBJECTPATH_REMOVE_ASSET_PATH_FNAMES = 1007  # FSOFTOBJECTPATH_REMOVE_ASSET_PATH_FNAMES
UE5_ADD_SOFTOBJECTPATH_LIST = 1008            # ADD_SOFTOBJECTPATH_LIST
UE5_DATA_RESOURCES = 1009                     # DATA_RESOURCES
UE5_SCRIPT_SERIALIZATION_OFFSET = 1010        # SCRIPT_SERIALIZATION_OFFSET
UE5_PROPERTY_TAG_EXTENSION = 1011             # PROPERTY_TAG_EXTENSION_AND_OVERRIDABLE_SERIALIZATION
UE5_PROPERTY_TAG_COMPLETE_TYPE_NAME = 1012   # PROPERTY_TAG_COMPLETE_TYPE_NAME
UE5_ASSETREGISTRY_PACKAGEBUILDDEPENDENCIES = 1013  # ASSETREGISTRY_PACKAGEBUILDDEPENDENCIES
UE5_METADATA_SERIALIZATION_OFFSET = 1014     # METADATA_SERIALIZATION_OFFSET
UE5_VERSE_CELLS = 1015                        # VERSE_CELLS
UE5_PACKAGE_SAVED_HASH = 1016                 # PACKAGE_SAVED_HASH (修正：原代码误用 1004)
UE5_OS_SUB_OBJECT_SHADOW_SERIALIZATION = 1017  # OS_SUB_OBJECT_SHADOW_SERIALIZATION
UE5_IMPORT_TYPE_HIERARCHIES = 1018            # IMPORT_TYPE_HIERARCHIES

# UE4 Version Constants (EUnrealEngineObjectUE4Version) - 按实际值计算
UE4_ADDED_PACKAGE_SUMMARY_LOCALIZATION_ID = 385  # VER_UE4_ADDED_PACKAGE_SUMMARY_LOCALIZATION_ID (old)
UE4_SERIALIZE_TEXT_IN_PACKAGES = 401            # VER_UE4_SERIALIZE_TEXT_IN_PACKAGES (old)
# 正确值（从 ObjectVersion.h 计算）
UE4_WORLD_LEVEL_INFO = 223                      # VER_UE4_WORLD_LEVEL_INFO
UE4_ADDED_CHUNKID = 277                         # VER_UE4_ADDED_CHUNKID_TO_ASSETDATA_AND_UPACKAGE
UE4_CHANGED_CHUNKID_TO_ARRAY = 341             # VER_UE4_CHANGED_CHUNKID_TO_BE_AN_ARRAY_OF_CHUNKIDS
UE4_ENGINE_VERSION_OBJECT = 334                 # VER_UE4_ENGINE_VERSION_OBJECT
UE4_ADD_STRING_ASSET_REFERENCES_MAP = 382      # VER_UE4_ADD_STRING_ASSET_REFERENCES_MAP
UE4_PACKAGE_SUMMARY_HAS_COMPATIBLE_ENGINE_VERSION = 442  # VER_UE4_PACKAGE_SUMMARY_HAS_COMPATIBLE_ENGINE_VERSION
UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS = 505  # VER_UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS
VER_UE4_TemplateIndex_IN_COOKED_EXPORTS = 506    # Phase 6: ObjectVersion.h line 711
UE4_ADDED_SEARCHABLE_NAMES = 508               # VER_UE4_ADDED_SEARCHABLE_NAMES
VER_UE4_64BIT_EXPORTOFFSETS = 508              # Phase 6: 64-bit export offsets
UE4_ADDED_PACKAGE_OWNER = 516                  # VER_UE4_ADDED_PACKAGE_OWNER
UE4_NON_OUTER_PACKAGE_IMPORT = 518             # VER_UE4_NON_OUTER_PACKAGE_IMPORT
UE4_LOAD_FOR_EDITOR_GAME = 383                 # VER_UE4_LOAD_FOR_EDITOR_GAME
UE4_COOKED_ASSETS_IN_EDITOR_SUPPORT = 401      # VER_UE4_COOKED_ASSETS_IN_EDITOR_SUPPORT

# UE5 Release Object Version constants (Phase 6 D-08/D-10)
UE5_REMOVE_OBJECT_EXPORT_PACKAGE_GUID = 1010    # FReleaseObjectVersion::RemoveObjectExportPackageGuid
UE5_TRACK_OBJECT_EXPORT_IS_INHERITED = 1011     # FReleaseObjectVersion::TrackObjectExportIsInherited
UE5_GENERATE_PUBLIC_HASH = 1015                 # FReleaseObjectVersion::GeneratePublicHash
UE5_OPTIONAL_RESOURCES = 1003                   # FReleaseObjectVersion::OptionalResources (bImportOptional field)


# ============================================================================
# 自定义异常（D-15 优雅降级）
# ============================================================================

class UAssetError(Exception):
    """uasset 解析错误基类"""
    pass


class VersionError(UAssetError):
    """版本不支持错误"""
    pass


@dataclass
class ErrorContext:
    """
    D-15/D-18: 错误上下文信息。

    记录错误发生时的解析状态，帮助定位问题。

    Phase 6 D-12/D-13/D-14: 新增导出表解析阶段信息。
    """
    offset: int           # 文件偏移位置
    phase: str            # 解析阶段：header/name_table/import_map/export_map/properties/blueprint
    operation: str        # 操作类型：read_i32/read_name/seek 等
    context_name: str = ""  # 相关对象名或属性名
    # Phase 6 新增（D-12/D-13/D-14）：导出表解析阶段信息
    export_index: Optional[int] = None    # 当前导出索引（0-based）
    expected_offset: Optional[int] = None  # 期望偏移
    actual_offset: Optional[int] = None    # 实际偏移
    field_name: str = ""                  # 字段名（如 "TemplateIndex"）
    version_info: Dict[str, int] = field(default_factory=dict)  # 版本检查失败信息


class ParseError(UAssetError):
    """解析错误（可携带部分结果和上下文）"""

    def __init__(self, message: str, partial_result: Optional[Dict] = None, context: Optional[ErrorContext] = None):
        super().__init__(message)
        self.partial_result = partial_result
        self.context = context  # D-15: error context


# ============================================================================
# FArchive 基类（D-01 单一类设计）
# ============================================================================

class FArchive:
    """
    二进制读取类，镜像 UE 的 FArchive 模式。
    支持字节序检测和交换、边界验证。
    """

    def __init__(self, path: str):
        """
        初始化归档，打开文件并获取大小。

        Args:
            path: .uasset 文件路径
        """
        self._path = path
        self._file: BinaryIO = open(path, 'rb')
        self._byte_swapping: bool = False
        self._file_size: int = os.path.getsize(path)

        # D-02/D-03: mmap branch
        self._mmap: Optional[mmap.mmap] = None
        self._use_mmap: bool = False
        self._mmap_warning: Optional[str] = None

        # D-01: Check threshold
        if self._file_size >= MMAP_THRESHOLD:
            try:
                # D-04/D-07: Full file mapping, cross-platform
                self._mmap = mmap.mmap(
                    self._file.fileno(),
                    0,  # Maps entire file
                    access=mmap.ACCESS_READ
                )
                self._use_mmap = True
            except (OSError, ValueError, PermissionError) as e:
                # D-03: mmap failure - fallback to normal read
                self._mmap_warning = f"mmap failed ({type(e).__name__}): {e}"
                self._use_mmap = False

    def read(self, size: int) -> bytes:
        """
        基础读取方法 - 不对原始字节进行交换。

        Args:
            size: 要读取的字节数

        Returns:
            读取的字节（原始顺序，不反转）

        Raises:
            ParseError: 若剩余字节不足

        Note:
            字节交换仅适用于数值类型（i32, u32, i64, f32等），
            由类型特定的读取方法处理。UTF-8字符串、GUID、SavedHash等
            原始字节数据不应被反转。
        """
        current_pos = self.tell()
        remaining = self._file_size - current_pos
        if size > remaining:
            raise ParseError(
                f"Cannot read {size} bytes at position {current_pos}, "
                f"only {remaining} bytes remaining"
            )

        # D-02: mmap branch
        if self._use_mmap and self._mmap:
            data = self._mmap.read(size)
            if len(data) < size:
                raise ParseError(
                    f"mmap.read() returned {len(data)} bytes, expected {size}"
                )
            return data

        return self._file.read(size)

    def seek(self, pos: int) -> None:
        """
        定位到指定位置（带边界验证，D-14）。

        Args:
            pos: 目标位置

        Raises:
            ParseError: 若 pos 超出文件大小或为负数
        """
        # D-10: use validate_offset
        self.validate_offset(pos, "seek")

        # D-02: mmap branch
        if self._use_mmap and self._mmap:
            self._mmap.seek(pos)
        else:
            self._file.seek(pos)

    def validate_offset(self, offset: int, context: str = "") -> None:
        """
        D-10: 全偏移验证 - 在定位前检查偏移有效性。

        Args:
            offset: 要验证的偏移值
            context: 上下文信息（如 "NameOffset", "ExportOffset"）

        Raises:
            ParseError: 若偏移无效（负数或超出文件大小）
        """
        if offset < 0:
            raise ParseError(
                f"Invalid offset {offset} (negative) at {context}"
            )
        if offset > self._file_size:
            raise ParseError(
                f"Offset {offset} exceeds file size {self._file_size} at {context}"
            )

    def validate_size(self, size: int, context: str = "") -> None:
        """
        D-11/D-16: PropertyTag.Size 完整验证。

        验证维度：
        1. size >= 0（非负）
        2. size <= remaining_bytes（不超剩余）
        3. size <= max_reasonable（合理上限）

        max_reasonable = 文件大小 10%，最小 1KB，最大 100MB（D-16）
        """
        if size < 0:
            raise ParseError(f"Invalid size {size} (negative) at {context}")

        current_pos = self.tell()
        remaining = self._file_size - current_pos
        if size > remaining:
            raise ParseError(f"Size {size} exceeds remaining {remaining} bytes at {context}")

        min_reasonable = 1024
        max_reasonable_cap = 100 * 1024 * 1024
        max_reasonable = max(min_reasonable, min(self._file_size // 10, max_reasonable_cap))

        if size > max_reasonable:
            raise ParseError(f"Size {size} exceeds max_reasonable {max_reasonable} at {context}")

    def tell(self) -> int:
        """返回当前位置"""
        if self._use_mmap and self._mmap:
            return self._mmap.tell()
        return self._file.tell()

    def close(self) -> None:
        """关闭文件和 mmap（D-05 统一关闭）"""
        # D-05: Unified close - release mmap then file
        if self._mmap:
            self._mmap.close()
            self._mmap = None
        if self._file:
            self._file.close()
            self._file = None
        self._use_mmap = False

    def set_byte_swapping(self, enabled: bool) -> None:
        """设置字节交换标志（D-11）"""
        self._byte_swapping = enabled

    def total_size(self) -> int:
        """返回文件总大小"""
        return self._file_size

    def get_mmap_info(self) -> Dict:
        """返回 mmap 状态信息（D-03）"""
        return {
            "used": self._use_mmap,
            "warning": self._mmap_warning
        }

    # ========================================================================
    # 类型读取方法（使用 struct.unpack 配合字节序感知格式）
    # ========================================================================

    def read_u8(self) -> int:
        """读取 unsigned 8-bit integer（字节序无关）"""
        return struct.unpack('<B', self.read(1))[0]

    def read_bytes(self, n: int) -> bytes:
        """读取原始字节（无字节序交换，Phase 6 D-10）"""
        return self.read(n)

    def read_i32(self) -> int:
        """读取 signed 32-bit integer（支持字节交换）"""
        fmt = '>' if self._byte_swapping else '<'
        return struct.unpack(fmt + 'i', self.read(4))[0]

    def read_u16(self) -> int:
        """读取 unsigned 16-bit integer（支持字节交换）"""
        fmt = '>' if self._byte_swapping else '<'
        return struct.unpack(fmt + 'H', self.read(2))[0]

    def read_u32(self) -> int:
        """读取 unsigned 32-bit integer（支持字节交换）"""
        fmt = '>' if self._byte_swapping else '<'
        return struct.unpack(fmt + 'I', self.read(4))[0]

    def read_i64(self) -> int:
        """读取 signed 64-bit integer（支持字节交换）"""
        fmt = '>' if self._byte_swapping else '<'
        return struct.unpack(fmt + 'q', self.read(8))[0]

    def read_u64(self) -> int:
        """读取 unsigned 64-bit integer（支持字节交换）"""
        fmt = '>' if self._byte_swapping else '<'
        return struct.unpack(fmt + 'Q', self.read(8))[0]

    def read_f32(self) -> float:
        """读取 32-bit float（支持字节交换）"""
        fmt = '>' if self._byte_swapping else '<'
        return struct.unpack(fmt + 'f', self.read(4))[0]

    def read_f64(self) -> float:
        """读取 64-bit double（支持字节交换）"""
        fmt = '>' if self._byte_swapping else '<'
        return struct.unpack(fmt + 'd', self.read(8))[0]

    def read_fstring(self) -> str:
        """
        读取 UE FString（带长度前缀的字符串，D-10 仅 UTF-8）。

        UE 5.x 格式：
        - length > 0: UTF-8 编码
        - length == 0: 空字符串
        - length < 0: 空字符串（UTF-16 标记，UE5 已弃用）

        Returns:
            解析后的字符串（去除 null 终止符）
        """
        length = self.read_i32()

        if length == 0:
            return ""

        if length < 0:
            # UE 5.x 不应出现 UTF-16，但作为防御性处理
            # length < 0 表示 UTF-16 编码，实际长度为 -length * 2
            # WR-02 fix: Sanity check for overflow prevention
            utf16_len = -length * 2
            if utf16_len > 10_000_000:  # Sanity check for overflow
                raise ParseError(f"UTF-16 string length {utf16_len} too large")
            self.read(utf16_len)  # 跳过 UTF-16 数据
            return ""

        # UTF-8 编码（UE 5.x 标准）
        data = self.read(length)
        return data.decode('utf-8', errors='replace').rstrip('\x00')

    def read_name(self, name_map: List[str]) -> str:
        """
        读取 FName（名称表索引 + 实例编号）。

        Args:
            name_map: 已解析的名称表

        Returns:
            解析后的名称字符串（如 "ObjectName_0"）
        """
        index = self.read_u32()
        number = self.read_u32()

        if 0 <= index < len(name_map):
            base_name = name_map[index]
            # 实例编号 > 0 时添加后缀
            if number > 0:
                return f"{base_name}_{number}"
            return base_name

        return "None"


# ============================================================================
# Dataclass 模型（D-06 使用 dataclasses）
# ============================================================================

@dataclass
class GenerationInfo:
    """
    FGenerationInfo 版本世代信息。

    来自 UE 源码 PackageFileSummary.h：
    记录包的编辑世代信息，用于增量保存。
    """
    export_count: int = 0  # 该世代导出数量
    name_count: int = 0    # 该世代名称数量


@dataclass
class EngineVersion:
    """
    FEngineVersion 引擎版本信息。

    来自 UE 源码 EngineVersion.h：
    记录保存文件的引擎版本。
    """
    major: int = 0       # 主版本号 (u16)
    minor: int = 0       # 次版本号 (u16)
    patch: int = 0       # 补丁版本号 (u16)
    changelist: int = 0  # Changelist 号 (u32)
    branch: str = ""     # 分支名 (FString)


@dataclass
class CustomVersion:
    """
    自定义版本（D-05 存储 GUID 不验证）。

    UE 使用 GUID 为键的子系统版本系统。
    """
    guid: str      # GUID 字符串格式（16 bytes）
    version: int   # 子系统版本号


@dataclass
class PackageIndex:
    """
    FPackageIndex 编码（D-07 存原始 int32）。

    来自 ObjectResource.h：
    - Index > 0: ExportMap[Index - 1]
    - Index < 0: ImportMap[-Index - 1]
    - Index = 0: null
    """
    index: int     # 原始有符号值

    @property
    def is_import(self) -> bool:
        """是否为导入引用（负数）"""
        return self.index < 0

    @property
    def is_export(self) -> bool:
        """是否为导出引用（正数）"""
        return self.index > 0

    @property
    def is_null(self) -> bool:
        """是否为空引用（零）"""
        return self.index == 0

    def to_import_index(self) -> int:
        """转换为导入表索引（-Index - 1）"""
        return -self.index - 1

    def to_export_index(self) -> int:
        """转换为导出表索引（Index - 1）"""
        return self.index - 1


def resolve_package_index_to_reference(
    pkg_idx: PackageIndex,
    import_map: List["ObjectImport"],
    export_map: List["ObjectExport"],
    name_map: List[str]
) -> Optional[Dict[str, Any]]:
    """
    解析FPackageIndex为可读对象引用信息。

    Phase 11-02: 增强ObjectProperty解析返回可读对象引用。

    Args:
        pkg_idx: PackageIndex对象（已解码的FPackageIndex）
        import_map: ImportMap列表
        export_map: ExportMap列表
        name_map: NameMap列表（用于解析FName索引）

    Returns:
        None if pkg_idx.is_null
        {"type": "import", "class_name": str, "object_name": str, "package": str} if import
        {"type": "export", "class_name": str, "object_name": str} if export
    """
    if pkg_idx.is_null:
        return None

    if pkg_idx.is_import:
        imp_idx = pkg_idx.to_import_index()
        if 0 <= imp_idx < len(import_map):
            imp = import_map[imp_idx]
            # class_name 和 object_name 可能是 FName 索引或已解析字符串
            class_name = name_map[imp.class_name] if isinstance(imp.class_name, int) else imp.class_name
            object_name = name_map[imp.object_name] if isinstance(imp.object_name, int) else imp.object_name
            package = name_map[imp.class_package] if isinstance(imp.class_package, int) else imp.class_package
            return {
                "type": "import",
                "class_name": class_name,
                "object_name": object_name,
                "package": package
            }

    elif pkg_idx.is_export:
        exp_idx = pkg_idx.to_export_index()
        if 0 <= exp_idx < len(export_map):
            exp = export_map[exp_idx]
            # 类名可能需要递归解析class_index
            class_name = _resolve_class_name(exp.class_index, import_map, export_map, name_map)
            object_name = name_map[exp.object_name] if isinstance(exp.object_name, int) else exp.object_name
            return {
                "type": "export",
                "class_name": class_name,
                "object_name": object_name
            }

    return None  # 索引越界等异常情况


def _resolve_class_name(
    class_index: PackageIndex,
    import_map: List["ObjectImport"],
    export_map: List["ObjectExport"],
    name_map: List[str]
) -> str:
    """
    递归解析class_index获取类名。

    Phase 11-02: 辅助函数用于解析导出对象的类名。

    Args:
        class_index: PackageIndex对象（类引用）
        import_map: ImportMap列表
        export_map: ExportMap列表
        name_map: NameMap列表

    Returns:
        类名字符串，如果无法解析则返回 "Unknown"
    """
    if class_index.is_null or class_index.index == 0:
        return "None"

    resolved = resolve_package_index_to_reference(class_index, import_map, export_map, name_map)
    if resolved:
        return resolved.get("class_name", "Unknown")
    return "Unknown"


def validate_package_index(
    index: PackageIndex,
    import_map: List["ObjectImport"],
    export_map: List["ObjectExport"],
    context: str = ""
) -> Optional[str]:
    """
    D-12/D-17: PackageIndex 完整验证。

    验证维度：范围验证、失败信息、类型一致性、目标有效性
    Returns: None if valid, warning string if invalid
    """
    if index.is_null:
        return None

    if index.is_import:
        import_idx = index.to_import_index()
        if not (0 <= import_idx < len(import_map)):
            return f"PackageIndex {index.index} import out of range at {context}"
        return None

    elif index.is_export:
        export_idx = index.to_export_index()
        if not (0 <= export_idx < len(export_map)):
            return f"PackageIndex {index.index} export out of range at {context}"
        return None

    return f"PackageIndex {index.index} invalid at {context}"


@dataclass
class PackageFileSummary:
    """
    PackageFileSummary 文件头（D-08 读取所有字段）。

    来自 PackageFileSummary.h：
    包含版本信息、偏移量、计数等完整文件头数据。
    字段顺序按 UE 源码 PackageFileSummary.cpp 序列化顺序。
    """
    tag: int                            # 魔术标签（0x9E2A83C1）
    legacy_file_version: int            # -2 至 -9（D-04）
    file_version_ue4: int               # UE4 版本号
    legacy_ue3_version: int = 0         # LegacyUE3版本（仅 legacy != -4）
    file_version_ue5: int = 0           # UE5 版本号（仅 legacy <= -8）
    file_version_licensee: int = 0      # Licensee 版本
    saved_hash: bytes = field(default_factory=lambda: b'')  # FIoHash (20 bytes) for UE5 >= 1016
    total_header_size: int = 0          # 文件头总大小
    custom_versions: List[CustomVersion] = field(default_factory=list)  # D-05
    package_name: str = ""              # PackageName FString
    package_flags: int = 0              # D-12 仅存储

    # 名称表字段（按 UE 源码顺序）
    name_count: int = 0
    name_offset: int = 0

    # 软对象路径（UE5 >= 1008，在 NameOffset 之后、LocalizationId 之前）
    soft_object_paths_count: int = 0
    soft_object_paths_offset: int = 0

    # UE4 专用字段（在 SoftObjectPaths 之后）
    localization_id: str = ""           # UE4 >= 385
    gatherable_text_data_count: int = 0  # UE4 >= 401
    gatherable_text_data_offset: int = 0  # UE4 >= 401

    # 导出表字段（Export 在 Import 之前！）
    export_count: int = 0
    export_offset: int = 0

    # 导入表字段
    import_count: int = 0
    import_offset: int = 0

    # Cell Export/Import（UE5 >= 1015 VERSE_CELLS）
    cell_export_count: int = 0
    cell_export_offset: int = 0
    cell_import_count: int = 0
    cell_import_offset: int = 0

    # MetaData Offset（UE5 >= 1014）
    metadata_offset: int = 0

    # Depends Offset（通用字段）
    depends_offset: int = 0

    # Soft Package References（UE4 >= 382）
    soft_package_references_count: int = 0
    soft_package_references_offset: int = 0

    # Searchable Names（UE4 >= 508）
    searchable_names_offset: int = 0

    # Thumbnail Table（通用字段）
    thumbnail_table_offset: int = 0

    # Import Type Hierarchies（UE5 >= 1018）
    import_type_hierarchies_count: int = 0
    import_type_hierarchies_offset: int = 0

    # Guid（UE5 < 1016，Legacy Guid，16 bytes）- 已合并到 saved_hash
    # Persistent Guid（UE4 >= 516，WITH_EDITORONLY_DATA）
    persistent_guid: str = ""  # FGuid hex string

    # Generations 和引擎版本（通用字段）
    generations: List[GenerationInfo] = field(default_factory=list)
    saved_by_engine_version: EngineVersion = field(default_factory=EngineVersion)
    compatible_with_engine_version: EngineVersion = field(default_factory=EngineVersion)

    # 压缩和包源（通用字段）
    compression_flags: int = 0
    package_source: int = 0

    # Asset Registry Data（通用字段）
    asset_registry_data_offset: int = 0

    # Bulk Data Start Offset（通用字段）
    bulk_data_start_offset: int = 0

    # World Tile Info（UE4 >= 223）
    world_tile_info_data_offset: int = 0

    # Chunk IDs（UE4 >= 277）
    chunk_ids: List[str] = field(default_factory=list)  # FGuid hex strings

    # Preload Dependencies（UE4 >= 505）
    preload_dependency_count: int = 0
    preload_dependency_offset: int = 0

    # NamesReferencedFromExportDataCount（UE5 >= 1001，在文件头末尾！）
    names_referenced_from_export_data_count: int = 0

    # Payload Toc Offset（UE5 >= 1002）
    payload_toc_offset: int = 0

    # Data Resource Offset（UE5 >= 1009）
    data_resource_offset: int = 0


@dataclass
class ObjectImport:
    """
    FObjectImport 导入表条目（CORE-04）。

    来自 ObjectResource.h：
    表示外部依赖（其他包中的对象引用）。

    Phase 10 Gap #2 修复：添加 UE5 条件字段（PackageName, bImportOptional）。
    """
    class_package: str      # 来源包名（FName 解析后）
    class_name: str         # 类名（FName 解析后）
    outer_index: PackageIndex  # Outer 引用
    object_name: str        # 对象名（FName 解析后）
    # UE5 条件字段（Phase 10 Gap #2 修复）
    package_name: Optional[str] = None   # PackageName（UEVer >= 518 且 !FilterEditorOnly）
    b_import_optional: Optional[bool] = None  # bImportOptional（UEVer >= 1003）


@dataclass
class ObjectExport:
    """
    FObjectExport 导出表条目（CORE-05/CORE-06, Phase 6 BUG-01/BUG-02）。

    来自 ObjectResource.h：表示包内对象定义。

    Phase 6 D-04/D-16/D-17: 完整字段实现。
    字段顺序遵守 Python dataclass 规则：必填字段在前，可选字段在后。
    注意：dataclass 定义顺序与 UE 源码读取顺序不同（UE 读取顺序在 read_export_map 中实现）。
    """
    # 必填字段（无默认值）
    class_index: PackageIndex      # 类引用（CORE-06 资产类型识别）
    super_index: PackageIndex      # 父类引用
    outer_index: PackageIndex      # Outer 引用
    object_name: str               # 对象名
    object_flags: int              # EObjectFlags
    serial_size: int               # 序列化数据大小
    serial_offset: int             # 序列化数据偏移
    # 可选/条件字段（有默认值）
    template_index: PackageIndex = field(default_factory=lambda: PackageIndex(0))  # D-04/D-01: TemplateIndex（UE4 >= 506）
    # bool flags（D-07）
    b_forced_export: bool = False
    b_not_for_client: bool = False
    b_not_for_server: bool = False
    # 条件 bool flags（D-08）
    b_is_inherited_instance: Optional[bool] = None  # UE5 >= 1011
    package_flags: int = 0         # D-09: PackageFlags
    # 其他条件 bool flags（D-08）
    b_not_always_loaded_for_editor_game: Optional[bool] = None
    b_is_asset: Optional[bool] = None
    b_generate_public_hash: Optional[bool] = None
    # UE5+ 字段
    script_serial_size: int = 0
    script_serial_offset: int = 0
    # 属性列表 (Phase 2 PROP-01 至 PROP-08)
    properties: List["PropertyValue"] = field(default_factory=list)


@dataclass
class PropertyTag:
    """
    PropertyTag 结构（PROP-01）。

    来自 PropertyTag.h lines 37-105:
    FPropertyTag 包含属性元信息，用于标识属性类型和大小。
    """
    name: str                         # 属性名（FName）
    type: str                         # 类型名字符串（如 "IntProperty")
    size: int                         # 序列化数据大小（字节）
    array_index: int = 0              # 数组元素索引（默认 0）
    flags: int = 0                    # EPropertyTagFlags 标志位
    property_guid: Optional[bytes] = None  # 16 bytes GUID（HasPropertyGuid 时）
    bool_val: int = 0                 # BoolProperty 值（BoolTrue 标志位）


@dataclass
class PropertyValue:
    """
    属性值容器（D-08/D-09）。

    存储解析后的属性值，使用 Python 原生类型。
    """
    name: str                         # 属性名
    type: str                         # 属性类型
    value: any = None                 # 解析后的值（int, float, str, list 等）
    array_index: int = 0              # 数组元素索引


# ============================================================================
# Phase 9: 高级属性类型 dataclass 定义
# ============================================================================

@dataclass
class AdvancedPropertyValue:
    """
    高级属性值基类（D-07a）。

    统一基类设计，包含 property_type 字段用于类型识别。
    所有高级属性 dataclass 继承此基类。

    来自 CONTEXT.md D-07a。
    """
    property_type: str  # 属性类型名（如 "StructProperty", "MapProperty")


@dataclass
class StructValue(AdvancedPropertyValue):
    """
    StructProperty 值容器（D-01a）。

    格式：{struct_type: str, fields: dict}
    嵌套结构体解析，递归深度限制 5（D-01）。

    来自 PropertyStruct.cpp §167-172。
    """
    struct_type: str              # 结构体类型名
    fields: Dict[str, Any]        # 嵌套字段（递归解析）


@dataclass
class MapValue(AdvancedPropertyValue):
    """
    MapProperty 值容器（D-02a）。

    格式：{key_type: str, value_type: str, entries: List[{key: Any, value: Any}]}
    支持基本类型、枚举、Struct、Object 键（D-02）。

    来自 PropertyMap.cpp §267-880。
    """
    key_type: str                 # 键类型名
    value_type: str               # 值类型名
    entries: List[Dict[str, Any]] # 键值对列表


@dataclass
class SetValue(AdvancedPropertyValue):
    """
    SetProperty 值容器（D-03a）。

    格式：{element_type: str, elements: List[Any]}
    解析为 List，不验证唯一性（D-03）。

    来自 PropertySet.cpp §221-427。
    """
    element_type: str             # 元素类型名
    elements: List[Any]           # 元素列表


@dataclass
class EnumValue(AdvancedPropertyValue):
    """
    EnumProperty 值容器（D-04a）。

    格式：{enum_type: str, value_name: str}
    返回枚举值名（如 'EWalletState::Active'）（D-04）。

    来自 EnumProperty.cpp §279-353。
    """
    enum_type: str                # 枚举类型名
    value_name: str               # 枚举值名（包含类型前缀）


@dataclass
class TextValue(AdvancedPropertyValue):
    """
    TextProperty 值容器（D-05a）。

    格式：{namespace: str, key: str, source_string: str}
    完整 FText 结构返回（D-05）。

    来自 TextProperty.cpp §135-139。
    """
    namespace: str                # 本地化命名空间
    key: str                      # 本地化键
    source_string: str            # 源字符串


@dataclass
class DelegateValue(AdvancedPropertyValue):
    """
    DelegateProperty 值容器（D-06a）。

    格式：{object_ref: int, function_name: str}
    原始引用格式，延迟解析（D-06b）。

    来自 PropertyDelegate.cpp §86-89。
    """
    object_ref: int               # FPackageIndex 原始值
    function_name: str            # 函数名（FName）


@dataclass
class FEdGraphPinType:
    """
    Pin type structure from EdGraphPin.h lines 76-225.

    Per D-08: full structure parsing, not just name formatting.
    Per RESEARCH.md Pitfall 1: version-aware serialization with FFrameworkObjectVersion checks.
    ContainerType added in FFrameworkObjectVersion::EdGraphPinContainerType.
    bIsConst added in VER_UE4_SERIALIZE_PINTYPE_CONST.
    bIsUObjectWrapper added in FReleaseObjectVersion::PinTypeIncludesUObjectWrapperFlag.
    """
    pin_category: str = ""           # FName (RenderName, bool, int, etc.)
    pin_sub_category: str = ""       # FName (sub-type, e.g., "Int" for Integer)
    pin_sub_category_object: int = 0 # FPackageIndex (resolved to class name)
    container_type: int = 0          # EPinContainerType: 0=None, 1=Array, 2=Set, 3=Map
    is_reference: bool = False
    is_const: bool = False           # Added in VER_UE4_SERIALIZE_PINTYPE_CONST
    is_weak_pointer: bool = False
    is_uobject_wrapper: bool = False # Added in FReleaseObjectVersion::PinTypeIncludesUObjectWrapperFlag


@dataclass
class BlueprintVariable:
    """
    Variable definition from FBPVariableDescription.

    Per D-05/D-06: use UE original names with container prefix.
    """
    var_name: str                    # FName
    var_type: "FEdGraphPinType"      # Full type structure (defined next)
    category: str                    # FText (simplified to string)
    property_flags: int              # uint64 EPropertyFlags
    default_value: any = None        # Parsed or raw string per D-13/D-14
    friendly_name: str = ""          # FString


@dataclass
class BlueprintMetadata:
    """
    Blueprint metadata extracted from ExportMap.

    Per D-01/D-02/D-03: auto-detect with warning on failure.
    Per D-04: deferred BlueprintType detection (normal:class->ImportExport).
    """
    is_blueprint: bool
    parent_class: Optional[str] = None  # Per D-09: only direct parent
    variables: List["BlueprintVariable"] = field(default_factory=list)
    detection_warning: Optional[str] = None  # Per D-03


# ============================================================================
# Phase 7: Blueprint Graph Data Classes (GRAPH-01 to GRAPH-10)
# ============================================================================

@dataclass
class UEdGraphPin:
    """
    UEdGraphPin 蓝图引脚完整结构（GRAPH-04）。

    来自 UE 源码 EdGraphPin.h 第 76-225 行。

    Per D-01/D-01a: LinkedTo 存储为原始数据列表，Phase 8 构建连接映射。
    """
    pin_id: str                          # FGuid hex（16 bytes）
    pin_name: str                        # FName 解析结果
    direction: int                       # uint8: 0=Input, 1=Output, 2=None (EGPD_Input/Output/None)
    pin_type: "FEdGraphPinType"          # Phase 3 已实现的引脚类型结构
    default_value: Optional[str] = None  # FString - 默认值
    auto_default_value: Optional[str] = None  # FString - 自动生成的默认值
    linked_to_raw: List[str] = field(default_factory=list)  # D-01a: 原始连接数据列表
    sub_pins: List[str] = field(default_factory=list)       # SubPin PinIds（GUID hex）
    parent_pin: Optional[str] = None                        # ParentPin PinId（GUID hex）
    flags: int = 0                                          # uint8 bitfield


@dataclass
class UEdGraphNode:
    """
    UEdGraphNode 蓝图节点基类（GRAPH-03）。

    来自 UE 源码 EdGraphNode.h + K2Node.h。

    Per D-02: 基类字段 + 类型特定数据（node_data 多态）。
    Per D-02b: class_name 用于类型识别分派。
    """
    node_guid: str                       # FGuid hex（16 bytes）
    node_pos_x: int = 0                  # int32 - 编辑器位置 X
    node_pos_y: int = 0                  # int32 - 编辑器位置 Y
    node_comment: str = ""               # FString - 注释文本
    pins: List["UEdGraphPin"] = field(default_factory=list)  # 引脚列表
    class_name: str = ""                 # 类型识别结果（K2Node_CallFunction 等）
    node_data: Optional[any] = None      # 类型特定数据（多态）


@dataclass
class UEdGraph:
    """
    UEdGraph 蓝图图容器（GRAPH-02）。

    来自 UE 源码 EdGraph.h。

    Per D-03: 完整解析 Graph→Node→Pin 三层结构。
    Per D-04: 顶层 graphs 字段，与 blueprint 同级。
    """
    graph_name: str                      # 导出 ObjectName
    graph_class: str                     # ClassIndex 解析结果（EdGraph/UberEdGraph）
    schema: Optional[str] = None         # FPackageIndex 解析 - 图 Schema
    nodes: List["UEdGraphNode"] = field(default_factory=list)  # 节点列表
    graph_guid: Optional[str] = None     # FGuid hex（16 bytes）
    b_editable: bool = True              # uint8 - 是否可编辑


@dataclass
class FMemberReference:
    """
    FMemberReference 成员引用结构（GRAPH-05/06）。

    用于 K2Node_CallFunction 的 FunctionReference 和 K2Node_Event 的 EventReference。

    来自 UE 源码 UObject.h - FSimpleMemberReference / FMemberReference。
    """
    member_parent: Optional[str] = None  # 类路径（FPackageIndex 解析结果）
    member_name: str = ""                # FName - 函数/事件名
    member_guid: Optional[str] = None    # FGuid hex（16 bytes）- 函数 GUID
    b_self_context: bool = False         # uint8 - self 调用标志


# ============================================================================
# 节点类型特定数据类（GRAPH-05~09）
# ============================================================================

@dataclass
class K2NodeCallFunction:
    """
    K2Node_CallFunction 特有数据（GRAPH-05）。

    来自编辑器导出格式验证：
    FunctionReference=(MemberName="Jump",bSelfContext=True)

    Per RESEARCH.md L546-555: FunctionReference + bDefaultsToPureFunc
    """
    function_reference: FMemberReference
    b_defaults_to_pure: bool = False      # uint8 - 是否为纯函数


@dataclass
class K2NodeEvent:
    """
    K2Node_Event 特有数据（GRAPH-06）。

    来自编辑器导出格式验证：
    EventReference=(MemberParent="/Script/Engine.BPGenClass",MemberName="Touch Jump Start",MemberGuid=...)

    Per RESEARCH.md L556-562: EventReference + bOverrideFunction
    """
    event_reference: FMemberReference
    b_override_function: bool = False     # uint8 - 是否为重写函数


@dataclass
class K2NodeKnot:
    """
    K2Node_Knot 特有数据（GRAPH-07）。

    Knot 节点（ reroute node）无额外字段，仅 InputPin/OutputPin 在基类 Pins 数组。

    Per RESEARCH.md L563-566: 无额外字段
    """
    pass  # 仅基类字段


@dataclass
class EdGraphNodeComment:
    """
    EdGraphNode_Comment 特有数据（GRAPH-08）。

    来自编辑器导出格式验证（test/编辑器中复制出的文本.txt L21-32, L275-302）：
    CommentColor=(R=0.050980,G=0.050980,B=0.050980,A=1.000000)
    NodeWidth=1440
    NodeHeight=544
    FontSize=14

    Per RESEARCH.md L567-574: CommentColor + NodeWidth/Height + FontSize
    """
    comment_color: Tuple[float, float, float, float] = (0.05, 0.05, 0.05, 1.0)  # RGBA
    node_width: int = 0                   # int32 - 注释框宽度
    node_height: int = 0                  # int32 - 注释框高度
    font_size: int = 14                   # int32 - 字体大小


@dataclass
class K2NodeEnhancedInputAction:
    """
    K2Node_EnhancedInputAction 特有数据（GRAPH-09）。

    来自编辑器导出格式验证（test/编辑器中复制出的文本.txt L58-99）：
    InputAction="/Script/EnhancedInput.InputAction'/Game/Input/Actions/IA_Look.IA_Look'"

    Per RESEARCH.md L575-580: InputAction (FSoftObjectPath)
    """
    input_action_path: str = ""           # FSoftObjectPath AssetPath 字符串


@dataclass
class ParseResult:
    """
    解析结果（D-15 部分结果）。

    包含解析后的所有数据和错误信息。

    Per D-04/D-04b: graphs 字段为顶层字段，与 blueprint 同级。
    """
    summary: Optional[PackageFileSummary] = None
    name_map: List[str] = field(default_factory=list)
    import_map: List[ObjectImport] = field(default_factory=list)
    export_map: List[ObjectExport] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)  # 收集所有错误
    blueprint: Optional["BlueprintMetadata"] = None  # Per D-02: auto-extracted
    graphs: List["UEdGraph"] = field(default_factory=list)  # Phase 7: 蓝图图数据
    is_success: bool = False
    # D-02/D-03: mmap tracking (Phase 5)
    mmap_used: bool = False
    mmap_warning: Optional[str] = None
    warnings: List[str] = field(default_factory=list)  # D-13: for Wave 4
    # Phase 10: 依赖分析字段（D-10-05/08/13）
    imports: List[Dict] = field(default_factory=list)           # D-10-05: ImportMap 依赖列表
    soft_references: List[Dict] = field(default_factory=list)   # D-10-08: SoftObjectPaths 软引用列表
    circular_deps: List[List[str]] = field(default_factory=list) # D-10-13: 循环依赖路径


# ============================================================================
# 解析函数
# ============================================================================

def read_package_summary(archive: FArchive) -> PackageFileSummary:
    """
    读取 PackageFileSummary 文件头（CORE-01/CORE-02/CORE-08）。

    来自 PackageFileSummary.cpp：
    读取魔术标签、检测字节序、验证版本、读取所有字段。

    字段读取顺序严格按 UE 源码 PackageFileSummary.cpp 序列化顺序（lines 178-539）：
    Tag → LegacyFileVersion → LegacyUE3Version → FileVersionUE4 → FileVersionUE5 →
    FileVersionLicensee → SavedHash(UE5>=1016) → CustomVersions → TotalHeaderSize(UE4) →
    PackageName → PackageFlags → NameCount → NameOffset →
    SoftObjectPaths(UE5>=1008) → LocalizationId(UE4) → GatherableTextData(UE4) →
    ExportCount → ExportOffset → ImportCount → ImportOffset →
    CellExport/CellImport(UE5>=1015) → MetaDataOffset(UE5>=1014) → DependsOffset →
    SoftPackageReferences(UE4>=382) → SearchableNames(UE4>=508) → ThumbnailTable →
    ImportTypeHierarchies(UE5>=1018) → Guid(UE5<1016) → PersistentGuid(UE4>=516) →
    Generations → EngineVersion → CompressionFlags → CompressedChunks → PackageSource →
    AdditionalPackagesToCook → NumTextureAllocations(legacy) → AssetRegistryData →
    BulkDataStart → WorldTileInfo(UE4>=223) → ChunkIDs(UE4>=277) → PreloadDependencies(UE4>=505) →
    NamesReferencedCount(UE5>=1001, 末尾!) → PayloadToc(UE5>=1002) → DataResource(UE5>=1009)

    Args:
        archive: FArchive 实例

    Returns:
        PackageFileSummary dataclass

    Raises:
        VersionError: 若版本不支持
        ParseError: 若解析失败
    """
    archive.seek(0)

    # === 第 1 步：魔数和版本号 ===
    tag = archive.read_u32()

    if tag == PACKAGE_FILE_TAG_SWAPPED:
        archive.set_byte_swapping(True)
        tag = PACKAGE_FILE_TAG
    elif tag != PACKAGE_FILE_TAG:
        raise VersionError(f"Invalid package tag: {hex(tag)}")

    legacy_file_version = archive.read_i32()

    if legacy_file_version < LEGACY_FILE_VERSION_MIN or legacy_file_version > LEGACY_FILE_VERSION_MAX:
        raise VersionError(f"Unsupported legacy version: {legacy_file_version}")

    # LegacyUE3Version（仅在 legacy_file_version != -4 时存在）
    if legacy_file_version != -4:
        legacy_ue3_version = archive.read_i32()
    else:
        legacy_ue3_version = 0

    # UE4 版本
    file_version_ue4 = archive.read_i32()

    # UE5 版本（仅在 legacy_file_version <= -8 时存在）
    if legacy_file_version <= -8:
        file_version_ue5 = archive.read_i32()
    else:
        file_version_ue5 = 0

    if legacy_file_version <= -8 and file_version_ue5 < UE5_VERSION_MIN:
        raise VersionError(f"Unsupported UE5 version: {file_version_ue5}")

    # Licensee 版本
    file_version_licensee = archive.read_i32()

    # === 第 2 步：SavedHash（UE5 >= 1016）===
    # PackageFileSummary.cpp line 181-196: SavedHash 读取
    saved_hash = b''
    total_header_size = 0
    is_ue4_file = legacy_file_version > -8

    if legacy_file_version <= -8 and file_version_ue5 >= UE5_PACKAGE_SAVED_HASH:
        saved_hash = archive.read(20)  # FIoHash = 20 bytes
        # TotalHeaderSize 在 SavedHash 之后立即读取（UE5 >= 1016）
        total_header_size = archive.read_i32()

    # === 第 3 步：CustomVersions ===
    # PackageFileSummary.cpp line 198-208
    custom_versions_count = archive.read_u32()
    if custom_versions_count > MAX_CUSTOM_VERSIONS:
        raise ParseError(f"Custom versions count exceeds maximum")
    custom_versions: List[CustomVersion] = []
    for _ in range(custom_versions_count):
        guid_bytes = archive.read(16)
        version = archive.read_i32()
        custom_versions.append(CustomVersion(guid=guid_bytes.hex(), version=version))

    # === 第 4 步：TotalHeaderSize（UE4 文件）===
    if is_ue4_file:
        total_header_size = archive.read_i32()

    # === 第 5 步：PackageName 和 PackageFlags ===
    package_name = archive.read_fstring()
    package_flags = archive.read_u32()

    # === 第 6 步：NameCount 和 NameOffset ===
    # PackageFileSummary.cpp line 278
    name_count = archive.read_i32()
    if name_count > MAX_NAME_COUNT:
        raise ParseError(f"Name count exceeds maximum")
    name_offset = archive.read_i32()
    archive.validate_offset(name_offset, "NameOffset")

    # === 第 7 步：SoftObjectPaths（UE5 >= 1008，在 NameOffset 之后！）===
    # PackageFileSummary.cpp line 282-285
    soft_object_paths_count = 0
    soft_object_paths_offset = 0
    if not is_ue4_file and file_version_ue5 >= UE5_ADD_SOFTOBJECTPATH_LIST:
        soft_object_paths_count = archive.read_i32()
        soft_object_paths_offset = archive.read_i32()

    # === 第 8 步：LocalizationId（未烘焙文件）===
    # PackageFileSummary.cpp line 287-292: wrapped in !IsFilterEditorOnly()
    # 对于未烘焙文件（PKG_Cooked 未设置），LocalizationId 应该被序列化
    # 版本检查: FileVersionUE >= VER_UE4_ADDED_PACKAGE_SUMMARY_LOCALIZATION_ID (385)
    # 对于 UE5 文件，FileVersionUE5 >= 1000 总是 >= 385
    localization_id = ""
    is_cooked = (package_flags & PKG_Cooked) != 0
    if not is_cooked:
        # 版本检查：对于 UE5 文件总是满足，对于 UE4 文件检查 >= 385
        if is_ue4_file and file_version_ue4 >= UE4_ADDED_PACKAGE_SUMMARY_LOCALIZATION_ID:
            localization_id = archive.read_fstring()
        elif not is_ue4_file:  # UE5 文件，版本总是 >= 385
            localization_id = archive.read_fstring()

    # === 第 9 步：GatherableTextData（所有文件）===
    # PackageFileSummary.cpp line 295-298: 不在 IsFilterEditorOnly() 检查内！
    # 版本检查: FileVersionUE >= VER_UE4_SERIALIZE_TEXT_IN_PACKAGES (401)
    # 对于 UE5 文件，FileVersionUE5 >= 1000 总是 >= 401（operator>= 用 UE4 分支）
    gatherable_text_data_count = 0
    gatherable_text_data_offset = 0
    if file_version_ue4 >= UE4_SERIALIZE_TEXT_IN_PACKAGES or not is_ue4_file:
        gatherable_text_data_count = archive.read_i32()
        gatherable_text_data_offset = archive.read_i32()

    # === 第 10 步：ExportCount 和 ExportOffset ===
    # PackageFileSummary.cpp line 299
    export_count = archive.read_i32()
    if export_count > MAX_EXPORT_COUNT:
        raise ParseError(f"Export count exceeds maximum")
    export_offset = archive.read_i32()
    archive.validate_offset(export_offset, "ExportOffset")

    # === 第 11 步：ImportCount 和 ImportOffset ===
    # PackageFileSummary.cpp line 300
    import_count = archive.read_i32()
    if import_count > MAX_IMPORT_COUNT:
        raise ParseError(f"Import count exceeds maximum")
    import_offset = archive.read_i32()
    archive.validate_offset(import_offset, "ImportOffset")

    # === 第 12 步：CellExport/CellImport（UE5 >= 1015 VERSE_CELLS）===
    # PackageFileSummary.cpp line 302-306
    cell_export_count = 0
    cell_export_offset = 0
    cell_import_count = 0
    cell_import_offset = 0
    if not is_ue4_file and file_version_ue5 >= UE5_VERSE_CELLS:
        cell_export_count = archive.read_i32()
        cell_export_offset = archive.read_i32()
        cell_import_count = archive.read_i32()
        cell_import_offset = archive.read_i32()

    # === 第 13 步：MetaDataOffset（UE5 >= 1014）===
    # PackageFileSummary.cpp line 308-310
    metadata_offset = 0
    if not is_ue4_file and file_version_ue5 >= UE5_METADATA_SERIALIZATION_OFFSET:
        metadata_offset = archive.read_i32()

    # === 第 14 步：DependsOffset ===
    # PackageFileSummary.cpp line 313
    depends_offset = archive.read_i32()

    # === 第 15 步：SoftPackageReferences（UE4 >= 382）===
    # PackageFileSummary.cpp line 315-318
    soft_package_references_count = 0
    soft_package_references_offset = 0
    if file_version_ue4 >= UE4_ADD_STRING_ASSET_REFERENCES_MAP:
        soft_package_references_count = archive.read_i32()
        soft_package_references_offset = archive.read_i32()

    # === 第 16 步：SearchableNames（UE4 >= 508）===
    # PackageFileSummary.cpp line 320-323
    searchable_names_offset = 0
    if file_version_ue4 >= UE4_ADDED_SEARCHABLE_NAMES:
        searchable_names_offset = archive.read_i32()

    # === 第 17 步：ThumbnailTableOffset ===
    # PackageFileSummary.cpp line 325
    thumbnail_table_offset = archive.read_i32()

    # === 第 18 步：ImportTypeHierarchies（UE5 >= 1018）===
    # PackageFileSummary.cpp line 327-335
    import_type_hierarchies_count = 0
    import_type_hierarchies_offset = 0
    if not is_ue4_file and file_version_ue5 >= UE5_IMPORT_TYPE_HIERARCHIES:
        import_type_hierarchies_count = archive.read_i32()
        import_type_hierarchies_offset = archive.read_i32()

    # === 第 19 步：Legacy Guid（UE5 < 1016 或 UE4）===
    # PackageFileSummary.cpp line 337-352: 对于 UE5 < 1016 或 UE4 文件，读取 FGuid (16 bytes)
    # 对于 UE5 >= 1016，SavedHash 已经在头部开始时读取，跳过这个 Legacy Guid
    # 注意：Legacy Guid (FGuid 16 bytes) 和 SavedHash (FIoHash 20 bytes) 是不同结构
    # saved_hash 字段仅用于 UE5 >= 1016 的 FIoHash，UE5 < 1016 和 UE4 应保持为空
    if not is_ue4_file and file_version_ue5 < UE5_PACKAGE_SAVED_HASH:
        # UE5 < 1016: 读取 Legacy Guid (16 bytes)，但不存入 saved_hash
        archive.read(16)  # Legacy Guid, 跳过
    elif is_ue4_file:
        # UE4 文件: 总是读取 Legacy Guid (16 bytes)
        archive.read(16)  # Legacy Guid, 跳过

    # === 第 20 步：PersistentGuid（UE4 >= 516，WITH_EDITORONLY_DATA && !IsFilterEditorOnly）===
    # PackageFileSummary.cpp line 354-376: 包裹在 WITH_EDITORONLY_DATA 和 !IsFilterEditorOnly()
    # 对于 cooked 文件，PersistentGuid 不被序列化
    persistent_guid = ""
    if not is_cooked and file_version_ue4 >= UE4_ADDED_PACKAGE_OWNER:
        guid_bytes = archive.read(16)
        persistent_guid = guid_bytes.hex()

        # OwnerPersistentGuid（UE4 >= 516 and < 518）
        # PackageFileSummary.cpp line 370-375
        if file_version_ue4 < UE4_NON_OUTER_PACKAGE_IMPORT:
            archive.read(16)  # OwnerPersistentGuid，跳过

    # === 第 21 步：Generations ===
    # PackageFileSummary.cpp line 379-395
    generations_count = archive.read_i32()
    generations: List[GenerationInfo] = []
    for _ in range(generations_count):
        gen_export_count = archive.read_i32()
        gen_name_count = archive.read_i32()
        generations.append(GenerationInfo(export_count=gen_export_count, name_count=gen_name_count))

    # === 第 22 步：SavedByEngineVersion ===
    # PackageFileSummary.cpp line 397-419
    saved_by_engine_version = EngineVersion()
    if file_version_ue4 >= UE4_ENGINE_VERSION_OBJECT:
        saved_by_engine_version = EngineVersion(
            major=archive.read_u16(),
            minor=archive.read_u16(),
            patch=archive.read_u16(),
            changelist=archive.read_u32(),
            branch=archive.read_fstring()
        )
    else:
        # UE4 < 334: 读取 EngineChangelist
        engine_changelist = archive.read_i32()
        if engine_changelist != 0:
            saved_by_engine_version = EngineVersion(
                major=4, minor=0, patch=0,
                changelist=engine_changelist,
                branch=""
            )

    # === 第 23 步：CompatibleWithEngineVersion ===
    # PackageFileSummary.cpp line 421-440
    compatible_with_engine_version = EngineVersion()
    if file_version_ue4 >= UE4_PACKAGE_SUMMARY_HAS_COMPATIBLE_ENGINE_VERSION:
        compatible_with_engine_version = EngineVersion(
            major=archive.read_u16(),
            minor=archive.read_u16(),
            patch=archive.read_u16(),
            changelist=archive.read_u32(),
            branch=archive.read_fstring()
        )
    else:
        # UE4 < 442: 复用 SavedByEngineVersion
        compatible_with_engine_version = EngineVersion(
            major=saved_by_engine_version.major,
            minor=saved_by_engine_version.minor,
            patch=saved_by_engine_version.patch,
            changelist=saved_by_engine_version.changelist,
            branch=saved_by_engine_version.branch
        )

    # === 第 24 步：CompressionFlags ===
    # PackageFileSummary.cpp line 442-448
    compression_flags = archive.read_u32()

    # === 第 25 步：CompressedChunks（已废弃，TArray）===
    # PackageFileSummary.cpp line 450-451
    compressed_chunks_count = archive.read_i32()
    for _ in range(compressed_chunks_count):
        archive.read(12)  # FCompressedChunk = 12 bytes (int64 start + int32 size)，跳过

    # === 第 26 步：PackageSource ===
    # PackageFileSummary.cpp line 461
    package_source = archive.read_u32()

    # === 第 27 步：AdditionalPackagesToCook（已废弃，TArray）===
    # PackageFileSummary.cpp line 465-466
    additional_packages_count = archive.read_i32()
    for _ in range(additional_packages_count):
        archive.read_fstring()  # FString，跳过

    # === 第 28 步：NumTextureAllocations（legacy，LegacyFileVersion > -7）===
    # PackageFileSummary.cpp line 468-474
    if legacy_file_version > -7:
        archive.read_i32()  # NumTextureAllocations，跳过

    # === 第 29 步：AssetRegistryDataOffset ===
    # PackageFileSummary.cpp line 476
    asset_registry_data_offset = archive.read_i32()

    # === 第 30 步：BulkDataStartOffset ===
    # PackageFileSummary.cpp line 477
    bulk_data_start_offset = archive.read_i64()

    # === 第 31 步：WorldTileInfoDataOffset（UE4 >= 223）===
    # PackageFileSummary.cpp line 479-482
    world_tile_info_data_offset = 0
    if file_version_ue4 >= UE4_WORLD_LEVEL_INFO:
        world_tile_info_data_offset = archive.read_i32()

    # === 第 32 步：ChunkIDs（UE4 >= 277）===
    # PackageFileSummary.cpp line 484-502
    chunk_ids: List[str] = []
    if file_version_ue4 >= UE4_CHANGED_CHUNKID_TO_ARRAY:
        # TArray<FGuid>
        chunk_ids_count = archive.read_i32()
        for _ in range(chunk_ids_count):
            guid_bytes = archive.read(16)
            chunk_ids.append(guid_bytes.hex())
    elif file_version_ue4 >= UE4_ADDED_CHUNKID:
        # Single ChunkID (int32)
        chunk_id = archive.read_i32()
        if chunk_id >= 0:
            # 转换为 FGuid 格式（但实际是 int32）
            chunk_ids.append(hex(chunk_id))

    # === 第 33 步：PreloadDependencies（UE4 >= 505）===
    # PackageFileSummary.cpp line 503-511
    preload_dependency_count = 0
    preload_dependency_offset = 0
    if file_version_ue4 >= UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS:
        preload_dependency_count = archive.read_i32()
        preload_dependency_offset = archive.read_i32()
    else:
        preload_dependency_count = -1
        preload_dependency_offset = 0

    # === 第 34 步：NamesReferencedFromExportDataCount（UE5 >= 1001，在末尾！）===
    # PackageFileSummary.cpp line 513-520
    names_referenced_from_export_data_count = 0
    if not is_ue4_file and file_version_ue5 >= UE5_NAMES_REFERENCED_FROM_EXPORT_DATA:
        names_referenced_from_export_data_count = archive.read_i32()
    else:
        names_referenced_from_export_data_count = name_count  # UE 默认值

    # === 第 35 步：PayloadTocOffset（UE5 >= 1002）===
    # PackageFileSummary.cpp line 522-529
    payload_toc_offset = 0
    if not is_ue4_file and file_version_ue5 >= UE5_PAYLOAD_TOC:
        payload_toc_offset = archive.read_i64()  # int64
    else:
        payload_toc_offset = -1  # INDEX_NONE

    # === 第 36 步：DataResourceOffset（UE5 >= 1009）===
    # PackageFileSummary.cpp line 531-538
    data_resource_offset = 0
    if not is_ue4_file and file_version_ue5 >= UE5_DATA_RESOURCES:
        data_resource_offset = archive.read_i32()
    else:
        data_resource_offset = -1

    # === 第 37 步：TotalHeaderSize（UE5 < 1016 版本）===
    # PackageFileSummary.cpp: UE5 < 1016 时 TotalHeaderSize 在最后
    if not is_ue4_file and file_version_ue5 < UE5_PACKAGE_SAVED_HASH:
        total_header_size = archive.read_i32()

    return PackageFileSummary(
        tag=tag,
        legacy_file_version=legacy_file_version,
        file_version_ue4=file_version_ue4,
        legacy_ue3_version=legacy_ue3_version,
        file_version_ue5=file_version_ue5,
        file_version_licensee=file_version_licensee,
        saved_hash=saved_hash,
        total_header_size=total_header_size,
        custom_versions=custom_versions,
        package_name=package_name,
        package_flags=package_flags,
        name_count=name_count,
        name_offset=name_offset,
        soft_object_paths_count=soft_object_paths_count,
        soft_object_paths_offset=soft_object_paths_offset,
        localization_id=localization_id,
        gatherable_text_data_count=gatherable_text_data_count,
        gatherable_text_data_offset=gatherable_text_data_offset,
        export_count=export_count,
        export_offset=export_offset,
        import_count=import_count,
        import_offset=import_offset,
        cell_export_count=cell_export_count,
        cell_export_offset=cell_export_offset,
        cell_import_count=cell_import_count,
        cell_import_offset=cell_import_offset,
        metadata_offset=metadata_offset,
        depends_offset=depends_offset,
        soft_package_references_count=soft_package_references_count,
        soft_package_references_offset=soft_package_references_offset,
        searchable_names_offset=searchable_names_offset,
        thumbnail_table_offset=thumbnail_table_offset,
        import_type_hierarchies_count=import_type_hierarchies_count,
        import_type_hierarchies_offset=import_type_hierarchies_offset,
        persistent_guid=persistent_guid,
        generations=generations,
        saved_by_engine_version=saved_by_engine_version,
        compatible_with_engine_version=compatible_with_engine_version,
        compression_flags=compression_flags,
        package_source=package_source,
        asset_registry_data_offset=asset_registry_data_offset,
        bulk_data_start_offset=bulk_data_start_offset,
        world_tile_info_data_offset=world_tile_info_data_offset,
        chunk_ids=chunk_ids,
        preload_dependency_count=preload_dependency_count,
        preload_dependency_offset=preload_dependency_offset,
        names_referenced_from_export_data_count=names_referenced_from_export_data_count,
        payload_toc_offset=payload_toc_offset,
        data_resource_offset=data_resource_offset
    )


def read_name_table(archive: FArchive, summary: PackageFileSummary) -> List[str]:
    """
    读取名称表。

    使用 FNameEntrySerialized 格式：
    - FString (Length + Data)
    - Hash bytes (4 bytes) for UE4 >= VER_UE4_NAME_HASHES_SERIALIZED (502) and UE5 files

    Args:
        archive: FArchive 实例
        summary: PackageFileSummary 实例

    Returns:
        名称表列表（NameMap）
    """
    archive.seek(summary.name_offset)

    # UE4 version constant: VER_UE4_NAME_HASHES_SERIALIZED = 502
    # For UE4 >= 502 AND UE5 files, name entries have 4-byte hash suffix
    # UE5 files always have name hashes (FileVersionUE5 >= 1000 > 502)
    NAME_HASHES_SERIALIZED_VERSION = 502
    is_ue4_file = summary.legacy_file_version > -8
    has_name_hashes = (is_ue4_file and summary.file_version_ue4 >= NAME_HASHES_SERIALIZED_VERSION) or (not is_ue4_file)

    name_map: List[str] = []
    for _ in range(summary.name_count):
        name = archive.read_fstring()
        name_map.append(name)

        # Read hash bytes if UE4 >= 502 or UE5
        # Reference: UE UnrealNames.cpp line 4429-4431
        if has_name_hashes:
            # NonCasePreservingHash (uint16) + CasePreservingHash (uint16)
            archive.read(4)  # Skip hash bytes

    return name_map


def read_import_map(
    archive: FArchive,
    summary: PackageFileSummary,
    name_map: List[str]
) -> List[ObjectImport]:
    """
    读取导入表（CORE-04）。

    来自 ObjectResource.h / ObjectResource.cpp：
    FObjectImport 结构：
    - ClassPackage (FName)
    - ClassName (FName)
    - OuterIndex (FPackageIndex)
    - ObjectName (FName)
    - PackageName (FName, 条件: UEVer >= 518 且 !IsFilterEditorOnly)
    - bImportOptional (bool, 条件: UEVer >= 1003 OPTIONAL_RESOURCES)

    Args:
        archive: FArchive 实例
        summary: PackageFileSummary 实例
        name_map: 已解析的名称表

    Returns:
        导入表列表（ImportMap）
    """
    archive.seek(summary.import_offset)

    is_ue4_file = summary.legacy_file_version > -8
    # 未烘焙文件 IsFilterEditorOnly = false，所以条件字段需要读取
    is_filter_editor_only = False  # FLinkerLoad for uncooked packages

    import_map: List[ObjectImport] = []
    for _ in range(summary.import_count):
        class_package = archive.read_name(name_map)
        class_name = archive.read_name(name_map)
        outer_index = PackageIndex(archive.read_i32())
        object_name = archive.read_name(name_map)

        # PackageName: UEVer >= VER_UE4_NON_OUTER_PACKAGE_IMPORT (518) && !IsFilterEditorOnly
        has_package_name = False
        if not is_filter_editor_only:
            if is_ue4_file and summary.file_version_ue4 >= UE4_NON_OUTER_PACKAGE_IMPORT:
                has_package_name = True
            elif not is_ue4_file:
                has_package_name = True

        package_name: Optional[str] = None
        if has_package_name:
            package_name = archive.read_name(name_map)

        # bImportOptional: UEVer >= OPTIONAL_RESOURCES (1003)
        has_import_optional = False
        if is_ue4_file and summary.file_version_ue4 >= UE5_OPTIONAL_RESOURCES:
            has_import_optional = True
        elif not is_ue4_file and summary.file_version_ue5 >= UE5_OPTIONAL_RESOURCES:
            has_import_optional = True

        b_import_optional: Optional[bool] = None
        if has_import_optional:
            b_import_optional = bool(archive.read_u8())

        import_map.append(ObjectImport(
            class_package=class_package,
            class_name=class_name,
            outer_index=outer_index,
            object_name=object_name,
            package_name=package_name,
            b_import_optional=b_import_optional
        ))

    return import_map


def build_imports_list(import_map: List[ObjectImport]) -> List[Dict]:
    """
    构建 imports 依赖列表（DEPS-01）。

    Per D-10-01: {class, package, object} 格式
    Per D-10-03: 保持原始顺序（首次出现）
    Per D-10-04: 合并重复（相同三元组）

    Args:
        import_map: read_import_map() 返回的导入表

    Returns:
        List[Dict]: [{"class": str, "package": str, "object": str}]
    """
    seen = set()
    imports = []

    for imp in import_map:
        key = (imp.class_name, imp.class_package, imp.object_name)

        if key not in seen:
            seen.add(key)
            imports.append({
                "class": imp.class_name,
                "package": imp.class_package,
                "object": imp.object_name
            })

    return imports


def read_soft_object_paths(
    archive: FArchive,
    summary: PackageFileSummary,
    name_map: List[str]
) -> List[Dict]:
    """
    读取 SoftObjectPaths 数组（DEPS-02）。

    Per D-10-06: 实现完整解析
    Per D-10-07: {asset_path, sub_path} 格式
    Per D-10-09: 仅 UE5 >= 1008 时解析

    UE5 版本格式变化（SoftObjectPath.cpp L555-591）：
    - UE5 < 1007: AssetPathName(FName) + SubPathWide(FWideString)
    - UE5 >= 1007: PackageName(FName) + AssetName(FName) + SubPathString(FUtf8String)

    Args:
        archive: FArchive 实例
        summary: PackageFileSummary 实例
        name_map: 已解析的名称表

    Returns:
        List[Dict]: [{"asset_path": str, "sub_path": str}]
    """
    is_ue5_file = summary.legacy_file_version <= -8
    if not is_ue5_file or summary.file_version_ue5 < UE5_ADD_SOFTOBJECTPATH_LIST:
        return []

    if summary.soft_object_paths_count <= 0:
        return []

    if summary.soft_object_paths_offset <= 0:
        return []

    archive.seek(summary.soft_object_paths_offset)

    soft_refs = []
    for _ in range(summary.soft_object_paths_count):
        # UE5 >= 1007: FTopLevelAssetPath 格式（两个 FName）
        if summary.file_version_ue5 >= UE5_FSOFTOBJECTPATH_REMOVE_ASSET_PATH_FNAMES:
            package_name = archive.read_name(name_map)
            asset_name = archive.read_name(name_map)
            # 组合为完整 asset_path：PackageName.AssetName 或 PackageName
            if asset_name:
                asset_path = f"{package_name}.{asset_name}"
            else:
                asset_path = package_name
            # SubPathString: FUtf8String（与 FString 格式相同）
            sub_path = archive.read_fstring()
        else:
            # UE5 < 1007: 单 FName + FWideString 格式
            asset_path = archive.read_name(name_map)
            # FWideString 格式与 FString 相同（UTF-16 LE，但实际存储常为 UTF-8）
            sub_path = archive.read_fstring()

        soft_refs.append({
            "asset_path": asset_path,
            "sub_path": sub_path
        })

    return soft_refs


def detect_circular_deps(import_map: List[ObjectImport]) -> List[List[str]]:
    """
    检测 ImportMap 中的高密度依赖作为潜在循环警告（DEPS-03）。

    Per D-10-10: DFS 图遍历思想（简化实现）
    Per D-10-11: 检测同一 class_package 的多次引用
    Per D-10-12: 路径数组格式 [pkg, pkg]

    实现说明（ImportMap 单向依赖特性）：
    - ImportMap 仅包含"当前包→外部包"的单向引用
    - 无法从单文件 ImportMap 检测真正的跨包循环
    - 此实现检测高密度依赖：同一外部包被多次引用（潜在循环信号）
    - 输出格式 [pkg, pkg] 表示"pkg 被多次引用"，暗示潜在循环风险

    Args:
        import_map: 导入表列表

    Returns:
        List[List[str]]: 高密度依赖路径列表，每个路径为 [package_name, package_name]
    """
    if not import_map:
        return []

    package_refs: Dict[str, int] = {}
    for imp in import_map:
        pkg = imp.class_package
        package_refs[pkg] = package_refs.get(pkg, 0) + 1

    high_density_deps = []
    for pkg, count in package_refs.items():
        if count > 1:
            high_density_deps.append([pkg, pkg])

    return high_density_deps


def read_export_map(
    archive: FArchive,
    summary: PackageFileSummary,
    name_map: List[str]
) -> List[ObjectExport]:
    """
    读取导出表（CORE-05/CORE-06, Phase 6 BUG-01/BUG-02/BUG-03）。

    严格按 ObjectResource.cpp 第 130-217 行顺序：
    1. ClassIndex → 2. SuperIndex → 3. TemplateIndex(条件) → 4. OuterIndex →
    5. ObjectName → 6. ObjectFlags → 7-8. SerialSize/Offset →
    9-11. bool flags → 12. PackageGuid(条件) → 13. bIsInheritedInstance(条件) →
    14. PackageFlags → 15-17. 其他 bool flags →
    19-20. ScriptSerializationStartOffset/EndOffset(条件)

    Args:
        archive: FArchive 实例
        summary: PackageFileSummary 实例
        name_map: 已解析的名称表

    Returns:
        导出表列表（ExportMap）

    Raises:
        ParseError: 导出表解析失败（携带 ErrorContext）
    """
    archive.seek(summary.export_offset)

    export_map: List[ObjectExport] = []
    is_ue5_file = summary.legacy_file_version <= -8

    # UE5 文件自动满足所有 UE4 版本条件（file_version_ue4 可能是 0）
    # 参考 FPackageFileVersion::operator>= 实现
    effective_ue4_version = summary.file_version_ue4 if not is_ue5_file else 1000  # UE5 视为高版本

    for export_idx in range(summary.export_count):
        object_name = ""  # 初始化用于错误上下文

        try:
            # 1. ClassIndex
            class_index = PackageIndex(archive.read_i32())

            # 2. SuperIndex
            super_index = PackageIndex(archive.read_i32())

            # 3. TemplateIndex（D-01：条件读取 UE4 >= 506，UE5 文件自动满足）
            template_index = PackageIndex(0)
            if effective_ue4_version >= VER_UE4_TemplateIndex_IN_COOKED_EXPORTS:  # 506
                template_index = PackageIndex(archive.read_i32())

            # 4. OuterIndex（D-02：TemplateIndex 之后）
            outer_index = PackageIndex(archive.read_i32())

            # 5. ObjectName
            object_name = archive.read_name(name_map)

            # 6. ObjectFlags
            object_flags = archive.read_u32()

            # 7-8. SerialSize/Offset（UE4 >= 508 使用 i64，否则 i32）
            if effective_ue4_version >= VER_UE4_64BIT_EXPORTOFFSETS:  # 508
                serial_size = archive.read_i64()
                serial_offset = archive.read_i64()
            else:
                serial_size = archive.read_i32()
                serial_offset = archive.read_i32()

            # 9-11. bool flags（D-07：各读取 1 byte）
            b_forced_export = bool(archive.read_u8())
            b_not_for_client = bool(archive.read_u8())
            b_not_for_server = bool(archive.read_u8())

            # 12. PackageGuid（D-10/D-11：UE5 < 1010时读取但不存储）
            if is_ue5_file and summary.file_version_ue5 < UE5_REMOVE_OBJECT_EXPORT_PACKAGE_GUID:  # 1010
                # 读取 16 bytes FGuid，但不存储（DummyPackageGuid）
                archive.read_bytes(16)

            # 13. bIsInheritedInstance（D-08：UE5 >= 1011）
            b_is_inherited_instance = None
            if is_ue5_file and summary.file_version_ue5 >= UE5_TRACK_OBJECT_EXPORT_IS_INHERITED:  # 1011
                b_is_inherited_instance = bool(archive.read_u8())

            # 14. PackageFlags（D-09）
            package_flags = archive.read_u32()

            # 15-17. 其他 bool flags（D-08：条件读取）
            b_not_always_loaded_for_editor_game = None
            b_is_asset = None
            b_generate_public_hash = None

            # UE4 版本条件：bNotAlwaysLoadedForEditorGame（UE4 >= 383，UE5 总是满足）
            if effective_ue4_version >= UE4_LOAD_FOR_EDITOR_GAME:
                b_not_always_loaded_for_editor_game = bool(archive.read_u8())

            # UE4 版本条件：bIsAsset（UE4 >= 401，UE5 总是满足）
            if effective_ue4_version >= UE4_COOKED_ASSETS_IN_EDITOR_SUPPORT:
                b_is_asset = bool(archive.read_u8())

            # UE5 版本条件：bGeneratePublicHash（UE5 >= OPTIONAL_RESOURCES=1003）
            if is_ue5_file and summary.file_version_ue5 >= UE5_GENERATE_PUBLIC_HASH:
                b_generate_public_hash = bool(archive.read_u8())

            # 18. 依赖数组（UE4 >= 505 / UE5 总是满足）
            # FirstExportDependency + 4个依赖计数（5个 i32）
            first_export_dependency = 0
            serialization_before_serialization_deps = 0
            create_before_serialization_deps = 0
            serialization_before_create_deps = 0
            create_before_create_deps = 0
            if effective_ue4_version >= UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS:
                first_export_dependency = archive.read_i32()
                serialization_before_serialization_deps = archive.read_i32()
                create_before_serialization_deps = archive.read_i32()
                serialization_before_create_deps = archive.read_i32()
                create_before_create_deps = archive.read_i32()

            # 19-20. ScriptSerializationStartOffset/EndOffset
            # 条件: !UseUnversionedPropertySerialization() && UEVer() >= SCRIPT_SERIALIZATION_OFFSET(1010)
            # UseUnversionedPropertySerialization()基于PKG_UnversionedProperties标志判断
            # 若PKG_UnversionedProperties未设置，则使用versioned property serialization，需要读取这些字段
            script_serial_size = 0
            script_serial_offset = 0
            uses_unversioned = (summary.package_flags & PKG_UnversionedProperties) != 0
            if is_ue5_file and not uses_unversioned and summary.file_version_ue5 >= UE5_SCRIPT_SERIALIZATION_OFFSET:
                script_serial_size = archive.read_i64()
                script_serial_offset = archive.read_i64()

            # 构建导出条目
            export_map.append(ObjectExport(
                class_index=class_index,
                super_index=super_index,
                template_index=template_index,
                outer_index=outer_index,
                object_name=object_name,
                object_flags=object_flags,
                serial_size=serial_size,
                serial_offset=serial_offset,
                b_forced_export=b_forced_export,
                b_not_for_client=b_not_for_client,
                b_not_for_server=b_not_for_server,
                b_is_inherited_instance=b_is_inherited_instance,
                package_flags=package_flags,
                b_not_always_loaded_for_editor_game=b_not_always_loaded_for_editor_game,
                b_is_asset=b_is_asset,
                b_generate_public_hash=b_generate_public_hash,
                script_serial_size=script_serial_size,
                script_serial_offset=script_serial_offset
            ))

        except Exception as e:
            # D-12/D-13/D-14：错误上下文增强
            context = ErrorContext(
                offset=archive.tell(),
                phase="export_map",
                operation="read_export",
                context_name=object_name,
                export_index=export_idx,
                expected_offset=None,  # 无法精确计算（字段可变）
                actual_offset=archive.tell(),
                field_name="",
                version_info={
                    "file_version_ue4": summary.file_version_ue4,
                    "file_version_ue5": summary.file_version_ue5,
                    "threshold": VER_UE4_TemplateIndex_IN_COOKED_EXPORTS
                }
            )
            raise ParseError(
                f"导出表解析失败（导出 #{export_idx}）：{str(e)}",
                partial_result={"export_map": export_map},
                context=context
            )

    return export_map


def get_asset_class(
    export: ObjectExport,
    import_map: List[ObjectImport],
    export_map: List[ObjectExport]
) -> Optional[str]:
    """
    从导出条目识别资产类型（CORE-06）。

    通过 class_index 查找导入表或导出表获取类名。

    Args:
        export: ObjectExport 实例
        import_map: 导入表列表
        export_map: 导出表列表

    Returns:
        类名字符串或 None（若无法解析）
    """
    if export.class_index.is_import:
        # 从导入表获取类名
        import_idx = export.class_index.to_import_index()
        if 0 <= import_idx < len(import_map):
            return import_map[import_idx].class_name
    elif export.class_index.is_export:
        # 从导出表获取类名
        export_idx = export.class_index.to_export_index()
        if 0 <= export_idx < len(export_map):
            return export_map[export_idx].object_name

    return None


def resolve_class_name(
    class_index: PackageIndex,
    import_map: List[ObjectImport],
    export_map: List[ObjectExport]
) -> Optional[str]:
    """
    从 PackageIndex 解析类名（GRAPH-03 辅助函数）。

    用于解析 Schema、ClassIndex 等 FPackageIndex 字段。

    Args:
        class_index: PackageIndex 实例
        import_map: 导入表列表
        export_map: 导出表列表

    Returns:
        类名字符串或 None（若无法解析）
    """
    if class_index.is_import:
        # 从导入表获取类名
        import_idx = class_index.to_import_index()
        if 0 <= import_idx < len(import_map):
            return import_map[import_idx].class_name
    elif class_index.is_export:
        # 从导出表获取类名
        export_idx = class_index.to_export_index()
        if 0 <= export_idx < len(export_map):
            return export_map[export_idx].object_name

    return None


def detect_blueprint(
    export: ObjectExport,
    import_map: List[ObjectImport],
    export_map: List[ObjectExport]
) -> bool:
    """
    Detect if export is a blueprint asset (BLUE-01).

    Per D-01: check ClassIndex resolution for "Blueprint" keyword in class name.
    Per D-04: only detect presence, don't distinguish BlueprintType.

    Args:
        export: ObjectExport to check
        import_map: Import table for ClassIndex lookup
        export_map: Export table for ClassIndex lookup

    Returns:
        True if export is a blueprint, False otherwise
    """
    class_name = get_asset_class(export, import_map, export_map)
    if class_name and "Blueprint" in class_name:
        return True
    return False


def extract_blueprint_graphs(
    archive: FArchive,
    summary: PackageFileSummary,
    name_map: List[str],
    import_map: List[ObjectImport],
    export_map: List[ObjectExport]
) -> List[UEdGraph]:
    """
    从 ExportMap 提取蓝图图（GRAPH-01 入口）。

    Per D-03a: 遍历 ExportMap，ClassIndex 解析后包含 "EdGraph" 或 "Ubergraph" 的导出视为图对象。
    Per D-03b: 此阶段仅检测和基本信息提取，不深入解析 Nodes 数组（Wave 2 实现）。

    安全检查（T-07-01-02）：
    - PKG_Cooked 检查避免解析已剥离资产（Pitfall 3）

    Args:
        summary: PackageFileSummary 包含 package_flags
        import_map: 导入表列表（用于 ClassIndex 解析）
        export_map: 导出表列表（用于 ClassIndex 解析）

    Returns:
        List[UEdGraph]: 检测到的图列表（仅基本信息，nodes 为空）
    """
    graphs: List[UEdGraph] = []

    # T-07-01-02: 检查 PKG_Cooked 标志
    # Pitfall 3: cooked 资产无图数据（已剥离）
    is_cooked = (summary.package_flags & PKG_Cooked) != 0
    if is_cooked:
        # cooked 资产返回空列表，Phase 8 输出警告
        return []

    # 遍历 ExportMap 寻找 EdGraph 类型导出
    for export in export_map:
        # D-03a: ClassIndex 解析为类名
        class_name = get_asset_class(export, import_map, export_map)

        if class_name and ("EdGraph" in class_name or "UberEdGraph" in class_name):
            # D-03b/D-03c: 完整解析 Graph→Node→Pin 三层结构
            graph = read_ue_graph(
                archive, name_map, summary,
                export_map, import_map,
                export, class_name
            )
            graphs.append(graph)

    return graphs


def resolve_parent_class(
    super_index: PackageIndex,
    import_map: List[ObjectImport],
    export_map: List[ObjectExport]
) -> Tuple[Optional[str], Optional[str]]:
    """
    Resolve ParentClass FPackageIndex to object name (BLUE-02).

    Per D-09: only direct parent (no inheritance chain).
    Per D-10: resolve to ImportMap/ExportMap object name.
    Per D-11: return raw index + warning on resolution failure.

    Args:
        super_index: FPackageIndex from ObjectExport.super_index
        import_map: Import table for lookup
        export_map: Export table for lookup

    Returns:
        Tuple of (resolved_name, warning_if_any)
        - (class_name, None) on success
        - (None, warning_string) on failure
    """
    if super_index.is_null:
        # No parent (UObject root)
        return None, None

    if super_index.is_import:
        import_idx = super_index.to_import_index()
        if 0 <= import_idx < len(import_map):
            return import_map[import_idx].object_name, None
        warning = f"ParentClass import index {super_index.index} out of range"
        return None, warning

    elif super_index.is_export:
        export_idx = super_index.to_export_index()
        if 0 <= export_idx < len(export_map):
            return export_map[export_idx].object_name, None
        warning = f"ParentClass export index {super_index.index} out of range"
        return None, warning

    # Invalid index (should not happen, but handle defensively)
    warning = f"ParentClass invalid FPackageIndex: {super_index.index}"
    return None, warning


def read_ed_graph_pin_type(
    archive: FArchive,
    name_map: List[str],
    summary: PackageFileSummary
) -> FEdGraphPinType:
    """
    Parse FEdGraphPinType from export data (BLUE-05).

    Serialization order from EdGraphPin.cpp lines 163-346 [VERIFIED]:
    1. PinCategory (FName)
    2. PinSubCategory (FName)
    3. PinSubCategoryObject (FPackageIndex / int32)
    4. ContainerType (uint8)
    5. PinValueType (FEdGraphTerminalType) - if ContainerType == 3 (Map)
    6. bIsReference (bool - uint8)
    7. bIsWeakPointer (bool - uint8)
    8. PinSubCategoryMemberReference (FSimpleMemberReference) - skip for Phase 3
    9. bIsConst (bool - uint8)
    10. bIsUObjectWrapper (bool - uint8)

    Per D-08: parse all fields, not just format for display.
    Per D-06/D-07: full structure needed for ContainerType + object reference.
    Per RESEARCH.md Pitfall 1: version-aware serialization with FFrameworkObjectVersion checks.

    Version dependencies:
    - ContainerType field added in FFrameworkObjectVersion::EdGraphPinContainerType
    - bIsConst added in VER_UE4_SERIALIZE_PINTYPE_CONST
    - bIsUObjectWrapper added in FReleaseObjectVersion::PinTypeIncludesUObjectWrapperFlag

    Args:
        archive: FArchive positioned at start of FEdGraphPinType
        name_map: NameMap for FName resolution
        summary: PackageFileSummary for version info

    Returns:
        FEdGraphPinType dataclass with all fields populated
    """
    pin_type = FEdGraphPinType()

    # Step 1-2: PinCategory and PinSubCategory (FName)
    pin_type.pin_category = archive.read_name(name_map)
    pin_type.pin_sub_category = archive.read_name(name_map)

    # Step 3: PinSubCategoryObject (FPackageIndex as int32)
    pin_type.pin_sub_category_object = archive.read_i32()

    # Step 4: ContainerType (uint8)
    # Per EdGraphPin.cpp line 216: FFrameworkObjectVersion >= EdGraphPinContainerType
    # For Phase 3, we always read ContainerType as it's standard in modern UE files
    pin_type.container_type = archive.read_u8()

    # Step 5: PinValueType for Map containers (skip for Phase 3)
    if pin_type.container_type == 3:  # Map
        # FEdGraphTerminalType: TerminalCategory + TerminalSubCategory + TerminalSubCategoryObject
        archive.read_name(name_map)  # TerminalCategory
        archive.read_name(name_map)  # TerminalSubCategory
        archive.read_i32()           # TerminalSubCategoryObject

    # Step 6-7: bIsReference and bIsWeakPointer
    pin_type.is_reference = archive.read_u8() != 0
    pin_type.is_weak_pointer = archive.read_u8() != 0

    # Step 8: PinSubCategoryMemberReference (skip for Phase 3)
    # FSimpleMemberReference: MemberParent (i32) + MemberName (FName) + MemberGuid (16)
    archive.read_i32()  # MemberParent (FPackageIndex)
    archive.read_name(name_map)  # MemberName
    archive.read(16)  # MemberGuid

    # Step 9: bIsConst
    # Added in VER_UE4_SERIALIZE_PINTYPE_CONST (UE4 version check)
    # Always read in Phase 3 as modern assets have this field
    pin_type.is_const = archive.read_u8() != 0

    # Step 10: bIsUObjectWrapper
    # Added in FReleaseObjectVersion::PinTypeIncludesUObjectWrapperFlag
    # Always read in Phase 3 as modern assets have this field
    pin_type.is_uobject_wrapper = archive.read_u8() != 0

    return pin_type


def read_ue_graph_pin(
    archive: FArchive,
    name_map: List[str],
    summary: PackageFileSummary
) -> UEdGraphPin:
    """
    读取 UEdGraphPin（GRAPH-04）。

    序列化顺序（基于 UE 源码 EdGraphPin.cpp L163-346）：
    1. PinId (FGuid 16 bytes) -> hex string
    2. PinName (FName) -> str
    3. Direction (uint8) -> int (0=Input, 1=Output, 2=None)
    4. PinType (FEdGraphPinType) -> 调用 read_ed_graph_pin_type()
    5. DefaultValue (FString) -> str
    6. AutogeneratedDefaultValue (FString) -> str
    7. LinkedTo 数组 (int32 count + PinId[]) -> D-01a: 存储原始数据
    8. SubPins 数组 (int32 count + PinId[]) -> PinId 列表
    9. ParentPin (条件：has_parent flag + PinId) -> Optional[str]
    10. Flags (uint8) -> int

    安全边界（T-07-02-04）：
    - linked_to_count <= MAX_LINKEDTO_PER_PIN (100)
    - sub_pins_count <= MAX_LINKEDTO_PER_PIN (100)

    Args:
        archive: FArchive positioned at pin start
        name_map: NameMap for FName resolution
        summary: PackageFileSummary for version info

    Returns:
        UEdGraphPin dataclass

    Raises:
        ParseError: 若 count 超出安全边界
    """
    # 1. PinId (FGuid 16 bytes)
    pin_id_bytes = archive.read_bytes(16)
    pin_id = pin_id_bytes.hex()

    # 2. PinName (FName)
    pin_name = archive.read_name(name_map)

    # 3. Direction (uint8: 0=Input, 1=Output, 2=None)
    direction = archive.read_u8()

    # 4. PinType — 直接复用 Phase 3 实现
    pin_type = read_ed_graph_pin_type(archive, name_map, summary)

    # 5-6. DefaultValue strings
    default_value = archive.read_fstring()
    auto_default_value = archive.read_fstring()

    # 7. LinkedTo 数组 — D-01a: 存储为原始数据列表
    linked_to_count = archive.read_i32()
    if linked_to_count < 0:
        raise ParseError(
            f"Invalid linked_to_count {linked_to_count} (negative) at pin {pin_id}"
        )
    if linked_to_count > MAX_LINKEDTO_PER_PIN:
        raise ParseError(
            f"linked_to_count {linked_to_count} exceeds MAX_LINKEDTO_PER_PIN "
            f"{MAX_LINKEDTO_PER_PIN} at pin {pin_id}"
        )

    linked_to_raw: List[str] = []
    for _ in range(linked_to_count):
        # 每个 linked pin 是 PinId GUID
        linked_pin_id_bytes = archive.read_bytes(16)
        linked_pin_id = linked_pin_id_bytes.hex()
        linked_to_raw.append(linked_pin_id)

    # 8. SubPins 数组
    sub_pins_count = archive.read_i32()
    if sub_pins_count < 0:
        raise ParseError(
            f"Invalid sub_pins_count {sub_pins_count} (negative) at pin {pin_id}"
        )
    if sub_pins_count > MAX_LINKEDTO_PER_PIN:
        raise ParseError(
            f"sub_pins_count {sub_pins_count} exceeds MAX_LINKEDTO_PER_PIN "
            f"{MAX_LINKEDTO_PER_PIN} at pin {pin_id}"
        )

    sub_pins: List[str] = []
    for _ in range(sub_pins_count):
        sub_pin_id_bytes = archive.read_bytes(16)
        sub_pin_id = sub_pin_id_bytes.hex()
        sub_pins.append(sub_pin_id)

    # 9. ParentPin（条件字段）
    has_parent = archive.read_u8() != 0
    parent_pin: Optional[str] = None
    if has_parent:
        parent_pin_bytes = archive.read_bytes(16)
        parent_pin = parent_pin_bytes.hex()

    # 10. Flags bitfield
    flags = archive.read_u8()

    return UEdGraphPin(
        pin_id=pin_id,
        pin_name=pin_name,
        direction=direction,
        pin_type=pin_type,
        default_value=default_value,
        auto_default_value=auto_default_value,
        linked_to_raw=linked_to_raw,
        sub_pins=sub_pins,
        parent_pin=parent_pin,
        flags=flags
    )


def read_ue_graph_node(
    archive: FArchive,
    name_map: List[str],
    summary: PackageFileSummary,
    export_map: List[ObjectExport],
    import_map: List[ObjectImport],
    node_export: ObjectExport
) -> UEdGraphNode:
    """
    读取 UEdGraphNode 基类字段（GRAPH-03）。

    序列化顺序（基于 UE 源码 EdGraphNode.cpp）：
    1. Pins 数组 (int32 count + loop call read_ue_graph_pin)
    2. NodePosX (int32)
    3. NodePosY (int32)
    4. NodeGuid (FGuid 16 bytes)
    5. NodeComment (FString)

    安全边界（T-07-02-02）：
    - pins_count <= MAX_PINS_PER_NODE (1000)

    Args:
        archive: FArchive positioned at node serial_offset
        name_map: NameMap for FName resolution
        summary: PackageFileSummary for version info
        export_map: 导出表（用于类名解析）
        import_map: 导入表（用于类名解析）
        node_export: 当前节点导出条目

    Returns:
        UEdGraphNode（基类字段 + class_name）

    Raises:
        ParseError: 若 pins_count 超出安全边界
    """
    # 定位到节点序列化数据起始位置
    archive.seek(node_export.serial_offset)

    # 1. Pins 数组
    pins_count = archive.read_i32()
    if pins_count < 0:
        raise ParseError(
            f"Invalid pins_count {pins_count} (negative) at node {node_export.object_name}"
        )
    if pins_count > MAX_PINS_PER_NODE:
        raise ParseError(
            f"pins_count {pins_count} exceeds MAX_PINS_PER_NODE {MAX_PINS_PER_NODE} "
            f"at node {node_export.object_name}"
        )

    pins: List[UEdGraphPin] = []
    for _ in range(pins_count):
        pin = read_ue_graph_pin(archive, name_map, summary)
        pins.append(pin)

    # 2-3. NodePos
    node_pos_x = archive.read_i32()
    node_pos_y = archive.read_i32()

    # 4. NodeGuid
    node_guid_bytes = archive.read_bytes(16)
    node_guid = node_guid_bytes.hex()

    # 5. NodeComment
    node_comment = archive.read_fstring()

    # 类型识别（D-02b）
    class_name = resolve_class_name(node_export.class_index, import_map, export_map)
    if class_name is None:
        class_name = ""

    # 类型分派（D-02b, GRAPH-05~09）
    # Per RESEARCH.md L260-316: match/case 类型分派
    node_data: Any = None
    match class_name:
        case "K2Node_CallFunction":
            node_data = read_k2node_call_function(
                archive, name_map, import_map, export_map
            )
        case "K2Node_Event":
            node_data = read_k2node_event(
                archive, name_map, import_map, export_map
            )
        case "K2Node_Knot":
            node_data = read_k2node_knot(archive)
        case "EdGraphNode_Comment":
            node_data = read_edgraph_node_comment(archive)
        case "K2Node_EnhancedInputAction":
            node_data = read_k2node_enhanced_input(archive, name_map)
        case _:
            # D-02a: 未知类型 — 记录类型名，继续解析
            node_data = {"unknown_type": class_name}

    return UEdGraphNode(
        node_guid=node_guid,
        node_pos_x=node_pos_x,
        node_pos_y=node_pos_y,
        node_comment=node_comment,
        pins=pins,
        class_name=class_name,
        node_data=node_data
    )


# ============================================================================
# 节点类型特定解析器（GRAPH-05~09）
# ============================================================================

def read_fmember_reference(
    archive: FArchive,
    name_map: List[str],
    import_map: List[ObjectImport],
    export_map: List[ObjectExport]
) -> FMemberReference:
    """
    读取 FMemberReference（GRAPH-05/06 辅助函数）。

    用于 K2Node_CallFunction 和 K2Node_Event 的函数/事件引用。

    序列化顺序（基于 RESEARCH.md L318-355 推断，编辑器导出验证）：
    1. MemberParent (FPackageIndex i32)
    2. MemberName (FName)
    3. MemberGuid (FGuid 16 bytes)
    4. bSelfContext (uint8)

    Args:
        archive: FArchive positioned at FMemberReference
        name_map: NameMap for FName resolution
        import_map: 导入表（用于 FPackageIndex 解析）
        export_map: 导出表（用于 FPackageIndex 解析）

    Returns:
        FMemberReference 实例
    """
    # 1. MemberParent (FPackageIndex)
    member_parent_index = archive.read_i32()
    member_parent: Optional[str] = None
    if member_parent_index != 0:
        member_parent = resolve_class_name(
            PackageIndex(member_parent_index), import_map, export_map
        )

    # 2. MemberName (FName)
    member_name = archive.read_name(name_map)

    # 3. MemberGuid (FGuid 16 bytes)
    member_guid_bytes = archive.read_bytes(16)
    member_guid = member_guid_bytes.hex()

    # 4. bSelfContext (uint8)
    b_self_context = archive.read_u8() != 0

    return FMemberReference(
        member_parent=member_parent,
        member_name=member_name,
        member_guid=member_guid,
        b_self_context=b_self_context
    )


def read_k2node_call_function(
    archive: FArchive,
    name_map: List[str],
    import_map: List[ObjectImport],
    export_map: List[ObjectExport]
) -> K2NodeCallFunction:
    """
    读取 K2Node_CallFunction 特有字段（GRAPH-05）。

    来自编辑器导出验证（test/编辑器中复制出的文本.txt L0-9）：
    FunctionReference=(MemberName="Jump",bSelfContext=True)

    序列化顺序：
    1. FunctionReference (FMemberReference)
    2. bDefaultsToPureFunc (uint8)

    Args:
        archive: FArchive positioned after base class fields
        name_map: NameMap for FName resolution
        import_map: 导入表
        export_map: 导出表

    Returns:
        K2NodeCallFunction 实例
    """
    # 1. FunctionReference (FMemberReference)
    function_reference = read_fmember_reference(
        archive, name_map, import_map, export_map
    )

    # 2. bDefaultsToPureFunc (uint8)
    b_defaults_to_pure = archive.read_u8() != 0

    return K2NodeCallFunction(
        function_reference=function_reference,
        b_defaults_to_pure=b_defaults_to_pure
    )


def read_k2node_event(
    archive: FArchive,
    name_map: List[str],
    import_map: List[ObjectImport],
    export_map: List[ObjectExport]
) -> K2NodeEvent:
    """
    读取 K2Node_Event 特有字段（GRAPH-06）。

    来自编辑器导出验证：
    EventReference=(MemberParent="/Script/Engine.BPGenClass",MemberName="...",MemberGuid=...)

    序列化顺序：
    1. EventReference (FMemberReference)
    2. bOverrideFunction (uint8)

    Args:
        archive: FArchive positioned after base class fields
        name_map: NameMap for FName resolution
        import_map: 导入表
        export_map: 导出表

    Returns:
        K2NodeEvent 实例
    """
    # 1. EventReference (FMemberReference)
    event_reference = read_fmember_reference(
        archive, name_map, import_map, export_map
    )

    # 2. bOverrideFunction (uint8)
    b_override_function = archive.read_u8() != 0

    return K2NodeEvent(
        event_reference=event_reference,
        b_override_function=b_override_function
    )


def read_k2node_knot(archive: FArchive) -> K2NodeKnot:
    """
    读取 K2Node_Knot 特有字段（GRAPH-07）。

    Knot 节点无额外字段，仅 InputPin/OutputPin 在基类 Pins 数组。

    Per RESEARCH.md L563-566: 无额外字段，返回空实例。

    Args:
        archive: FArchive（不读取任何数据）

    Returns:
        K2NodeKnot 空实例
    """
    return K2NodeKnot()


def read_edgraph_node_comment(archive: FArchive) -> EdGraphNodeComment:
    """
    读取 EdGraphNode_Comment 特有字段（GRAPH-08）。

    来自编辑器导出验证（test/编辑器中复制出的文本.txt L20-57, L275-302）：
    CommentColor=(R=0.050980,G=0.050980,B=0.050980,A=1.000000)
    NodeWidth=1440
    NodeHeight=544
    FontSize=14

    序列化顺序：
    1. CommentColor (4 floats RGBA)
    2. NodeWidth (int32)
    3. NodeHeight (int32)
    4. FontSize (int32)

    注意：NodeComment 已在基类 NodeComment 字段读取。

    Args:
        archive: FArchive positioned after base class fields

    Returns:
        EdGraphNodeComment 实例
    """
    # 1. CommentColor (4 floats RGBA)
    r = struct.unpack('<f', archive.read(4))[0]
    g = struct.unpack('<f', archive.read(4))[0]
    b = struct.unpack('<f', archive.read(4))[0]
    a = struct.unpack('<f', archive.read(4))[0]
    comment_color = (r, g, b, a)

    # 2-4. NodeWidth/Height/FontSize (int32)
    node_width = archive.read_i32()
    node_height = archive.read_i32()
    font_size = archive.read_i32()

    return EdGraphNodeComment(
        comment_color=comment_color,
        node_width=node_width,
        node_height=node_height,
        font_size=font_size
    )


def read_k2node_enhanced_input(
    archive: FArchive,
    name_map: List[str]
) -> K2NodeEnhancedInputAction:
    """
    读取 K2Node_EnhancedInputAction 特有字段（GRAPH-09）。

    来自编辑器导出验证（test/编辑器中复制出的文本.txt L58-99）：
    InputAction="/Script/EnhancedInput.InputAction'/Game/Input/Actions/IA_Look.IA_Look'"

    序列化顺序：
    1. InputAction (FSoftObjectPath: AssetPath FString)

    Args:
        archive: FArchive positioned after base class fields
        name_map: NameMap（可能用于其他字段，但 InputAction 为 FString）

    Returns:
        K2NodeEnhancedInputAction 实例
    """
    # 1. InputAction (FSoftObjectPath AssetPath)
    # FSoftObjectPath 序列化为 AssetPath (FString) + SubPathString (FString)
    # 但编辑器导出显示仅有 AssetPath，暂只读取 AssetPath
    input_action_path = archive.read_fstring()

    return K2NodeEnhancedInputAction(
        input_action_path=input_action_path
    )


def read_ue_graph(
    archive: FArchive,
    name_map: List[str],
    summary: PackageFileSummary,
    export_map: List[ObjectExport],
    import_map: List[ObjectImport],
    graph_export: ObjectExport,
    graph_class: str
) -> UEdGraph:
    """
    读取 UEdGraph（GRAPH-02/03）。

    序列化顺序（基于 UE 源码 EdGraph.cpp）：
    1. Schema (FPackageIndex -> resolve)
    2. Nodes 数组 (int32 count + FPackageIndex[])
       — 需从 FPackageIndex 找到对应导出并调用 read_ue_graph_node
    3. GraphGuid (FGuid 16 bytes)
    4. bEditable (uint8)

    安全边界（T-07-02-03）：
    - nodes_count <= MAX_NODES_PER_GRAPH (5000)

    Args:
        archive: FArchive
        name_map: NameMap for FName resolution
        summary: PackageFileSummary for version info
        export_map: 导出表
        import_map: 导入表
        graph_export: 图导出条目
        graph_class: 已解析的类名

    Returns:
        UEdGraph with nodes populated

    Raises:
        ParseError: 若 nodes_count 超出安全边界
    """
    # 定位到图序列化数据起始位置
    archive.seek(graph_export.serial_offset)

    # 1. Schema (FPackageIndex)
    schema_index = archive.read_i32()
    schema: Optional[str] = None
    if schema_index != 0:
        schema = resolve_class_name(PackageIndex(schema_index), import_map, export_map)

    # 2. Nodes 数组（FPackageIndex 数组）
    nodes_count = archive.read_i32()
    if nodes_count < 0:
        raise ParseError(
            f"Invalid nodes_count {nodes_count} (negative) at graph {graph_export.object_name}"
        )
    if nodes_count > MAX_NODES_PER_GRAPH:
        raise ParseError(
            f"nodes_count {nodes_count} exceeds MAX_NODES_PER_GRAPH {MAX_NODES_PER_GRAPH} "
            f"at graph {graph_export.object_name}"
        )

    nodes: List[UEdGraphNode] = []

    # Nodes 是导出索引数组（FPackageIndex > 0）
    for _ in range(nodes_count):
        node_index = archive.read_i32()  # FPackageIndex
        if node_index > 0 and node_index <= len(export_map):
            node_export = export_map[node_index - 1]
            node = read_ue_graph_node(
                archive, name_map, summary,
                export_map, import_map, node_export
            )
            nodes.append(node)

    # 3. GraphGuid
    graph_guid_bytes = archive.read_bytes(16)
    graph_guid = graph_guid_bytes.hex()

    # 4. bEditable
    b_editable = archive.read_u8() != 0

    return UEdGraph(
        graph_name=graph_export.object_name,
        graph_class=graph_class,
        schema=schema,
        nodes=nodes,
        graph_guid=graph_guid,
        b_editable=b_editable
    )


def parse_default_value(value_str: str, var_type: FEdGraphPinType) -> any:
    """
    Parse DefaultValue string to Python native type (BLUE-03).

    Per D-13: Parse to int, float, bool, str.
    Per D-14: Fallback to raw string on parse failure.
    Per D-15: Only basic types - no arrays, vectors, objects.
    Per D-16: Vector types stay as string "(X=...,Y=...,Z=...)".

    Args:
        value_str: The DefaultValue FString from FBPVariableDescription
        var_type: FEdGraphPinType for type detection (PinCategory)

    Returns:
        Parsed Python value (int, float, bool, str) or raw string.
    """
    if not value_str:
        return None

    # Check for vector format per D-16: keep as string
    if value_str.startswith("(") and value_str.endswith(")"):
        return value_str

    # Match PinCategory for type detection
    category = var_type.pin_category.lower()

    # Boolean parsing (D-13)
    if category in ("bool", "boolean"):
        if value_str.lower() in ("true", "1"):
            return True
        elif value_str.lower() in ("false", "0"):
            return False
        # D-14: fallback to raw string
        return value_str

    # Integer parsing (D-13)
    if category in ("int", "integer"):
        match = re.match(r'^-?\d+$', value_str)
        if match:
            return int(value_str)
        return value_str  # D-14: fallback

    # Float/Real parsing (D-13)
    if category in ("float", "real", "double"):
        match = re.match(r'^-?\d+\.?\d*$', value_str)
        if match:
            return float(value_str)
        return value_str  # D-14: fallback

    # String/Name: keep as-is (D-15)
    if category in ("string", "name", "text"):
        return value_str

    # Unknown category: fallback to raw string (D-14)
    return value_str


def read_blueprint_variable(
    archive: FArchive,
    name_map: List[str],
    summary: PackageFileSummary
) -> BlueprintVariable:
    """
    Parse FBPVariableDescription from blueprint export (BLUE-03).

    Serialization order from Blueprint.h lines 200-256 [VERIFIED]:
    1. VarName (FName)
    2. VarGuid (FGuid - 16 bytes) - skip
    3. VarType (FEdGraphPinType)
    4. FriendlyName (FString)
    5. Category (FText - simplified to FString)
    6. PropertyFlags (uint64)
    7. RepNotifyFunc (FName) - skip
    8. ReplicationCondition (uint8) - skip
    9. MetaDataArray (TArray) - skip for Phase 3
    10. DefaultValue (FString)

    Per D-05/D-06/D-07: full FEdGraphPinType for type info.
    Per D-13/D-14/D-15/D-16: parse DefaultValue with parse_default_value().

    Args:
        archive: FArchive positioned at start of FBPVariableDescription
        name_map: NameMap for FName resolution
        summary: PackageFileSummary for version info

    Returns:
        BlueprintVariable dataclass with all parsed fields
    """
    var = BlueprintVariable(
        var_name=archive.read_name(name_map)
    )

    # VarGuid (16 bytes) - skip, not needed for Phase 3
    archive.read(16)

    # VarType (FEdGraphPinType)
    var.var_type = read_ed_graph_pin_type(archive, name_map, summary)

    # FriendlyName (FString)
    var.friendly_name = archive.read_fstring()

    # Category (FText) - simplified to FString for Phase 3
    # FText has complex serialization; simplified representation
    var.category = archive.read_fstring()

    # PropertyFlags (uint64)
    var.property_flags = archive.read_u64()

    # RepNotifyFunc (FName) - skip for Phase 3 (D-16 deferred metadata)
    archive.read_name(name_map)

    # ReplicationCondition (uint8) - skip for Phase 3
    archive.read_u8()

    # MetaDataArray count + entries - skip for Phase 3 (deferred)
    meta_count = archive.read_i32()
    for _ in range(meta_count):
        archive.read_name(name_map)  # DataKey
        archive.read_fstring()       # DataValue

    # DefaultValue (FString) - parse per D-13/D-14/D-15
    default_str = archive.read_fstring()
    var.default_value = parse_default_value(default_str, var.var_type)

    return var


def extract_blueprint_metadata(
    export: ObjectExport,
    archive: FArchive,
    import_map: List[ObjectImport],
    export_map: List[ObjectExport],
    name_map: List[str],
    summary: PackageFileSummary
) -> Tuple[Optional[BlueprintMetadata], Optional[str]]:
    """
    Extract complete blueprint metadata from export (BLUE-06).

    Flow:
    1. Check if export is a blueprint via detect_blueprint()
    2. Use export.super_index for ParentClass resolution
    3. Seek to export.serial_offset
    4. Read NewVariables count + array via read_blueprint_variable()
    5. Return BlueprintMetadata

    Per D-02/D-03: auto-detection with warning on failure.

    Args:
        export: ObjectExport to extract from
        archive: FArchive instance
        import_map: Import table for resolution
        export_map: Export table for resolution
        name_map: NameMap for FName resolution
        summary: PackageFileSummary for version info

    Returns:
        Tuple of (BlueprintMetadata, warning_if_any)
        - (blueprint_metadata, None) on success
        - (None, warning_string) on detection failure
    """
    # Step 1: Detect if this export is a blueprint
    if not detect_blueprint(export, import_map, export_map):
        return None, None  # Not a blueprint, no warning

    # Step 2: ParentClass - use export.super_index directly
    # Per D-09/D-10: resolve to object name from ImportMap/ExportMap
    parent_class, parent_warning = resolve_parent_class(
        export.super_index,
        import_map,
        export_map
    )

    # Step 3: Seek to export data
    archive.seek(export.serial_offset)

    # Step 4: Read NewVariables array (TArray<FBPVariableDescription>)
    # Per Blueprint.h: NewVariables is TArray, so read count first
    # Note: Blueprint exports have additional fields before NewVariables
    # For Phase 3, we use a simplified approach that reads variables directly

    variables: List[BlueprintVariable] = []

    try:
        # Read NewVariables count (int32)
        var_count = archive.read_i32()

        # Per D-04: sanity check on variable count
        if var_count > 1000:
            warning = f"NewVariables count {var_count} exceeds reasonable limit"
            blueprint = BlueprintMetadata(
                is_blueprint=True,
                parent_class=parent_class,
                variables=variables,
                detection_warning=warning
            )
            return blueprint, warning

        # Read each variable
        for _ in range(var_count):
            var = read_blueprint_variable(archive, name_map, summary)
            variables.append(var)

    except ParseError as e:
        # Per D-03: add warning on extraction failure
        warning = f"Variable extraction failed: {e}"
        blueprint = BlueprintMetadata(
            is_blueprint=True,
            parent_class=parent_class,
            variables=variables,
            detection_warning=warning
        )
        return blueprint, warning

    blueprint = BlueprintMetadata(
        is_blueprint=True,
        parent_class=parent_class,
        variables=variables,
        detection_warning=parent_warning
    )

    return blueprint, None


# ============================================================================
# PropertyTag 解析（Phase 2）
# ============================================================================

def use_complete_type_name(legacy_version: int, ue5_version: int) -> bool:
    """
    判断是否使用完整 TypeName 格式（PROP-09）。

    UE5 >= PROPERTY_TAG_COMPLETE_TYPE_NAME (1000) 使用完整 TypeName 字符串。
    UE4 始终使用旧格式（短名称 + 分离字段）。

    Args:
        legacy_version: LegacyFileVersion（-2 至 -9）
        ue5_version: UE5 版本号

    Returns:
        True 使用 UE5 新格式，False 使用 UE4 旧格式
    """
    if legacy_version <= -8 and ue5_version >= PROPERTY_TAG_COMPLETE_TYPE_NAME:
        return True
    return False


def read_property_tag(
    archive: FArchive,
    name_map: List[str],
    legacy_version: int,
    ue5_version: int
) -> PropertyTag:
    """
    读取 PropertyTag 结构（PROP-01）。

    根据 UE 源码 PropertyTag.cpp：
    - UE5 新格式（>= PROPERTY_TAG_COMPLETE_TYPE_NAME）：完整 TypeName 字符串
    - UE4 旧格式：短 Type 名称 + 分离字段（ArrayIndex、BoolVal 等）

    Args:
        archive: FArchive 实例
        name_map: 名称表
        legacy_version: LegacyFileVersion
        ue5_version: UE5 版本号

    Returns:
        PropertyTag dataclass
    """
    tag = PropertyTag(
        name=archive.read_name(name_map),
        type="",
        size=0
    )

    if use_complete_type_name(legacy_version, ue5_version):
        # UE5 新格式（PropertyTag.cpp lines 436-545）
        tag.type = archive.read_fstring()  # Complete TypeName string
        tag.size = archive.read_i32()
        archive.validate_size(tag.size, tag.name)  # D-11: validate PropertyTag.Size
        tag.flags = archive.read_u8()

        # 条件字段（基于标志位）
        if tag.flags & PROP_TAG_HAS_ARRAY_INDEX:
            tag.array_index = archive.read_i32()

        if tag.flags & PROP_TAG_HAS_PROPERTY_GUID:
            tag.property_guid = archive.read(16)

        # BoolTrue 标志表示 bool 值为 true
        if tag.flags & PROP_TAG_BOOL_TRUE:
            tag.bool_val = 1
    else:
        # UE4 旧格式（PropertyTag.cpp lines 195-401）
        tag.type = archive.read_name(name_map)  # Short type name only
        tag.size = archive.read_i32()
        archive.validate_size(tag.size, tag.name)  # D-11: validate PropertyTag.Size
        tag.array_index = archive.read_i32()  # Always present in UE4

        # 类型特定的额外字段（Phase 2 仅处理基本类型）
        # BoolProperty: BoolVal 字段存在
        if tag.type == "BoolProperty":
            tag.bool_val = archive.read_u8()

        # PropertyGuid（UE4 >= VER_UE4_PROPERTY_GUID_IN_PROPERTY_TAG）
        # Phase 2 简化处理：不读取 PropertyGuid，跳过依赖版本检查
        # 完整实现需检查 file_version_ue4 >= VER_UE4_PROPERTY_GUID_IN_PROPERTY_TAG

    return tag


# ============================================================================
# 属性值解析（Phase 2 基本类型）
# ============================================================================

def parse_bool_property(tag: PropertyTag, archive: FArchive) -> bool:
    """
    解析 BoolProperty（PROP-04）。

    BoolProperty 值存储在 PropertyTag.BoolVal，无额外数据读取。
    参考 PropertyTag.cpp lines 558-571。

    Args:
        tag: PropertyTag 实例
        archive: FArchive 实例（不读取额外数据）

    Returns:
        bool 值
    """
    return bool(tag.bool_val)


def parse_int_property(tag: PropertyTag, archive: FArchive) -> int:
    """
    解析 IntProperty（PROP-02）。

    根据 Type 名称分派：
    - IntProperty: read_i32() → 4 bytes
    - Int64Property: read_i64() → 8 bytes
    - Int16Property: read_u16() → 2 bytes
    - Int8Property/ByteProperty: read_u8() → 1 byte

    Args:
        tag: PropertyTag 实例
        archive: FArchive 实例

    Returns:
        int 值
    """
    type_name = tag.type
    if type_name == "Int64Property":
        return archive.read_i64()
    elif type_name == "Int16Property":
        return struct.unpack('<h', archive.read(2))[0]
    elif type_name in ("Int8Property", "ByteProperty"):
        return archive.read_u8()
    else:  # IntProperty (default)
        return archive.read_i32()


def parse_float_property(tag: PropertyTag, archive: FArchive) -> float:
    """
    解析 FloatProperty（PROP-03）。

    根据 Type 名称分派：
    - FloatProperty: read_f32() → 4 bytes IEEE 754
    - DoubleProperty: read_f64() → 8 bytes IEEE 754

    Args:
        tag: PropertyTag 实例
        archive: FArchive 实例

    Returns:
        float 值
    """
    type_name = tag.type
    if type_name == "DoubleProperty":
        return archive.read_f64()
    else:  # FloatProperty (default)
        return archive.read_f32()


def parse_str_property(tag: PropertyTag, archive: FArchive) -> str:
    """
    解析 StrProperty（PROP-05）。

    使用 archive.read_fstring() 方法读取带长度前缀的 UTF-8 字符串。

    Args:
        tag: PropertyTag 实例
        archive: FArchive 实例

    Returns:
        str 值
    """
    return archive.read_fstring()


def parse_name_property(tag: PropertyTag, archive: FArchive, name_map: List[str]) -> str:
    """
    解析 NameProperty（PROP-06）。

    使用 archive.read_name() 方法从 NameMap 读取 FName。

    Args:
        tag: PropertyTag 实例
        archive: FArchive 实例
        name_map: 名称表

    Returns:
        str 值（名称字符串）
    """
    return archive.read_name(name_map)


def parse_object_property(tag: PropertyTag, archive: FArchive) -> int:
    """
    解析 ObjectProperty（PROP-07）。

    读取 FPackageIndex（int32），返回原始索引值。
    索引解析（映射到 ImportMap/ExportMap）推迟到阶段 3/4。

    参考 ObjectResource.h - FPackageIndex 序列化。

    Args:
        tag: PropertyTag 实例
        archive: FArchive 实例

    Returns:
        int 值（原始 FPackageIndex）
    """
    return archive.read_i32()


def parse_soft_object_property(
    tag: PropertyTag,
    archive: FArchive,
    name_map: List[str]
) -> Dict[str, str]:
    """
    解析 SoftObjectProperty（FSoftObjectPath）。

    Phase 11-03: 新增SoftObjectProperty解析器。

    UE5格式：
    - AssetPath: FString（如 "/Game/Characters/Mannequin/Animations/Walk")
    - SubPath: FString（如 "" 空字符串表示无子路径，或"SubObject.Path")

    参考 SoftObjectPath.h - FSoftObjectPath 序列化。

    Args:
        tag: PropertyTag 实例（包含属性名和类型）
        archive: FArchive 二进制读取器
        name_map: NameMap列表（未使用，保持签名一致性）

    Returns:
        {"asset_path": str, "sub_path": str}
    """
    asset_path = archive.read_fstring()
    sub_path = archive.read_fstring()

    return {
        "asset_path": asset_path,
        "sub_path": sub_path
    }


def parse_array_property(
    tag: PropertyTag,
    archive: FArchive,
    name_map: List[str],
    export_map: List[ObjectExport],
    depth: int = 0
) -> List[any]:
    """
    解析 ArrayProperty（PROP-08, D-16）。

    ArrayProperty 格式：
    1. 读取元素数量（int32）
    2. 循环读取各元素值

    参考 PropertyArray.cpp lines 128-824。

    Args:
        tag: PropertyTag 实例
        archive: FArchive 实例
        name_map: 名称表
        export_map: 导出表
        depth: 当前嵌套深度（D-18 最大 10）

    Returns:
        List 值（元素列表）

    Raises:
        ParseError: 若嵌套深度超过 10
    """
    MAX_DEPTH = 10  # D-18 嵌套深度限制

    if depth > MAX_DEPTH:
        raise ParseError(
            f"ArrayProperty nesting depth {depth} exceeds maximum {MAX_DEPTH}"
        )

    count = archive.read_i32()
    elements: List[any] = []

    # Phase 2: 基本类型数组元素解析
    # 注意：复杂类型数组（如结构体数组）需要读取内部 PropertyTag
    # 此实现假设元素类型可从 tag.type 推断或为基本类型
    for i in range(count):
        # 简化实现：假设元素为基本类型，直接读取值
        # 完整实现需要读取内部 PropertyTag 并分派
        # Phase 2 仅处理基本类型数组
        inner_tag = PropertyTag(
            name=f"{tag.name}[{i}]",
            type=_get_inner_type(tag.type),
            size=tag.size // count if count > 0 else 0
        )

        inner_value = parse_property_value(inner_tag, archive, name_map, export_map)
        elements.append(inner_value)

    return elements


def _get_inner_type(array_type: str) -> str:
    """
    从 ArrayProperty 类型名推断内部元素类型（简化版）。

    Phase 2 简化：假设基本类型数组。
    完整实现需从 TypeName 参数或 InnerType 字段获取。

    Args:
        array_type: 数组类型名（如 "ArrayProperty"）

    Returns:
        推断的元素类型名
    """
    # Phase 2 简化：返回通用类型，实际值由 parse_property_value 处理
    # 完整实现需解析 TypeName 参数获取真实内部类型
    return "IntProperty"  # 默认假设


# ============================================================================
# Phase 9: TypeName 参数解析辅助函数（Wave 2）
# ============================================================================

def _extract_struct_type_from_tag(tag: PropertyTag) -> str:
    """
    从 PropertyTag 提取结构体类型名（D-08）。

    UE5 格式: "StructProperty(/Script/CoreUObject.Vector)"
    UE4 格式: 使用分离字段（简化处理）。

    Args:
        tag: PropertyTag 实例

    Returns:
        结构体类型名（去除路径前缀）
    """
    type_str = tag.type

    # UE5: 提取括号内参数
    if "(" in type_str:
        # 格式: "StructProperty(/Script/CoreUObject.Vector)"
        # 提取括号内内容
        start = type_str.find("(")
        end = type_str.find(")")
        if start != -1 and end != -1:
            struct_path = type_str[start+1:end]
            # 提取类型名（去除路径前缀）
            if "." in struct_path:
                return struct_path.split(".")[-1]
            return struct_path

    # UE4: 简化处理，返回类型名
    # 完整实现需要从分离字段获取（StructName 字段）
    return "UnknownStruct"


def _extract_map_types_from_tag(tag: PropertyTag) -> Tuple[str, str]:
    """
    从 PropertyTag 提取 Map Key/Value 类型（D-08）。

    UE5 格式: "MapProperty(IntProperty,StrProperty)"
    UE4 格式: 使用分离字段（简化处理）。

    Args:
        tag: PropertyTag 实例

    Returns:
        (key_type, value_type) 元组
    """
    type_str = tag.type

    # UE5: 提取括号内参数
    if "(" in type_str:
        start = type_str.find("(")
        end = type_str.find(")")
        if start != -1 and end != -1:
            params = type_str[start+1:end]
            # 分割 Key,Value
            parts = params.split(",")
            if len(parts) >= 2:
                return parts[0].strip(), parts[1].strip()

    # UE4: 简化处理，返回默认类型
    # 完整实现需要从分离字段获取（InnerType、ValueType 字段）
    return "IntProperty", "IntProperty"


def _extract_set_type_from_tag(tag: PropertyTag) -> str:
    """
    从 PropertyTag 提取 Set 元素类型（D-08）。

    UE5 格式: "SetProperty(IntProperty)"
    UE4 格式: 使用分离字段（简化处理）。

    Args:
        tag: PropertyTag 实例

    Returns:
        元素类型名
    """
    type_str = tag.type

    # UE5: 提取括号内参数
    if "(" in type_str:
        start = type_str.find("(")
        end = type_str.find(")")
        if start != -1 and end != -1:
            return type_str[start+1:end].strip()

    # UE4: 简化处理
    # 完整实现需要从分离字段获取（InnerType 字段）
    return "IntProperty"


def _extract_enum_type_from_tag(tag: PropertyTag) -> str:
    """
    从 PropertyTag 提取枚举类型名（D-08）。

    UE5 格式: "EnumProperty(/Script/Game.EWalletState)"
    UE4 格式: 使用分离字段（简化处理）。

    Args:
        tag: PropertyTag 实例

    Returns:
        枚举类型名（去除路径前缀）
    """
    type_str = tag.type

    # UE5: 提取括号内参数
    if "(" in type_str:
        start = type_str.find("(")
        end = type_str.find(")")
        if start != -1 and end != -1:
            enum_path = type_str[start+1:end]
            # 提取类型名（去除路径前缀）
            if "." in enum_path:
                return enum_path.split(".")[-1]
            return enum_path

    # UE4: 简化处理
    # 完整实现需要从分离字段获取（EnumName 字段）
    return "UnknownEnum"


# ============================================================================
# Phase 9: 高级属性解析函数（Wave 1 占位符）
# ============================================================================

def parse_struct_property(
    tag: PropertyTag,
    archive: FArchive,
    name_map: List[str],
    export_map: List[ObjectExport],
    summary: Optional[PackageFileSummary] = None,
    depth: int = 0
) -> StructValue:
    """
    解析 StructProperty（ADVP-01）。

    递归 PropertyTag 循环解析内部字段。
    最大递归深度 5（D-01）。

    来自 PropertyStruct.cpp §167-172。

    Args:
        tag: PropertyTag 实例
        archive: FArchive 实例
        name_map: 名称表
        export_map: 导出表
        summary: PackageFileSummary 实例（版本检查）
        depth: 递归深度（最大 5）

    Returns:
        StructValue dataclass

    Raises:
        ParseError: 若嵌套深度超过 5
    """
    MAX_DEPTH = 5  # D-01 深度限制（不同于 ArrayProperty 的 10）

    if depth > MAX_DEPTH:
        raise ParseError(
            f"StructProperty nesting depth {depth} exceeds maximum {MAX_DEPTH}"
        )

    # 提取结构体类型名（UE5 格式）
    # UE5: tag.type = "StructProperty(/Script/CoreUObject.Vector)"
    struct_type = _extract_struct_type_from_tag(tag)

    fields: Dict[str, Any] = {}
    property_count = 0

    # PropertyTag 循环（直到 Name == "None"）
    while property_count < MAX_PROPERTY_COUNT:
        property_count += 1

        # 需要版本信息来调用 read_property_tag
        if summary is None:
            # 无版本信息时使用默认值（可能导致解析错误）
            legacy_version = 0
            ue5_version = 0
        else:
            legacy_version = summary.legacy_file_version
            ue5_version = summary.file_version_ue5

        inner_tag = read_property_tag(
            archive, name_map,
            legacy_version,
            ue5_version
        )

        if inner_tag.name == "None":
            break

        # 递归解析字段值（depth + 1）
        field_value = parse_property_value(
            inner_tag, archive, name_map, export_map,
            summary, depth + 1
        )
        fields[inner_tag.name] = field_value

    return StructValue(
        property_type="StructProperty",
        struct_type=struct_type,
        fields=fields
    )


def parse_map_property(
    tag: PropertyTag,
    archive: FArchive,
    name_map: List[str],
    export_map: List[ObjectExport],
    summary: Optional[PackageFileSummary] = None
) -> MapValue:
    """
    解析 MapProperty（ADVP-02）。

    支持基本类型、枚举、Struct、Object 键（D-02）。

    来自 PropertyMap.cpp §267-880。

    Args:
        tag: PropertyTag 实例
        archive: FArchive 实例
        name_map: 名称表
        export_map: 导出表
        summary: PackageFileSummary 实例（版本检查）

    Returns:
        MapValue dataclass
    """
    # 提取 Key/Value 类型（UE5 格式）
    # UE5: tag.type = "MapProperty(IntProperty,StrProperty)"
    key_type, value_type = _extract_map_types_from_tag(tag)

    # 简化格式：NumEntries + Key/Value pairs
    num_entries = archive.read_i32()
    entries: List[Dict[str, Any]] = []

    for _ in range(num_entries):
        # D-02b 键解析分派
        key = _dispatch_key_parse(key_type, archive, name_map, export_map, summary)
        value = _dispatch_value_parse(value_type, archive, name_map, export_map, summary)
        entries.append({"key": key, "value": value})

    return MapValue(
        property_type="MapProperty",
        key_type=key_type,
        value_type=value_type,
        entries=entries
    )


def _dispatch_key_parse(
    key_type: str,
    archive: FArchive,
    name_map: List[str],
    export_map: List[ObjectExport],
    summary: Optional[PackageFileSummary] = None
) -> Any:
    """
    键类型分派解析（D-02b）。

    支持：基本类型、枚举、Struct、Object。

    Args:
        key_type: 键类型名
        archive: FArchive 实例
        name_map: 名称表
        export_map: 导出表
        summary: PackageFileSummary 实例

    Returns:
        解析后的键值
    """
    # 基本类型分派（复用 parse_property_value）
    basic_types = [
        "IntProperty", "Int64Property", "FloatProperty", "DoubleProperty",
        "StrProperty", "NameProperty", "BoolProperty", "ByteProperty"
    ]
    if key_type in basic_types:
        dummy_tag = PropertyTag(name="Key", type=key_type, size=0)
        return parse_property_value(dummy_tag, archive, name_map, export_map, summary, depth=0)

    # ObjectProperty 键
    if key_type == "ObjectProperty":
        return archive.read_i32()  # FPackageIndex 原始值

    # EnumProperty 键
    if key_type == "EnumProperty":
        return archive.read_name(name_map)  # FName 枚举值名

    # StructProperty 键（简化处理）
    # 完整实现需要 PropertyTag 循环
    # D-02b: 简化处理，返回 None
    return None


def _dispatch_value_parse(
    value_type: str,
    archive: FArchive,
    name_map: List[str],
    export_map: List[ObjectExport],
    summary: Optional[PackageFileSummary] = None
) -> Any:
    """
    值类型分派解析。

    复用 parse_property_value type_dispatch。

    Args:
        value_type: 值类型名
        archive: FArchive 实例
        name_map: 名称表
        export_map: 导出表
        summary: PackageFileSummary 实例

    Returns:
        解析后的值
    """
    dummy_tag = PropertyTag(name="Value", type=value_type, size=0)
    return parse_property_value(dummy_tag, archive, name_map, export_map, summary, depth=0)


def parse_set_property(
    tag: PropertyTag,
    archive: FArchive,
    name_map: List[str],
    export_map: List[ObjectExport],
    summary: Optional[PackageFileSummary] = None
) -> SetValue:
    """
    解析 SetProperty（ADVP-03）。

    解析为 List，不验证唯一性（D-03）。
    格式与 ArrayProperty 相似。

    来自 PropertySet.cpp §221-427。

    Args:
        tag: PropertyTag 实例
        archive: FArchive 实例
        name_map: 名称表
        export_map: 导出表
        summary: PackageFileSummary 实例（版本检查）

    Returns:
        SetValue dataclass
    """
    # 提取元素类型（UE5 格式）
    # UE5: tag.type = "SetProperty(IntProperty)"
    element_type = _extract_set_type_from_tag(tag)

    # 简化格式：NumElements + 元素循环
    num_elements = archive.read_i32()
    elements: List[Any] = []

    for _ in range(num_elements):
        # 元素解析（复用 type_dispatch）
        dummy_tag = PropertyTag(name="Element", type=element_type, size=0)
        element = parse_property_value(dummy_tag, archive, name_map, export_map, summary, depth=0)
        elements.append(element)

    return SetValue(
        property_type="SetProperty",
        element_type=element_type,
        elements=elements
    )


def parse_enum_property(
    tag: PropertyTag,
    archive: FArchive,
    name_map: List[str],
    summary: Optional[PackageFileSummary] = None
) -> EnumValue:
    """
    解析 EnumProperty（ADVP-04）。

    FName EnumValueName 序列化（非整数值）。
    返回枚举值名（如 'EWalletState::Active'）（D-04）。

    来自 EnumProperty.cpp §279-353。

    Args:
        tag: PropertyTag 实例
        archive: FArchive 实例
        name_map: 名称表
        summary: PackageFileSummary 实例（版本检查，未使用）

    Returns:
        EnumValue dataclass
    """
    # 提取枚举类型名（UE5 格式）
    # UE5: tag.type = "EnumProperty(/Script/Game.EWalletState)"
    enum_type = _extract_enum_type_from_tag(tag)

    # SerializeItem: FName EnumValueName
    enum_value_name = archive.read_name(name_map)

    # D-04 返回枚举值名（如 "EWalletState::Active"）
    # 格式：EnumType::ValueName
    value_name = f"{enum_type}::{enum_value_name}"

    return EnumValue(
        property_type="EnumProperty",
        enum_type=enum_type,
        value_name=value_name
    )


def parse_text_property(
    tag: PropertyTag,
    archive: FArchive
) -> TextValue:
    """
    解析 TextProperty（ADVP-05）。

    FText 序列化格式：
    - Flags (int32)
    - Namespace (FString)
    - Key (FString)
    - SourceString (FString)

    完整结构返回（D-05）。

    来自 TextProperty.cpp §135-139。

    Args:
        tag: PropertyTag 实例
        archive: FArchive 实例

    Returns:
        TextValue dataclass
    """
    # FText 序列化格式
    flags = archive.read_i32()
    namespace = archive.read_fstring()
    key = archive.read_fstring()
    source_string = archive.read_fstring()

    # D-05 完整结构返回
    return TextValue(
        property_type="TextProperty",
        namespace=namespace or "",
        key=key or "",
        source_string=source_string or ""
    )


def parse_delegate_property(
    tag: PropertyTag,
    archive: FArchive,
    name_map: List[str]
) -> DelegateValue:
    """
    解析 DelegateProperty（ADVP-06）。

    FScriptDelegate 序列化：
    - ObjectRef (FPackageIndex = int32)
    - FunctionName (FName)

    原始引用格式，延迟解析（D-06b）。

    来自 PropertyDelegate.cpp §86-89。

    Args:
        tag: PropertyTag 实例
        archive: FArchive 实例
        name_map: 名称表

    Returns:
        DelegateValue dataclass
    """
    # FScriptDelegate 序列化
    object_ref = archive.read_i32()  # FPackageIndex 原始值
    function_name = archive.read_name(name_map)

    # D-06b 延迟解析 ObjectRef
    # Phase 10 依赖分析时解析为对象名
    return DelegateValue(
        property_type="DelegateProperty",
        object_ref=object_ref,
        function_name=function_name
    )


def parse_properties_from_export(
    export: ObjectExport,
    archive: FArchive,
    summary: PackageFileSummary,
    name_map: List[str],
    export_map: List[ObjectExport],
    import_map: Optional[List["ObjectImport"]] = None
) -> List[PropertyValue]:
    """
    从导出条目解析所有属性（PROP-01 至 PROP-08）。

    参考 Class.cpp SerializeVersionedTaggedProperties 模式：
    1. Seek 到 export.serial_offset
    2. 循环读取 PropertyTag 直到 Name == "None"
    3. 分派到类型特定解析函数
    4. 边界验证（seek 到 start + tag.size）

    Phase 11-02: 增强ObjectProperty返回可读对象引用。

    Args:
        export: ObjectExport 实例
        archive: FArchive 实例
        summary: PackageFileSummary 实例（版本信息）
        name_map: 名称表
        export_map: 导出表
        import_map: 导入表（Phase 11-02 ObjectProperty解析需要）

    Returns:
        List[PropertyValue] 属性值列表
    """
    archive.seek(export.serial_offset)
    properties: List[PropertyValue] = []
    property_count = 0  # D-08: loop counter for SAFE-05

    while True:
        # D-08/D-09: Property loop limit check
        if property_count >= MAX_PROPERTY_COUNT:
            raise ParseError(
                f"Property count exceeds {MAX_PROPERTY_COUNT} - possible infinite loop"
            )
        property_count += 1

        tag = None  # Phase 11 D-01: 初始化 tag 用于异常处理
        start_pos = None  # Phase 11 D-01: 初始化 start_pos 用于异常处理

        try:
            tag = read_property_tag(
                archive,
                name_map,
                summary.legacy_file_version,
                summary.file_version_ue5
            )

            # 终止标记：Name == "None"
            if tag.name == "None":
                break

            # 记录起始位置用于边界验证
            start_pos = archive.tell()

            # 分派到类型特定解析器
            value = parse_property_value(tag, archive, name_map, export_map)

            # 边界验证：确保定位到正确位置
            expected_end = start_pos + tag.size
            current_pos = archive.tell()
            if current_pos != expected_end:
                # 修正位置（处理读取不足或过多）
                archive.seek(expected_end)

            properties.append(PropertyValue(
                name=tag.name,
                type=tag.type,
                value=value,
                array_index=tag.array_index
            ))

            # Phase 11-02: 增强ObjectProperty解析返回可读对象引用
            # 在append之后修改最后一个属性值（如果import_map可用）
            if import_map is not None and tag.type == "ObjectProperty" and isinstance(value, int):
                pkg_idx = PackageIndex(value)
                resolved = resolve_package_index_to_reference(pkg_idx, import_map, export_map, name_map)
                # 更新最后一个属性的value为增强格式
                properties[-1].value = {"raw_index": value, "resolved": resolved}

        except ParseError as e:
            # D-19: Smart continue - skip damaged property using PropertyTag.Size
            # Phase 11 D-01: 检查 tag 和 start_pos 是否已定义
            if tag is not None and start_pos is not None and tag.size > 0 and start_pos + tag.size <= archive.total_size():
                archive.seek(start_pos + tag.size)
                # D-14: Record warning (would be passed to caller via ParseResult)
                properties.append(PropertyValue(
                    name=tag.name,
                    type="Warning",
                    value=f"Property skipped: {e}"
                ))
                continue
            else:
                # Cannot skip - tag undefined or Size invalid, abort property parsing for this export
                properties.append(PropertyValue(
                    name="ParseError",
                    type="Error",
                    value=f"Property parsing aborted: {e}"
                ))
                break

    return properties


def parse_property_value(
    tag: PropertyTag,
    archive: FArchive,
    name_map: List[str],
    export_map: List[ObjectExport],
    summary: Optional[PackageFileSummary] = None,
    depth: int = 0
) -> any:
    """
    分派属性值解析（PROP-02 至 PROP-06）。

    根据 tag.type 分派到类型特定的解析函数。
    未知类型返回 None（D-26 跳过策略）。

    Phase 9 扩展（D-08）：
    - 添加 summary 参数用于版本检查
    - 添加 depth 参数用于 StructProperty 递归深度限制

    Args:
        tag: PropertyTag 实例
        archive: FArchive 实例
        name_map: 名称表
        export_map: 导出表
        summary: PackageFileSummary 实例（Phase 9 高级属性需要）
        depth: 递归深度（Phase 9 StructProperty 需要）

    Returns:
        解析后的值（Python 原生类型）或 None（未知类型）
    """
    type_dispatch = {
        # Phase 2 基本类型（忽略 summary/depth 参数）
        "BoolProperty": lambda t, a, n, e, s, d: parse_bool_property(t, a),
        "IntProperty": lambda t, a, n, e, s, d: parse_int_property(t, a),
        "Int64Property": lambda t, a, n, e, s, d: parse_int_property(t, a),
        "Int16Property": lambda t, a, n, e, s, d: parse_int_property(t, a),
        "Int8Property": lambda t, a, n, e, s, d: parse_int_property(t, a),
        "ByteProperty": lambda t, a, n, e, s, d: parse_int_property(t, a),
        "FloatProperty": lambda t, a, n, e, s, d: parse_float_property(t, a),
        "DoubleProperty": lambda t, a, n, e, s, d: parse_float_property(t, a),
        "StrProperty": lambda t, a, n, e, s, d: parse_str_property(t, a),
        "NameProperty": lambda t, a, n, e, s, d: parse_name_property(t, a, n),
        "ObjectProperty": lambda t, a, n, e, s, d: parse_object_property(t, a),
        "ArrayProperty": lambda t, a, n, e, s, d: parse_array_property(t, a, n, e),
        # Phase 9 高级属性（Wave 2 实现函数）
        "StructProperty": lambda t, a, n, e, s, d: parse_struct_property(t, a, n, e, s, d),
        "MapProperty": lambda t, a, n, e, s, d: parse_map_property(t, a, n, e, s),
        "SetProperty": lambda t, a, n, e, s, d: parse_set_property(t, a, n, e, s),
        "EnumProperty": lambda t, a, n, e, s, d: parse_enum_property(t, a, n, s),
        "TextProperty": lambda t, a, n, e, s, d: parse_text_property(t, a),
        "DelegateProperty": lambda t, a, n, e, s, d: parse_delegate_property(t, a, n),
        # Phase 11-03: SoftObjectProperty解析器
        "SoftObjectProperty": lambda t, a, n, e, s, d: parse_soft_object_property(t, a, n),
    }

    parser = type_dispatch.get(tag.type)
    if parser:
        return parser(tag, archive, name_map, export_map, summary, depth)

    # 未知类型：跳过（D-26）
    return None


def parse_uasset(path: str) -> ParseResult:
    """
    主入口：解析 .uasset 文件（D-15 优雅降级）。

    流程：
    1. 创建 FArchive
    2. 读取 PackageFileSummary
    3. 读取 NameMap
    4. 读取 ImportMap
    5. 读取 ExportMap
    6. 返回 ParseResult

    错误处理：
    - VersionError: 返回错误信息，不崩溃
    - ParseError: 返回部分结果和错误信息

    Args:
        path: .uasset 文件路径

    Returns:
        ParseResult 实例（含解析数据和错误信息）
    """
    result = ParseResult()
    archive = None

    try:
        archive = FArchive(path)

        # D-02/D-03: Extract mmap info for ParseResult
        mmap_info = archive.get_mmap_info()
        result.mmap_used = mmap_info["used"]
        result.mmap_warning = mmap_info["warning"]

        # 读取文件头
        result.summary = read_package_summary(archive)

        # 读取名称表
        result.name_map = read_name_table(archive, result.summary)

        # 读取导入表
        result.import_map = read_import_map(archive, result.summary, result.name_map)

        # 读取导出表
        result.export_map = read_export_map(archive, result.summary, result.name_map)

        # Phase 11: 解析ExportMap属性（EXTR-01）
        for export in result.export_map:
            if export.serial_size > 0:
                try:
                    export.properties = parse_properties_from_export(
                        export, archive, result.summary, result.name_map, result.export_map,
                        result.import_map  # Phase 11-02: 传递import_map用于ObjectProperty解析
                    )
                except UAssetError as e:
                    result.errors.append(f"Property parse error in {export.object_name}: {e}")
                    export.properties = []  # 保持空列表而非None

        result.is_success = True

        # Blueprint extraction (Phase 3)
        # Per D-02: auto-detect and extract on every parse
        # Per D-03: add warnings to errors list if detection fails

        blueprint_metadata = None
        for export in result.export_map:
            if detect_blueprint(export, result.import_map, result.export_map):
                # Create temporary archive for extraction
                temp_archive = FArchive(path)
                temp_archive.set_byte_swapping(archive._byte_swapping)

                try:
                    meta, warn = extract_blueprint_metadata(
                        export,
                        temp_archive,
                        result.import_map,
                        result.export_map,
                        result.name_map,
                        result.summary
                    )
                    if meta:
                        blueprint_metadata = meta
                        if warn:
                            result.errors.append(f"blueprint parent warning: {warn}")
                except ParseError as e:
                    result.errors.append(f"blueprint extraction error: {e}")
                finally:
                    temp_archive.close()
                break  # Only process first blueprint found

        result.blueprint = blueprint_metadata

        # Phase 7: Blueprint Graph Extraction
        # Per D-03/D-04: Extract graphs after blueprint metadata
        try:
            # Re-open archive for graph parsing (previous archive still open at this point)
            result.graphs = extract_blueprint_graphs(
                archive,
                result.summary,
                result.name_map,
                result.import_map,
                result.export_map
            )
        except ParseError as e:
            result.errors.append(f"graph extraction error: {e}")

        # Phase 10: Dependency Analysis (DEPS-01~04)
        # Per D-10-05/08/13: Populate imports/soft_references/circular_deps fields
        try:
            # DEPS-01: ImportMap → imports
            result.imports = build_imports_list(result.import_map)

            # DEPS-02: SoftObjectPaths → soft_references
            result.soft_references = read_soft_object_paths(
                archive,
                result.summary,
                result.name_map
            )

            # DEPS-03: 高密度依赖检测（同一包多次引用）
            result.circular_deps = detect_circular_deps(result.import_map)

        except ParseError as e:
            result.errors.append(f"dependency analysis error: {e}")

    except VersionError as e:
        result.errors.append(str(e))
        result.is_success = False

    except ParseError as e:
        result.errors.append(str(e))
        # 携带部分结果
        if e.partial_result:
            for key, value in e.partial_result.items():
                if hasattr(result, key):
                    setattr(result, key, value)
        result.is_success = False

    except Exception as e:
        result.errors.append(f"Unexpected error: {str(e)}")
        result.is_success = False

    finally:
        if archive:
            archive.close()

    return result


# ============================================================================
# Output Formatting Functions (Phase 4 + Phase 8)
# ============================================================================

# Phase 8: Graph Output Functions (GRAPH-11, GRAPH-12, OUT2-01)

# D-08-10: 控制流节点类型（追踪时停止）
CONTROL_FLOW_NODES = frozenset({
    "K2Node_IfThenElse",
    "K2Node_Switch",
    "K2Node_SwitchString",
    "K2Node_SwitchEnum",
    "K2Node_SwitchInteger",
    "K2Node_MacroInstance",  # 宏实例可能包含循环
})


def build_connections_map(graph: UEdGraph) -> Tuple[List[Dict], List[str]]:
    """
    构建引脚连接映射（D-08-01~06）。

    将 linked_to_raw（PinId GUID hex）转换为 {node_guid, pin_name} 表示。

    算法：
    1. 构建 PinId → (node_guid, pin_name) 查找表
    2. 遍历所有 Output pins (direction=1)
    3. 对每个 linked_to_raw 中的 PinId，查找目标 pin
    4. 构建 {from, to} 连接对象
    5. 处理查找失败（warning + 原始数据）

    Args:
        graph: UEdGraph 对象

    Returns:
        Tuple[List[Dict], List[str]]: (connections 列表, warnings 列表)
    """
    # Step 1: Build pin_lookup: pin_id → (node_guid, pin_name)
    pin_lookup: Dict[str, Tuple[str, str]] = {}
    for node in graph.nodes:
        for pin in node.pins:
            pin_lookup[pin.pin_id] = (node.node_guid, pin.pin_name)

    # Step 2-4: Build connections (only from Output pins, D-08-05)
    connections: List[Dict] = []
    warnings: List[str] = []

    for node in graph.nodes:
        for pin in node.pins:
            if pin.direction == 1:  # EGPD_Output
                for linked_pin_id in pin.linked_to_raw:
                    if linked_pin_id in pin_lookup:
                        target_node_guid, target_pin_name = pin_lookup[linked_pin_id]
                        # D-08-06: {from, to} 对象结构
                        connections.append({
                            "from": {"node_guid": node.node_guid, "pin_name": pin.pin_name},
                            "to": {"node_guid": target_node_guid, "pin_name": target_pin_name}
                        })
                    else:
                        # D-08-04: Warning + raw data
                        warnings.append(f"PinId {linked_pin_id} not found in graph")
                        connections.append({
                            "from": {"node_guid": node.node_guid, "pin_name": pin.pin_name},
                            "to": {"raw_pin_id": linked_pin_id},
                            "warning": "target pin not found"
                        })

    return connections, warnings


def format_graphs_json(graphs: List[UEdGraph]) -> List[Dict]:
    """
    格式化蓝图图数据为 JSON 输出（GRAPH-11, GRAPH-12, OUT2-01）。

    Per D-08-03: connections 放在 graph 层级
    Per D-04: graphs 与 blueprint_metadata 同级
    Per D-08-09: execution_flows 数组

    Args:
        graphs: List[UEdGraph] from ParseResult.graphs

    Returns:
        List[Dict]: 每个 graph 的 JSON 表示
    """
    from dataclasses import asdict

    formatted = []
    for graph in graphs:
        # 构建连接映射
        connections, warnings = build_connections_map(graph)

        # 构建执行流（Phase 8 Wave 2）
        execution_flows = build_execution_flows(graph)

        graph_dict = {
            "graph_name": graph.graph_name,
            "graph_class": graph.graph_class,
            "nodes": [asdict(node) for node in graph.nodes],
            "connections": connections,
            "execution_flows": execution_flows,  # D-08-09: execution_flows 数组
        }

        # D-08-04: 添加 warnings（如果有）
        if warnings:
            graph_dict["warnings"] = warnings

        # 可选字段
        if graph.graph_guid:
            graph_dict["graph_guid"] = graph.graph_guid
        if graph.schema:
            graph_dict["schema"] = graph.schema

        formatted.append(graph_dict)

    return formatted


def build_execution_flows(graph: UEdGraph) -> List[Dict]:
    """
    构建执行流路径（D-08-07~11）。

    从 K2Node_Event 开始，沿 exec pin 连接追踪到 CallFunction 链路。

    算法：
    1. 找到所有 K2Node_Event 节点（执行流起点）
    2. 对每个 Event，沿 exec pin 连接追踪
    3. 记录节点信息：{node_guid, node_type, function_name}
    4. 检测控制流节点 → 停止
    5. 检测已访问节点 → 停止并标记循环

    Args:
        graph: UEdGraph 对象

    Returns:
        List[Dict]: execution_flows 数组
    """
    # 构建节点和引脚查找表
    pin_lookup: Dict[str, Tuple[str, str]] = {}
    node_lookup: Dict[str, UEdGraphNode] = {}

    for node in graph.nodes:
        node_lookup[node.node_guid] = node
        for pin in node.pins:
            pin_lookup[pin.pin_id] = (node.node_guid, pin.pin_name)

    execution_flows: List[Dict] = []

    # Step 1: 找到所有 Event 节点
    event_nodes = [n for n in graph.nodes if n.class_name == "K2Node_Event"]

    for event_node in event_nodes:
        flow = _trace_execution_from_event(
            event_node, pin_lookup, node_lookup
        )

        # 构建执行流记录
        start_event_name = _get_event_name(event_node)
        execution_flows.append({
            "start_event": start_event_name,
            "nodes": flow
        })

    return execution_flows


def _trace_execution_from_event(
    start_node: UEdGraphNode,
    pin_lookup: Dict[str, Tuple[str, str]],
    node_lookup: Dict[str, UEdGraphNode]
) -> List[Dict]:
    """
    追踪单条执行流（D-08-07~11）。

    Args:
        start_node: K2Node_Event 起点
        pin_lookup: pin_id → (node_guid, pin_name) 查找表
        node_lookup: node_guid → node 查找表

    Returns:
        List[Dict]: 节点信息序列
    """
    visited: Set[str] = set()  # D-08-11: 循环检测
    flow: List[Dict] = []
    current_node = start_node

    while current_node:
        # 循环检测（D-08-11）
        if current_node.node_guid in visited:
            flow.append({
                "node_guid": current_node.node_guid,
                "node_type": current_node.class_name,
                "cycle_detected": True
            })
            break

        visited.add(current_node.node_guid)

        # 记录节点信息（D-08-08）
        node_info = {
            "node_guid": current_node.node_guid,
            "node_type": current_node.class_name,
        }

        # 提取 function_name（CallFunction 类型）
        if current_node.class_name == "K2Node_CallFunction":
            if current_node.node_data and hasattr(current_node.node_data, 'function_reference'):
                node_info["function_name"] = current_node.node_data.function_reference.member_name

        # 提取 event_name（Event 类型）
        if current_node.class_name == "K2Node_Event":
            if current_node.node_data and hasattr(current_node.node_data, 'event_reference'):
                node_info["event_name"] = current_node.node_data.event_reference.member_name

        flow.append(node_info)

        # D-08-10: 控制流节点停止
        if current_node.class_name in CONTROL_FLOW_NODES:
            flow.append({"stopped_at": "control_flow_node"})
            break

        # 查找下一个节点（沿 exec output pin）
        current_node = _find_next_exec_node(current_node, pin_lookup, node_lookup)

    return flow


def _find_next_exec_node(
    node: UEdGraphNode,
    pin_lookup: Dict[str, Tuple[str, str]],
    node_lookup: Dict[str, UEdGraphNode]
) -> Optional[UEdGraphNode]:
    """
    查找 exec output pin 连接的下一个节点。

    Args:
        node: 当前节点
        pin_lookup: pin_id → (node_guid, pin_name) 查找表
        node_lookup: node_guid → node 查找表

    Returns:
        Optional[UEdGraphNode]: 下一个节点，或 None
    """
    # 找到 exec 类型 output pin
    for pin in node.pins:
        if pin.direction == 1:  # Output
            # 检查 pin_type.pin_category 是否为 exec
            if pin.pin_type and pin.pin_type.pin_category == "exec":
                # 查找连接的目标 pin
                for linked_pin_id in pin.linked_to_raw:
                    if linked_pin_id in pin_lookup:
                        target_node_guid, _ = pin_lookup[linked_pin_id]
                        return node_lookup.get(target_node_guid)
    return None


def _get_event_name(node: UEdGraphNode) -> str:
    """
    获取 Event 节点的事件名称。

    Args:
        node: K2Node_Event 节点

    Returns:
        str: 事件名称，或 "Unknown"
    """
    if node.node_data and hasattr(node.node_data, 'event_reference'):
        return node.node_data.event_reference.member_name
    return "Unknown"


def format_json_full(result: ParseResult) -> Dict:
    """
    Format full JSON output with complete asset data (OUT-01, OUT-03).

    Per D-01: Tiered output (full detail)
    Per D-02: Package → Exports → Properties hierarchy
    Per D-03: Top-level errors field
    Per D-04: Top-level blueprint_metadata (None for non-blueprint)
    Per D-05: Raw FPackageIndex values preserved where unresolved
    Per D-06: name_map excluded (already parsed to object names)

    Args:
        result: ParseResult from parse_uasset()

    Returns:
        Dict with keys: summary, exports, blueprint_metadata, errors
    """
    from dataclasses import asdict

    summary_dict = {}
    if result.summary:
        summary_dict = {
            "version_ue4": result.summary.file_version_ue4,
            "version_ue5": result.summary.file_version_ue5,
            "legacy_version": result.summary.legacy_file_version,
            "package_flags": result.summary.package_flags,  # D-08: raw u32
            "package_name": result.summary.package_name
        }

    return {
        "summary": summary_dict,
        "exports": format_exports_list(result),
        "blueprint_metadata": format_blueprint_dict(result.blueprint) if result.blueprint else None,
        "graphs": format_graphs_json(result.graphs),  # Phase 8: OUT2-01
        # Phase 10: 依赖分析字段（D-10-05/08/13）
        "imports": result.imports,                     # D-10-05: ImportMap 依赖列表
        "soft_references": result.soft_references,     # D-10-08: SoftObjectPaths 软引用
        "circular_deps": result.circular_deps,         # D-10-13: 高密度依赖路径
        "errors": result.errors
    }


def format_exports_list(result: ParseResult) -> List[Dict]:
    """
    Format exports list for JSON output.

    Per D-11/D-12: ParentClass, SuperIndex resolved in Phase 3
    Per D-13: Warning field on resolution failure
    Per D-15: Soft object paths output raw path strings

    Args:
        result: ParseResult containing export_map

    Returns:
        List of dicts with keys: index, name, class, serial_size, properties,
        outer_index, super_index, parent_class
    """
    exports_list = []

    for i, exp in enumerate(result.export_map):
        # Resolve ParentClass from Phase 3 extraction
        parent_class = None
        parent_warning = None
        if result.blueprint and result.blueprint.is_blueprint:
            parent_class = result.blueprint.parent_class
            parent_warning = result.blueprint.detection_warning

        export_dict = {
            "index": i,
            "name": exp.object_name,
            "class": get_asset_class(exp, result.import_map, result.export_map),
            "serial_size": exp.serial_size,
            "properties": format_properties_list(exp.properties) if exp.properties else [],
            # Per D-12: resolved references
            "outer_index": resolve_fpackage_index(exp.outer_index, result),
            "super_index": resolve_fpackage_index(exp.super_index, result),
            "parent_class": parent_class,  # from Phase 3 or resolution
        }

        # Per D-13: include warning if resolution failed
        if parent_warning:
            export_dict["parent_warning"] = parent_warning

        exports_list.append(export_dict)

    return exports_list


def resolve_fpackage_index(idx: PackageIndex, result: ParseResult) -> Dict:
    """
    Resolve FPackageIndex to object name (OUT-04, D-11/D-12).

    Args:
        idx: PackageIndex to resolve
        result: ParseResult containing import_map and export_map

    Returns:
        Dict with keys: raw, resolved, kind
        - raw: original int32 value
        - resolved: object name string or None
        - kind: "null", "import", or "export"
    """
    if idx.is_null:
        return {"raw": 0, "resolved": None, "kind": "null"}
    elif idx.is_import:
        # Import: negative index, maps to import_map
        import_idx = -idx.index - 1  # Convert to 0-based import index
        if 0 <= import_idx < len(result.import_map):
            resolved = result.import_map[import_idx].object_name
            return {"raw": idx.index, "resolved": resolved, "kind": "import"}
        else:
            return {"raw": idx.index, "resolved": None, "kind": "import"}
    elif idx.is_export:
        # Export: positive index, maps to export_map
        export_idx = idx.index - 1  # Convert to 0-based export index
        if 0 <= export_idx < len(result.export_map):
            resolved = result.export_map[export_idx].object_name
            return {"raw": idx.index, "resolved": resolved, "kind": "export"}
        else:
            return {"raw": idx.index, "resolved": None, "kind": "export"}
    else:
        # Fallback for edge cases
        return {"raw": idx.index, "resolved": None, "kind": "unknown"}


def format_properties_list(properties: List[PropertyValue]) -> List[Dict]:
    """
    Format properties list for JSON output.

    Per OUT-05: None → null in JSON (Python None preserved)

    Args:
        properties: List of PropertyValue objects

    Returns:
        List of dicts with keys: name, type, value, array_index
    """
    props_list = []

    for prop in properties:
        prop_dict = {
            "name": prop.name,
            "type": prop.type,
            "value": prop.value,  # None → JSON null automatically
            "array_index": prop.array_index
        }
        props_list.append(prop_dict)

    return props_list


def format_json_summary(result: ParseResult) -> Dict:
    """
    Format compact JSON summary (OUT-03).

    Per D-09: Medium detail - export names + types + properties (name+type+value)
    Per D-10: Skip low-level details - no name_map, import_map, CustomVersions

    Args:
        result: ParseResult from parse_uasset()

    Returns:
        Dict with keys: version, package_name, exports, blueprint_metadata, errors
    """
    version_dict = {}
    if result.summary:
        version_dict = {
            "ue4": result.summary.file_version_ue4,
            "ue5": result.summary.file_version_ue5 or result.summary.legacy_file_version,
            "legacy": result.summary.legacy_file_version
        }

    exports_summary = []
    for exp in result.export_map:
        export_summary = {
            "name": exp.object_name,
            "class": get_asset_class(exp, result.import_map, result.export_map),
            "properties": [
                {"name": p.name, "type": p.type, "value": p.value}
                for p in (exp.properties or [])
            ]
        }
        exports_summary.append(export_summary)

    return {
        "version": version_dict,
        "package_name": result.summary.package_name if result.summary else "",
        "exports": exports_summary,
        "blueprint_metadata": format_blueprint_dict(result.blueprint) if result.blueprint else None,
        "errors": result.errors
    }


def format_text_full(result: ParseResult) -> str:
    """
    Format YAML-style text output with full detail (OUT-02, OUT2-03).

    Per D-17: YAML style hierarchy with 2-space indentation
    Per D-19: ERRORS block at end
    Per D-21: Blueprint metadata embedded
    Per D-22: Nested YAML indentation
    Phase 8: Graphs section with summary (OUT2-03)

    Args:
        result: ParseResult from parse_uasset()

    Returns:
        str: YAML-style text output
    """
    lines = []

    # Package header
    if result.summary:
        package_name = result.summary.package_name or "Unknown"
        lines.append(f"Package: {package_name}")
        lines.append(f"  Version: UE4={result.summary.file_version_ue4}, UE5={result.summary.file_version_ue5}")
        lines.append(f"  Flags: 0x{result.summary.package_flags:08X}")
        lines.append(f"  Imports: {len(result.import_map)}")
        lines.append(f"  Exports: {len(result.export_map)}")
        lines.append("")
    else:
        lines.append("Package: Unknown")
        lines.append("  Version: Unknown")
        lines.append("  Flags: Unknown")
        lines.append("  Imports: 0")
        lines.append("  Exports: 0")
        lines.append("")

    # Exports section
    lines.append("Exports:")
    for i, exp in enumerate(result.export_map):
        asset_class = get_asset_class(exp, result.import_map, result.export_map)
        lines.append(f"  - Name: {exp.object_name}")
        lines.append(f"    Class: {asset_class}")
        lines.append(f"    SerialSize: {exp.serial_size}")

        if exp.properties:
            lines.append(f"    Properties:")
            for prop in exp.properties:
                lines.append(f"      - Name: {prop.name}")
                lines.append(f"        Type: {prop.type}")
                value_str = str(prop.value) if prop.value is not None else "null"
                lines.append(f"        Value: {value_str}")

        lines.append("")  # Blank line between exports

    # Blueprint section
    if result.blueprint and result.blueprint.is_blueprint:
        lines.append("Blueprint:")
        parent = result.blueprint.parent_class or "Unknown"
        lines.append(f"  ParentClass: {parent}")
        lines.append(f"  Variables: {len(result.blueprint.variables)}")

        for var in result.blueprint.variables:
            lines.append(f"  - Name: {var.var_name}")
            lines.append(f"    Type: {var.var_type.pin_category}")
            default = var.default_value or "None"
            lines.append(f"    Default: {default}")
            category = var.category or "Default"
            lines.append(f"    Category: {category}")

        lines.append("")  # Blank line after blueprint

    # Phase 8: Graphs section (OUT2-03)
    if result.graphs:
        lines.append("Graphs:")
        for graph in result.graphs:
            # 获取连接数量
            connections, _ = build_connections_map(graph)

            # 获取执行流数据
            execution_flows = build_execution_flows(graph)

            lines.append(f"  - Name: {graph.graph_name}")
            lines.append(f"    Class: {graph.graph_class}")
            lines.append(f"    Nodes: {len(graph.nodes)}")
            lines.append(f"    Connections: {len(connections)}")

            # 执行流概览
            lines.append(f"    ExecutionFlows: {len(execution_flows)}")
            for flow in execution_flows:
                start_event = flow.get("start_event", "Unknown")
                node_count = len(flow.get("nodes", []))
                lines.append(f"      - {start_event}: {node_count} nodes")

        lines.append("")  # Graphs 区块后的空行

    # ERRORS block
    if result.errors:
        lines.append("ERRORS:")
        for err in result.errors:
            lines.append(f"  - {err}")
    else:
        lines.append("ERRORS:")
        lines.append("  (none)")

    return "\n".join(lines)


def format_text_summary(result: ParseResult) -> str:
    """
    Format compact YAML-style text summary (OUT-02).

    Per D-18: One line per export: "Name (Type)"
    Per D-22: YAML indentation

    Args:
        result: ParseResult from parse_uasset()

    Returns:
        str: Compact YAML-style text summary
    """
    lines = []

    # Package header
    package_name = result.summary.package_name if result.summary else "Unknown"
    lines.append(f"Package: {package_name}")
    lines.append(f"Exports: {len(result.export_map)}")
    lines.append("")  # Blank line

    # Exports: one line each
    for exp in result.export_map:
        asset_class = get_asset_class(exp, result.import_map, result.export_map)
        lines.append(f"  - {exp.object_name} ({asset_class})")

    # Blueprint summary
    if result.blueprint and result.blueprint.is_blueprint:
        lines.append("")
        lines.append("Blueprint:")
        parent = result.blueprint.parent_class or "Unknown"
        lines.append(f"  Parent: {parent}")
        lines.append(f"  Variables: {len(result.blueprint.variables)}")

    return "\n".join(lines)


def format_blueprint_dict(blueprint: BlueprintMetadata) -> Dict:
    """
    Format BlueprintMetadata for JSON output (D-04).

    Args:
        blueprint: BlueprintMetadata object

    Returns:
        Dict with keys: parent_class, variables, detection_warning
    """
    variables_list = []
    for v in blueprint.variables:
        var_dict = {
            "name": v.var_name,
            "type": {
                "pin_category": v.var_type.pin_category,
                "pin_sub_category": v.var_type.pin_sub_category,
                "container_type": v.var_type.container_type,
                "is_reference": v.var_type.is_reference,
                "is_const": v.var_type.is_const
            },
            "category": v.category,
            "property_flags": v.property_flags,
            "default_value": v.default_value,  # None if not set
            "friendly_name": v.friendly_name
        }
        variables_list.append(var_dict)

    return {
        "parent_class": blueprint.parent_class,  # None if not resolved
        "variables": variables_list,
        "detection_warning": blueprint.detection_warning  # None if no warning
    }


# ============================================================================
# CLI Functions (Phase 4)
# ============================================================================

# Exit code constants (D-26)
EXIT_SUCCESS = 0
EXIT_PARSE_ERROR = 1
EXIT_FILE_NOT_FOUND = 2
EXIT_ARGUMENT_ERROR = 3


def create_parser() -> argparse.ArgumentParser:
    """
    Create argparse parser for CLI (CLI-01 to CLI-04).

    Per D-23: Double entry point support
    Per D-24: Mutually exclusive --json/--text/--summary flags
    Per D-27: Optional flags: --verbose, --output FILE, --export INDEX

    Returns:
        argparse.ArgumentParser: Configured parser
    """
    parser = argparse.ArgumentParser(
        prog='uasset_read',
        description='Parse Unreal Engine .uasset files and output structured data'
    )

    # Positional: file path (CLI-01)
    parser.add_argument('file', help='Path to .uasset file to parse')

    # Mutually exclusive output flags (D-24)
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument('--json', action='store_true', help='Output full JSON structure')
    group.add_argument('--text', action='store_true', help='Output YAML-style text (default)')
    group.add_argument('--summary', action='store_true', help='Output compact summary format')

    # Optional flags (D-27)
    parser.add_argument('--verbose', action='store_true', help='Include extra detail fields')
    parser.add_argument('--output', metavar='FILE', help='Write output to file instead of stdout')
    parser.add_argument('--export', metavar='INDEX', type=int, help='Output only specific export by index')
    parser.add_argument('--graph', action='store_true', help='Include blueprint graph data in output')

    return parser


def main():
    """
    Main CLI entry point (CLI-05).

    Per D-23: Double entry point (also __main__.py)
    Per D-25: stdout for data, stderr for errors
    Per D-26: Exit codes 0/1/2/3
    Per D-28: UTF-8 encoding for file output

    Exit codes:
    - 0: Success
    - 1: Parse error
    - 2: File not found
    - 3: Argument error
    """
    parser = create_parser()

    try:
        args = parser.parse_args()
    except SystemExit as e:
        # argparse exits on error, map to EXIT_ARGUMENT_ERROR
        sys.exit(EXIT_ARGUMENT_ERROR)

    # D-26: file not found check
    file_path = Path(args.file)
    if not file_path.exists():
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(EXIT_FILE_NOT_FOUND)

    # Parse the file
    result = parse_uasset(args.file)

    # D-26: parse error handling
    if not result.is_success:
        print("Parse errors:", file=sys.stderr)
        for err in result.errors:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(EXIT_PARSE_ERROR)

    # Phase 8: --graph flag handling (D-08-12/13)
    # 优先级：--graph 检查在最前
    if args.graph:
        # D-08-13: --graph + --json/--verbose = full output with graphs
        if args.json or args.verbose:
            output_str = json.dumps(format_json_full(result), indent=2, ensure_ascii=False)
        elif args.text:
            # --graph --text = text output with Graphs section
            output_str = format_text_full(result)
        else:
            # D-08-13: --graph alone = only graphs in JSON format
            output_str = json.dumps({"graphs": format_graphs_json(result.graphs)},
                                    indent=2, ensure_ascii=False)
    elif args.json:
        output_str = json.dumps(format_json_full(result), indent=2, ensure_ascii=False)
    elif args.summary:
        output_str = json.dumps(format_json_summary(result), indent=2, ensure_ascii=False)
    else:
        # Default: --text or no flag
        output_str = format_text_full(result)

    # D-25/D-28: Output routing with UTF-8
    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(output_str)
            print(f"Output written to {args.output}", file=sys.stderr)
        except IOError as e:
            print(f"Error writing to file: {e}", file=sys.stderr)
            sys.exit(EXIT_ARGUMENT_ERROR)
    else:
        # stdout for data (D-25)
        print(output_str)

    sys.exit(EXIT_SUCCESS)


# ============================================================================
# Public API Exports
# ============================================================================

__all__ = [
    # Dataclasses
    'CustomVersion',
    'PackageIndex',
    'PackageFileSummary',
    'ObjectImport',
    'ObjectExport',
    'PropertyTag',
    'PropertyValue',
    'ParseResult',
    'FEdGraphPinType',
    'BlueprintVariable',
    'BlueprintMetadata',
    # Phase 7: Blueprint Graph Data Classes
    'UEdGraphPin',
    'UEdGraphNode',
    'UEdGraph',
    'FMemberReference',
    # Phase 7 Wave 3: Node Type Specific Data Classes (GRAPH-05~09)
    'K2NodeCallFunction',
    'K2NodeEvent',
    'K2NodeKnot',
    'EdGraphNodeComment',
    'K2NodeEnhancedInputAction',
    # Phase 9: Advanced Property Value Data Classes (ADVP-01~06)
    'AdvancedPropertyValue',
    'StructValue',
    'MapValue',
    'SetValue',
    'EnumValue',
    'TextValue',
    'DelegateValue',

    # FArchive
    'FArchive',

    # Exceptions and Context
    'UAssetError',
    'VersionError',
    'ParseError',
    'ErrorContext',

    # Constants
    'PACKAGE_FILE_TAG',
    'PACKAGE_FILE_TAG_SWAPPED',
    'PROP_TAG_NONE',
    'PROP_TAG_HAS_ARRAY_INDEX',
    'PROP_TAG_HAS_PROPERTY_GUID',
    'PROP_TAG_HAS_EXTENSIONS',
    'PROP_TAG_BOOL_TRUE',
    'PROPERTY_TAG_COMPLETE_TYPE_NAME',

    # Phase 5: Performance and safety constants
    'MMAP_THRESHOLD',
    'MAX_PROPERTY_COUNT',
    # Phase 7: Blueprint Graph Parsing Safety Constants
    'MAX_PINS_PER_NODE',
    'MAX_NODES_PER_GRAPH',
    'MAX_LINKEDTO_PER_PIN',

    # Phase 5: Boundary validation functions
    'validate_package_index',
    # Phase 11-02: PackageIndex resolution function
    'resolve_package_index_to_reference',

    # Core parsing functions
    'read_package_summary',
    'read_name_table',
    'read_import_map',
    'read_export_map',
    'get_asset_class',
    'detect_blueprint',
    'resolve_parent_class',
    'parse_uasset',

    # Blueprint parsing functions (Phase 3)
    'read_ed_graph_pin_type',
    'parse_default_value',
    'read_blueprint_variable',
    'extract_blueprint_metadata',
    # Phase 7: Blueprint Graph Extraction and Parsing
    'resolve_class_name',
    'extract_blueprint_graphs',
    'read_ue_graph_pin',
    'read_ue_graph_node',
    'read_ue_graph',
    # Phase 7 Wave 3: Node Type Specific Parsers (GRAPH-05~09)
    'read_fmember_reference',
    'read_k2node_call_function',
    'read_k2node_event',
    'read_k2node_knot',
    'read_edgraph_node_comment',
    'read_k2node_enhanced_input',

    # Property parsing functions (Phase 2)
    'use_complete_type_name',
    'read_property_tag',
    'parse_bool_property',
    'parse_int_property',
    'parse_float_property',
    'parse_str_property',
    'parse_name_property',
    'parse_object_property',
    'parse_array_property',
    'parse_property_value',
    'parse_properties_from_export',
    # Phase 9: Advanced Property Parsing Functions (ADVP-01~06)
    'parse_struct_property',
    'parse_map_property',
    'parse_set_property',
    'parse_enum_property',
    'parse_text_property',
    'parse_delegate_property',

    # Output formatting functions (Phase 4)
    'format_json_full',
    'format_json_summary',
    'format_text_full',
    'format_text_summary',
    'format_exports_list',
    'format_properties_list',
    'format_blueprint_dict',
    'resolve_fpackage_index',

    # CLI functions (Phase 4)
    'create_parser',
    'main',
    'EXIT_SUCCESS',
    'EXIT_PARSE_ERROR',
    'EXIT_FILE_NOT_FOUND',
    'EXIT_ARGUMENT_ERROR',
]


# ============================================================================
# Module Entry Point (D-23 double entry)
# ============================================================================

if __name__ == '__main__':
    main()