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
from typing import Optional, List, Dict, BinaryIO, Tuple, Any, Union


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
PROPERTY_TAG_COMPLETE_TYPE_NAME = 1012  # UE5 format switch threshold (EUnrealEngineObjectUE5Version::PROPERTY_TAG_COMPLETE_TYPE_NAME)
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

# Phase 22 Debug Flags
DEBUG_PIN_PARSING = "--debug-pin" in sys.argv or "--debug-pins" in sys.argv

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

# UE4 Version Constants (EUnrealEngineObjectUE4Version) - 从ObjectVersion.h精确解析
UE4_ADDED_PACKAGE_SUMMARY_LOCALIZATION_ID = 385  # VER_UE4_ADDED_PACKAGE_SUMMARY_LOCALIZATION_ID (old)
UE4_SERIALIZE_TEXT_IN_PACKAGES = 401            # VER_UE4_SERIALIZE_TEXT_IN_PACKAGES (old)
# 正确值（从 ObjectVersion.h 计算）
UE4_WORLD_LEVEL_INFO = 223                      # VER_UE4_WORLD_LEVEL_INFO
UE4_ADDED_CHUNKID = 277                         # VER_UE4_ADDED_CHUNKID_TO_ASSETDATA_AND_UPACKAGE
UE4_CHANGED_CHUNKID_TO_ARRAY = 341             # VER_UE4_CHANGED_CHUNKID_TO_BE_AN_ARRAY_OF_CHUNKIDS
UE4_ENGINE_VERSION_OBJECT = 334                 # VER_UE4_ENGINE_VERSION_OBJECT
UE4_ADD_STRING_ASSET_REFERENCES_MAP = 382      # VER_UE4_ADD_STRING_ASSET_REFERENCES_MAP
UE4_PACKAGE_SUMMARY_HAS_COMPATIBLE_ENGINE_VERSION = 442  # VER_UE4_PACKAGE_SUMMARY_HAS_COMPATIBLE_ENGINE_VERSION
# Phase 11 GAP修复：版本常量精确值（从ObjectVersion.h枚举位置计算）
UE4_LOAD_FOR_EDITOR_GAME = 365                  # VER_UE4_LOAD_FOR_EDITOR_GAME (line 422)
UE4_COOKED_ASSETS_IN_EDITOR_SUPPORT = 485       # VER_UE4_COOKED_ASSETS_IN_EDITOR_SUPPORT (line 665)
UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS = 507  # VER_UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS (line 709)
VER_UE4_TemplateIndex_IN_COOKED_EXPORTS = 508    # VER_UE4_TemplateIndex_IN_COOKED_EXPORTS (line 711)
UE4_ADDED_SEARCHABLE_NAMES = 510               # VER_UE4_ADDED_SEARCHABLE_NAMES (line 715)
VER_UE4_64BIT_EXPORTOFFSETS = 511              # VER_UE4_64BIT_EXPORTMAP_SERIALSIZES (line 717)
UE4_ADDED_PACKAGE_OWNER = 518                  # VER_UE4_ADDED_PACKAGE_OWNER (line 731)
UE4_NON_OUTER_PACKAGE_IMPORT = 520             # VER_UE4_NON_OUTER_PACKAGE_IMPORT (line 734)
# FEdGraphPinType MemberReference 版本阈值（从ObjectVersion.h计算）
# VER_UE4_MEMBERREFERENCE_IN_PINTYPE = 355 (PinSubCategoryMemberReference added to FEdGraphPinType)
VER_UE4_MEMBERREFERENCE_IN_PINTYPE = 355       # VER_UE4_MEMBERREFERENCE_IN_PINTYPE (line 400)
# FText History版本阈值（从ObjectVersion.h计算）
VER_UE4_FTEXT_HISTORY = 528                    # VER_UE4_FTEXT_HISTORY (line 428: ~214+314)

# UE5 Version Constants (EUnrealEngineObjectUE5Version) - 从ObjectVersion.h精确解析
# Phase 11 GAP修复：UE5版本常量精确值
UE5_REMOVE_OBJECT_EXPORT_PACKAGE_GUID = 1005    # EUnrealEngineObjectUE5Version::REMOVE_OBJECT_EXPORT_PACKAGE_GUID (line 62)
UE5_TRACK_OBJECT_EXPORT_IS_INHERITED = 1006     # EUnrealEngineObjectUE5Version::TRACK_OBJECT_EXPORT_IS_INHERITED (line 65)
UE5_OPTIONAL_RESOURCES = 1003                   # EUnrealEngineObjectUE5Version::OPTIONAL_RESOURCES (line 56)
UE5_SCRIPT_SERIALIZATION_OFFSET = 1010          # EUnrealEngineObjectUE5Version::SCRIPT_SERIALIZATION_OFFSET (line 77)

# ============================================================
# CustomVersion GUIDs (Phase 18: Pin序列化解析)
# 来源：UE 5.7 源码 DevObjectVersion.cpp, EngineVersion.cpp
# ============================================================

# FrameworkObjectVersion GUID (DevObjectVersion.cpp L194)
# FGuid(0xCFFC743F, 0x43B04480, 0x939114DF, 0x171D2073)
# Serialized as 4 uint32 in little-endian -> 3F74FCCF8044B043DF14919373201D17
FFRAMEWORK_OBJECT_VERSION_GUID = "3F74FCCF8044B043DF14919373201D17"

# UE5MainStreamObjectVersion GUID (DevObjectVersion.cpp L332)
# FGuid(0x697DD581, 0xE64F41AB, 0xAA4A51EC, 0xBEB7B628)
# Serialized as 4 uint32 in little-endian -> 81D57D69AB414FE6EC514AAA28B6B7BE
FUE5_MAINSTREAM_VERSION_GUID = "81D57D69AB414FE6EC514AAA28B6B7BE"

# ReleaseObjectVersion GUID (EngineVersion.cpp L266)
# FGuid(0x9C54D522, 0xA8264FBE, 0x94210746, 0x61B482D0)
# Serialized as 4 uint32 in little-endian -> 22D5549CBE4F26A846072194D082B461
FRELEASE_OBJECT_VERSION_GUID = "22D5549CBE4F26A846072194D082B461"

# ============================================================
# Version Thresholds (Phase 18: Pin序列化版本检查)
# 枚举值从0开始计数，值 = 枚举位置
# ============================================================

# FFrameworkObjectVersion thresholds (FrameworkObjectVersion.h)
# 枚举从0开始计数
FFRAMEWORK_VERSION_ED_GRAPH_PIN_CONTAINER_TYPE = 15  # 第16个枚举值 (EdGraphPinContainerType)
# Phase 22 FIX-01: 修正阈值 - PinsStoreFName 是第20个枚举值（=19），而非21个
# 实际数据验证：framework_version=17 时，PinName 仍为 FName 格式
# 可能是因为 UE5 资产始终使用 FName，阈值检查仅针对旧版资产
FFRAMEWORK_VERSION_PINS_STORE_FNAME = 19             # 第20个枚举值 (PinsStoreFName)

# FUE5MainStreamObjectVersion thresholds (UE5MainStreamObjectVersions.inl L161)
FUE5_MAINSTREAM_VERSION_ED_GRAPH_PIN_SOURCE_INDEX = 50  # EdGraphPinSourceIndex

# FReleaseObjectVersion thresholds (ReleaseObjectVersion.h)
# 枚举从0开始计数
FRELEASE_VERSION_PIN_TYPE_UOBJECT_WRAPPER = 10  # 第11个枚举值 (PinTypeIncludesUObjectWrapperFlag)


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

    def peek_i32(self) -> int:
        """预读 signed 32-bit integer（不移动位置，Phase 22 FIX-12）"""
        current_pos = self.tell()
        try:
            fmt = '>' if self._byte_swapping else '<'
            data = self.read(4)
            result = struct.unpack(fmt + 'i', data)[0]
            self.seek(current_pos)  # 回退到原位置
            return result
        except Exception:
            self.seek(current_pos)
            raise

    def read_u16(self) -> int:
        """读取 unsigned 16-bit integer（支持字节交换）"""
        fmt = '>' if self._byte_swapping else '<'
        return struct.unpack(fmt + 'H', self.read(2))[0]

    def read_u32(self) -> int:
        """读取 unsigned 32-bit integer（支持字节交换）"""
        fmt = '>' if self._byte_swapping else '<'
        return struct.unpack(fmt + 'I', self.read(4))[0]

    def peek_i32(self) -> int:
        """读取 signed 32-bit integer 但不移动文件指针（支持字节交换）"""
        current_pos = self.tell()
        value = self.read_i32()
        self.seek(current_pos)
        return value

    def read_bool(self) -> bool:
        """
        读取 UE bool 值（序列化为 uint32，4 bytes）。

        UE 源码参考：Archive.h line 1535
        "Serialize bool as if it were UBOOL (legacy, 32 bit int)"

        Returns:
            bool: True 如果 uint32 != 0，False 如果 uint32 == 0
        """
        return self.read_u32() != 0

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
        读取 UE FString（带长度前缀的字符串）。

        UE 5.x 格式（基于 UE 源码 String.cpp.inl L1779-1876）：
        - length == 0: 空字符串，仅 4 bytes length，无额外数据
        - length > 0: UTF-8/ANSI 编码，包含 null terminator
        - length < 0: UTF-16 编码（已弃用）

        Returns:
            解析后的字符串（去除 null 终止符）
        """
        length = self.read_i32()

        if length == 0:
            # Empty FString: UE 只写入 4 bytes 的 0，不写入 null terminator
            # Per String.cpp.inl L1876: if (!SaveNum) { Str.Data.Empty(); }
            return ""

        if length < 0:
            # UE FString UTF-16 encoding: length < 0 indicates UTF-16
            # -length gives character count (including null terminator)
            utf16_len = -length * 2
            if utf16_len > 10_000_000:  # Sanity check for overflow
                raise ParseError(f"UTF-16 string length {utf16_len} too large")
            data = self.read(utf16_len)
            # Skip null terminator and decode
            return data.decode('utf-16', errors='replace').rstrip('\x00')

        # UTF-8/ANSI 编码（UE 5.x 标准）
        # length includes null terminator
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

    def _parse_property_flags(self, property_flags: int) -> dict:
        """
        Phase 26: 解析属性标志。

        Args:
            property_flags: 原始属性标志值 (uint64)

        Returns:
            包含解析后标志的字典
        """
        return {
            'is_edit_anywhere': bool(property_flags & CPF_EditAnywhere),
            'is_edit_instance_only': bool(property_flags & CPF_EditInstanceOnly),
            'is_blueprint_read_only': bool(property_flags & CPF_BlueprintReadOnly),
            'is_blueprint_readable': bool(property_flags & CPF_BlueprintReadWrite),
            'is_blueprint_writable': bool(property_flags & CPF_BlueprintReadWrite),
            'is_transient': bool(property_flags & CPF_Transient),
            'is_duplicate_transient': bool(property_flags & CPF_DuplicateTransient),
            'is_save_game': bool(property_flags & CPF_SaveGame),
            'is_no_clear': bool(property_flags & CPF_NoClear),
            'is_reference_only': bool(property_flags & CPF_ReferenceOnly),
            'is_blueprint_assignable': bool(property_flags & CPF_BlueprintAssignable),
            'is_blueprint_callable': bool(property_flags & CPF_BlueprintCallable),
            'is_rep_notify': bool(property_flags & CPF_RepNotify),
            'is_interp': bool(property_flags & CPF_Interp),
            'is_expose_on_spawn': bool(property_flags & CPF_ExposeOnSpawn),
            'is_net': bool(property_flags & CPF_Net),
            'is_replicated': bool(property_flags & CPF_Replicated),
            'is_non_pi_ed_duplicate_transient': bool(property_flags & CPF_NonPIEDuplicateTransient),
        }

    # ========================================================================
    # Phase 26: 事件元数据解析函数
    # ========================================================================

    def _parse_function_flags(self, function_flags: int) -> dict:
        """
        Phase 26: 解析函数标志（META-02）。

        Args:
            function_flags: 原始函数标志值 (uint32)

        Returns:
            包含解析后标志的字典
        """
        return {
            'is_pure': bool(function_flags & FUNC_BlueprintPure),
            'is_blueprint_callable': bool(function_flags & FUNC_BlueprintCallable),
            'is_blueprint_event': bool(function_flags & FUNC_BlueprintEvent),
            'is_blueprint_implementable_event': bool(function_flags & FUNC_BlueprintEvent),
            'is_native': bool(function_flags & FUNC_Native),
            'is_const': bool(function_flags & FUNC_Const),
            'is_static': bool(function_flags & FUNC_Static),
            'is_virtual': not bool(function_flags & FUNC_Final),
            'is_exec': bool(function_flags & FUNC_Exec),
            'is_net': bool(function_flags & FUNC_Net),
            'is_net_reliable': bool(function_flags & FUNC_NetReliable),
            'is_net_server': bool(function_flags & FUNC_NetServer),
            'is_net_client': bool(function_flags & FUNC_NetClient),
            'is_net_multicast': bool(function_flags & FUNC_NetMulticast),
            'is_blueprint_private': bool(function_flags & FUNC_Private),
            'is_blueprint_protected': bool(function_flags & FUNC_Protected),
            'is_blueprint_public': bool(function_flags & FUNC_Public),
            'is_blueprint_cosmetic': bool(function_flags & FUNC_BlueprintCosmetic),
            'is_editor_only': bool(function_flags & FUNC_EditorOnly),
            'is_final': bool(function_flags & FUNC_Final),
            'is_delegate': bool(function_flags & FUNC_Delegate),
            'is_multicast_delegate': bool(function_flags & FUNC_MulticastDelegate),
            'is_has_out_parms': bool(function_flags & FUNC_HasOutParms),
            'is_has_defaults': bool(function_flags & FUNC_HasDefaults),
        }

    def read_function_parameters(self, func_export) -> List:
        """
        读取函数参数列表（Phase 26: META-02）。

        Args:
            func_export: 函数导出对象

        Returns:
            FunctionParameter 列表
        """
        from .constants import CPF_OutParm, CPF_OptionalParm

        parameters = []

        # 遍历函数的 Children
        if func_export and hasattr(func_export, 'children'):
            for child in func_export.children:
                # 检查是否为 FProperty
                if self.is_property(child):
                    # 读取参数名称
                    param_name = getattr(child, 'name', '')

                    # 读取参数类型
                    param_type = self.get_property_type(child)

                    # 读取默认值
                    default_value = self.get_default_value(child)

                    # 读取属性标志
                    property_flags = getattr(child, 'property_flags', 0)

                    # 判断是否为输出参数
                    is_output = bool(property_flags & CPF_OutParm)
                    is_input = not is_output

                    # 判断是否为可选参数
                    is_optional = bool(property_flags & CPF_OptionalParm)

                    # 读取元数据
                    meta_data = self.read_metadata(child)

                    parameters.append(FunctionParameter(
                        name=param_name,
                        param_type=param_type,
                        default_value=default_value,
                        is_input=is_input,
                        is_output=is_output,
                        is_optional=is_optional,
                        property_flags=property_flags,
                        meta_data=meta_data
                    ))

        return parameters

    def read_metadata(self, event_export) -> dict:
        """
        读取事件元数据（Phase 26）。

        Args:
            event_export: 事件导出对象

        Returns:
            元数据字典
        """
        meta_data = {}

        # 尝试从事件导出中读取元数据
        if hasattr(event_export, 'metadata'):
            for key, value in event_export.metadata.items():
                meta_data[key] = value

        return meta_data

    def get_return_type(self, func_export) -> str:
        """
        获取函数返回类型（Phase 26: META-02）。

        Args:
            func_export: 函数导出对象

        Returns:
            返回类型字符串
        """
        # 从函数导出中读取返回类型
        if hasattr(func_export, 'return_type'):
            return func_export.return_type
        elif hasattr(func_export, 'ReturnValue'):
            # 从 ReturnValue 属性中推断类型
            return_value = func_export.ReturnValue
            if hasattr(return_value, 'type'):
                return return_value.type
        return ""

    def get_property_type(self, property_export) -> str:
        """
        获取属性类型（Phase 26: META-02）。

        Args:
            property_export: 属性导出对象

        Returns:
            属性类型字符串
        """
        # 从属性导出中读取类型
        if hasattr(property_export, 'type'):
            return property_export.type
        elif hasattr(property_export, 'property_class'):
            return property_export.property_class
        elif hasattr(property_export, 'property_type'):
            return property_export.property_type
        return ""

    def get_default_value(self, property_export) -> any:
        """
        获取属性默认值（Phase 26: META-02）。

        Args:
            property_export: 属性导出对象

        Returns:
            默认值
        """
        # 从属性导出中读取默认值
        if hasattr(property_export, 'default_value'):
            return property_export.default_value
        elif hasattr(property_export, 'DefaultValue'):
            return property_export.DefaultValue
        return None

    def is_property(self, export) -> bool:
        """
        判断导出对象是否为属性（Phase 26: META-02）。

        Args:
            export: 导出对象

        Returns:
            是否为属性
        """
        # 检查对象类型或类名
        if hasattr(export, 'class_name'):
            class_name = export.class_name
            # 检查是否为 FProperty 的子类
            property_classes = [
                'BoolProperty', 'IntProperty', 'FloatProperty', 'StrProperty',
                'StructProperty', 'ArrayProperty', 'MapProperty', 'SetProperty',
                'ObjectProperty', 'NameProperty', 'ByteProperty', 'EnumProperty',
                'TextProperty', 'DelegateProperty', 'InterfaceProperty'
            ]
            return any(prop_class in class_name for prop_class in property_classes)
        return False

    def read_blueprint_events(self, blueprint_class: 'ObjectExport', name_map: List[str]) -> List:
        """
        读取蓝图事件（Phase 26）。

        Args:
            blueprint_class: 蓝图类导出对象
            name_map: 名称表

        Returns:
            BlueprintEvent 列表
        """
        events = []

        # 遍历 Blueprint 的 Events
        if blueprint_class and hasattr(blueprint_class, 'events'):
            for event_export in blueprint_class.events:
                # 读取事件名称
                event_name = name_map[event_export.name_index] if hasattr(event_export, 'name_index') else getattr(event_export, 'name', '')

                # 读取事件标志
                function_flags = getattr(event_export, 'function_flags', 0)

                # 解析事件标志
                flags = self._parse_function_flags(function_flags)

                # 判断事件类型
                if flags['is_blueprint_event']:
                    event_type = "CustomEvent"
                elif flags['is_override']:
                    event_type = "OverriddenEvent"
                else:
                    event_type = "Unknown"

                # 读取参数
                parameters = self.read_function_parameters(event_export)

                # 读取元数据
                meta_data = self.read_metadata(event_export)

                # 检查是否为多播委托
                is_multicast = flags['is_multicast_delegate']
                multicast_delegate = None
                if is_multicast:
                    multicast_delegate = MulticastDelegate(
                        delegate_name=event_name,
                        signature_function=meta_data.get('SignatureFunction', ''),
                        is_callable_in_blueprint=flags['is_blueprint_callable']
                    )

                # 检查是否为重写事件
                is_override = meta_data.get('bOverrideFunction', False)
                override_parent_class = meta_data.get('MemberParent', '')
                override_parent_event = meta_data.get('MemberName', '')

                # 检查是否为接口事件
                is_interface_event = meta_data.get('IsInterfaceEvent', False)
                interface_class = meta_data.get('InterfaceClass', '')

                events.append(BlueprintEvent(
                    name=event_name,
                    event_type=event_type,
                    function_flags=function_flags,
                    is_blueprint_event=flags['is_blueprint_event'],
                    is_blueprint_implementable_event=meta_data.get('IsBlueprintImplementableEvent', False),
                    is_net=flags['is_net'],
                    is_net_multicast=flags['is_net_multicast'],
                    is_net_reliable=flags['is_net_reliable'],
                    is_net_client=flags['is_net_client'],
                    is_net_server=flags['is_net_server'],
                    is_replicated=meta_data.get('IsReplicated', False),
                    is_cosmetic=flags['is_blueprint_cosmetic'],
                    is_static=flags['is_static'],
                    is_multicast=is_multicast,
                    multicast_delegate=multicast_delegate,
                    is_override=is_override,
                    override_parent_class=override_parent_class,
                    override_parent_event=override_parent_event,
                    is_interface_event=is_interface_event,
                    interface_class=interface_class,
                    parameters=parameters,
                    meta_data=meta_data,
                ))

        return events

    def read_blueprint_functions(self, blueprint_class: 'ObjectExport') -> List:
        """
        读取蓝图函数（Phase 26: META-02）。

        Args:
            blueprint_class: 蓝图类导出对象

        Returns:
            BlueprintFunction 列表
        """
        functions = []

        # 遍历 Blueprint 的 Functions
        if blueprint_class and hasattr(blueprint_class, 'functions'):
            for func_export in blueprint_class.functions:
                # 读取函数名称
                func_name = getattr(func_export, 'name', '')

                # 读取返回类型
                return_type = self.get_return_type(func_export)

                # 读取函数标志
                function_flags = getattr(func_export, 'function_flags', 0)

                # 解析函数标志
                flags = self._parse_function_flags(function_flags)

                # 读取访问修饰符
                if flags['is_blueprint_private']:
                    access_specifier = "Private"
                elif flags['is_blueprint_protected']:
                    access_specifier = "Protected"
                else:
                    access_specifier = "Public"

                # 读取参数
                parameters = self.read_function_parameters(func_export)

                # 读取元数据
                meta_data = self.read_metadata(func_export)

                functions.append(BlueprintFunction(
                    name=func_name,
                    return_type=return_type,
                    parameters=parameters,
                    function_flags=function_flags,
                    access_specifier=access_specifier,
                    meta_data=meta_data,
                    **flags
                ))

        return functions

    def read_interface_events(self, blueprint_class: 'ObjectExport', name_map: List[str]) -> List:
        """
        读取接口事件（Phase 26）。

        Args:
            blueprint_class: 蓝图类导出对象
            name_map: 名称表

        Returns:
            BlueprintEvent 列表（接口事件）
        """
        events = []

        # 遍历 Blueprint 实现的接口
        if blueprint_class and hasattr(blueprint_class, 'implemented_interfaces'):
            for interface_export in blueprint_class.implemented_interfaces:
                # 读取接口名称
                interface_name = name_map[interface_export.name_index] if hasattr(interface_export, 'name_index') else getattr(interface_export, 'name', '')

                # 获取接口的事件（这里需要实现接口类的事件读取逻辑）
                # 由于接口事件通常在接口类中定义，这里暂时返回空列表
                # 实际实现需要递归读取接口类的所有事件

                # 标记为接口事件
                for event in events:
                    event.is_interface_event = True
                    event.interface_class = interface_name

        return events


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

    def get_custom_version(self, guid: str, default: int = 0) -> int:
        """
        查找 CustomVersion 版本值。

        GUID 格式兼容：接受带分隔符的大写格式（如 "CFFC743F-43B04480-939114DF-171D2073"）
        或无分隔符的小写格式（如 "cffc743f43b04480939114df171d2073"）。

        Args:
            guid: CustomVersion GUID 字符串
            default: 未找到时的默认值

        Returns:
            版本号或默认值
        """
        # Normalize GUID: remove dashes, convert to lowercase
        normalized_guid = guid.replace("-", "").lower()
        for cv in self.custom_versions:
            if cv.guid == normalized_guid:
                return cv.version
        return default
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
    # Phase 13-02: 变换属性提取结果
    transforms: Dict[str, Any] = field(default_factory=dict)


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
    # D-03: PropertyTag Extensions 字段（PropertyTag.cpp lines 155-173）
    override_operation: Optional[int] = None  # EOverriddenPropertyOperation (u8)
    experimental_overridable_logic: Optional[int] = None  # bExperimentalOverridableLogic (u8)


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


# ============================================================================
# Phase 13: 变换属性类型 dataclass 定义
# ============================================================================

@dataclass(kw_only=True)
class VectorValue(AdvancedPropertyValue):
    """
    Vector struct property value (Phase 13)。

    X/Y/Z 坐标值，用于 RelativeLocation 等位置属性。
    继承 AdvancedPropertyValue 基类保持一致性（per D-04）。

    来自 CONTEXT.md D-04a。
    """
    x: float
    y: float
    z: float
    property_type: str = field(default='StructProperty')  # 覆盖父类字段，放最后


@dataclass(kw_only=True)
class RotatorValue(AdvancedPropertyValue):
    """
    Rotator struct property value (Phase 13)。

    Roll/Pitch/Yaw 角度值，UE 使用度数格式（per D-02）。
    unit 字段标注单位为度数，防止误用弧度计算（per D-02a）。

    来自 CONTEXT.md D-04a。
    """
    roll: float    # UE FRotator.Roll (degrees)
    pitch: float   # UE FRotator.Pitch (degrees)
    yaw: float     # UE FRotator.Yaw (degrees)
    unit: str = 'degrees'  # D-02a: 单位标注
    property_type: str = field(default='StructProperty')  # 覆盖父类字段，放最后


@dataclass(kw_only=True)
class ScaleValue(AdvancedPropertyValue):
    """
    Scale3D struct property value (Phase 13)。

    X/Y/Z 缩放因子，用于 RelativeScale3D 属性。
    继承 AdvancedPropertyValue 基类保持一致性（per D-04）。

    来自 CONTEXT.md D-04a。
    """
    x: float
    y: float
    z: float
    property_type: str = field(default='StructProperty')  # 覆盖父类字段，放最后


def format_transform_value(value: float, precision_type: str) -> Union[int, float]:
    """
    格式化变换属性值，应用类型自适应精度处理（per D-03a）。

    Location: 整数优先，否则 3 位小数
    Rotation: 3 位小数
    Scale: 4 位小数

    Args:
        value: 原始浮点值
        precision_type: 精度类型 ('location', 'rotation', 'scale')

    Returns:
        格式化后的值（int 或 float）

    来自 CONTEXT.md D-03a。
    """
    if precision_type == 'location':
        # D-03a: Location 整数优先 - 检测是否为整数
        if value == int(value):
            return int(value)
        return round(value, 3)
    elif precision_type == 'rotation':
        # D-03a: Rotation 3 位小数精度
        return round(value, 3)
    elif precision_type == 'scale':
        # D-03a: Scale 4 位小数精度
        return round(value, 4)
    return value


def parse_vector_value(struct_value: StructValue, precision_type: str = 'location') -> VectorValue:
    """
    解析 Vector struct property 到 VectorValue（per D-01a）。

    从 StructValue.fields 提取 X/Y/Z 字段（大写字母命名），
    应用 format_transform_value 精度处理。

    Args:
        struct_value: StructValue 实例，struct_type="Vector"
        precision_type: 精度类型 ('location' 或 'scale')

    Returns:
        VectorValue dataclass

    Raises:
        KeyError: 若 fields 中缺少 X/Y/Z 字段

    来自 CONTEXT.md D-01a。
    """
    fields = struct_value.fields
    x = format_transform_value(fields["X"], precision_type)
    y = format_transform_value(fields["Y"], precision_type)
    z = format_transform_value(fields["Z"], precision_type)
    return VectorValue(x=x, y=y, z=z)


def parse_rotator_value(struct_value: StructValue) -> RotatorValue:
    """
    解析 Rotator struct property 到 RotatorValue（per D-01a）。

    从 StructValue.fields 提取 Roll/Pitch/Yaw 字段（大写字母命名），
    应用 format_transform_value 精度处理（rotation）。

    Args:
        struct_value: StructValue 实例，struct_type="Rotator"

    Returns:
        RotatorValue dataclass（unit='degrees'）

    Raises:
        KeyError: 若 fields 中缺少 Roll/Pitch/Yaw 字段

    来自 CONTEXT.md D-01a。
    """
    fields = struct_value.fields
    roll = format_transform_value(fields["Roll"], 'rotation')
    pitch = format_transform_value(fields["Pitch"], 'rotation')
    yaw = format_transform_value(fields["Yaw"], 'rotation')
    return RotatorValue(roll=roll, pitch=pitch, yaw=yaw)


def parse_scale_value(struct_value: StructValue) -> ScaleValue:
    """
    解析 Scale3D struct property 到 ScaleValue（per D-01a）。

    从 StructValue.fields 提取 X/Y/Z 字段（大写字母命名），
    Scale3D 使用与 Vector 相同的字段格式。

    Args:
        struct_value: StructValue 实例，struct_type="Vector"

    Returns:
        ScaleValue dataclass

    Raises:
        KeyError: 若 fields 中缺少 X/Y/Z 字段

    来自 CONTEXT.md D-01a。
    """
    fields = struct_value.fields
    x = format_transform_value(fields["X"], 'scale')
    y = format_transform_value(fields["Y"], 'scale')
    z = format_transform_value(fields["Z"], 'scale')
    return ScaleValue(x=x, y=y, z=z)


def extract_component_transforms(
    export_properties: List[PropertyValue],
    component_name: str = None
) -> Dict[str, Any]:
    """
    从组件 export 的 properties 中提取变换属性（per D-01, D-01a）。

    筛选 RelativeLocation/RelativeRotation/RelativeScale3D 属性，
    分派到对应解析函数转换为 VectorValue/RotatorValue/ScaleValue。

    Args:
        export_properties: PropertyValue 列表（来自 parse_properties_from_export）
        component_name: 组件名称（可选，用于日志）

    Returns:
        Dict[str, Any]: 包含 relative_location/relative_rotation/relative_scale 键
                       值为 VectorValue/RotatorValue/ScaleValue 或 None

    来自 CONTEXT.md D-01, D-01a。
    """
    transforms = {}

    for prop in export_properties:
        if prop.type != "StructProperty" or not prop.value:
            continue

        struct_val = prop.value
        if not isinstance(struct_val, StructValue):
            continue

        prop_name = prop.name

        # D-01: 筛选 RelativeLocation/RelativeRotation/RelativeScale3D
        if prop_name == "RelativeLocation" and struct_val.struct_type == "Vector":
            transforms["relative_location"] = parse_vector_value(struct_val, 'location')
        elif prop_name == "RelativeRotation" and struct_val.struct_type == "Rotator":
            transforms["relative_rotation"] = parse_rotator_value(struct_val)
        elif prop_name == "RelativeScale3D" and struct_val.struct_type == "Vector":
            transforms["relative_scale"] = parse_scale_value(struct_val)

    return transforms


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
    Phase 12: enhanced with is_component, metadata, flags_labels (per D-02/D-03).
    Phase 26: 增强变量元数据解析，提取默认值和属性修饰符。
    """
    var_name: str                    # FName
    var_type: "FEdGraphPinType"      # Full type structure (defined next)
    category: str                    # FText (simplified to string)
    property_flags: int              # uint64 EPropertyFlags
    default_value: any = None        # Parsed or raw string per D-13/D-14
    friendly_name: str = ""          # FString
    is_component: bool = False       # Phase 12: component variable flag (per D-02)
    metadata: Dict[str, str] = field(default_factory=dict)  # Phase 12: MetaDataArray (per D-03)
    flags_labels: List[str] = field(default_factory=list)   # Phase 12: PropertyFlags labels (per D-03)

    # Phase 26: 增强字段
    edit_condition: str = ""         # EditCondition 表达式
    meta_class: str = ""             # MetaClass

    # 可见性标志
    is_edit_anywhere: bool = False
    is_edit_instance_only: bool = False
    is_visible_anywhere: bool = False
    is_blueprint_read_only: bool = False

    # 完整标志位
    is_blueprint_readable: bool = False
    is_blueprint_writable: bool = False
    is_transient: bool = False
    is_duplicate_transient: bool = False
    is_text_export_transient: bool = False
    is_non_transient: bool = False
    is_export_object: bool = False
    is_save_game: bool = False
    is_no_clear: bool = False
    is_reference_only: bool = False
    is_blueprint_assignable: bool = False
    is_blueprint_callable: bool = False
    is_net: bool = False
    is_replicated: bool = False
    is_rep_notify: bool = False
    is_interp: bool = False
    is_non_pi_ed_duplicate_transient: bool = False
    is_expose_on_spawn: bool = False

    # 编辑器相关
    edit_category: str = ""
    edit_widget: str = ""            # SpinBox、Slider 等

    # 元数据（备用字段）
    meta_data: dict = None

    def __post_init__(self):
        if self.meta_data is None:
            self.meta_data = {}


@dataclass
class BlueprintMetadata:
    """
    Blueprint metadata extracted from ExportMap.

    Per D-01/D-02/D-03: auto-detect with warning on failure.
    Per D-04: deferred BlueprintType detection (normal:class->ImportExport).
    Phase 26: 增强蓝图元数据，添加 functions 和 events 字段。
    """
    is_blueprint: bool
    parent_class: Optional[str] = None  # Per D-09: only direct parent
    variables: List["BlueprintVariable"] = field(default_factory=list)
    detection_warning: Optional[str] = None  # Per D-03
    functions: List["BlueprintFunction"] = field(default_factory=list)  # Phase 26: 函数列表
    events: List["BlueprintEvent"] = field(default_factory=list)  # Phase 26: 事件列表


# ============================================================================
# Phase 26: Blueprint 事件元数据增强
# ============================================================================

@dataclass
class FunctionParameter:
    """
    函数参数（Phase 26: META-02）。

    来自蓝图函数/事件的参数定义。
    增强函数参数解析，提取详细参数信息和属性标志。
    """
    name: str = ""                    # FName - 参数名
    param_type: str = ""              # 参数类型
    default_value: any = None         # 默认值
    is_input: bool = True             # 是否为输入参数
    is_output: bool = False           # 是否为输出参数
    is_optional: bool = False         # 是否为可选参数
    property_flags: int = 0           # EPropertyFlags

    # 元数据
    meta_data: dict = None

    def __post_init__(self):
        if self.meta_data is None:
            self.meta_data = {}


@dataclass
class MulticastDelegate:
    """多播委托（Phase 26）"""
    delegate_name: str = ""
    signature_function: str = ""
    is_callable_in_blueprint: bool = False

    def __post_init__(self):
        pass


@dataclass
class BlueprintEvent:
    """蓝图事件元数据（增强版 - Phase 26）"""
    name: str = ""
    event_type: str = ""  # CustomEvent、OverriddenEvent、InterfaceEvent

    # 事件标志
    function_flags: int = 0

    # 标志位解析
    is_blueprint_event: bool = False
    is_blueprint_implementable_event: bool = False
    is_net: bool = False
    is_net_multicast: bool = False
    is_net_reliable: bool = False
    is_net_client: bool = False
    is_net_server: bool = False
    is_replicated: bool = False
    is_cosmetic: bool = False
    is_static: bool = False

    # 多播委托
    is_multicast: bool = False
    multicast_delegate: MulticastDelegate = None

    # 重写事件
    is_override: bool = False
    override_parent_class: str = ""
    override_parent_event: str = ""

    # 接口事件
    is_interface_event: bool = False
    interface_class: str = ""

    # 参数
    parameters: List[FunctionParameter] = None

    # 元数据
    meta_data: dict = None

    def __post_init__(self):
        if self.parameters is None:
            self.parameters = []
        if self.meta_data is None:
            self.meta_data = {}


@dataclass
class BlueprintFunction:
    """
    蓝图函数元数据（增强版 - Phase 26: META-02）。

    来自 UFunction 结构。
    增强函数元数据解析，提取参数详细信息和函数属性。
    """
    name: str = ""                    # FName - 函数名
    return_type: str = ""             # 返回类型
    parameters: List[FunctionParameter] = None  # 参数列表

    # 函数属性
    function_flags: int = 0           # EFunctionFlags

    # 标志位解析
    is_pure: bool = False
    is_blueprint_callable: bool = False
    is_blueprint_event: bool = False
    is_blueprint_implementable_event: bool = False
    is_native: bool = False
    is_const: bool = False
    is_static: bool = False
    is_virtual: bool = False
    is_exec: bool = False
    is_net: bool = False
    is_net_reliable: bool = False
    is_net_server: bool = False
    is_net_client: bool = False
    is_net_multicast: bool = False
    is_blueprint_private: bool = False
    is_blueprint_protected: bool = False
    is_blueprint_public: bool = False
    is_blueprint_pure: bool = False
    is_blueprint_cosmetic: bool = False
    is_editor_only: bool = False
    is_final: bool = False
    is_delegate: bool = False
    is_multicast_delegate: bool = False
    is_has_out_parms: bool = False
    is_has_defaults: bool = False

    # 访问修饰符
    access_specifier: str = "Public"  # Public, Private, Protected

    # 元数据
    meta_data: dict = None

    def __post_init__(self):
        if self.parameters is None:
            self.parameters = []
        if self.meta_data is None:
            self.meta_data = {}


# ============================================================================
# Phase 7: Blueprint Graph Data Classes (GRAPH-01 to GRAPH-10)
# ============================================================================

@dataclass
class UEdGraphPin:
    """
    UEdGraphPin 蓝图引脚完整结构（Phase 18 扩展）。

    来自 UE 源码 EdGraphPin.cpp L1838-1964 序列化顺序验证。

    Per D-01/D-01a: LinkedTo 存储为原始数据列表，Phase 8 构建连接映射。
    Per PIN-01~05: 完整字段支持，包含版本依赖字段和显示属性。
    """
    # PIN-01: 基础信息
    pin_id: str                              # FGuid hex（16 bytes）
    pin_name: str                            # FName 解析结果
    pin_tooltip: str = ""                    # FString - PinToolTip (Phase 18)
    direction: int = 0                       # uint8: 0=Input, 1=Output, 2=None

    # PIN-02: PinType
    pin_type: "FEdGraphPinType" = None       # FEdGraphPinType结构

    # PIN-03: 默认值
    default_value: Optional[str] = None      # FString
    auto_default_value: Optional[str] = None  # FString
    default_object: Optional[int] = None     # FPackageIndex (Phase 18)
    default_text_value: Optional[str] = None  # FText简化 (Phase 18)

    # PIN-04: 连接引用（Phase 18: 改为dict格式）
    linked_to_raw: List[dict] = field(default_factory=list)  # D-01a改为dict格式
    sub_pins: List[dict] = field(default_factory=list)       # 同linked_to格式
    parent_pin: Optional[dict] = None                        # 同linked_to格式

    # PIN-05: 显示属性（BitField解析）
    hidden: bool = False                     # bit 0
    not_connectable: bool = False            # bit 1
    advanced_view: bool = False              # bit 4
    orphaned_pin: bool = False               # bit 5

    # EditorOnly/版本依赖字段（内部使用，不输出到JSON）
    owning_node_index: int = 0               # FPackageIndex (序列化起始)
    source_index: Optional[int] = None      # int32 - 版本依赖
    persistent_guid: Optional[str] = None   # FGuid hex - EditorOnly

    # Legacy字段（保持兼容）
    flags: int = 0                           # uint8 bitfield (deprecated)


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


# ============================================================================
# 从新版模块复用 ParseResult/StatusInfo（避免测试 isinstance 失败）
# ============================================================================
from uasset_read.models.result import ParseResult, StatusInfo


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
            b_import_optional = archive.read_bool()

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

    # Phase 11 GAP修复：检查PKG_Cooked标志
    # TemplateIndex和PreloadDependencies只在cooked资产中有效（ObjectVersion.h注释）
    is_cooked = (summary.package_flags & PKG_Cooked) != 0

    for export_idx in range(summary.export_count):
        object_name = ""  # 初始化用于错误上下文

        try:
            # 1. ClassIndex
            class_index = PackageIndex(archive.read_i32())

            # 2. SuperIndex
            super_index = PackageIndex(archive.read_i32())

            # 3. TemplateIndex（条件读取 UE4 >= 508）
            template_index = PackageIndex(0)
            if effective_ue4_version >= VER_UE4_TemplateIndex_IN_COOKED_EXPORTS:  # 508
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

            # 9-11. bool flags（UE 标准：各序列化为 4 bytes uint32）
            b_forced_export = archive.read_bool()
            b_not_for_client = archive.read_bool()
            b_not_for_server = archive.read_bool()

            # 12. PackageGuid（Phase 11 GAP: UE5 < 1005时读取但不存储）
            if is_ue5_file and summary.file_version_ue5 < UE5_REMOVE_OBJECT_EXPORT_PACKAGE_GUID:  # 1005
                # 读取 16 bytes FGuid，但不存储（DummyPackageGuid）
                archive.read_bytes(16)

            # 13. bIsInheritedInstance（Phase 11 GAP: UE5 >= 1006）
            b_is_inherited_instance = None
            if is_ue5_file and summary.file_version_ue5 >= UE5_TRACK_OBJECT_EXPORT_IS_INHERITED:  # 1006
                b_is_inherited_instance = archive.read_bool()

            # 14. PackageFlags（D-09）
            package_flags = archive.read_u32()

            # 15-17. 其他 bool flags（D-08：条件读取）
            b_not_always_loaded_for_editor_game = None
            b_is_asset = None
            b_generate_public_hash = None

            # UE4 版本条件：bNotAlwaysLoadedForEditorGame（UE4 >= 383，UE5 总是满足）
            if effective_ue4_version >= UE4_LOAD_FOR_EDITOR_GAME:
                b_not_always_loaded_for_editor_game = archive.read_bool()

            # UE4 版本条件：bIsAsset（UE4 >= 401，UE5 总是满足）
            if effective_ue4_version >= UE4_COOKED_ASSETS_IN_EDITOR_SUPPORT:
                b_is_asset = archive.read_bool()

            # UE5 版本条件：bGeneratePublicHash（Phase 11 GAP: UE5 >= OPTIONAL_RESOURCES=1003）
            if is_ue5_file and summary.file_version_ue5 >= UE5_OPTIONAL_RESOURCES:
                b_generate_public_hash = archive.read_bool()

            # 18. 依赖数组（UE4 >= 507）
            # FirstExportDependency + 4个依赖计数（5个 i32）
            first_export_dependency = 0
            serialization_before_serialization_deps = 0
            create_before_serialization_deps = 0
            serialization_before_create_deps = 0
            create_before_create_deps = 0
            if effective_ue4_version >= UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS:  # 507
                first_export_dependency = archive.read_i32()
                serialization_before_serialization_deps = archive.read_i32()
                create_before_serialization_deps = archive.read_i32()
                serialization_before_create_deps = archive.read_i32()
                create_before_create_deps = archive.read_i32()

            # 19-20. ScriptSerializationStartOffset/EndOffset
            # 条件: !UseUnversionedPropertySerialization() && UEVer() >= SCRIPT_SERIALIZATION_OFFSET(1010)
            # UseUnversionedPropertySerialization()基于PKG_UnversionedProperties标志判断
            # 若PKG_UnversionedProperties未设置，则使用versioned property serialization，需要读取这些字段
            # 参考: ObjectResource.cpp 第 212-222 行
            # 序列化顺序: StartOffset 先, EndOffset 后
            script_serial_offset = 0
            script_serial_size = 0
            uses_unversioned = (summary.package_flags & PKG_UnversionedProperties) != 0
            if is_ue5_file and not uses_unversioned and summary.file_version_ue5 >= UE5_SCRIPT_SERIALIZATION_OFFSET:
                script_serial_offset = archive.read_i64()  # ScriptSerializationStartOffset (第一个)
                script_serial_size = archive.read_i64()  # ScriptSerializationEndOffset (第二个)

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
        # 从导入表获取类名（object_name 是实际类名，如 EdGraph）
        import_idx = export.class_index.to_import_index()
        if 0 <= import_idx < len(import_map):
            return import_map[import_idx].object_name
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
        # 从导入表获取对象名（而非类型名 class_name）
        import_idx = class_index.to_import_index()
        if 0 <= import_idx < len(import_map):
            return import_map[import_idx].object_name
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


def detect_blueprint_generated_class(
    export: ObjectExport,
    import_map: List[ObjectImport],
    export_map: List[ObjectExport]
) -> bool:
    """
    Detect if export is a BlueprintGeneratedClass (Phase 12, per D-01).

    Variables are extracted from BlueprintGeneratedClass exports, not UBlueprint.
    BlueprintGeneratedClass is the compiled class representation.

    Args:
        export: ObjectExport to check
        import_map: Import table for ClassIndex lookup
        export_map: Export table for ClassIndex lookup

    Returns:
        True if export is BlueprintGeneratedClass, False otherwise
    """
    if export.class_index.is_import:
        idx = export.class_index.to_import_index()
        if 0 <= idx < len(import_map):
            class_name = import_map[idx].class_name
            # BlueprintGeneratedClass or subclasses (AnimBlueprintGeneratedClass, etc.)
            return "BlueprintGeneratedClass" in class_name
    return False


def find_main_blueprint_generated_class(
    export_map: List[ObjectExport],
    import_map: List[ObjectImport],
    asset_name: str
) -> Optional[ObjectExport]:
    """
    Find the main BlueprintGeneratedClass export (Phase 12, per D-01).

    Uses object_name matching with asset_name + serial_size maximum principle.
    Main BPGC typically has object_name = asset_name + "_C".

    Args:
        export_map: Export table to search
        import_map: Import table for ClassIndex lookup
        asset_name: Asset name to match (without .uasset suffix)

    Returns:
        ObjectExport of main BlueprintGeneratedClass, or None if not found
    """
    candidates = []
    for export in export_map:
        if detect_blueprint_generated_class(export, import_map, export_map):
            # Main BPGC object_name is typically asset_name + "_C"
            if export.object_name and export.object_name.startswith(asset_name):
                candidates.append(export)

    if candidates:
        # Select the one with largest serial_size (main class has most data)
        return max(candidates, key=lambda e: e.serial_size)
    return None


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
    for export_idx, export in enumerate(export_map):
        # D-03a: ClassIndex 解析为类名
        class_name = get_asset_class(export, import_map, export_map)

        if class_name and class_name in ['EdGraph', 'UberEdGraph']:
            # D-03b/D-03c: 完整解析 Graph→Node→Pin 三层结构
            # export_idx + 1 = 1-based FPackageIndex for export
            graph = read_ue_graph(
                archive, name_map, summary,
                export_map, import_map,
                export, class_name, export_idx + 1
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
    Parse FEdGraphPinType with version checks.

    ROOT CAUSE FIX: FEdGraphPinType 有两种序列化模式：
    
    1. 默认反射序列化（UEVer() < VER_UE4_EDGRAPHPINTYPE_SERIALIZATION = 324）：
       - 用于 UE5 资产（FileVersionUE4 = -9）
       - 序列化所有 UPROPERTY 字段，顺序按 EdGraphPin.h L76-133 声明顺序
       
    2. 自定义序列化（UEVer() >= 324）：
       - 用于 UE4 资产（FileVersionUE4 >= 324）
       - 序列化顺序来自 EdGraphPin.cpp L163-346

    Args:
        archive: FArchive positioned at start of FEdGraphPinType
        name_map: NameMap for FName resolution
        summary: PackageFileSummary for version info

    Returns:
        FEdGraphPinType dataclass with all fields populated
    """
    pin_type = FEdGraphPinType()

    # 版本获取
    framework_version = summary.get_custom_version(FFRAMEWORK_OBJECT_VERSION_GUID, 0)
    release_version = summary.get_custom_version(FRELEASE_OBJECT_VERSION_GUID, 0)
    ue4_version = summary.file_version_ue4

    # ROOT CAUSE FIX: 判断使用哪种序列化模式
    # Per EdGraphPin.cpp L163-166: if (Ar.UEVer() < VER_UE4_EDGRAPHPINTYPE_SERIALIZATION) return false
    # 返回 false 时使用默认反射序列化
    # VER_UE4_EDGRAPHPINTYPE_SERIALIZATION = 324 (从 ObjectVersion.h 计算)
    VER_UE4_EDGRAPHPINTYPE_SERIALIZATION = 324
    use_custom_serialization = ue4_version >= VER_UE4_EDGRAPHPINTYPE_SERIALIZATION

    if DEBUG_PIN_PARSING:
        print(f"[DEBUG PIN_TYPE] ue4_version={ue4_version}, use_custom_serialization={use_custom_serialization}")

    if not use_custom_serialization:
        # 默认反射序列化模式（UE5 资产）
        # Per EdGraphPin.h L76-133: UPROPERTY 字段声明顺序
        # 1. PinCategory (FName)
        pin_type.pin_category = archive.read_name(name_map)
        # 2. PinSubCategory (FName)
        pin_type.pin_sub_category = archive.read_name(name_map)
        # 3. PinSubCategoryObject (TWeakObjectPtr -> FPackageIndex)
        pin_type.pin_sub_category_object = archive.read_i32()
        # 4. PinSubCategoryMemberReference (FSimpleMemberReference - 3 fields)
        #    MemberParent + MemberName + MemberGuid
        archive.read_i32()       # MemberParent (FPackageIndex)
        archive.read_name(name_map)  # MemberName (FName)
        archive.read(16)         # MemberGuid (FGuid)
        # 5. PinValueType (FEdGraphTerminalType) - 总是序列化！
        archive.read_name(name_map)  # TerminalCategory
        archive.read_name(name_map)  # TerminalSubCategory
        archive.read_i32()           # TerminalSubCategoryObject
        # 6. ContainerType (EPinContainerType - uint8)
        pin_type.container_type = archive.read_u8()
        # 7-12. Bit flags (bIsArray_DEPRECATED + 5 flags as uint8:1)
        # Per UE 源码，位字段作为单个 uint8 序列化
        flags_byte = archive.read_u8()
        pin_type.is_reference = (flags_byte & 0x04) != 0  # bIsReference at bit 2
        pin_type.is_const = (flags_byte & 0x08) != 0      # bIsConst at bit 3
        pin_type.is_weak_pointer = (flags_byte & 0x10) != 0  # bIsWeakPointer at bit 4
        pin_type.is_uobject_wrapper = (flags_byte & 0x20) != 0  # bIsUObjectWrapper at bit 5
        # bSerializeAsSinglePrecisionFloat at bit 6 (忽略)
        
        if DEBUG_PIN_PARSING:
            print(f"[DEBUG PIN_TYPE] Default reflection: PinCategory={pin_type.pin_category}, ContainerType={pin_type.container_type}")
    else:
        # 自定义序列化模式（UE4 >= 324）
        # Per EdGraphPin.cpp L163-346
        # Phase 22 FIX-03: UE5.7 版本检查修复
        use_fname_format = framework_version >= FFRAMEWORK_VERSION_PINS_STORE_FNAME or summary.file_version_ue5 > 0

        # 1-2. PinCategory and PinSubCategory (version dependent)
        cat_start = archive.tell()
        if use_fname_format:
            pin_type.pin_category = archive.read_name(name_map)
            pin_type.pin_sub_category = archive.read_name(name_map)
        else:
            pin_type.pin_category = archive.read_fstring()
            pin_type.pin_sub_category = archive.read_fstring()
        cat_end = archive.tell()
        if DEBUG_PIN_PARSING:
            print(f"[DEBUG PIN_TYPE] PinCategory/SubCategory: {cat_end - cat_start} bytes, cat={pin_type.pin_category}")

        # 3. PinSubCategoryObject (FPackageIndex)
        obj_start = archive.tell()
        pin_type.pin_sub_category_object = archive.read_i32()
        obj_end = archive.tell()
        if DEBUG_PIN_PARSING:
            print(f"[DEBUG PIN_TYPE] PinSubCategoryObject: {obj_end - obj_start} bytes, value={pin_type.pin_sub_category_object}")

        # 4-5. ContainerType (version dependent)
        container_start = archive.tell()
        use_modern_container = framework_version >= FFRAMEWORK_VERSION_ED_GRAPH_PIN_CONTAINER_TYPE or summary.file_version_ue5 > 0
        if use_modern_container:
            pin_type.container_type = archive.read_u8()
            if pin_type.container_type == 3:  # Map
                archive.read_name(name_map)  # TerminalCategory
                archive.read_name(name_map)  # TerminalSubCategory
                archive.read_i32()           # TerminalSubCategoryObject
        else:
            b_is_map = archive.read_bool()
            b_is_set = archive.read_bool()
            b_is_array = archive.read_bool()
            if b_is_map:
                pin_type.container_type = 3
            elif b_is_set:
                pin_type.container_type = 2
            elif b_is_array:
                pin_type.container_type = 1
            else:
                pin_type.container_type = 0
        container_end = archive.tell()
        if DEBUG_PIN_PARSING:
            print(f"[DEBUG PIN_TYPE] ContainerType: {container_end - container_start} bytes, value={pin_type.container_type}, modern={use_modern_container}")

        # 6-7. bIsReference and bIsWeakPointer
        ref_start = archive.tell()
        pin_type.is_reference = archive.read_bool()
        pin_type.is_weak_pointer = archive.read_bool()
        ref_end = archive.tell()
        if DEBUG_PIN_PARSING:
            print(f"[DEBUG PIN_TYPE] bIsReference/WeakPointer: {ref_end - ref_start} bytes, ref={pin_type.is_reference}, weak={pin_type.is_weak_pointer}")

        # 8. PinSubCategoryMemberReference (version dependent)
        # Per EdGraphPin.cpp L254-269: UEVer() >= VER_UE4_MEMBERREFERENCE_IN_PINTYPE
        # FSimpleMemberReference (3 fields): MemberParent + MemberName + MemberGuid
        if ue4_version >= VER_UE4_MEMBERREFERENCE_IN_PINTYPE:
            ref_start = archive.tell()
            mp = archive.read_i32()       # MemberParent
            mn = archive.read_name(name_map)  # MemberName
            mg = archive.read(16)         # MemberGuid
            ref_end = archive.tell()
            if DEBUG_PIN_PARSING:
                print(f"[DEBUG PIN_TYPE] FSimpleMemberReference: {ref_end - ref_start} bytes (Parent={mp}, Name={mn})")

        # 9. bIsConst (version dependent)
        # Per EdGraphPin.cpp L271-276: UEVer() >= VER_UE4_SERIALIZE_PINTYPE_CONST
        VER_UE4_SERIALIZE_PINTYPE_CONST = 366  # 从 ObjectVersion.h 计算
        const_start = archive.tell()
        if ue4_version >= VER_UE4_SERIALIZE_PINTYPE_CONST:
            pin_type.is_const = archive.read_bool()
        else:
            pin_type.is_const = False  # Default value, not serialized
        const_end = archive.tell()
        if DEBUG_PIN_PARSING:
            print(f"[DEBUG PIN_TYPE] bIsConst: {const_end - const_start} bytes, value={pin_type.is_const}, threshold={VER_UE4_SERIALIZE_PINTYPE_CONST}")

        # 10. bIsUObjectWrapper (version dependent)
        # Per EdGraphPin.cpp L278-283: CustomVer >= PinTypeIncludesUObjectWrapperFlag
        FRELEASE_VERSION_PIN_TYPE_INCLUDES_UOBJECT_WRAPPER = 10
        wrapper_start = archive.tell()
        if release_version >= FRELEASE_VERSION_PIN_TYPE_INCLUDES_UOBJECT_WRAPPER:
            pin_type.is_uobject_wrapper = archive.read_bool()
        else:
            pin_type.is_uobject_wrapper = False  # Default value
        wrapper_end = archive.tell()
        if DEBUG_PIN_PARSING:
            print(f"[DEBUG PIN_TYPE] bIsUObjectWrapper: {wrapper_end - wrapper_start} bytes, value={pin_type.is_uobject_wrapper}, rel_ver={release_version}")

    return pin_type

def read_pin_reference(
    archive: FArchive,
    name_map: List[str],
    export_map: List[ObjectExport],
    import_map: List[ObjectImport]
) -> Optional[dict]:
    """
    读取单个Pin引用（SerializePin格式）。

    用于LinkedTo/SubPins/ParentPin字段，格式来自UE源码EdGraphPin.cpp L2132-2296：
    1. bNullPtr (bool/uint8)
    2. OwningNode (FPackageIndex/int32)
    3. PinGuid (FGuid 16 bytes)

    Args:
        archive: FArchive positioned at pin reference start
        name_map: NameMap for FName resolution
        export_map: ExportMap for FPackageIndex resolution
        import_map: ImportMap for FPackageIndex resolution

    Returns:
        dict with "owning_node" (str) and "pin_guid" (str), or None if null
    """
    # 1. bNullPtr flag
    b_null_ptr = archive.read_bool()
    if b_null_ptr:
        return None

    # 2. OwningNode (FPackageIndex)
    owning_node_index = archive.read_i32()

    # 3. PinGuid (FGuid 16 bytes)
    pin_guid_bytes = archive.read_bytes(16)
    pin_guid = pin_guid_bytes.hex().upper()

    # Resolve OwningNode FPackageIndex to node name
    # FPackageIndex: >0 = ExportMap, <0 = ImportMap (negated index)
    owning_node_name = ""
    if owning_node_index > 0:
        node_idx = owning_node_index - 1  # FPackageIndex is 1-indexed
        if node_idx < len(export_map):
            owning_node_name = export_map[node_idx].object_name
    elif owning_node_index < 0:
        import_idx = -owning_node_index - 1
        if import_idx < len(import_map):
            owning_node_name = import_map[import_idx].object_name

    return {
        "owning_node": owning_node_name,
        "pin_guid": pin_guid
    }


def read_pin_array(
    archive: FArchive,
    name_map: List[str],
    export_map: List[ObjectExport],
    import_map: List[ObjectImport]
) -> List[dict]:
    """
    读取Pin引用数组（SerializePinArray格式）。

    用于LinkedTo/SubPins字段，格式来自UE源码EdGraphPin.cpp L2063-2098：
    1. ArrayNum (int32)
    2. For each: read_pin_reference()

    安全边界：count <= MAX_LINKEDTO_PER_PIN (100)

    Args:
        archive: FArchive positioned at array start
        name_map: NameMap for FName resolution
        export_map: ExportMap for FPackageIndex resolution
        import_map: ImportMap for FPackageIndex resolution

    Returns:
        List of dict pin references (empty list if count=0)

    Raises:
        ParseError: if count exceeds MAX_LINKEDTO_PER_PIN or negative
    """
    # 1. ArrayNum (int32)
    array_count = archive.read_i32()

    if DEBUG_PIN_PARSING:
        print(f"[DEBUG PIN ARRAY] Reading {array_count} pins at offset: {archive.tell():#x}")

    if array_count < 0:
        raise ParseError(f"Invalid pin array count: {array_count} (negative)")
    if array_count > MAX_LINKEDTO_PER_PIN:
        raise ParseError(
            f"Pin array count {array_count} exceeds MAX_LINKEDTO_PER_PIN "
            f"{MAX_LINKEDTO_PER_PIN}"
        )

    # 2. For each element
    pins: List[dict] = []
    for i in range(array_count):
        pin_ref = read_pin_reference(archive, name_map, export_map, import_map)
        if DEBUG_PIN_PARSING:
            print(f"[DEBUG PIN ARRAY]   [{i}] {pin_ref}")
        if pin_ref is not None:
            pins.append(pin_ref)

    if DEBUG_PIN_PARSING:
        print(f"[DEBUG PIN ARRAY] Total {len(pins)} pins read, offset now: {archive.tell():#x}")

    return pins


def skip_ftext_editoronly(archive: FArchive) -> None:
    """
    跳过 EditorOnly FText 字段（如 PinFriendlyName）。

    FText 序列化格式（UE 源码 Text.cpp:850-1043）：
    1. Flags (int32)
    2. HistoryType (int8) - ETextHistoryType 枚举
    3. 根据 HistoryType 类型：
       - None (-1/255): bHasCultureInvariantString (uint8) + [CultureInvariantString (FString)]
       - Base (0): Namespace (FString) + Key (FString) + SourceString (FString)
       - NamedFormat (1): SourceFmt + Arguments map
       - 其他类型：通用跳过策略

    Per Phase 22-06: ETextHistoryType 枚举值修正（TextHistory.h L23-41）
    - None = -1 (int8) = 255 (uint8)
    - Base = 0
    - NamedFormat = 1
    - OrderedFormat = 2
    - ...

    安全边界（T-22-02-01）：添加异常处理防止解析崩溃
    安全边界（T-22-02-02）：添加最大循环限制防止 DoS

    Args:
        archive: FArchive positioned at FText start
    """
    start_pos = archive.tell()
    try:
        # 1. Flags (int32)
        flags = archive.read_i32()

        # 2. HistoryType (int8/uint8)
        history_type = archive.read_u8()

        # 调试输出（可通过 --debug-ftext 启用）
        if "--debug-ftext" in sys.argv:
            print(f"DEBUG FText: pos={start_pos}, flags={flags}, history_type={history_type}")

        # 3. 根据 HistoryType 跳过后续数据
        # ETextHistoryType 枚举值（修正后）：
        # None = 255 (uint8) = -1 (int8)
        # Base = 0
        # NamedFormat = 1
        # OrderedFormat = 2
        # ...

        if history_type == 255:  # None (int8 = -1)
            # bHasCultureInvariantString (bool 序列化为 uint8)
            b_has_culture_invariant = archive.read_u8()
            if "--debug-ftext" in sys.argv:
                print(f"  None: bHasCultureInvariant={b_has_culture_invariant}")
            if b_has_culture_invariant != 0:
                # CultureInvariantString (FString)
                archive.read_fstring()
        elif history_type == 0:  # Base
            # Phase 22 FIX-10: 检查 FText 是否为空（未被序列化）
            # 如果 flags=0，这可能是空的 FText（EditorOnly 数据被过滤）
            # 但也可能是 Base 类型的 FText（需要读取 3 FStrings）
            # 使用 lookahead 检查：如果下一个 4 bytes 不是合理的字符串长度，假设 FText 未被序列化
            ftext_data_start = archive.tell()
            try:
                # 读取 Namespace 长度（第一个 FString）
                ns_len = archive.read_u32()
                # 检查长度是否合理（0-100000）
                if 0 <= ns_len <= 100000:
                    # 正常的 Base FText，读取剩余部分
                    archive.read_bytes(ns_len * 2)  # Namespace content (UTF-16)
                    key_len = archive.read_u32()
                    archive.read_bytes(key_len * 2)  # Key content
                    src_len = archive.read_u32()
                    archive.read_bytes(src_len * 2)  # Source content
                    if "--debug-ftext" in sys.argv:
                        print(f"  Base: read 3 FStrings (ns={ns_len}, key={key_len}, src={src_len})")
                else:
                    # 可能是垃圾数据，回退到 FText 起始位置
                    # 假设 FText 未被序列化
                    archive.seek(start_pos)  # 回退到 FText 开始位置（flags 之前）
                    if "--debug-ftext" in sys.argv:
                        print(f"  Base: Invalid len {ns_len}, assuming FText not serialized")
                    # 重新抛出异常，让调用者知道 FText 未被跳过
                    raise ValueError("FText not serialized")
            except Exception as e:
                # 回退到起始位置
                archive.seek(start_pos)
        elif history_type >= 1 and history_type <= 12:  # NamedFormat 到 StringTableEntry
            # 其他类型的通用跳过策略（T-22-02-02：限制循环）
            # NamedFormat: SourceFmt + Arguments map
            # OrderedFormat: SourceFmt + Arguments array
            # 简化处理：读取最多 5 个 FString（覆盖大多数类型）
            max_strings = 5
            for _ in range(max_strings):
                try:
                    archive.read_fstring()
                except Exception:
                    break
            if "--debug-ftext" in sys.argv:
                print(f"  Type {history_type}: read up to {max_strings} FStrings")
        else:
# Phase 22 FIX-08: 处理特殊的 history_type 值
            # history_type=255 可能表示空FText或未初始化的FText
            # 在这种情况下，不应该跳过任何额外的字节（只跳过flags和history_type本身）
            if history_type == 255:
                # 不跳过额外的字节，只跳过了flags(4) + historyType(1) = 5字节
                if "--debug-ftext" in sys.argv:
                    print(f"  history_type=255: treating as empty FText, no extra bytes skipped")
            else:
                # 其他未知 HistoryType，回退
                if "--debug-ftext" in sys.argv:
                    print(f"  Unknown HistoryType {history_type} - seeking back to start")
                archive.seek(start_pos)
    except Exception as e:
        # T-22-02-01: 异常处理防止解析崩溃
        # 回退到起始位置
        if "--debug-ftext" in sys.argv:
            print(f"  Exception: {e} - seeking back to {start_pos}")
        archive.seek(start_pos)


def read_ue_graph_pin(
    archive: FArchive,
    name_map: List[str],
    summary: PackageFileSummary,
    export_map: List[ObjectExport],
    import_map: List[ObjectImport]
) -> UEdGraphPin:
    """
    读取 UEdGraphPin（完整序列化格式）。

    序列化顺序（UE源码 EdGraphPin.cpp L1838-1964 验证）：
    1. OwningNode (FPackageIndex) - 序列化起始字段
    2. PinId (FGuid 16 bytes)
    3. PinName (FName/FString) - 版本依赖
    4. [PinFriendlyName] (FText) - EditorOnly，跳过
    5. [SourceIndex] (int32) - 版本依赖
    6. PinToolTip (FString)
    7. Direction (uint8)
    8. PinType (FEdGraphPinType)
    9. DefaultValue (FString)
    10. AutogeneratedDefaultValue (FString)
    11. DefaultObject (FPackageIndex)
    12. DefaultTextValue (FText) - 简化处理
    13. LinkedTo (SerializePinArray)
    14. SubPins (SerializePinArray)
    15. ParentPin (SerializePin)
    16. ReferencePassThroughConnection (SerializePin) - 位置同步
    17. [PersistentGuid] (FGuid) - EditorOnly，跳过
    18. [BitField] (uint32) - EditorOnly，解析显示属性

    Args:
        archive: FArchive positioned at pin start
        name_map: NameMap for FName resolution
        summary: PackageFileSummary for version info
        export_map: ExportMap for FPackageIndex resolution
        import_map: ImportMap for FPackageIndex resolution

    Returns:
        UEdGraphPin dataclass with all fields populated
    """
    # 版本检查（使用18-01定义的常量）
    framework_version = summary.get_custom_version(FFRAMEWORK_OBJECT_VERSION_GUID, 0)
    mainstream_version = summary.get_custom_version(FUE5_MAINSTREAM_VERSION_GUID, 0)

    # Phase 22 FIX-03: UE5.7 版本检查修复
    # 当 CustomVersion 不存在时，使用 file_version_ue5 作为 fallback
    # Phase 22 FIX-03: UE5 CustomVersion fallback
    # Per Archive.cpp L558-567: 加载时用 FCurrentCustomVersions::GetAll() 填充，
    # 所以即使资产文件中没有存储 GUID，UE 也会从注册表获取最新版本。
    # 我的解析器没有注册表机制，用 file_version_ue5 > 0 作为 fallback。
    # UE5 资产（file_version_ue5 > 0）应该使用现代 FName 格式。
    use_fname_format = framework_version >= FFRAMEWORK_VERSION_PINS_STORE_FNAME or summary.file_version_ue5 > 0

    pin_start_pos = archive.tell()

    if DEBUG_PIN_PARSING:
        print(f"[DEBUG PIN] ========================================")
        print(f"[DEBUG PIN] Pin parsing started at offset: {pin_start_pos:#x}")
        print(f"[DEBUG PIN] framework_version: {framework_version}, mainstream_version: {mainstream_version}")
        print(f"[DEBUG PIN] use_fname_format: {use_fname_format}")

    # 1. OwningNode (FPackageIndex) [L1844] - 关键：序列化起始字段
    owning_node_index = archive.read_i32()
    if DEBUG_PIN_PARSING:
        print(f"[DEBUG PIN] 1. OwningNode: {owning_node_index}, offset now: {archive.tell():#x}")

    # 2. PinId (FGuid 16 bytes) [L1845]
    pin_id_bytes = archive.read_bytes(16)
    pin_id = pin_id_bytes.hex().upper()
    if DEBUG_PIN_PARSING:
        print(f"[DEBUG PIN] 2. PinId: {pin_id}, offset now: {archive.tell():#x}")

    # 3. PinName (version dependent) [L1847-1856]
    # Phase 22 FIX-03: UE5 资产始终使用 FName 格式
    # 使用智能版本判断：CustomVersion >= threshold OR file_version_ue5 > 0
    if use_fname_format:
        pin_name = archive.read_name(name_map)
    else:
        pin_name = archive.read_fstring()
    if DEBUG_PIN_PARSING:
        print(f"[DEBUG PIN] 3. PinName: {pin_name}, offset now: {archive.tell():#x}")

    # 4. PinFriendlyName (FText) - EditorOnly [L1858-1863]
# Phase 22 FIX-08: 修复FText history_type=255的处理
    # 根据调试分析，history_type=255应该跳过固定字节
    # 但之前的12字节跳过导致后续字段位置错误
    # 新策略：根据实际字节数调整，使用动态检测
    ftext_start_pos = archive.tell()

    if DEBUG_PIN_PARSING:
        print(f"[DEBUG PIN] 4. PinFriendlyName (FText) attempt at offset: {ftext_start_pos:#x}")

    # 尝试读取FText并检测实际大小
    try:
        flags = archive.read_i32()
        history_type = archive.read_u8()

        if DEBUG_PIN_PARSING:
            print(f"[DEBUG PIN]    FText: flags={flags}, history_type={history_type}")

        # 根据history_type决定跳过多少字节
        # Per UE 源码 Text.cpp L1020-1036 和 TextHistory.h:
        # ETextHistoryType::None = -1 (int8), Base = 0
        if history_type == -1 or history_type == 255:  # ETextHistoryType::None (int8: 255 = -1)
            # Per UE 源码 Text.cpp L1020-1036:
            # 当 history_type = None 时，检查 bHasCultureInvariantString
            if DEBUG_PIN_PARSING:
                print(f"[DEBUG PIN]    FText type None (-1/255): checking bHasCultureInvariantString")

            # 读取 bHasCultureInvariantString (bool)
            b_has_culture_invariant = archive.read_bool()
            if DEBUG_PIN_PARSING:
                print(f"[DEBUG PIN]    bHasCultureInvariantString: {b_has_culture_invariant}")

            if b_has_culture_invariant:
                # 读取 CultureInvariantString (FString)
                culture_invariant_string = archive.read_fstring()
                if DEBUG_PIN_PARSING:
                    print(f"[DEBUG PIN]    CultureInvariantString: '{culture_invariant_string}'")
        elif history_type == 0:  # ETextHistoryType::Base
            archive.read_fstring()  # Namespace
            archive.read_fstring()  # Key
            archive.read_fstring()  # SourceString
            if DEBUG_PIN_PARSING:
                print(f"[DEBUG PIN]    FText type 0 (Base): skipped 3 FStrings, offset now: {archive.tell():#x}")
        else:
            # 其他类型，跳过最多5个FString
            max_strings = 5
            for _ in range(max_strings):
                try:
                    archive.read_fstring()
                except Exception:
                    break
            if DEBUG_PIN_PARSING:
                print(f"[DEBUG PIN]    FText type {history_type}: skipped up to {max_strings} strings, offset now: {archive.tell():#x}")

    except Exception as e:
        # FText读取失败，回退到起始位置
        archive.seek(ftext_start_pos)
        if DEBUG_PIN_PARSING:
            print(f"[DEBUG PIN]    FText skip failed: {e}, seeking back to {ftext_start_pos:#x}")

    # 5. SourceIndex (int32) - version dependent [L1865-1868]
    # Phase 22 FIX-08: 修复版本检查逻辑 - UE5.7 资产中 SourceIndex 存在
    source_index = None
    if mainstream_version >= FUE5_MAINSTREAM_VERSION_ED_GRAPH_PIN_SOURCE_INDEX:
        source_index = archive.read_i32()
        if DEBUG_PIN_PARSING:
            print(f"[DEBUG PIN] 5. SourceIndex: {source_index}, offset now: {archive.tell():#x}")
    else:
        # 对于 UE5.7 资产，即使版本检查失败，也尝试读取 SourceIndex
        start_pos = archive.tell()
        try:
            test_source = archive.read_i32()
            if -100 <= test_source <= 1000000:  # 合理范围
                source_index = test_source
                if DEBUG_PIN_PARSING:
                    print(f"[DEBUG PIN] 5. SourceIndex (fallback): {source_index}, offset now: {archive.tell():#x}")
            else:
                archive.seek(start_pos)
                if DEBUG_PIN_PARSING:
                    print(f"[DEBUG PIN] 5. SourceIndex not read (version {mainstream_version} < threshold), offset: {archive.tell():#x}")
        except Exception:
            archive.seek(start_pos)

    # 6. PinToolTip (FString) [L1870]
    tooltip_start = archive.tell()
    pin_tooltip = archive.read_fstring()
    if DEBUG_PIN_PARSING:
        tooltip_bytes = archive.tell() - tooltip_start
        print(f"[DEBUG PIN] 6. PinToolTip: '{pin_tooltip}', {tooltip_bytes} bytes, offset now: {archive.tell():#x}")

    # 7. Direction (uint8) [L1871]
    direction = archive.read_u8()
    if DEBUG_PIN_PARSING:
        print(f"[DEBUG PIN] 7. Direction: {direction}, offset now: {archive.tell():#x}")

    # 8. PinType (FEdGraphPinType) [L1872]
    pintype_start = archive.tell()
    pin_type = read_ed_graph_pin_type(archive, name_map, summary)
    if DEBUG_PIN_PARSING:
        pintype_bytes = archive.tell() - pintype_start
        print(f"[DEBUG PIN] 8. PinType: {pin_type.pin_category}, {pintype_bytes} bytes, offset now: {archive.tell():#x}")

    # 9-10. DefaultValue strings [L1873-1874]
    # Phase 22-09 Task 3: 添加异常处理，防止解析崩溃
    try:
        default_value = archive.read_fstring()
        if DEBUG_PIN_PARSING:
            print(f"[DEBUG PIN] 9. DefaultValue: '{default_value}', offset now: {archive.tell():#x}")
    except Exception as e:
        default_value = ""
        if DEBUG_PIN_PARSING:
            print(f"[DEBUG PIN] 9. DefaultValue: ERROR ({e}), using empty string, offset now: {archive.tell():#x}")

    try:
        autogenerated_default_value = archive.read_fstring()
        if DEBUG_PIN_PARSING:
            print(f"[DEBUG PIN] 10. AutogeneratedDefaultValue: '{autogenerated_default_value}', offset now: {archive.tell():#x}")
    except Exception as e:
        autogenerated_default_value = ""
        if DEBUG_PIN_PARSING:
            print(f"[DEBUG PIN] 10. AutogeneratedDefaultValue: ERROR ({e}), using empty string, offset now: {archive.tell():#x}")

    # 11. DefaultObject (FPackageIndex) [L1875]
    try:
        default_object_index = archive.read_i32()
        if DEBUG_PIN_PARSING:
            print(f"[DEBUG PIN] 11. DefaultObject: {default_object_index}, offset now: {archive.tell():#x}")
    except Exception as e:
        default_object_index = 0
        if DEBUG_PIN_PARSING:
            print(f"[DEBUG PIN] 11. DefaultObject: ERROR ({e}), using 0, offset now: {archive.tell():#x}")

    # 12. DefaultTextValue (FText) [L1876]
    # Phase 22 FIX-15: 正确处理 FText 空值序列化
    # 实际数据验证：当 FText 为空时，序列化格式可能是：
    # flags(4) + ???(4) + history_type(1, value=255/None) + bHasCulture(4) = 13 bytes
    # 或：flags(4) = 0 表示完全空的 FText，后续是 LinkedTo
    default_text_value = None
    dtv_start_pos = archive.tell()

    # 先读取 flags
    text_flags = archive.read_i32()

    if DEBUG_PIN_PARSING:
        print(f"[DEBUG PIN] 12. DefaultTextValue: flags={text_flags}, start={dtv_start_pos:#x}")

    if text_flags == 0:
        # Phase 22 FIX-15: 尝试检测 FText 是否完全为空
        # 检查后续字节判断序列化模式
        peek_pos = archive.tell()
        next_val = archive.peek_i32() if hasattr(archive, 'peek_i32') else archive.read_i32()
        archive.seek(peek_pos)  # 回退

        if next_val == 0:
            # 可能是 history_type=0 但后续数据无效
            # 或者是空的序列化
            # 尝试读取完整 FText 格式：flags + 4bytes + history_type + bHasCulture
            archive.read_i32()  # 跳过中间 4 bytes
            text_history_type = archive.read_u8()

            if text_history_type == 255:  # None
                b_has_culture = archive.read_i32()
                if DEBUG_PIN_PARSING:
                    print(f"[DEBUG PIN] 12. DefaultTextValue: flags=0, middle=0, history=255, bHasCulture={b_has_culture}")
            else:
                # 其他 history_type，尝试跳过
                if DEBUG_PIN_PARSING:
                    print(f"[DEBUG PIN] 12. DefaultTextValue: flags=0, middle=0, history={text_history_type}")
                # 回退并跳过 9 bytes (flags + 4 + history_type)
                archive.seek(dtv_start_pos + 9)
        else:
            # next_val != 0，可能是 LinkedTo 开始
            # FText 只占 flags (4 bytes)
            if DEBUG_PIN_PARSING:
                print(f"[DEBUG PIN] 12. DefaultTextValue: flags=0 only, next={next_val:#x}")
    else:
        # flags != 0，正常 FText 序列化
        text_history_type = archive.read_u8()
        if text_history_type == 255 or text_history_type == -1:  # None
            b_has_culture_invariant = archive.read_i32()
            if b_has_culture_invariant != 0:
                archive.read_fstring()
        elif text_history_type == 0:  # Base
            archive.read_fstring()  # Namespace
            archive.read_fstring()  # Key
            archive.read_fstring()  # SourceString
        else:
            for _ in range(5):
                try:
                    archive.read_fstring()
                except Exception:
                    break

    if DEBUG_PIN_PARSING:
        print(f"[DEBUG PIN] 12. DefaultTextValue: done, offset now: {archive.tell():#x}")

    # 13. LinkedTo (SerializePinArray) [L1886]
    linkedto_start = archive.tell()
    try:
        linked_to = read_pin_array(archive, name_map, export_map, import_map)
        if DEBUG_PIN_PARSING:
            linkedto_bytes = archive.tell() - linkedto_start
            print(f"[DEBUG PIN] 13. LinkedTo: {len(linked_to)} pins, {linkedto_bytes} bytes, offset now: {archive.tell():#x}")
    except Exception as e:
        linked_to = []
        # Debug Session Phase 22 Fix: 回退到读取 array_count 之前的位置
        # read_pin_array 已经读取了 array_count（4 bytes），需要回退
        archive.seek(linkedto_start)
        # 读取并跳过 array_count
        array_count = archive.read_i32()
        if DEBUG_PIN_PARSING:
            print(f"[DEBUG PIN] 13. LinkedTo: ERROR ({e}), using empty list, skipped array_count={array_count}, offset now: {archive.tell():#x}")

    # 14. SubPins (SerializePinArray) [L1889]
    subpins_start = archive.tell()
    try:
        sub_pins = read_pin_array(archive, name_map, export_map, import_map)
        if DEBUG_PIN_PARSING:
            subpins_bytes = archive.tell() - subpins_start
            print(f"[DEBUG PIN] 14. SubPins: {len(sub_pins)} pins, {subpins_bytes} bytes, offset now: {archive.tell():#x}")
    except Exception as e:
        sub_pins = []
        # Debug Session Phase 22 Fix: 回退到读取 array_count 之前的位置
        # read_pin_array 已经读取了 array_count（4 bytes），需要回退
        archive.seek(subpins_start)
        # 读取并跳过 array_count
        array_count = archive.read_i32()
        if DEBUG_PIN_PARSING:
            print(f"[DEBUG PIN] 14. SubPins: ERROR ({e}), using empty list, skipped array_count={array_count}, offset now: {archive.tell():#x}")

    # 15. ParentPin (SerializePin) [L1891]
    parent_pin = read_pin_reference(archive, name_map, export_map, import_map)
    if DEBUG_PIN_PARSING:
        print(f"[DEBUG PIN] 15. ParentPin: {parent_pin}, offset now: {archive.tell():#x}")

    # 16. ReferencePassThroughConnection (SerializePin) [L1892]
    # 不在需求范围，仅读取用于位置同步
    ref_pass_through = read_pin_reference(archive, name_map, export_map, import_map)
    if DEBUG_PIN_PARSING:
        print(f"[DEBUG PIN] 16. ReferencePassThroughConnection: {ref_pass_through}, offset now: {archive.tell():#x}")

    # 17-18. EditorOnly fields [L1894-1948]
    hidden = False
    not_connectable = False
    advanced_view = False
    orphaned_pin = False

    # Phase 22-09 Task 3: 读取 PersistentGuid (16 bytes)
    # UE 5.x 编辑器保存的资产在 ReferencePassThrough 之后、BitField 之前
    # 序列化 PersistentGuid 字段（EditorOnly，仅用于位置同步）
    try:
        persistent_guid_bytes = archive.read_bytes(16)
        persistent_guid = persistent_guid_bytes.hex().upper()
        if DEBUG_PIN_PARSING:
            print(f"[DEBUG PIN] 17. PersistentGuid: {persistent_guid}, offset now: {archive.tell():#x}")
    except Exception as e:
        if DEBUG_PIN_PARSING:
            print(f"[DEBUG PIN] 17. PersistentGuid read failed: {e}")

    # 假设cooked资产跳过EditorOnly字段，尝试读取BitField
    # 对于UE5.7 editor保存的资产，可能存在BitField
    # 尝试读取，若有解析错误则保持默认值
    try:
        # 18. BitField (uint32) [L1902-1942]
        bitfield = archive.read_u32()
        hidden = bool(bitfield & (1 << 0))
        not_connectable = bool(bitfield & (1 << 1))
        advanced_view = bool(bitfield & (1 << 4))
        orphaned_pin = bool(bitfield & (1 << 5))
        if DEBUG_PIN_PARSING:
            print(f"[DEBUG PIN] 18. BitField: {bitfield:#010x}, hidden={hidden}, not_connectable={not_connectable}, offset now: {archive.tell():#x}")
    except Exception as e:
        # cooked资产可能没有BitField，保持默认值
        if DEBUG_PIN_PARSING:
            print(f"[DEBUG PIN] 18. BitField read failed: {e}, using defaults")

    pin_end_pos = archive.tell()
    if DEBUG_PIN_PARSING:
        total_bytes = pin_end_pos - pin_start_pos
        print(f"[DEBUG PIN] Pin parsing complete: {total_bytes} bytes total")
        print(f"[DEBUG PIN] Final offset: {pin_end_pos:#x}")
        print(f"[DEBUG PIN] ========================================")

    return UEdGraphPin(
        pin_id=pin_id,
        pin_name=pin_name,
        pin_tooltip=pin_tooltip,
        direction=direction,
        pin_type=pin_type,
        default_value=default_value,
        auto_default_value=autogenerated_default_value,
        default_object=default_object_index,
        default_text_value=default_text_value,
        linked_to_raw=linked_to,
        sub_pins=sub_pins,
        parent_pin=parent_pin,
        hidden=hidden,
        not_connectable=not_connectable,
        advanced_view=advanced_view,
        orphaned_pin=orphaned_pin,
        owning_node_index=owning_node_index,
        source_index=source_index,
        persistent_guid=persistent_guid
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

    node_name = node_export.object_name
    node_class = get_asset_class(node_export, import_map, export_map)

    if DEBUG_PIN_PARSING:
        print(f"[DEBUG NODE] ========================================")
        print(f"[DEBUG NODE] Node: {node_name}")
        print(f"[DEBUG NODE] Class: {node_class}")
        print(f"[DEBUG NODE] serial_offset: {node_export.serial_offset:#x}")
        print(f"[DEBUG NODE] serial_size: {node_export.serial_size}")
        print(f"[DEBUG NODE] script_serial_offset: {node_export.script_serial_offset:#x}")
        print(f"[DEBUG NODE] script_serial_size: {node_export.script_serial_size}")

    # Phase 28a FIX: 解析 script_serial 中的 tagged properties
    # UE 序列化顺序: Super::Serialize (tagged properties) → Pins
    # FunctionReference/EventReference 在 tagged properties 中
    # UE5: NodePosX/NodePosY/NodeGuid/NodeComment 也在 tagged properties 中
    function_reference: Optional[FMemberReference] = None
    event_reference: Optional[FMemberReference] = None
    node_pos_x: int = 0
    node_pos_y: int = 0
    node_guid: str = ""
    node_comment: str = ""
    raw_properties: Dict[str, Any] = {}  # 收集未知 PropertyTags（用于未知节点类型）

    if node_export.script_serial_size > 0:
        script_start = node_export.serial_offset + node_export.script_serial_offset
        script_end = script_start + node_export.script_serial_size
        archive.seek(script_start)

        # UE5 >= 1011: SerializationControlExtensions
        if summary.file_version_ue5 >= 1011:
            ctrl = archive.read_u8()
            if ctrl & 0x02:
                archive.read_u8()  # skip override_operation

        # Loop through PropertyTags
        while archive.tell() < script_end:
            tag = read_property_tag(archive, name_map, summary.legacy_file_version, summary.file_version_ue5)
            if tag.name == "None":
                break

            if tag.name == "FunctionReference" and tag.size > 0:
                # Phase 28a FIX: StructProperty(MemberReference) value 包含嵌套 PropertyTags
                # FMemberReference 是 USTRUCT，其 UPROPERTY 字段作为嵌套 PropertyTags 序列化
                # 参考: Engine/Classes/Engine/MemberReference.h
                value_start = archive.tell()
                value_end = value_start + tag.size

                # 解析嵌套 PropertyTags
                member_parent_idx = 0
                member_scope = ""
                member_name = ""
                member_guid = ""
                b_self_context = False

                while archive.tell() < value_end:
                    inner_tag = read_property_tag(archive, name_map, summary.legacy_file_version, summary.file_version_ue5)
                    if inner_tag.name == "None":
                        break

                    # 根据嵌套属性名读取值
                    if inner_tag.name == "MemberParent" and inner_tag.size > 0:
                        # ObjectProperty: PackageIndex (i32)
                        member_parent_idx = archive.read_i32()
                    elif inner_tag.name == "MemberScope" and inner_tag.size > 0:
                        # StrProperty: FString
                        member_scope = archive.read_fstring()
                    elif inner_tag.name == "MemberName":
                        # NameProperty: FName (8 bytes: index + number)
                        # Note: size may be 0 or 8, always read 8 bytes for FName
                        member_name = archive.read_name(name_map)
                    elif inner_tag.name == "MemberGuid" and inner_tag.size > 0:
                        # StructProperty(FGuid): 16 bytes
                        member_guid = archive.read_bytes(16).hex()
                    elif inner_tag.name == "bSelfContext":
                        # BoolProperty: UE5 stores value in tag.bool_val (flags), not as UBOOL
                        # If size > 0, read UBOOL; else use bool_val from flags
                        if inner_tag.size > 0:
                            b_self_context = archive.read_i32() != 0
                        else:
                            b_self_context = inner_tag.bool_val != 0
                    elif inner_tag.name == "bWasDeprecated":
                        # BoolProperty: same handling
                        if inner_tag.size > 0:
                            archive.read_i32()
                        # else: value stored in bool_val, skip (not needed)
                    elif inner_tag.size > 0:
                        # Unknown nested property: skip
                        archive.seek(archive.tell() + inner_tag.size)

                function_reference = FMemberReference(
                    member_parent=resolve_class_name(PackageIndex(member_parent_idx), import_map, export_map) if member_parent_idx != 0 else None,
                    member_name=member_name,
                    member_guid=member_guid,
                    b_self_context=b_self_context
                )
            elif tag.name == "EventReference" and tag.size > 0:
                # Phase 28a FIX: Same nested PropertyTags structure
                value_start = archive.tell()
                value_end = value_start + tag.size

                member_parent_idx = 0
                member_scope = ""
                member_name = ""
                member_guid = ""
                b_self_context = False

                while archive.tell() < value_end:
                    inner_tag = read_property_tag(archive, name_map, summary.legacy_file_version, summary.file_version_ue5)
                    if inner_tag.name == "None":
                        break

                    if inner_tag.name == "MemberParent" and inner_tag.size > 0:
                        member_parent_idx = archive.read_i32()
                    elif inner_tag.name == "MemberScope" and inner_tag.size > 0:
                        member_scope = archive.read_fstring()
                    elif inner_tag.name == "MemberName":
                        member_name = archive.read_name(name_map)
                    elif inner_tag.name == "MemberGuid" and inner_tag.size > 0:
                        member_guid = archive.read_bytes(16).hex()
                    elif inner_tag.name == "bSelfContext":
                        if inner_tag.size > 0:
                            b_self_context = archive.read_i32() != 0
                        else:
                            b_self_context = inner_tag.bool_val != 0
                    elif inner_tag.name == "bWasDeprecated":
                        if inner_tag.size > 0:
                            archive.read_i32()
                    elif inner_tag.size > 0:
                        archive.seek(archive.tell() + inner_tag.size)

                event_reference = FMemberReference(
                    member_parent=resolve_class_name(PackageIndex(member_parent_idx), import_map, export_map) if member_parent_idx != 0 else None,
                    member_name=member_name,
                    member_guid=member_guid,
                    b_self_context=b_self_context
                )
            # Phase 28a FIX: UE5 stores NodePosX/NodePosY/NodeGuid/NodeComment as PropertyTags
            elif tag.name == "NodePosX":
                node_pos_x = archive.read_i32()
            elif tag.name == "NodePosY":
                node_pos_y = archive.read_i32()
            elif tag.name == "NodeGuid" and tag.size > 0:
                # StructProperty(FGuid): 16 bytes
                node_guid = archive.read_bytes(16).hex()
            elif tag.name == "NodeComment" and tag.size > 0:
                # StrProperty: FString
                node_comment = archive.read_fstring()
            elif tag.size > 0:
                # 收集未知 PropertyTag（用于未知节点类型调试和未来扩展）
                value_start = archive.tell()
                raw_properties[tag.name] = {"size": tag.size, "offset": value_start}
                archive.seek(archive.tell() + tag.size)

    # Phase 22 FIX-11: 使用固定偏移量计算 pins_offset
    #
    # 根据 UE 源码分析和实际数据验证：
    # script_serial 包含 UObject::Serialize 数据（UPROPERTY 字段）
    # script_serial 之后有一个 int32 = 0（可能是结束标记）
    # Pins 数组在 script_serial + 4 bytes 之后开始
    #
    # 公式：pins_offset = script_serial_offset + script_serial_size
    # 然后跳过第一个 int32（结束标记）
    
    pins_offset = node_export.script_serial_offset + node_export.script_serial_size

    if DEBUG_PIN_PARSING:
        print(f"[DEBUG FIX-11] Using fixed pins_offset: {pins_offset:#x}")
        print(f"[DEBUG FIX-11] Formula: script_serial_offset({node_export.script_serial_offset:#x}) + "
              f"script_serial_size({node_export.script_serial_size})")

    archive.seek(node_export.serial_offset + pins_offset)

    # 跳过第一个 int32（结束标记）
    _end_marker = archive.read_i32()
    # 1. Pins 数组
    pins_count = archive.read_i32()
    if DEBUG_PIN_PARSING:
        print(f"[DEBUG NODE] Reading pins_count: {pins_count} at offset {archive.tell():#x}")

    if pins_count < 0:
        raise ParseError(
            f"Invalid pins_count {pins_count} (negative) at node {node_name}"
        )
    if pins_count > MAX_PINS_PER_NODE:
        raise ParseError(
            f"pins_count {pins_count} exceeds MAX_PINS_PER_NODE {MAX_PINS_PER_NODE} "
            f"at node {node_name}"
        )

    pins: List[UEdGraphPin] = []
    for i in range(pins_count):
        if DEBUG_PIN_PARSING:
            print(f"[DEBUG NODE] Reading pin #{i} at offset {archive.tell():#x}")

        # Phase 22 FIX-01: 处理 SerializePin 前置字段
        # SerializePin 先序列化: bNullPtr + OwningNode + PinGuid
        # 然后 UEdGraphPin::Serialize 再次序列化 OwningNode + PinId + ...
        b_null_ptr = archive.read_i32()  # bool 序列化为 i32
        if DEBUG_PIN_PARSING:
            print(f"[DEBUG NODE]   bNullPtr: {b_null_ptr}")

        if b_null_ptr != 0:
            # null pin，跳过 OwningNode_1 + PinGuid_1（20字节）
            archive.read_i32()  # OwningNode_1（4字节）
            archive.read_bytes(16)  # PinGuid_1（16字节）
            if DEBUG_PIN_PARSING:
                print(f"[DEBUG NODE]   Skipping null pin (20 bytes)")
            continue

        # SerializePin 前置字段：OwningNode_1 + PinGuid_1（跳过）
        _owning_node_1 = archive.read_i32()  # OwningNode（SerializePin 部分）
        _pin_guid_1 = archive.read_bytes(16)  # PinGuid（SerializePin 部分）
        if DEBUG_PIN_PARSING:
            print(f"[DEBUG NODE]   OwningNode_1: {_owning_node_1}, PinGuid_1: {_pin_guid_1.hex()}")

        # 然后调用 read_ue_graph_pin 读取 UEdGraphPin::Serialize 部分
        try:
            pin = read_ue_graph_pin(archive, name_map, summary, export_map, import_map)
            pins.append(pin)
        except Exception as e:
            # Phase 22 DEBUG: 记录 Pin 读取失败
            DEBUG_PIN_ERRORS = False  # 设为 True 启用错误日志
            if DEBUG_PIN_ERRORS:
                import traceback
                print(f"DEBUG PIN ERROR: Node {node_export.object_name}, Pin #{len(pins)}: {e}")
                print(f"  Position: {archive.tell()}")
                print(traceback.format_exc())
            # 读取失败，跳过此 pin
            continue

    if DEBUG_PIN_PARSING:
        print(f"[DEBUG NODE] Successfully read {len(pins)}/{pins_count} pins")
        print(f"[DEBUG NODE] ========================================")

    # 2-5. NodePos/NodeGuid/NodeComment
    # Phase 28a FIX: UE5 stores these as PropertyTags in script_serial
    # UE4: read as raw data after pins
    # UE5: skip raw data read if already extracted from PropertyTags
    if node_guid == "":
        # UE4 format: read as raw data
        node_pos_x = archive.read_i32()
        node_pos_y = archive.read_i32()
        node_guid_bytes = archive.read_bytes(16)
        node_guid = node_guid_bytes.hex()
        node_comment = archive.read_fstring()
    # else: UE5 format - values already extracted from PropertyTags

    if DEBUG_PIN_PARSING:
        print(f"[DEBUG NODE] After NodeComment: pos={archive.tell():#x}")
        print(f"[DEBUG NODE] NodeComment value: '{node_comment}'")

    # 类型识别（D-02b）
    class_name = resolve_class_name(node_export.class_index, import_map, export_map)
    if class_name is None:
        class_name = ""

    if DEBUG_PIN_PARSING:
        print(f"[DEBUG NODE] Before type dispatch: pos={archive.tell():#x}, class={class_name}")

    # 类型分派（D-02b, GRAPH-05~09）
    # Per RESEARCH.md L260-316: match/case 类型分派
    node_data: Any = None
    match class_name:
        case "K2Node_CallFunction":
            # Phase 28a FIX: Use extracted FunctionReference from script_serial
            node_data = K2NodeCallFunction(
                function_reference=function_reference or FMemberReference(),
                b_defaults_to_pure=False
            )
        case "K2Node_Event":
            # Phase 28a FIX: Use extracted EventReference from script_serial
            node_data = K2NodeEvent(
                event_reference=event_reference or FMemberReference(),
                b_override_function=False
            )
        case "K2Node_Knot":
            node_data = read_k2node_knot(archive)
        case "EdGraphNode_Comment":
            node_data = read_edgraph_node_comment(archive)
        case "K2Node_EnhancedInputAction":
            node_data = read_k2node_enhanced_input(archive, name_map)
        case _:
            # D-02a: 未知类型 — 记录类型名和原始 PropertyTag 数据
            node_data = {"unknown_type": class_name}
            if raw_properties:
                node_data["_raw_properties"] = raw_properties

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

    序列化顺序（基于 UE 源码 MemberReference.h L74-95）：
    1. MemberParent (TObjectPtr<UObject> -> FPackageIndex i32)
    2. MemberScope (FString) - 局部变量作用域名称
    3. MemberName (FName)
    4. MemberGuid (FGuid 16 bytes)
    5. bSelfContext (bool)
    6. bWasDeprecated (bool)

    Args:
        archive: FArchive positioned at FMemberReference
        name_map: NameMap for FName resolution
        import_map: 导入表（用于 FPackageIndex 解析）
        export_map: 导出表（用于 FPackageIndex 解析）

    Returns:
        FMemberReference 实例
    """
    start_pos = archive.tell()

    # 1. MemberParent (FPackageIndex)
    member_parent_index = archive.read_i32()
    member_parent: Optional[str] = None
    if member_parent_index != 0:
        member_parent = resolve_class_name(
            PackageIndex(member_parent_index), import_map, export_map
        )

    # 2. MemberScope (FString) - Phase 22-09 FIX: 漏掉此字段导致位置错位
    member_scope = archive.read_fstring()

    # 3. MemberName (FName)
    member_name = archive.read_name(name_map)

    # 4. MemberGuid (FGuid 16 bytes)
    member_guid_bytes = archive.read_bytes(16)
    member_guid = member_guid_bytes.hex()

    # 5. bSelfContext (bool)
    b_self_context = archive.read_bool()

    # 6. bWasDeprecated (bool) - Phase 22-09 FIX: 漏掉此字段
    b_was_deprecated = archive.read_bool()

    if DEBUG_PIN_PARSING:
        print(f"[DEBUG FMEMBER] start_pos={start_pos:#x}")
        print(f"[DEBUG FMEMBER] member_parent_index={member_parent_index} -> {member_parent}")
        print(f"[DEBUG FMEMBER] member_scope='{member_scope}'")
        print(f"[DEBUG FMEMBER] member_name='{member_name}'")
        print(f"[DEBUG FMEMBER] member_guid={member_guid}")
        print(f"[DEBUG FMEMBER] b_self_context={b_self_context}")
        print(f"[DEBUG FMEMBER] b_was_deprecated={b_was_deprecated}")
        print(f"[DEBUG FMEMBER] end_pos={archive.tell():#x}")

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
    b_defaults_to_pure = archive.read_bool()

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
    b_override_function = archive.read_bool()

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
    graph_class: str,
    graph_export_idx: int = 0
) -> UEdGraph:
    """
    读取 UEdGraph（GRAPH-02/03）。

    序列化顺序（基于 UE 源码 EdGraph.cpp）：
    1. Schema (FPackageIndex -> resolve)
    2. Nodes 数组 (int32 count + FPackageIndex[])
       — 需从 FPackageIndex 找到对应导出并调用 read_ue_graph_node
    3. GraphGuid (FGuid 16 bytes)
    4. bEditable (uint8)

    **当 nodes_count = 0 时**（UE 5.x 新格式）：
    节点通过 outer_index 关联到图，需要遍历 export_map 收集。

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
        graph_export_idx: 图在 export_map 中的索引（1-based）

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
    failed_nodes: List[str] = []  # Phase 22 FIX-03: 记录失败节点名称

    # Nodes 是导出索引数组（FPackageIndex > 0）
    for _ in range(nodes_count):
        node_index = archive.read_i32()  # FPackageIndex
        if node_index > 0 and node_index <= len(export_map):
            node_export = export_map[node_index - 1]
            try:
                node = read_ue_graph_node(
                    archive, name_map, summary,
                    export_map, import_map, node_export
                )
                nodes.append(node)
            except ParseError as e:
                # Phase 22 FIX-03: 记录失败节点名称，便于调试
                failed_nodes.append(node_export.object_name)
                # 节点解析失败时跳过，继续处理其他节点
                pass

    # Phase 22 FIX-03: 调试模式下输出失败节点信息
    if failed_nodes and "--debug-graph" in sys.argv:
        print(f"DEBUG: Failed nodes ({len(failed_nodes)}): {failed_nodes}")

    # 当 nodes_count = 0 时，通过 outer_index 收集节点（UE 5.x 新格式）
    if nodes_count == 0 and graph_export_idx > 0:
        for node_export in export_map:
            # 节点的 outer_index 应指向该图（export_idx 是 1-based）
            if node_export.outer_index.index == graph_export_idx:
                # 检查是否是节点类型（K2Node 或 EdGraphNode）
                node_class = get_asset_class(node_export, import_map, export_map)
                if node_class and (node_class.startswith("K2Node") or node_class.startswith("EdGraphNode") or "Node" in node_class):
                    try:
                        node = read_ue_graph_node(
                            archive, name_map, summary,
                            export_map, import_map, node_export
                        )
                        nodes.append(node)
                    except ParseError:
                        # 节点解析失败时创建基本节点信息
                        nodes.append(UEdGraphNode(
                            node_guid="",
                            node_pos_x=0,
                            node_pos_y=0,
                            node_comment="",
                            pins=[],
                            class_name=node_class or "",
                            node_data={"node_name": node_export.object_name}
                        ))

    # 3. GraphGuid
    graph_guid_bytes = archive.read_bytes(16)
    graph_guid = graph_guid_bytes.hex()

    # 4. bEditable
    b_editable = archive.read_bool()

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


# ============================================================================
# Phase 12: PropertyFlags parsing (per D-03)
# ============================================================================

# EPropertyFlags constants from ObjectMacros.h L415-480
CPF_Edit = 0x0000000000000001               # EditAnywhere/EditConst
CPF_BlueprintVisible = 0x0000000000000004   # BlueprintReadWrite/BlueprintReadOnly
CPF_BlueprintReadOnly = 0x0000000000000010  # Determines read vs write
CPF_Transient = 0x0000000000002000          # Transient
CPF_EditConst = 0x0000000000020000          # EditConst
CPF_InstancedReference = 0x0000000000080000 # Component reference (per D-02)
CPF_Config = 0x0000000000004000             # Config
CPF_SaveGame = 0x0000000001000000           # SaveGame
CPF_Deprecated = 0x0000000020000000         # Deprecated
CPF_Protected = 0x0000080000000000          # Protected
CPF_AdvancedDisplay = 0x0000040000000000    # AdvancedDisplay
CPF_ExposeOnSpawn = 0x0001000000000000      # ExposeOnSpawn

# Phase 26: Additional property flags
CPF_EditAnywhere = 0x02000000               # EditAnywhere
CPF_EditInstanceOnly = 0x04000000           # EditInstanceOnly
CPF_BlueprintReadWrite = 0x00000100         # BlueprintReadWrite
CPF_DuplicateTransient = 0x00008000         # DuplicateTransient
CPF_NoClear = 0x00080000                    # NoClear
CPF_ReferenceOnly = 0x00100000              # ReferenceOnly
CPF_BlueprintAssignable = 0x80000000        # BlueprintAssignable
CPF_BlueprintCallable = 0x00004000          # BlueprintCallable
CPF_RepNotify = 0x10000000                  # RepNotify
CPF_Interp = 0x20000000                    # Interp
CPF_Net = 0x00000020                       # Net
CPF_Replicated = 0x00100000                 # Replicated
CPF_NonPIEDuplicateTransient = 0x00800000  # NonPIEDuplicateTransient


# Function Flags (Phase 26: META-02)
FUNC_None                = 0x00000000
FUNC_Final               = 0x00000001
FUNC_RequiredAPI          = 0x00000002
FUNC_BlueprintAuthorityOnly = 0x00000004
FUNC_BlueprintCosmetic    = 0x00000008
FUNC_Net                 = 0x00000040
FUNC_NetReliable         = 0x00000080
FUNC_NetRequest           = 0x00000100
FUNC_Exec                = 0x00000200
FUNC_Native              = 0x00000400
FUNC_Event               = 0x00000800
FUNC_NetResponse         = 0x00001000
FUNC_Static              = 0x00002000
FUNC_NetMulticast        = 0x00004000
FUNC_UbergraphFunction   = 0x00008000
FUNC_MulticastDelegate   = 0x00010000
FUNC_Public              = 0x00020000
FUNC_Private             = 0x00040000
FUNC_Protected           = 0x00080000
FUNC_Delegate            = 0x00100000
FUNC_NetServer           = 0x00200000
FUNC_HasOutParms         = 0x00400000
FUNC_HasDefaults         = 0x00800000
FUNC_NetClient           = 0x01000000
FUNC_DLLImport            = 0x02000000
FUNC_BlueprintCallable   = 0x04000000
FUNC_BlueprintEvent      = 0x08000000
FUNC_BlueprintPure       = 0x10000000
FUNC_EditorOnly          = 0x20000000
FUNC_Const               = 0x40000000
FUNC_NetValidate         = 0x80000000


def parse_property_flags_to_labels(flags: int) -> List[str]:
    """
    Parse EPropertyFlags uint64 to readable label list (Phase 12, per D-03).

    From ObjectMacros.h L415-480. Key flags for blueprint variables:
    - CPF_Edit: Edit visibility
    - CPF_BlueprintVisible: Blueprint access
    - CPF_InstancedReference: Component reference (per D-02)

    Args:
        flags: uint64 EPropertyFlags value

    Returns:
        List of readable flag labels (sorted by importance)
    """
    labels = []

    # Edit flags (mutually exclusive patterns)
    if flags & CPF_Edit:
        if flags & CPF_EditConst:
            labels.append("EditConst")
        else:
            labels.append("EditAnywhere")

    # Blueprint visibility flags (mutually exclusive)
    if flags & CPF_BlueprintVisible:
        if flags & CPF_BlueprintReadOnly:
            labels.append("BlueprintReadOnly")
        else:
            labels.append("BlueprintReadWrite")

    # Component reference flag (per D-02)
    if flags & CPF_InstancedReference:
        labels.append("InstancedReference")

    # Other flags
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
    if flags & CPF_AdvancedDisplay:
        labels.append("AdvancedDisplay")

    return labels


def format_variable_type(pin_type: FEdGraphPinType, name_map: List[str] = None) -> str:
    """
    Format FEdGraphPinType to complete type string (Phase 12, per D-04).

    Handles:
    - Basic types (bool, int, float, string, etc.)
    - Container types (TArray, TSet, TMap)
    - Reference types (adds '*' suffix)
    - Const types (adds 'const' prefix)

    Args:
        pin_type: FEdGraphPinType structure
        name_map: Optional NameMap for resolving pin_sub_category_object

    Returns:
        Complete type string (e.g., "TArray<UObject*>", "const float")
    """
    # Container type prefix
    container_prefix = ""
    if pin_type.container_type == 1:  # Array
        container_prefix = "TArray<"
    elif pin_type.container_type == 2:  # Set
        container_prefix = "TSet<"
    elif pin_type.container_type == 3:  # Map
        container_prefix = "TMap<"  # Simplified - needs key/value info

    # Base type from PinCategory
    category = pin_type.pin_category.lower()
    sub_category = pin_type.pin_sub_category.lower()

    # Type mapping
    type_str = ""
    if category in ("bool", "boolean"):
        type_str = "bool"
    elif category in ("int", "integer"):
        type_str = "int"
    elif category in ("float", "real", "double"):
        type_str = "float"
    elif category in ("string", "str"):
        type_str = "FString"
    elif category in ("name"):
        type_str = "FName"
    elif category in ("text"):
        type_str = "FText"
    elif category in ("object", "class", "interface"):
        # Try to resolve pin_sub_category_object to class name
        if pin_type.pin_sub_category_object != 0 and name_map:
            # FPackageIndex resolution would require ImportMap/ExportMap
            # For Phase 12, use sub_category if available
            if sub_category and sub_category != "none":
                type_str = sub_category
            else:
                type_str = "UObject"
        else:
            type_str = "UObject"
        # Add reference pointer for object types
        if not pin_type.is_weak_pointer:
            type_str += "*"
    elif sub_category and sub_category != "none":
        # Use sub_category as type name (more specific)
        type_str = sub_category
        # Check if it's a reference type
        if category in ("object", "class") or "object" in category:
            type_str += "*"
    else:
        # Fallback to category name
        type_str = category

    # Container suffix
    container_suffix = ""
    if container_prefix:
        container_suffix = ">"

    # Const prefix
    const_prefix = ""
    if pin_type.is_const:
        const_prefix = "const "

    return f"{const_prefix}{container_prefix}{type_str}{container_suffix}"


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

    # MetaDataArray count + entries - Phase 12: store metadata (per D-03)
    meta_count = archive.read_i32()
    var.metadata = {}
    for _ in range(meta_count):
        key = archive.read_name(name_map)  # DataKey
        value = archive.read_fstring()       # DataValue
        if key:  # Avoid None key
            var.metadata[key] = value

    # Phase 12: Parse PropertyFlags to readable labels (per D-03)
    var.flags_labels = parse_property_flags_to_labels(var.property_flags)

    # Phase 26: Parse property flags to boolean fields
    flags = archive._parse_property_flags(var.property_flags)
    var.is_edit_anywhere = flags['is_edit_anywhere']
    var.is_edit_instance_only = flags['is_edit_instance_only']
    var.is_blueprint_read_only = flags['is_blueprint_read_only']
    var.is_blueprint_readable = flags['is_blueprint_readable']
    var.is_blueprint_writable = flags['is_blueprint_writable']
    var.is_transient = flags['is_transient']
    var.is_duplicate_transient = flags['is_duplicate_transient']
    var.is_save_game = flags['is_save_game']
    var.is_no_clear = flags['is_no_clear']
    var.is_reference_only = flags['is_reference_only']
    var.is_blueprint_assignable = flags['is_blueprint_assignable']
    var.is_blueprint_callable = flags['is_blueprint_callable']
    var.is_rep_notify = flags['is_rep_notify']
    var.is_interp = flags['is_interp']
    var.is_expose_on_spawn = flags['is_expose_on_spawn']
    var.is_net = flags['is_net']
    var.is_replicated = flags['is_replicated']
    var.is_non_pi_ed_duplicate_transient = flags['is_non_pi_ed_duplicate_transient']

    # Phase 26: Extract metadata fields
    var.edit_condition = var.metadata.get('EditCondition', '')
    var.meta_class = var.metadata.get('MetaClass', '')
    var.edit_category = var.metadata.get('Category', '')
    var.edit_widget = var.metadata.get('EditWidget', '')

    # Phase 26: Copy metadata to meta_data field (备用字段)
    var.meta_data = var.metadata.copy()

    # DefaultValue (FString) - parse per D-13/D-14/D-15
    default_str = archive.read_fstring()
    var.default_value = parse_default_value(default_str, var.var_type)

    # Phase 12: Component variable identification (per D-02)
    # Dual verification: type name contains "Component" OR CPF_InstancedReference flag
    type_str = ""
    if var.var_type:
        # Prefer pin_sub_category for more specific type
        if var.var_type.pin_sub_category and var.var_type.pin_sub_category.lower() != "none":
            type_str = var.var_type.pin_sub_category
        elif var.var_type.pin_category:
            type_str = var.var_type.pin_category

    # Check type name contains "Component"
    is_component_by_name = isinstance(type_str, str) and "Component" in type_str

    # Check CPF_InstancedReference flag (0x0000000000080000)
    is_component_by_flag = (var.property_flags & CPF_InstancedReference) != 0

    # Dual verification: either condition satisfies
    var.is_component = is_component_by_flag or is_component_by_name

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

    # Special case: "None" PropertyTag only has Name, no TypeName/Size/Flags
    # Reference: PropertyTag.cpp - when Name == "None", serialization ends
    if tag.name == "None":
        return tag

    if use_complete_type_name(legacy_version, ue5_version):
        # UE5 新格式（PropertyTag.cpp lines 436-545）
        # Phase 28a FIX: TypeName 使用 FPropertyTypeName 格式
        # 格式: FPropertyTypeNameNode[] - 每个: FName(8) + InnerCount(4)
        # 参考: PropertyTypeName.cpp line 41-50

        # Read FPropertyTypeName nodes
        type_parts: List[Tuple[str, int]] = []
        pending = 1
        while pending > 0 and len(type_parts) < 20:  # Safety limit
            node_name = archive.read_name(name_map)
            inner_count = archive.read_i32()
            type_parts.append((node_name, inner_count))
            pending = pending - 1 + inner_count

        # Build type string: just use the first node name (root type)
        # e.g., "StructProperty(MemberReference)" -> just use "StructProperty"
        # Full type parsing would require more complex handling
        if type_parts:
            tag.type = type_parts[0][0]
        tag.size = archive.read_i32()
        archive.validate_size(tag.size, tag.name)  # D-11: validate PropertyTag.Size
        tag.flags = archive.read_u8()

        # 条件字段（基于标志位）
        if tag.flags & PROP_TAG_HAS_ARRAY_INDEX:
            tag.array_index = archive.read_i32()

        if tag.flags & PROP_TAG_HAS_PROPERTY_GUID:
            tag.property_guid = archive.read(16)

        # D-03: PropertyTag Extensions 处理
        # 参考: PropertyTag.cpp 第 155-173 行、第 541-544 行
        if tag.flags & PROP_TAG_HAS_EXTENSIONS:
            # EPropertyTagExtension (u8)
            property_extensions = archive.read_u8()

            # OverridableInformation 标志 (0x02) 触发额外字段
            if property_extensions & 0x02:
                # EOverriddenPropertyOperation (u8)
                tag.override_operation = archive.read_u8()
                # bExperimentalOverridableLogic — 根据研究暂按 u8 处理
                tag.experimental_overridable_logic = archive.read_u8()

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
    # D-01: UE 5.10+ ScriptSerializationStartOffset 是相对偏移
    # 参考: ObjectResource.h 第 280-285 行注释
    # "The location (relative to SerialOffset) of the beginning of the
    #  portion of this export's data that is serialized using tagged property serialization."
    if summary.file_version_ue5 >= UE5_SCRIPT_SERIALIZATION_OFFSET:
        property_start = export.serial_offset + export.script_serial_offset
    else:
        property_start = export.serial_offset
    archive.seek(property_start)

    # D-02: SerializationControlExtensions 头部处理
    # 参考: Class.cpp 第 1627-1654 行
    # 当 UE5 >= PROPERTY_TAG_EXTENSION (1011) 时，属性数据前有额外头部
    if summary.file_version_ue5 >= UE5_PROPERTY_TAG_EXTENSION:
        # EClassSerializationControlExtension (u8)
        serialization_control = archive.read_u8()

        # OverridableSerializationInformation 标志 (0x02)
        if serialization_control & 0x02:
            # EOverriddenPropertyOperation (u8) — 仅读取用于位置同步
            overridden_operation = archive.read_u8()
            # 注意：具体语义不解析，仅跳过字节

    # 计算属性数据边界
    # ScriptSerializationStartOffset 和 EndOffset 都是相对于 SerialOffset
    # 参考: ObjectResource.h 第 280-295 行
    if summary.file_version_ue5 >= UE5_SCRIPT_SERIALIZATION_OFFSET:
        property_end = export.serial_offset + export.script_serial_size  # EndOffset 也是相对于 SerialOffset
    else:
        property_end = export.serial_offset + export.serial_size  # 无 EndOffset，使用 serial_size

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
            # 边界检查：当前位置不应超过属性数据范围
            current_pos = archive.tell()
            if current_pos >= property_end:
                # 属性数据已耗尽，中断解析
                break

            tag = read_property_tag(
                archive,
                name_map,
                summary.legacy_file_version,
                summary.file_version_ue5
            )

            # 终止标记：Name == "None"
            if tag.name == "None":
                break

            # 边界检查：PropertyTag.Size 不应超过剩余属性数据范围
            if summary.file_version_ue5 >= UE5_SCRIPT_SERIALIZATION_OFFSET:
                remaining_property_data = property_end - archive.tell()
                if tag.size > remaining_property_data:
                    # Size 超出属性数据范围，可能数据格式变化
                    raise ParseError(
                        f"Property Size {tag.size} exceeds remaining property data {remaining_property_data} bytes"
                    )

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

                # Phase 13-02: 提取组件变换属性
                if export.properties:
                    export.transforms = extract_component_transforms(export.properties)

        result.is_success = True

        # Blueprint extraction (Phase 3)
        # Per D-02: auto-detect and extract on every parse
        # Per D-03: add warnings to errors list if detection fails
        # Phase 12: prefer BlueprintGeneratedClass for variables (per D-01)

        blueprint_metadata = None

        # Phase 12: First try BlueprintGeneratedClass (per D-01)
        # Extract asset name from name_map or summary
        asset_name = None
        if result.name_map:
            # First name is typically the asset name
            asset_name = result.name_map[0] if result.name_map else None

        if asset_name:
            main_bpgc = find_main_blueprint_generated_class(
                result.export_map,
                result.import_map,
                asset_name
            )
            if main_bpgc:
                # Create temporary archive for extraction
                temp_archive = FArchive(path)
                temp_archive.set_byte_swapping(archive._byte_swapping)

                try:
                    meta, warn = extract_blueprint_metadata(
                        main_bpgc,
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
                    result.errors.append(f"blueprint extraction error (BPGC): {e}")
                finally:
                    temp_archive.close()

        # Fall back to UBlueprint detection if BPGC not found
        if not blueprint_metadata:
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

# D-19-10: 执行流起点类型扩展（LINK-02）
START_EVENT_TYPES = frozenset({
    "K2Node_Event",
    "K2Node_EnhancedInputAction",
    "K2Node_VariableSet",
    "K2Node_CustomEvent"
})

# Phase 22-09: 有效 PinName 列表（用于 pins_offset 扫描验证）
# 排除常见的 UObject 属性名（BlueprintGuid, BlueprintType 等）
VALID_PIN_NAMES = frozenset({
    # Exec pins
    "execute", "then", "OutputDelegate", "InputDelegate",
    # Common self/WorldContext pins
    "self", "WorldContext", "Target",
    # Common data pins
    "ReturnValue", "Result", "Value", "Input", "Output",
    # ActionValue pins (EnhancedInputAction)
    "ActionValue", "ActionValue_X", "ActionValue_Y", "ActionValue_Z",
    # Trigger timing pins (EnhancedInputAction)
    "Triggered", "Started", "Completed", "Canceled", "Ongoing",
    # Common parameter names
    "A", "B", "X", "Y", "Z", "Right", "Forward", "Left", "Backward",
    "Yaw", "Pitch", "Roll",
    "Index", "Key", "Element", "Item", "Object", "Actor", "Component",
    "Class", "Name", "Type", "Tag", "Id", "GUID",
    # Event pins
    "Entry", "Exit", "Condition", "True", "False",
    # Common variants
    "InputPin", "OutputPin", "Input0", "Output0",
})

# D-19-14: 控制流节点分支类型映射（LINK-02）
BRANCH_TYPE_MAP = {
    "K2Node_IfThenElse": "if_then_else",
    "K2Node_Switch": "switch",
    "K2Node_SwitchString": "switch_string",
    "K2Node_SwitchEnum": "switch_enum",
    "K2Node_SwitchInteger": "switch_integer",
    "K2Node_MacroInstance": "macro_instance",
}


# ============================================================================
# Phase 19: LINK-01 - 连接输出格式化
# ============================================================================

# D-19-03: 连接输出格式全局可选配置
FORMAT_CONFIG = {
    "pin_reference_mode": "name",  # D-19-04: 默认 name 模式
}


def _derive_node_name(node: UEdGraphNode, idx: int) -> str:
    """
    从节点派生用户友好的节点名（D-19-02）。

    策略：使用 f"{class_name}_{idx}" 格式，避免同名节点冲突。

    Args:
        node: UEdGraphNode 节点对象
        idx: 节点在图中的索引（用于区分同名节点）

    Returns:
        str: 用户友好的节点名
    """
    # 使用 class_name + idx 后缀，避免冲突
    return f"{node.class_name}_{idx}"


def format_pin_ref(
    node_guid: str,
    pin_name: str,
    node_name_lookup: Dict[str, str],
    mode: str = "name"
) -> Dict:
    """
    格式化 Pin 引用（D-19-02, D-19-05）。

    Args:
        node_guid: 节点 GUID
        pin_name: Pin 名称
        node_name_lookup: node_guid → node_name 查找表
        mode: "name" 或 "guid" 模式（默认 name）

    Returns:
        Dict: 格式化后的 Pin 引用对象
        - name 模式: {"node": "K2Node_CallFunction_10", "pin": "execute"}
        - guid 模式: {"node_guid": "...", "pin_name": "execute"}

    查找失败时（D-19-05）：
        返回 {"node_guid": ..., "pin": ..., "warning": "node_name lookup failed"}
    """
    if mode == "name":
        # D-19-02: 使用 pin_name 格式
        if node_guid in node_name_lookup:
            return {
                "node": node_name_lookup[node_guid],
                "pin": pin_name
            }
        else:
            # D-19-05: 查找失败 fallback
            return {
                "node_guid": node_guid,  # fallback 原始 guid
                "pin": pin_name,
                "warning": "node_name lookup failed"
            }
    else:
        # guid 模式：保留原始格式
        return {
            "node_guid": node_guid,
            "pin_name": pin_name
        }


def build_connections_map(graph: UEdGraph) -> Tuple[List[Dict], List[str]]:
    """
    构建引脚连接映射（D-08-01~06, LINK-01, D-19-01~05）。

    将 linked_to_raw（PinId GUID hex）转换为用户友好的节点引用格式。
    默认使用 name 模式（D-19-04），可选 guid 模式（兼容性）。

    算法：
    1. 构建 node_guid → node_name 查找表（D-19-02）
    2. 构建 PinId → (node_guid, pin_name) 查找表
    3. 遍历所有 Output pins (direction=1)
    4. 对每个 linked_to_raw 中的 PinId，查找目标 pin
    5. 使用 format_pin_ref 转换格式（D-19-02）
    6. 处理查找失败（warning + 原始数据）

    Args:
        graph: UEdGraph 对象

    Returns:
        Tuple[List[Dict], List[str]]: (connections 列表, warnings 列表)
    """
    # Step 1a: Build node_name_lookup for name mode (D-19-02)
    node_name_lookup: Dict[str, str] = {}
    for idx, node in enumerate(graph.nodes):
        node_name_lookup[node.node_guid] = _derive_node_name(node, idx)

    # Step 1b: Build pin_lookup: pin_id → (node_guid, pin_name)
    pin_lookup: Dict[str, Tuple[str, str]] = {}
    for node in graph.nodes:
        for pin in node.pins:
            pin_lookup[pin.pin_id] = (node.node_guid, pin.pin_name)

    # Step 2-4: Build connections (支持 name 模式)
    mode = FORMAT_CONFIG["pin_reference_mode"]  # D-19-04
    connections: List[Dict] = []
    warnings: List[str] = []

    for node in graph.nodes:
        for pin in node.pins:
            if pin.direction == 1:  # EGPD_Output
                for linked_pin_ref in pin.linked_to_raw:
                    # Phase 18: linked_to_raw 为 dict 格式 {"pin_guid": str}
                    # 需提取 pin_guid 字段
                    target_pin_guid = linked_pin_ref.get("pin_guid") if isinstance(linked_pin_ref, dict) else linked_pin_ref

                    if target_pin_guid in pin_lookup:
                        target_node_guid, target_pin_name = pin_lookup[target_pin_guid]
                        # 使用 format_pin_ref 转换格式（D-19-02）
                        connections.append({
                            "from": format_pin_ref(node.node_guid, pin.pin_name, node_name_lookup, mode),
                            "to": format_pin_ref(target_node_guid, target_pin_name, node_name_lookup, mode)
                        })
                    else:
                        # D-08-04/D-19-05: Warning + raw data
                        warnings.append(f"PinId {target_pin_guid} not found in graph")
                        connections.append({
                            "from": format_pin_ref(node.node_guid, pin.pin_name, node_name_lookup, mode),
                            "to": {"raw_pin_id": target_pin_guid},
                            "warning": "target pin not found"
                        })

    return connections, warnings


# ============================================================================
# Phase 20: OUT-01 - 节点输出格式化
# ============================================================================

# D-20-07: Graph类型语义化映射
GRAPH_TYPE_MAP = {
    "EdGraph": "event",
    "UberEdGraph": "uber",
}


def format_node_dict(node: UEdGraphNode, idx: int) -> Dict:
    """
    格式化单个节点为 OUT-01 规范 JSON 结构。

    Per D-20-01: node_name 使用 _derive_node_name() 派生
    Per D-20-02: 字段名规范化（node_type, position:{x,y})
    Per D-20-03: function_reference/event_reference 提升到顶层

    Args:
        node: UEdGraphNode 节点对象
        idx: 节点在图中的索引

    Returns:
        Dict: OUT-01 规范节点结构
    """
    from dataclasses import asdict

    # D-20-01: 派生 node_name
    node_name = _derive_node_name(node, idx)

    # D-20-02: 字段名规范化
    result = {
        "node_name": node_name,
        "node_type": node.class_name,
        "node_guid": node.node_guid,
        "position": {"x": node.node_pos_x, "y": node.node_pos_y},
        "node_comment": node.node_comment,
        "pins": [asdict(pin) for pin in node.pins]  # Pin格式保持Phase 18规范
    }

    # D-20-03: 嵌套结构展开
    if node.node_data is not None:
        if isinstance(node.node_data, K2NodeCallFunction):
            # CallFunction: 提取 function_reference 到顶层
            fr = node.node_data.function_reference
            result["function_reference"] = {
                "member_name": fr.member_name,
                "member_parent": fr.member_parent,
                "self_context": fr.b_self_context
            }
        elif isinstance(node.node_data, K2NodeEvent):
            # Event: 提取 event_reference 到顶层
            er = node.node_data.event_reference
            result["event_reference"] = {
                "member_name": er.member_name,
                "member_parent": er.member_parent,
                "member_guid": er.member_guid
            }
        elif isinstance(node.node_data, K2NodeKnot):
            # Knot节点无额外顶层字段
            pass
        elif isinstance(node.node_data, dict):
            # 普通字典（如 fallback 节点）直接使用
            result["node_data"] = node.node_data
        elif hasattr(node.node_data, '__dataclass_fields__'):
            # Dataclass 实例
            result["node_data"] = asdict(node.node_data)
        else:
            # 其他类型：尝试转换为字典
            result["node_data"] = {"raw": str(node.node_data)}

    return result


def format_graphs_json(graphs: List[UEdGraph]) -> List[Dict]:
    """
    格式化蓝图图数据为 JSON 输出（GRAPH-11, GRAPH-12, OUT-02）。

    Per D-08-03: connections 放在 graph 层级
    Per D-08-09: execution_flows 数组
    Per D-19-09: data_flows 数组（LINK-03）
    Per D-20-07: graph_type 语义化映射（EdGraph→event, UberEdGraph→uber）
    Per OUT-01: nodes 使用 format_node_dict 格式化

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

        # 构建数据流（Phase 19 Wave 2, D-19-09, LINK-03）
        data_flows = build_data_flows(graph)

        graph_dict = {
            "graph_name": graph.graph_name,
            "graph_type": GRAPH_TYPE_MAP.get(graph.graph_class, graph.graph_class),  # D-20-07
            "nodes": [format_node_dict(node, idx) for idx, node in enumerate(graph.nodes)],  # OUT-01
            "connections": connections,
            "execution_flows": execution_flows,  # D-08-09: execution_flows 数组
            "data_flows": data_flows,  # D-19-09: data_flows 数组（LINK-03）
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


def build_graphs_summary(graphs: List[UEdGraph]) -> List[Dict]:
    """
    构建顶层 graphs_summary 字段（D-14-04~06, OUT-02）。

    将 execution_flows 从 graphs[] 内提升至顶层，按图分组。
    函数调用格式: FunctionName(ParamName:TypeCategory)

    Args:
        graphs: List[UEdGraph] from ParseResult.graphs

    Returns:
        List[Dict]: graphs_summary 数组
    """
    summary = []
    for graph in graphs:
        # 复用现有 build_execution_flows 数据
        flows = build_execution_flows(graph)

        # 转换为目标格式
        execution_flows_summary = []
        for flow in flows:
            event_name = flow.get("start_event", "Unknown")
            # 提取函数调用链
            calls = []
            for node in flow.get("nodes", []):
                if node.get("node_type") == "K2Node_CallFunction":
                    func_name = node.get("function_name", "Unknown")
                    # D-14-06: 提取参数类型（从 graph.nodes 中查找）
                    param_str = _extract_function_params(graph, node.get("node_guid"))
                    calls.append(f"{func_name}({param_str})")

            # Phase 28a FIX: Skip empty flows (no CallFunction nodes)
            # EnhancedInputAction's Started/Ongoing/Canceled/Completed may have no connections
            if not calls:
                continue

            function_name = calls[0] if calls else ""
            execution_flows_summary.append({
                "event": event_name,
                "function_name": function_name,
                "calls": calls
            })

        summary.append({
            "graph_name": graph.graph_name,
            "execution_flows": execution_flows_summary
        })

    return summary


def _extract_function_params(graph: UEdGraph, node_guid: str) -> str:
    """
    提取函数参数类型（D-14-06）。

    从节点 pins 中提取非 exec pin 的类型信息。
    格式: "Param1:Type1, Param2:Type2"

    Args:
        graph: UEdGraph 对象
        node_guid: 节点 GUID

    Returns:
        str: 参数类型字符串
    """
    # 查找节点
    node = None
    for n in graph.nodes:
        if n.node_guid == node_guid:
            node = n
            break

    if not node:
        return ""

    # 提取 input pins（非 exec 类型）
    params = []
    for pin in node.pins:
        if pin.direction == 0:  # Input
            if pin.pin_type and pin.pin_type.pin_category != "exec":
                pin_type = pin.pin_type.pin_category
                # 常见类型映射
                type_map = {
                    "string": "String",
                    "float": "Float",
                    "int": "Int",
                    "bool": "Bool",
                    "object": "Object",
                    "struct": "Struct",
                    "delegate": "Delegate",
                    "class": "Class",
                }
                type_name = type_map.get(pin_type, pin_type.capitalize())
                params.append(f"{pin.pin_name}:{type_name}")

    return ", ".join(params[:3])  # 最多显示 3 个参数


def build_execution_flows(graph: UEdGraph) -> List[Dict]:
    """
    构建执行流路径（D-08-07~11, D-19-10~12）。

    从 START_EVENT_TYPES 节点开始，沿 exec pin 连接追踪到 CallFunction 链路。

    算法：
    1. 找到所有 START_EVENT_TYPES 节点（执行流起点）
    2. 对每个起点，沿 exec pin 连接追踪
    3. EnhancedInputAction各触发时机分别追踪
    4. 记录节点信息：{node_guid, node_type, function_name}
    5. 检测控制流节点 → 停止
    6. 检测已访问节点 → 停止并标记循环

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

    # Step 1: 找到所有起点节点（D-19-10）
    start_nodes = [n for n in graph.nodes if n.class_name in START_EVENT_TYPES]

    for start_node in start_nodes:
        # D-19-12: EnhancedInputAction各触发时机分别追踪
        if start_node.class_name == "K2Node_EnhancedInputAction":
            # 遍历output exec pins，为每个触发时机构建执行流
            for pin in start_node.pins:
                if pin.direction == 1 and pin.pin_type and pin.pin_type.pin_category == "exec":
                    # pin.pin_name即为触发时机（Started/Triggered/Completed）
                    flow = _trace_execution_from_pin(start_node, pin, pin_lookup, node_lookup)
                    execution_flows.append({
                        "start_event": f"{start_node.class_name}.{pin.pin_name}",  # D-19-11
                        "nodes": flow
                    })
        else:
            # 其他起点类型：标准追踪
            flow = _trace_execution_from_event(start_node, pin_lookup, node_lookup)
            start_event_name = _get_start_event_name(start_node)  # 重命名函数
            execution_flows.append({
                "start_event": start_event_name,  # D-19-11
                "nodes": flow
            })

    return execution_flows


def build_data_flows(graph: UEdGraph, mode: str = "name") -> List[Dict]:
    """
    构建数据流图（D-19-06~09, LINK-03）。

    从非exec pins提取数据传递关系，构建data_flows数组。

    算法：
    1. 构建pin_lookup查找表（pin_id → (node_guid, pin_name)）
    2. 构建node_name_lookup查找表（node_guid → node_name）
    3. 遍历所有output pins（direction=1）
    4. 过滤exec类型pins（pin_type.category != "exec"）
    5. 对每个linked_to_raw中的目标pin，构建数据流关系
    6. 使用format_pin_ref()格式化输出（name或guid模式）

    Args:
        graph: UEdGraph对象
        mode: 输出格式模式（"name"或"guid"，默认"name"）

    Returns:
        List[Dict]: data_flows数组
        - 格式: [{"source": {"node": "...", "pin": "..."}, "target": {...}}]
    """
    # Step 1: Build pin_lookup
    pin_lookup: Dict[str, Tuple[str, str]] = {}
    for node in graph.nodes:
        for pin in node.pins:
            pin_lookup[pin.pin_id] = (node.node_guid, pin.pin_name)

    # Step 2: Build node_name_lookup（复用19-01逻辑）
    node_name_lookup: Dict[str, str] = {}
    for idx, node in enumerate(graph.nodes):
        node_name_lookup[node.node_guid] = _derive_node_name(node, idx)

    # Step 3-5: Build data flows（D-19-06/07/08）
    data_flows: List[Dict] = []

    for node in graph.nodes:
        for pin in node.pins:
            # D-19-06: 仅处理output pins，排除exec类型
            if pin.direction == 1:  # Output
                if pin.pin_type and pin.pin_type.pin_category != "exec":
                    # 构建数据流关系
                    for linked_pin_id in pin.linked_to_raw:
                        # Phase 18: linked_to_raw为dict格式 {"pin_guid": str}
                        target_pin_guid = linked_pin_id.get("pin_guid") if isinstance(linked_pin_id, dict) else linked_pin_id

                        if target_pin_guid in pin_lookup:
                            target_node_guid, target_pin_name = pin_lookup[target_pin_guid]
                            # D-19-07: 使用format_pin_ref格式化（依赖19-01）
                            data_flows.append({
                                "source": format_pin_ref(node.node_guid, pin.pin_name, node_name_lookup, mode),
                                "target": format_pin_ref(target_node_guid, target_pin_name, node_name_lookup, mode)
                            })

    # D-19-08: 返回扁平数组
    return data_flows


def _trace_execution_from_event(
    start_node: UEdGraphNode,
    pin_lookup: Dict[str, Tuple[str, str]],
    node_lookup: Dict[str, UEdGraphNode]
) -> List[Dict]:
    """
    追踪单条执行流（D-08-07~11, D-19-13~14）。

    Args:
        start_node: K2Node_Event 起点（或其他START_EVENT_TYPES起点）
        pin_lookup: pin_id → (node_guid, pin_name) 查找表
        node_lookup: node_guid → node 查找表

    Returns:
        List[Dict]: 节点信息序列
    """
    visited: Set[str] = set()  # D-08-11: 循环检测
    flow: List[Dict] = []
    current_node = start_node

    while current_node:
        # 循环检测（D-08-11, D-19-15）
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

        # D-19-13/14: 控制流节点标记停止 + 输出branch_type
        if current_node.class_name in CONTROL_FLOW_NODES:
            branch_type = BRANCH_TYPE_MAP.get(current_node.class_name, "unknown")
            node_info["branch_type"] = branch_type  # D-19-14
            node_info["stopped_at"] = "control_flow_node"  # 保留现有标记（移到节点层级）
            flow.append(node_info)
            break

        flow.append(node_info)

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
                    # Phase 18兼容: linked_to_raw为dict格式 {"pin_guid": str}
                    target_pin_guid = linked_pin_id.get("pin_guid") if isinstance(linked_pin_id, dict) else linked_pin_id
                    if target_pin_guid in pin_lookup:
                        target_node_guid, _ = pin_lookup[target_pin_guid]
                        return node_lookup.get(target_node_guid)
    return None


def _trace_execution_from_pin(
    start_node: UEdGraphNode,
    start_pin: UEdGraphPin,
    pin_lookup: Dict[str, Tuple[str, str]],
    node_lookup: Dict[str, UEdGraphNode]
) -> List[Dict]:
    """
    从特定Pin开始追踪执行流（D-19-12）。

    用于EnhancedInputAction多触发时机追踪。

    Args:
        start_node: 起点节点
        start_pin: 起点output exec pin
        pin_lookup: pin_id → (node_guid, pin_name) 查找表
        node_lookup: node_guid → node 查找表

    Returns:
        List[Dict]: 节点信息序列
    """
    # 从start_pin的linked_to_raw查找下一节点
    for linked_pin_id in start_pin.linked_to_raw:
        # Phase 18兼容: linked_to_raw为dict格式 {"pin_guid": str}
        target_pin_guid = linked_pin_id.get("pin_guid") if isinstance(linked_pin_id, dict) else linked_pin_id
        if target_pin_guid in pin_lookup:
            target_node_guid, _ = pin_lookup[target_pin_guid]
            next_node = node_lookup.get(target_node_guid)
            if next_node:
                # 从下一节点开始标准追踪
                return _trace_execution_from_event(next_node, pin_lookup, node_lookup)

    return []  # 无连接


def _get_start_event_name(node: UEdGraphNode) -> str:
    """
    获取起点节点的事件名称（D-19-11）。

    支持4种起点类型：
    - K2Node_Event: event_reference.member_name
    - K2Node_EnhancedInputAction: input_action_path或class_name
    - K2Node_VariableSet: "VariableSet"
    - K2Node_CustomEvent: "CustomEvent"

    Args:
        node: 起点节点

    Returns:
        str: 事件名称
    """
    if node.class_name == "K2Node_Event":
        if node.node_data and hasattr(node.node_data, 'event_reference'):
            return node.node_data.event_reference.member_name
    elif node.class_name == "K2Node_EnhancedInputAction":
        # 返回input_action_path路径名（如果有）或class_name
        if node.node_data and hasattr(node.node_data, 'input_action_path'):
            # 提取动作名称（路径最后一部分）
            path = node.node_data.input_action_path
            if path:
                return path.split('/')[-1] if '/' in path else path
        return node.class_name
    elif node.class_name == "K2Node_VariableSet":
        return "VariableSet"
    elif node.class_name == "K2Node_CustomEvent":
        return "CustomEvent"

    return "Unknown"


def build_status_info(result: ParseResult) -> StatusInfo:
    """
    构建 status 字段（D-14-01, OUT-01）。

    三元分类:
    - success: is_success=True, errors=[]（解析成功，无错误）
    - fail: is_success=True, errors non-empty（部分结果可用）
    - error: is_success=False（严重错误）

    Args:
        result: ParseResult 对象

    Returns:
        StatusInfo: status 对象
    """
    if result.is_success:
        if not result.errors:
            return StatusInfo(status="success")
        else:
            # D-14-01: 有错误但部分结果可用 → fail
            message = result.errors[0] if result.errors else None
            return StatusInfo(status="fail", message=message, code="PARSE_ERROR")
    else:
        # is_success=False → error
        message = result.errors[0] if result.errors else "Unknown error"
        return StatusInfo(status="error", message=message, code="PARSE_ERROR")


# ============================================================================
# API Frozen Since Phase 14 (D-14-14~16, OUT-06)
# ============================================================================
#
# 以下输出格式函数自 Phase 14 完成后冻结，后续 Phase 15+ 不修改核心字段结构:
# - format_json_full(): 顶层字段固定
# - format_json_summary(): 摘要字段固定（70%+ token 减少）
# - build_status_info(): status 结构固定
# - build_graphs_summary(): graphs_summary 结构固定
#
# 向后兼容承诺:
# - 新字段可通过可选参数添加（如 include_schema）
# - 字段语义不变（parent_class 含义保持）
# - 底层字段通过注释标记，不删除
# ============================================================================


def build_schema_info() -> Dict[str, str]:
    """
    构建字段语义注释（D-14-13, OUT-05）。

    仅在 --verbose 或 --schema 标志时输出。

    Returns:
        Dict[str, str]: 字段描述映射
    """
    return {
        "status": "解析结果状态（success/fail/error）",
        "output_version": "输出格式 API 版本标识",
        "summary": "资产基本信息（版本、包名）",
        "exports": "导出对象列表（蓝图、组件等）",
        "blueprint_metadata": "蓝图元数据（父类、变量、图）",
        "parent_class": "蓝图继承的父类名称",
        "variables": "蓝图变量列表（名称、类型、默认值、元数据）",
        "is_component": "变量是否为组件类型（SkeletalMeshComponent 等）",
        "graphs": "蓝图执行图数据（完整节点/引脚信息）",
        "graphs_summary": "顶层化的图执行流概览（事件→函数调用链）",
        "execution_flows": "函数调用链路径",
        "imports": "ImportMap 依赖列表（外部对象引用）",
        "soft_references": "SoftObjectPaths 软引用列表",
        "circular_deps": "检测到的循环依赖路径",
    }


def format_json_full(result: ParseResult, include_schema: bool = False) -> Dict:
    """
    Format full JSON output with complete asset data (OUT-03).

    Per D-01: Tiered output (full detail)
    Per D-02: Package → Exports → Properties hierarchy
    Per D-03: Top-level errors field
    Per D-04: 单一 blueprint 对象结构（D-20-04: graphs 移入 blueprint 内部）
    Per D-05: Raw FPackageIndex values preserved where unresolved
    Per D-06: name_map excluded (already parsed to object names)
    Per D-20-04: 单一 blueprint 对象结构（graphs 移入 blueprint 内部）
    Per D-20-05: output_version 升级到 "4.0"
    Per D-20-06: blueprint_name 从 package_name 提取

    Args:
        result: ParseResult from parse_uasset()
        include_schema: bool, whether to include _schema field (OUT-05)

    Returns:
        Dict with keys: status, output_version, summary, exports, blueprint, graphs_summary, imports, soft_references, circular_deps, errors
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

    # D-20-04: 构建单一 blueprint 对象（包含 graphs）
    blueprint_obj = None
    if result.blueprint:
        blueprint_obj = format_blueprint_dict(
            result.blueprint,
            blueprint_name=result.summary.package_name if result.summary else None
        )
        blueprint_obj["graphs"] = format_graphs_json(result.graphs)  # D-20-04: graphs 移入 blueprint

    output = {
        "status": asdict(build_status_info(result)),  # D-14-03: 顶层位置（第一个字段）
        "output_version": "4.0",  # D-20-05: 反映输出结构重大变化
        "summary": summary_dict,
        "exports": format_exports_list(result),
        "blueprint": blueprint_obj,  # D-20-04: 单一 blueprint 对象
        "graphs_summary": build_graphs_summary(result.graphs),  # D-14-04: 顶层化（OUT-02）
        # Phase 10: 依赖分析字段（D-10-05/08/13）
        "imports": result.imports,                     # D-10-05: ImportMap 依赖列表
        "soft_references": result.soft_references,     # D-10-08: SoftObjectPaths 软引用
        "circular_deps": result.circular_deps,         # D-10-13: 高密度依赖路径
        "errors": result.errors
    }

    # OUT-05: 添加 _schema 字段（仅在 include_schema=True）
    if include_schema:
        output["_schema"] = build_schema_info()

    return output


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


def format_json_summary(result: ParseResult, include_schema: bool = False) -> Dict:
    """
    Format compact JSON summary - 70%+ token reduction（D-14-07~09, OUT-03）。

    精简策略:
    - 移除: imports, soft_references, circular_deps, errors
    - 精简 exports: 仅 name, class, parent_class
    - 移除 properties 数组
    - 保留: status, output_version, graphs_summary

    Per D-07: 移除依赖字段
    Per D-08: 精简 exports
    Per D-09: 移除 properties 数组

    Args:
        result: ParseResult from parse_uasset()
        include_schema: bool, whether to include _schema field (OUT-05)

    Returns:
        Dict: 精简摘要
    """
    from dataclasses import asdict

    version_dict = {}
    if result.summary:
        version_dict = {
            "ue4": result.summary.file_version_ue4,
            "ue5": result.summary.file_version_ue5 or result.summary.legacy_file_version,
            "legacy": result.summary.legacy_file_version
        }

    # D-14-08: 精简 exports（仅 name, class, parent_class）
    exports_summary = []
    for i, exp in enumerate(result.export_map):
        # 获取 parent_class（仅在蓝图主对象的第一个 export）
        parent_class = ""
        if result.blueprint and result.blueprint.is_blueprint and i == 0:
            parent_class = result.blueprint.parent_class or ""

        exports_summary.append({
            "name": exp.object_name,
            "class": get_asset_class(exp, result.import_map, result.export_map),
            "parent_class": parent_class
        })

    output = {
        "status": asdict(build_status_info(result)),  # D-14-03: 顶层位置（第一个字段）
        "output_version": "4.0",  # D-20-05: API 版本标识（与 format_json_full 保持一致）
        "version": version_dict,
        "package_name": result.summary.package_name if result.summary else "",
        "exports": exports_summary,  # D-14-08: 精简版本（无 properties/serial_size 等）
        "graphs_summary": build_graphs_summary(result.graphs),  # D-14-04: 顶层化（OUT-02）
    }

    # D-14-07: 移除 imports/soft_references/circular_deps/errors
    # errors 数组已移除（status 字段已包含状态信息）

    # D-20-04: blueprint 精简（仅保留核心字段）
    if result.blueprint and result.blueprint.is_blueprint:
        output["blueprint"] = {
            "blueprint_name": result.summary.package_name if result.summary else None,
            "parent_class": result.blueprint.parent_class,
        }

    # OUT-05: 添加 _schema 字段（仅在 include_schema=True）
    if include_schema:
        output["_schema"] = build_schema_info()

    return output


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


def format_markdown(result: ParseResult) -> str:
    """
    格式化 Markdown 输出（D-14-10~12, OUT-04）。

    三节结构 + 表格优先 + Mermaid 流程图。

    Args:
        result: ParseResult from parse_uasset()

    Returns:
        str: Markdown 格式文本
    """
    lines = []

    # 标题
    asset_name = result.summary.package_name if result.summary else "Unknown"
    asset_name = asset_name.split("/")[-1] if "/" in asset_name else asset_name
    lines.append(f"# Asset: {asset_name}")
    lines.append("")

    # === Asset Overview ===
    lines.append("## Asset Overview")
    lines.append("| Field | Value |")
    lines.append("|-------|-------|")
    if result.summary:
        lines.append(f"| Package | {result.summary.package_name} |")
        ue_version = result.summary.file_version_ue5 or result.summary.file_version_ue4
        lines.append(f"| Version | UE {ue_version} |")
    # Status
    status_info = build_status_info(result)
    lines.append(f"| Status | {status_info.status} |")
    if status_info.message:
        lines.append(f"| Message | {status_info.message} |")
    lines.append("")

    # === Blueprint Details ===
    if result.blueprint and result.blueprint.is_blueprint:
        lines.append("## Blueprint Details")
        lines.append("| Field | Value |")
        lines.append("|-------|-------|")
        lines.append(f"| Parent Class | {result.blueprint.parent_class or 'Unknown'} |")
        # Variables 统计
        var_count = len(result.blueprint.variables) if result.blueprint.variables else 0
        comp_count = sum(1 for v in result.blueprint.variables if v.is_component) if result.blueprint.variables else 0
        lines.append(f"| Variables | {var_count} ({comp_count} components, {var_count - comp_count} regular) |")
        lines.append("")

    # === Graph Summary ===
    graphs_summary = build_graphs_summary(result.graphs)
    if graphs_summary:
        lines.append("## Graph Summary")
        for graph_summary in graphs_summary:
            graph_name = graph_summary.get("graph", "Unknown")
            lines.append(f"### {graph_name}")

            # Mermaid 流程图
            flows = graph_summary.get("execution_flows", [])
            if flows:
                lines.append("```mermaid")
                lines.append("graph LR")
                for flow in flows:
                    event = flow.get("event", "Unknown")
                    calls = flow.get("calls", [])
                    if calls:
                        # 第一个节点: event --> first_call
                        first_func = calls[0].split("(")[0]
                        lines.append(f"  {event} --> {first_func}")
                        # 链式连接
                        for i in range(len(calls) - 1):
                            fn1 = calls[i].split("(")[0]
                            fn2 = calls[i+1].split("(")[0]
                            lines.append(f"  {fn1} --> {fn2}")
                lines.append("```")
                lines.append("")
    else:
        lines.append("## Graph Summary")
        lines.append("No graphs in this asset.")
        lines.append("")

    # === Exports ===
    if result.export_map:
        lines.append("## Exports")
        lines.append("| Name | Class | Parent |")
        lines.append("|------|-------|--------|")
        for i, exp in enumerate(result.export_map):
            name = exp.object_name
            cls = get_asset_class(exp, result.import_map, result.export_map)
            parent = ""
            if result.blueprint and i == 0:
                parent = result.blueprint.parent_class or ""
            lines.append(f"| {name} | {cls} | {parent} |")
        lines.append("")

    return "\n".join(lines)


# ============================================================================
# Phase 26: 增强的 JSON 格式化函数 (META-04)
# ============================================================================

def _format_variable_enhanced(variable: BlueprintVariable) -> dict:
    """格式化增强的变量元数据（Phase 26: META-04）"""
    result = {
        "name": variable.var_name,
        "type": {
            "pin_category": variable.var_type.pin_category,
            "pin_sub_category": variable.var_type.pin_sub_category,
            "container_type": variable.var_type.container_type,
            "is_reference": variable.var_type.is_reference,
            "is_const": variable.var_type.is_const
        },
        "category": variable.category,
        "default_value": variable.default_value,
        "friendly_name": variable.friendly_name,
        "property_flags": variable.property_flags,
        "edit_condition": variable.edit_condition,
        "edit_category": variable.edit_category,
        "edit_widget": variable.edit_widget,
        "is_edit_anywhere": variable.is_edit_anywhere,
        "is_edit_instance_only": variable.is_edit_instance_only,
        "is_visible_anywhere": variable.is_visible_anywhere,
        "is_blueprint_read_only": variable.is_blueprint_read_only,
        "is_blueprint_readable": variable.is_blueprint_readable,
        "is_blueprint_writable": variable.is_blueprint_writable,
        "is_blueprint_assignable": variable.is_blueprint_assignable,
        "is_blueprint_callable": variable.is_blueprint_callable,
        "is_transient": variable.is_transient,
        "is_duplicate_transient": variable.is_duplicate_transient,
        "is_text_export_transient": variable.is_text_export_transient,
        "is_non_transient": variable.is_non_transient,
        "is_export_object": variable.is_export_object,
        "is_save_game": variable.is_save_game,
        "is_no_clear": variable.is_no_clear,
        "is_reference_only": variable.is_reference_only,
        "is_rep_notify": variable.is_rep_notify,
        "is_interp": variable.is_interp,
        "is_expose_on_spawn": variable.is_expose_on_spawn,
        "is_net": variable.is_net,
        "is_replicated": variable.is_replicated,
        "is_non_pi_ed_duplicate_transient": variable.is_non_pi_ed_duplicate_transient,
        "is_component": variable.is_component,
        "meta_data": variable.meta_data
    }
    return result


def _format_parameter(parameter: FunctionParameter) -> dict:
    """格式化函数参数（Phase 26: META-04）"""
    return {
        "name": parameter.name,
        "type": parameter.param_type,
        "default_value": parameter.default_value,
        "is_input": parameter.is_input,
        "is_output": parameter.is_output,
        "is_optional": parameter.is_optional,
        "property_flags": parameter.property_flags,
        "meta_data": parameter.meta_data
    }


def _format_function_enhanced(function: BlueprintFunction) -> dict:
    """格式化增强的函数元数据（Phase 26: META-04）"""
    result = {
        "name": function.name,
        "return_type": function.return_type,
        "function_flags": function.function_flags,
        "is_pure": function.is_pure,
        "is_blueprint_callable": function.is_blueprint_callable,
        "is_blueprint_event": function.is_blueprint_event,
        "is_blueprint_implementable_event": function.is_blueprint_implementable_event,
        "is_native": function.is_native,
        "is_const": function.is_const,
        "is_static": function.is_static,
        "is_virtual": function.is_virtual,
        "is_exec": function.is_exec,
        "is_net": function.is_net,
        "is_net_reliable": function.is_net_reliable,
        "is_net_server": function.is_net_server,
        "is_net_client": function.is_net_client,
        "is_net_multicast": function.is_net_multicast,
        "is_blueprint_private": function.is_blueprint_private,
        "is_blueprint_protected": function.is_blueprint_protected,
        "is_blueprint_public": function.is_blueprint_public,
        "is_blueprint_pure": function.is_blueprint_pure,
        "is_blueprint_cosmetic": function.is_blueprint_cosmetic,
        "is_editor_only": function.is_editor_only,
        "is_final": function.is_final,
        "is_delegate": function.is_delegate,
        "is_multicast_delegate": function.is_multicast_delegate,
        "is_has_out_parms": function.is_has_out_parms,
        "is_has_defaults": function.is_has_defaults,
        "access_specifier": function.access_specifier,
        "parameters": [_format_parameter(param) for param in function.parameters],
        "meta_data": function.meta_data
    }
    return result


def _format_event_enhanced(event: BlueprintEvent) -> dict:
    """格式化增强的事件元数据（Phase 26: META-04）"""
    result = {
        "name": event.name,
        "event_type": event.event_type,
        "function_flags": event.function_flags,
        "is_blueprint_event": event.is_blueprint_event,
        "is_blueprint_implementable_event": event.is_blueprint_implementable_event,
        "is_net": event.is_net,
        "is_net_multicast": event.is_net_multicast,
        "is_net_reliable": event.is_net_reliable,
        "is_net_client": event.is_net_client,
        "is_net_server": event.is_net_server,
        "is_replicated": event.is_replicated,
        "is_cosmetic": event.is_cosmetic,
        "is_static": event.is_static,
        "is_multicast": event.is_multicast,
        "is_override": event.is_override,
        "override_parent_class": event.override_parent_class,
        "override_parent_event": event.override_parent_event,
        "is_interface_event": event.is_interface_event,
        "interface_class": event.interface_class,
        "parameters": [_format_parameter(param) for param in event.parameters],
        "meta_data": event.meta_data
    }

    # 添加多播委托信息
    if event.multicast_delegate:
        result["multicast_delegate"] = {
            "delegate_name": event.multicast_delegate.delegate_name,
            "signature_function": event.multicast_delegate.signature_function,
            "is_callable_in_blueprint": event.multicast_delegate.is_callable_in_blueprint
        }

    return result


def format_blueprint_dict(blueprint: BlueprintMetadata, blueprint_name: str = None) -> Dict:
    """
    Format BlueprintMetadata for JSON output (D-04, D-20-06).

    Per D-20-06: blueprint_name 从 package_name 或导出名提取
    Phase 26: 增强元数据输出（META-04）

    Args:
        blueprint: BlueprintMetadata object
        blueprint_name: 资产名称（可选）

    Returns:
        Dict with keys: blueprint_name, parent_class, variables, functions, events, detection_warning
    """
    # 增强的变量输出（Phase 26）
    variables_list = [_format_variable_enhanced(var) for var in blueprint.variables]

    # 增强的函数输出（Phase 26）
    functions_list = [_format_function_enhanced(func) for func in blueprint.functions]

    # 增强的事件输出（Phase 26）
    events_list = [_format_event_enhanced(event) for event in blueprint.events]

    return {
        "blueprint_name": blueprint_name,  # D-20-06
        "parent_class": blueprint.parent_class,  # None if not resolved
        "variables": variables_list,  # Phase 26: 增强格式
        "functions": functions_list,  # Phase 26: 新增
        "events": events_list,  # Phase 26: 新增
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
    Per D-24: Mutually exclusive --json/--text/--summary/--markdown flags
    Per D-27: Optional flags: --verbose, --output FILE, --export INDEX
    D-14-17: --markdown flag (OUT-04)
    D-14-19: --schema flag (OUT-05)

    Returns:
        argparse.ArgumentParser: Configured parser
    """
    parser = argparse.ArgumentParser(
        prog='uasset_read',
        description='Parse Unreal Engine .uasset files and output structured data'
    )

    # Positional: file path (CLI-01)
    parser.add_argument('file', help='Path to .uasset file to parse')

    # Mutually exclusive output flags (D-24, D-14-17)
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument('--json', action='store_true', help='Output full JSON structure')
    group.add_argument('--text', action='store_true', help='Output YAML-style text (default)')
    group.add_argument('--summary', action='store_true', help='Output compact summary format')
    group.add_argument('--markdown', action='store_true', help='Output Markdown format (D-14-17)')

    # Optional flags (D-27, D-14-19)
    parser.add_argument('--verbose', action='store_true', help='Include extra detail fields')
    parser.add_argument('--output', metavar='FILE', help='Write output to file instead of stdout')
    parser.add_argument('--export', metavar='INDEX', type=int, help='Output only specific export by index')
    parser.add_argument('--graph', action='store_true', help='Include blueprint graph data in output')
    parser.add_argument('--schema', action='store_true', help='Include field semantic annotations (_schema) (D-14-19)')

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
            include_schema = args.schema or args.verbose
            output_str = json.dumps(format_json_full(result, include_schema), indent=2, ensure_ascii=False)
        elif args.text:
            # --graph --text = text output with Graphs section
            output_str = format_text_full(result)
        else:
            # D-08-13: --graph alone = only graphs in JSON format
            output_str = json.dumps({"graphs": format_graphs_json(result.graphs)},
                                    indent=2, ensure_ascii=False)
    elif args.markdown:
        # D-14-17: --markdown 标志输出 Markdown 格式
        output_str = format_markdown(result)
    elif args.json:
        include_schema = args.schema or args.verbose
        output_str = json.dumps(format_json_full(result, include_schema), indent=2, ensure_ascii=False)
    elif args.summary:
        include_schema = args.schema or args.verbose
        output_str = json.dumps(format_json_summary(result, include_schema), indent=2, ensure_ascii=False)
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
    'StatusInfo',  # Phase 14: JSend 风格 status 字段（OUT-01）
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
    # Phase 13: Transform Property Value Data Classes
    'VectorValue',
    'RotatorValue',
    'ScaleValue',
    'format_transform_value',
    'parse_vector_value',
    'parse_rotator_value',
    'parse_scale_value',
    'extract_component_transforms',

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
    # Phase 19: 连接输出格式配置（LINK-01）
    'FORMAT_CONFIG',

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
    # Phase 12: PropertyFlags and variable type formatting
    'parse_property_flags_to_labels',
    'format_variable_type',
    # Phase 12: BlueprintGeneratedClass identification (per D-01)
    'detect_blueprint_generated_class',
    'find_main_blueprint_generated_class',
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
    'format_markdown',  # Phase 14: Markdown 格式（OUT-04）
    'format_exports_list',
    'format_properties_list',
    'format_blueprint_dict',
    'resolve_fpackage_index',
    'build_schema_info',  # Phase 14: Schema 字段语义注释（OUT-05）
    # Phase 8: Graph Output Functions
    'build_connections_map',
    'format_graphs_json',
    'build_execution_flows',
    'CONTROL_FLOW_NODES',
    # Phase 19: 连接输出格式化函数（LINK-01）
    '_derive_node_name',
    'format_pin_ref',

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