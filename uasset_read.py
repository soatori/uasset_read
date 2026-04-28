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
from dataclasses import dataclass, field
from typing import Optional, List, Dict, BinaryIO


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