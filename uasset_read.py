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
from dataclasses import dataclass, field
from typing import Optional, List, Dict, BinaryIO, Tuple


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


# ============================================================================
# 自定义异常（D-15 优雅降级）
# ============================================================================

class UAssetError(Exception):
    """uasset 解析错误基类"""
    pass


class VersionError(UAssetError):
    """版本不支持错误"""
    pass


class ParseError(UAssetError):
    """解析错误（可携带部分结果）"""

    def __init__(self, message: str, partial_result: Optional[Dict] = None):
        super().__init__(message)
        self.partial_result = partial_result


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

        data = self._file.read(size)
        # 不在此处反转字节 - 类型特定方法负责处理字节序
        return data

    def seek(self, pos: int) -> None:
        """
        定位到指定位置（带边界验证，D-14）。

        Args:
            pos: 目标位置

        Raises:
            ParseError: 若 pos 超出文件大小
        """
        if pos > self._file_size:
            raise ParseError(
                f"Offset {pos} exceeds file size {self._file_size}"
            )
        self._file.seek(pos)

    def tell(self) -> int:
        """返回当前位置"""
        return self._file.tell()

    def close(self) -> None:
        """关闭文件"""
        self._file.close()

    def set_byte_swapping(self, enabled: bool) -> None:
        """设置字节交换标志（D-11）"""
        self._byte_swapping = enabled

    def total_size(self) -> int:
        """返回文件总大小"""
        return self._file_size

    # ========================================================================
    # 类型读取方法（使用 struct.unpack 配合字节序感知格式）
    # ========================================================================

    def read_u8(self) -> int:
        """读取 unsigned 8-bit integer（字节序无关）"""
        return struct.unpack('<B', self.read(1))[0]

    def read_i32(self) -> int:
        """读取 signed 32-bit integer（支持字节交换）"""
        fmt = '>' if self._byte_swapping else '<'
        return struct.unpack(fmt + 'i', self.read(4))[0]

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


@dataclass
class PackageFileSummary:
    """
    PackageFileSummary 文件头（D-08 读取所有字段）。

    来自 PackageFileSummary.h：
    包含版本信息、偏移量、计数等完整文件头数据。
    """
    tag: int                            # 魔术标签（0x9E2A83C1）
    legacy_file_version: int            # -2 至 -9（D-04）
    file_version_ue4: int               # UE4 版本号
    legacy_ue3_version: int = 0         # LegacyUE3版本（仅 legacy != -4）
    file_version_ue5: int = 0           # UE5 版本号（仅 legacy <= -8）
    file_version_licensee: int = 0      # Licensee 版本
    saved_hash: bytes = field(default_factory=lambda: b'')  # FIoHash (20 bytes) for UE5 >= PACKAGE_SAVED_HASH
    package_name: str = ""              # PackageName FString (UE PackageFileSummary.cpp line 258)
    localization_id: str = ""           # LocalizationId FString (UE4 >= VER_UE4_ADDED_PACKAGE_SUMMARY_LOCALIZATION_ID)
    gatherable_text_data_count: int = 0  # GatherableTextData entries count (UE4 >= VER_UE4_SERIALIZE_TEXT_IN_PACKAGES)
    gatherable_text_data_offset: int = 0  # GatherableTextData offset (UE4 >= VER_UE4_SERIALIZE_TEXT_IN_PACKAGES)
    package_flags: int = 0              # D-12 仅存储
    name_count: int = 0
    name_offset: int = 0                # 名称表绝对偏移
    soft_object_paths_count: int = 0
    soft_object_paths_offset: int = 0
    import_count: int = 0
    import_offset: int = 0              # 导入表绝对偏移
    export_count: int = 0
    export_offset: int = 0              # 导出表绝对偏移
    export_hashes_offset: int = 0
    import_export_guids_offset: int = 0
    import_export_guids_count: int = 0
    cooked_packages_offset: int = 0
    cooked_packages_count: int = 0
    asset_registry_data_offset: int = 0
    bulk_data_start_offset: int = 0     # BulkData 基准偏移（D-13 不解析载荷）
    total_header_size: int = 0
    custom_versions: List[CustomVersion] = field(default_factory=list)  # D-05
    payload_toc_offset: int = 0
    data_resource_offset: int = 0


@dataclass
class ObjectImport:
    """
    FObjectImport 导入表条目（CORE-04）。

    来自 ObjectResource.h：
    表示外部依赖（其他包中的对象引用）。
    """
    class_package: str      # 来源包名（FName 解析后）
    class_name: str         # 类名（FName 解析后）
    outer_index: PackageIndex  # Outer 引用
    object_name: str        # 对象名（FName 解析后）


@dataclass
class ObjectExport:
    """
    FObjectExport 导出表条目（CORE-05/CORE-06）。

    来自 ObjectResource.h：
    表示包内对象定义。
    """
    class_index: PackageIndex      # 类引用（CORE-06 资产类型识别）
    super_index: PackageIndex      # 父类引用
    outer_index: PackageIndex      # Outer 引用
    object_name: str               # 对象名
    object_flags: int              # EObjectFlags
    serial_size: int               # 序列化数据大小
    serial_offset: int             # 序列化数据偏移
    # UE5+ 字段
    script_serial_size: int = 0
    script_serial_offset: int = 0


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


@dataclass
class ParseResult:
    """
    解析结果（D-15 部分结果）。

    包含解析后的所有数据和错误信息。
    """
    summary: Optional[PackageFileSummary] = None
    name_map: List[str] = field(default_factory=list)
    import_map: List[ObjectImport] = field(default_factory=list)
    export_map: List[ObjectExport] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)  # 收集所有错误
    blueprint: Optional["BlueprintMetadata"] = None  # Per D-02: auto-extracted
    is_success: bool = False


# ============================================================================
# 解析函数
# ============================================================================

def read_package_summary(archive: FArchive) -> PackageFileSummary:
    """
    读取 PackageFileSummary 文件头（CORE-01/CORE-02/CORE-08）。

    来自 PackageFileSummary.cpp：
    读取魔术标签、检测字节序、验证版本、读取所有字段。

    Args:
        archive: FArchive 实例

    Returns:
        PackageFileSummary dataclass

    Raises:
        VersionError: 若版本不支持
        ParseError: 若解析失败
    """
    archive.seek(0)

    # 读取魔术标签
    tag = archive.read_u32()

    # 字节序检测（CORE-02/D-11）
    if tag == PACKAGE_FILE_TAG_SWAPPED:
        archive.set_byte_swapping(True)
        tag = PACKAGE_FILE_TAG
    elif tag != PACKAGE_FILE_TAG:
        raise VersionError(f"Invalid package tag: {hex(tag)}")

    # 读取 legacy_file_version
    legacy_file_version = archive.read_i32()

    # 版本验证（CORE-08/D-04）
    if legacy_file_version < LEGACY_FILE_VERSION_MIN or legacy_file_version > LEGACY_FILE_VERSION_MAX:
        raise VersionError(f"Unsupported legacy version: {legacy_file_version}")

    # LegacyUE3Version（仅在 legacy_file_version != -4 时存在）
    # 参考 UE 源码 PackageFileSummary.cpp line 130-134
    if legacy_file_version != -4:
        legacy_ue3_version = archive.read_i32()
    else:
        legacy_ue3_version = 0

    # UE4 版本（所有现代版本都有）
    # 参考 UE 源码 PackageFileSummary.cpp line 136
    file_version_ue4 = archive.read_i32()

    # UE5 版本（仅在 legacy_file_version <= -8 时存在）
    # 参考 UE 源码 PackageFileSummary.cpp line 138-141
    # 注意：UE 源码使用 <= -8，而非 >= -8
    if legacy_file_version <= -8:
        file_version_ue5 = archive.read_i32()
    else:
        file_version_ue5 = 0

    # UE5 版本验证（仅对 -8 及以上版本）
    if legacy_file_version <= -8 and file_version_ue5 < UE5_VERSION_MIN:
        raise VersionError(f"Unsupported UE5 version: {file_version_ue5}")

    # Licensee 版本
    file_version_licensee = archive.read_i32()

    # SavedHash and early TotalHeaderSize for UE5 >= PACKAGE_SAVED_HASH (version 1004)
    # Reference: UE 5.7 PackageFileSummary.cpp line 176-180
    saved_hash = b''
    total_header_size = 0
    PACKAGE_SAVED_HASH_VERSION = 1004  # EUnrealEngineObjectUE5Version::PACKAGE_SAVED_HASH

    if legacy_file_version <= -8 and file_version_ue5 >= PACKAGE_SAVED_HASH_VERSION:
        saved_hash = archive.read(20)  # FIoHash structure
        total_header_size = archive.read_i32()  # Early read, replaces trailer read

    # CustomVersions 数组（D-05 存储 GUID 不验证）
    custom_versions_count = archive.read_u32()
    if custom_versions_count > MAX_CUSTOM_VERSIONS:
        raise ParseError(
            f"Custom versions count {custom_versions_count} exceeds maximum {MAX_CUSTOM_VERSIONS}"
        )
    custom_versions: List[CustomVersion] = []
    for _ in range(custom_versions_count):
        # GUID 为 16 bytes
        guid_bytes = archive.read(16)
        guid_str = guid_bytes.hex()
        version = archive.read_i32()
        custom_versions.append(CustomVersion(guid=guid_str, version=version))

    # TotalHeaderSize for UE4 files (legacy > -8, version < PACKAGE_SAVED_HASH)
    # Reference: UE PackageFileSummary.cpp lines 254-258
    # For UE4 files, TotalHeaderSize is read BEFORE PackageName (after CustomVersions)
    # For UE5 >= PACKAGE_SAVED_HASH, TotalHeaderSize was already read in SavedHash block above
    if legacy_file_version > -8:
        # UE4 file: TotalHeaderSize after CustomVersions, before PackageName
        total_header_size = archive.read_i32()

    # PackageName (FString) - Reference: UE PackageFileSummary.cpp line 258
    # Note: PackageName is FString type (int32 length + UTF-8 data), NOT FName
    package_name = archive.read_fstring()

    # PackageFlags（D-12 仅存储）
    package_flags = archive.read_u32()

    # 名称表处理 (UE PackageFileSummary.cpp line 278)
    # NameCount + NameOffset ALWAYS present for modern UE4/UE5 files (legacy < 0)
    # Inline names format only for UE3 files (legacy >= 0), not supported per D-04
    name_count = archive.read_i32()
    if name_count > MAX_NAME_COUNT:
        raise ParseError(
            f"Name count {name_count} exceeds maximum {MAX_NAME_COUNT}"
        )
    name_offset = archive.read_i32()  # Always read for legacy < 0

    # SoftObjectPaths（UE5+ only）
    # Reference: UE PackageFileSummary.cpp line 282-285
    # FileVersionUE >= ADD_SOFTOBJECTPATH_LIST (UE5 only)
    # UE4 files do NOT have SoftObjectPaths
    soft_object_paths_count = 0
    soft_object_paths_offset = 0
    is_ue4_file = legacy_file_version > -8  # UE4 files (not UE5)
    if not is_ue4_file:  # UE5 files only
        soft_object_paths_count = archive.read_i32()
        soft_object_paths_offset = archive.read_i32()

    # LocalizationId FString - UE4 files only (legacy > -8)
    # Reference: UE PackageFileSummary.cpp line 289-292
    # FileVersionUE4 >= VER_UE4_ADDED_PACKAGE_SUMMARY_LOCALIZATION_ID (added in UE 4.20)
    # All UE4 v521+ files have this field
    localization_id = ""
    if is_ue4_file:
        localization_id = archive.read_fstring()

    # GatherableTextData Count/Offset - UE4 files only
    # Reference: UE PackageFileSummary.cpp line 295-298
    # FileVersionUE4 >= VER_UE4_SERIALIZE_TEXT_IN_PACKAGES (added in UE 4.26)
    # All UE4 v521+ files have these fields
    gatherable_text_data_count = 0
    gatherable_text_data_offset = 0
    if is_ue4_file:
        gatherable_text_data_count = archive.read_i32()
        gatherable_text_data_offset = archive.read_i32()

    # 导入表偏移
    import_count = archive.read_i32()
    if import_count > MAX_IMPORT_COUNT:
        raise ParseError(
            f"Import count {import_count} exceeds maximum {MAX_IMPORT_COUNT}"
        )
    import_offset = archive.read_i32()

    # 导出表偏移
    export_count = archive.read_i32()
    if export_count > MAX_EXPORT_COUNT:
        raise ParseError(
            f"Export count {export_count} exceeds maximum {MAX_EXPORT_COUNT}"
        )
    export_offset = archive.read_i32()

    # 导出哈希偏移
    export_hashes_offset = archive.read_i32()

    # ImportExportGuids
    import_export_guids_offset = archive.read_i32()
    import_export_guids_count = archive.read_i32()

    # CookedPackages
    cooked_packages_offset = archive.read_i32()
    cooked_packages_count = archive.read_i32()

    # AssetRegistryData 偏移
    asset_registry_data_offset = archive.read_i32()

    # BulkDataStartOffset（D-13 不解析载荷）
    bulk_data_start_offset = archive.read_i64()

    # TotalHeaderSize for UE5 files < PACKAGE_SAVED_HASH (version < 1004)
    # Reference: UE PackageFileSummary.cpp lines 254-258
    # UE4 files (legacy > -8): already read after CustomVersions
    # UE5 >= PACKAGE_SAVED_HASH: already read in SavedHash block
    # UE5 < PACKAGE_SAVED_HASH: need to read here (same position as UE4)
    if legacy_file_version <= -8 and file_version_ue5 < PACKAGE_SAVED_HASH_VERSION:
        # UE5 file with version < 1004: TotalHeaderSize at trailer position
        total_header_size = archive.read_i32()

    # UE5+ trailer 字段（可选，取决于版本）
    # 这些字段在文件末尾的 trailer 中，不是 header 连续字段
    # 我们在 header 中将它们初始化为 0，后续需要时可从 trailer 解析
    payload_toc_offset = 0
    data_resource_offset = 0

    return PackageFileSummary(
        tag=tag,
        legacy_file_version=legacy_file_version,
        file_version_ue4=file_version_ue4,
        legacy_ue3_version=legacy_ue3_version,
        file_version_ue5=file_version_ue5,
        file_version_licensee=file_version_licensee,
        saved_hash=saved_hash,
        package_name=package_name,
        localization_id=localization_id,
        gatherable_text_data_count=gatherable_text_data_count,
        gatherable_text_data_offset=gatherable_text_data_offset,
        custom_versions=custom_versions,
        package_flags=package_flags,
        name_count=name_count,
        name_offset=name_offset,
        soft_object_paths_count=soft_object_paths_count,
        soft_object_paths_offset=soft_object_paths_offset,
        import_count=import_count,
        import_offset=import_offset,
        export_count=export_count,
        export_offset=export_offset,
        export_hashes_offset=export_hashes_offset,
        import_export_guids_offset=import_export_guids_offset,
        import_export_guids_count=import_export_guids_count,
        cooked_packages_offset=cooked_packages_offset,
        cooked_packages_count=cooked_packages_count,
        asset_registry_data_offset=asset_registry_data_offset,
        bulk_data_start_offset=bulk_data_start_offset,
        total_header_size=total_header_size,
        payload_toc_offset=payload_toc_offset,
        data_resource_offset=data_resource_offset
    )


def read_name_table(archive: FArchive, summary: PackageFileSummary) -> List[str]:
    """
    读取名称表。

    使用 FNameEntrySerialized 格式：
    - FString (Length + Data)
    - Hash bytes (4 bytes) for UE4 >= VER_UE4_NAME_HASHES_SERIALIZED (502)

    Args:
        archive: FArchive 实例
        summary: PackageFileSummary 实例

    Returns:
        名称表列表（NameMap）
    """
    archive.seek(summary.name_offset)

    # UE4 version constant: VER_UE4_NAME_HASHES_SERIALIZED = 502
    # For UE4 >= 502, name entries have 4-byte hash suffix
    NAME_HASHES_SERIALIZED_VERSION = 502
    has_name_hashes = (summary.legacy_file_version > -8) and (summary.file_version_ue4 >= NAME_HASHES_SERIALIZED_VERSION)

    name_map: List[str] = []
    for _ in range(summary.name_count):
        name = archive.read_fstring()
        name_map.append(name)

        # Read hash bytes if UE4 >= 502
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

    来自 ObjectResource.h：
    FObjectImport 结构：
    - ClassPackage (FName)
    - ClassName (FName)
    - OuterIndex (FPackageIndex)
    - ObjectName (FName)

    Args:
        archive: FArchive 实例
        summary: PackageFileSummary 实例
        name_map: 已解析的名称表

    Returns:
        导入表列表（ImportMap）
    """
    archive.seek(summary.import_offset)

    import_map: List[ObjectImport] = []
    for _ in range(summary.import_count):
        class_package = archive.read_name(name_map)
        class_name = archive.read_name(name_map)
        outer_index = PackageIndex(archive.read_i32())
        object_name = archive.read_name(name_map)

        import_map.append(ObjectImport(
            class_package=class_package,
            class_name=class_name,
            outer_index=outer_index,
            object_name=object_name
        ))

    return import_map


def read_export_map(
    archive: FArchive,
    summary: PackageFileSummary,
    name_map: List[str]
) -> List[ObjectExport]:
    """
    读取导出表（CORE-05/CORE-06）。

    来自 ObjectResource.h：
    FObjectExport 结构：
    - ClassIndex (FPackageIndex)
    - SuperIndex (FPackageIndex)
    - OuterIndex (FPackageIndex)
    - ObjectName (FName)
    - ObjectFlags (u32)
    - SerialSize (i64)
    - SerialOffset (i64)
    - UE5+: ScriptSerialSize, ScriptSerialOffset

    Args:
        archive: FArchive 实例
        summary: PackageFileSummary 实例
        name_map: 已解析的名称表

    Returns:
        导出表列表（ExportMap）
    """
    archive.seek(summary.export_offset)

    export_map: List[ObjectExport] = []
    for _ in range(summary.export_count):
        class_index = PackageIndex(archive.read_i32())
        super_index = PackageIndex(archive.read_i32())
        outer_index = PackageIndex(archive.read_i32())
        object_name = archive.read_name(name_map)
        object_flags = archive.read_u32()
        serial_size = archive.read_i64()
        serial_offset = archive.read_i64()

        # UE5+ 脚本序列化字段（根据版本决定是否读取）
        # CR-02 fix: Check if file is actually UE5 (legacy <= -8), NOT ue5_version >= 0
        # UE4 files (legacy > -8) don't have these fields - file_version_ue5 stays at 0
        is_ue5_file = summary.legacy_file_version <= -8

        if is_ue5_file:
            script_serial_size = archive.read_i64()
            script_serial_offset = archive.read_i64()
        else:
            script_serial_size = 0
            script_serial_offset = 0

        export_map.append(ObjectExport(
            class_index=class_index,
            super_index=super_index,
            outer_index=outer_index,
            object_name=object_name,
            object_flags=object_flags,
            serial_size=serial_size,
            serial_offset=serial_offset,
            script_serial_size=script_serial_size,
            script_serial_offset=script_serial_offset
        ))

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


def parse_properties_from_export(
    export: ObjectExport,
    archive: FArchive,
    summary: PackageFileSummary,
    name_map: List[str],
    export_map: List[ObjectExport]
) -> List[PropertyValue]:
    """
    从导出条目解析所有属性（PROP-01 至 PROP-08）。

    参考 Class.cpp SerializeVersionedTaggedProperties 模式：
    1. Seek 到 export.serial_offset
    2. 循环读取 PropertyTag 直到 Name == "None"
    3. 分派到类型特定解析函数
    4. 边界验证（seek 到 start + tag.size）

    Args:
        export: ObjectExport 实例
        archive: FArchive 实例
        summary: PackageFileSummary 实例（版本信息）
        name_map: 名称表
        export_map: 导出表

    Returns:
        List[PropertyValue] 属性值列表
    """
    archive.seek(export.serial_offset)
    properties: List[PropertyValue] = []

    while True:
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

        except ParseError as e:
            # 单属性失败：记录并继续（D-25）
            properties.append(PropertyValue(
                name="ParseError",
                type="Error",
                value=str(e)
            ))
            continue

    return properties


def parse_property_value(
    tag: PropertyTag,
    archive: FArchive,
    name_map: List[str],
    export_map: List[ObjectExport]
) -> any:
    """
    分派属性值解析（PROP-02 至 PROP-06）。

    根据 tag.type 分派到类型特定的解析函数。
    未知类型返回 None（D-26 跳过策略）。

    Args:
        tag: PropertyTag 实例
        archive: FArchive 实例
        name_map: 名称表
        export_map: 导出表

    Returns:
        解析后的值（Python 原生类型）或 None（未知类型）
    """
    type_dispatch = {
        "BoolProperty": lambda t, a, n, e: parse_bool_property(t, a),
        "IntProperty": lambda t, a, n, e: parse_int_property(t, a),
        "Int64Property": lambda t, a, n, e: parse_int_property(t, a),
        "Int16Property": lambda t, a, n, e: parse_int_property(t, a),
        "Int8Property": lambda t, a, n, e: parse_int_property(t, a),
        "ByteProperty": lambda t, a, n, e: parse_int_property(t, a),
        "FloatProperty": lambda t, a, n, e: parse_float_property(t, a),
        "DoubleProperty": lambda t, a, n, e: parse_float_property(t, a),
        "StrProperty": lambda t, a, n, e: parse_str_property(t, a),
        "NameProperty": lambda t, a, n, e: parse_name_property(t, a, n),
        "ObjectProperty": lambda t, a, n, e: parse_object_property(t, a),
        "ArrayProperty": lambda t, a, n, e: parse_array_property(t, a, n, e),
    }

    parser = type_dispatch.get(tag.type)
    if parser:
        return parser(tag, archive, name_map, export_map)

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

        # 读取文件头
        result.summary = read_package_summary(archive)

        # 读取名称表
        result.name_map = read_name_table(archive, result.summary)

        # 读取导入表
        result.import_map = read_import_map(archive, result.summary, result.name_map)

        # 读取导出表
        result.export_map = read_export_map(archive, result.summary, result.name_map)

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

    # FArchive
    'FArchive',

    # Exceptions
    'UAssetError',
    'VersionError',
    'ParseError',

    # Constants
    'PACKAGE_FILE_TAG',
    'PACKAGE_FILE_TAG_SWAPPED',
    'PROP_TAG_NONE',
    'PROP_TAG_HAS_ARRAY_INDEX',
    'PROP_TAG_HAS_PROPERTY_GUID',
    'PROP_TAG_HAS_EXTENSIONS',
    'PROP_TAG_BOOL_TRUE',
    'PROPERTY_TAG_COMPLETE_TYPE_NAME',

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
]