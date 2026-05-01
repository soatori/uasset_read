"""
tests/test_uasset_read.py - uasset_read 单元测试

Phase 1 Plan 01-01 Task 4: 单元测试框架

使用合成数据测试核心解析功能：
- PackageFileSummary 读取
- 字节序检测
- 名称表提取
- 导入表解析
- 导出表解析
- 资产类型识别
- 版本验证
- 错误处理
"""

import pytest
import struct
import os
import tempfile
from uasset_read import (
    FArchive, PackageFileSummary, PackageIndex, ObjectImport, ObjectExport,
    ParseResult, CustomVersion,
    parse_uasset, get_asset_class,
    PACKAGE_FILE_TAG, PACKAGE_FILE_TAG_SWAPPED,
    UE5_VERSION_MIN, LEGACY_FILE_VERSION_MIN, LEGACY_FILE_VERSION_MAX,
    VersionError, ParseError
)


# ============================================================================
# 辅助函数：创建测试用的合成 .uasset 文件
# ============================================================================

def create_test_uasset(
    tag: int = PACKAGE_FILE_TAG,
    legacy_version: int = -8,
    ue4_version: int = 0,
    ue5_version: int = UE5_VERSION_MIN,
    licensee_version: int = 0,
    custom_versions: list = None,
    package_flags: int = 0,
    names: list = None,
    imports: list = None,
    exports: list = None,
    use_big_endian: bool = False
) -> str:
    """
    创建合成 .uasset 文件用于测试。

    Args:
        tag: 魔术标签
        legacy_version: LegacyFileVersion
        ue4_version: UE4 版本号
        ue5_version: UE5 版本号
        licensee_version: Licensee 版本
        custom_versions: 自定义版本列表 [(guid_bytes, version)]
        package_flags: PackageFlags
        names: 名称表列表 ["Name1", "Name2"]（直接使用，不追加默认值）
        imports: 导入表列表 [(class_package_idx, class_name_idx, outer_index, object_name_idx)]
        exports: 导出表列表 [(class_index, super_index, outer_index, object_name_idx, flags, serial_size, serial_offset)]
        use_big_endian: 使用大端序写入（用于字节交换测试）

    Returns:
        临时文件路径
    """
    # 默认值（名称表必须包含 "None" 在索引 0）
    if custom_versions is None:
        custom_versions = []
    if names is None:
        names = ["None", "TestName", "AnotherName", "TestClass", "TestPackage"]
    else:
        # 确保名称表以 "None" 开头（UE FName 约定）
        if names[0] != "None":
            names = ["None"] + names
    if imports is None:
        imports = []
    if exports is None:
        exports = []

    # 字节序格式：小端 '<' 或大端 '>'
    endian_fmt = '>' if use_big_endian else '<'

    # 创建临时文件
    fd, path = tempfile.mkstemp(suffix='.uasset')
    os.close(fd)

    # UE Version constants (from uasset_read.py)
    UE5_ADD_SOFTOBJECTPATH_LIST = 1008
    UE5_VERSE_CELLS = 1015
    UE5_METADATA_SERIALIZATION_OFFSET = 1014
    UE5_PACKAGE_SAVED_HASH = 1016
    UE5_PAYLOAD_TOC = 1002
    UE5_DATA_RESOURCES = 1009
    UE5_NAMES_REFERENCED_FROM_EXPORT_DATA = 1001
    UE5_IMPORT_TYPE_HIERARCHIES = 1018

    UE4_WORLD_LEVEL_INFO = 223
    UE4_ADDED_CHUNKID = 277
    UE4_CHANGED_CHUNKID_TO_ARRAY = 341
    UE4_ENGINE_VERSION_OBJECT = 334
    UE4_ADD_STRING_ASSET_REFERENCES_MAP = 382
    UE4_PACKAGE_SUMMARY_HAS_COMPATIBLE_ENGINE_VERSION = 442
    UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS = 505
    UE4_ADDED_SEARCHABLE_NAMES = 508
    UE4_ADDED_PACKAGE_OWNER = 516
    UE4_NON_OUTER_PACKAGE_IMPORT = 518
    UE4_ADDED_PACKAGE_SUMMARY_LOCALIZATION_ID = 385
    UE4_SERIALIZE_TEXT_IN_PACKAGES = 401
    PKG_Cooked = 0x200

    NAME_HASHES_SERIALIZED_VERSION = 502

    is_ue5_file = legacy_version <= -8
    is_cooked = (package_flags & PKG_Cooked) != 0

    with open(path, 'wb') as f:
        # === 文件头 ===
        # 魔术标签（始终使用小端序，因为字节交换检测基于此）
        f.write(struct.pack('<I', tag))

        # LegacyFileVersion
        f.write(struct.pack(endian_fmt + 'i', legacy_version))

        # LegacyUE3Version（仅在 legacy_version != -4 时存在）
        if legacy_version != -4:
            f.write(struct.pack(endian_fmt + 'i', 864))  # LegacyUE3Version

        # UE4 版本
        f.write(struct.pack(endian_fmt + 'i', ue4_version))

        # UE5 版本（仅在 legacy_version <= -8 时存在）
        if is_ue5_file:
            f.write(struct.pack(endian_fmt + 'i', ue5_version))

        # Licensee 版本
        f.write(struct.pack(endian_fmt + 'i', licensee_version))

        # SavedHash (UE5 >= 1016)
        total_header_size_pos = 0
        if is_ue5_file and ue5_version >= UE5_PACKAGE_SAVED_HASH:
            f.write(b'\x00' * 20)  # SavedHash placeholder (20 bytes)
            total_header_size_pos = f.tell()
            f.write(struct.pack(endian_fmt + 'i', 0))  # TotalHeaderSize placeholder

        # CustomVersions
        f.write(struct.pack(endian_fmt + 'I', len(custom_versions)))
        for guid_bytes, version in custom_versions:
            f.write(guid_bytes)  # 16 bytes GUID
            f.write(struct.pack(endian_fmt + 'i', version))

        # TotalHeaderSize for UE4 files
        if not is_ue5_file:
            total_header_size_pos = f.tell()
            f.write(struct.pack(endian_fmt + 'i', 0))  # Placeholder

        # PackageName (FString)
        package_name_bytes = "None".encode('utf-8') + b'\x00'
        f.write(struct.pack(endian_fmt + 'i', len(package_name_bytes)))
        f.write(package_name_bytes)

        # PackageFlags
        f.write(struct.pack(endian_fmt + 'I', package_flags))

        # NameCount + NameOffset
        name_count_pos = f.tell()
        f.write(struct.pack(endian_fmt + 'i', len(names)))
        name_offset_pos = f.tell()
        f.write(struct.pack(endian_fmt + 'i', 0))  # NameOffset placeholder

        # SoftObjectPaths (UE5 >= 1008)
        if is_ue5_file and ue5_version >= UE5_ADD_SOFTOBJECTPATH_LIST:
            f.write(struct.pack(endian_fmt + 'i', 0))  # Count
            f.write(struct.pack(endian_fmt + 'i', 0))  # Offset

        # LocalizationId (uncooked files only)
        # UE source: wrapped in !IsFilterEditorOnly()
        if not is_cooked:
            # LocalizationId FString
            if not is_ue5_file and ue4_version >= UE4_ADDED_PACKAGE_SUMMARY_LOCALIZATION_ID:
                f.write(struct.pack(endian_fmt + 'i', 0))  # Empty string
            elif is_ue5_file:  # UE5 files always have version >= 385
                f.write(struct.pack(endian_fmt + 'i', 0))  # Empty string

            # GatherableTextData (uncooked files only)
            # UE source: not wrapped in IsFilterEditorOnly but we assume uncooked for synthetic
            if ue4_version >= UE4_SERIALIZE_TEXT_IN_PACKAGES or is_ue5_file:
                f.write(struct.pack(endian_fmt + 'i', 0))  # Count
                f.write(struct.pack(endian_fmt + 'i', 0))  # Offset

        # ExportCount + ExportOffset (Export BEFORE Import!)
        export_count_pos = f.tell()
        f.write(struct.pack(endian_fmt + 'i', len(exports)))
        export_offset_pos = f.tell()
        f.write(struct.pack(endian_fmt + 'i', 0))  # ExportOffset placeholder

        # ImportCount + ImportOffset
        import_count_pos = f.tell()
        f.write(struct.pack(endian_fmt + 'i', len(imports)))
        import_offset_pos = f.tell()
        f.write(struct.pack(endian_fmt + 'i', 0))  # ImportOffset placeholder

        # CellExport/CellImport (UE5 >= 1015)
        if is_ue5_file and ue5_version >= UE5_VERSE_CELLS:
            f.write(struct.pack(endian_fmt + 'i', 0))  # CellExportCount
            f.write(struct.pack(endian_fmt + 'i', 0))  # CellExportOffset
            f.write(struct.pack(endian_fmt + 'i', 0))  # CellImportCount
            f.write(struct.pack(endian_fmt + 'i', 0))  # CellImportOffset

        # MetaDataOffset (UE5 >= 1014)
        if is_ue5_file and ue5_version >= UE5_METADATA_SERIALIZATION_OFFSET:
            f.write(struct.pack(endian_fmt + 'i', 0))

        # DependsOffset
        f.write(struct.pack(endian_fmt + 'i', 0))

        # SoftPackageReferences (UE4 >= 382)
        if ue4_version >= UE4_ADD_STRING_ASSET_REFERENCES_MAP or is_ue5_file:
            f.write(struct.pack(endian_fmt + 'i', 0))  # Count
            f.write(struct.pack(endian_fmt + 'i', 0))  # Offset

        # SearchableNames (UE4 >= 508)
        if ue4_version >= UE4_ADDED_SEARCHABLE_NAMES or is_ue5_file:
            f.write(struct.pack(endian_fmt + 'i', 0))

        # ThumbnailTableOffset
        f.write(struct.pack(endian_fmt + 'i', 0))

        # ImportTypeHierarchies (UE5 >= 1018)
        if is_ue5_file and ue5_version >= UE5_IMPORT_TYPE_HIERARCHIES:
            f.write(struct.pack(endian_fmt + 'i', 0))  # Count
            f.write(struct.pack(endian_fmt + 'i', 0))  # Offset

        # Legacy Guid (UE5 < 1016, or UE4 files)
        # PackageFileSummary.cpp line 337-352: FGuid (16 bytes)
        # For UE4 files: always read (FileVersionUE5 = 0 < 1016)
        # For UE5 files: read if ue5_version < 1016
        if is_ue5_file and ue5_version < UE5_PACKAGE_SAVED_HASH:
            f.write(b'\x00' * 16)  # Legacy Guid placeholder
        elif not is_ue5_file:
            # UE4 file: always read Legacy Guid
            f.write(b'\x00' * 16)  # Legacy Guid placeholder

        # PersistentGuid (UE4 >= 516, uncooked only)
        # PackageFileSummary.cpp line 354-376: WITH_EDITORONLY_DATA && !IsFilterEditorOnly
        # For test fixtures, assume uncooked (is_cooked = False from PKG_Cooked check)
        # Note: fixture sets package_flags=0 by default, so is_cooked=False
        if ue4_version >= UE4_ADDED_PACKAGE_OWNER or is_ue5_file:
            f.write(b'\x00' * 16)  # PersistentGuid placeholder
            # OwnerPersistentGuid (UE4 >= 516 and < 518)
            if not is_ue5_file and ue4_version >= UE4_ADDED_PACKAGE_OWNER and ue4_version < UE4_NON_OUTER_PACKAGE_IMPORT:
                f.write(b'\x00' * 16)  # OwnerPersistentGuid

        # Generations
        f.write(struct.pack(endian_fmt + 'i', 0))  # GenerationCount (empty)

        # SavedByEngineVersion (UE4 >= 334)
        if ue4_version >= UE4_ENGINE_VERSION_OBJECT or is_ue5_file:
            f.write(struct.pack(endian_fmt + 'H', 5))  # Major
            f.write(struct.pack(endian_fmt + 'H', 0))  # Minor
            f.write(struct.pack(endian_fmt + 'H', 0))  # Patch
            f.write(struct.pack(endian_fmt + 'I', 0))  # Changelist
            # Branch FString
            f.write(struct.pack(endian_fmt + 'i', 0))  # Empty branch

        # CompatibleWithEngineVersion (UE4 >= 442)
        if ue4_version >= UE4_PACKAGE_SUMMARY_HAS_COMPATIBLE_ENGINE_VERSION or is_ue5_file:
            f.write(struct.pack(endian_fmt + 'H', 5))  # Major
            f.write(struct.pack(endian_fmt + 'H', 0))  # Minor
            f.write(struct.pack(endian_fmt + 'H', 0))  # Patch
            f.write(struct.pack(endian_fmt + 'I', 0))  # Changelist
            f.write(struct.pack(endian_fmt + 'i', 0))  # Empty branch

        # CompressionFlags
        f.write(struct.pack(endian_fmt + 'I', 0))

        # CompressedChunks (TArray)
        f.write(struct.pack(endian_fmt + 'i', 0))  # Count

        # PackageSource
        f.write(struct.pack(endian_fmt + 'I', 0))

        # AdditionalPackagesToCook (TArray)
        f.write(struct.pack(endian_fmt + 'i', 0))  # Count

        # NumTextureAllocations (legacy > -7)
        if legacy_version > -7:
            f.write(struct.pack(endian_fmt + 'i', 0))

        # AssetRegistryDataOffset
        f.write(struct.pack(endian_fmt + 'i', 0))

        # BulkDataStartOffset
        f.write(struct.pack(endian_fmt + 'q', 0))

        # WorldTileInfoDataOffset (UE4 >= 223)
        if ue4_version >= UE4_WORLD_LEVEL_INFO or is_ue5_file:
            f.write(struct.pack(endian_fmt + 'i', 0))

        # ChunkIDs (UE4 >= 277, changed to array at 341)
        if ue4_version >= UE4_CHANGED_CHUNKID_TO_ARRAY or is_ue5_file:
            f.write(struct.pack(endian_fmt + 'i', 0))  # Count (empty)
        elif ue4_version >= UE4_ADDED_CHUNKID:
            f.write(struct.pack(endian_fmt + 'i', -1))  # Single ChunkID

        # PreloadDependencies (UE4 >= 505)
        if ue4_version >= UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS or is_ue5_file:
            f.write(struct.pack(endian_fmt + 'i', -1))  # Count
            f.write(struct.pack(endian_fmt + 'i', 0))   # Offset

        # NamesReferencedFromExportDataCount (UE5 >= 1001, at END!)
        if is_ue5_file and ue5_version >= UE5_NAMES_REFERENCED_FROM_EXPORT_DATA:
            f.write(struct.pack(endian_fmt + 'i', len(names)))

        # PayloadTocOffset (UE5 >= 1002)
        if is_ue5_file and ue5_version >= UE5_PAYLOAD_TOC:
            f.write(struct.pack(endian_fmt + 'q', -1))  # int64, INDEX_NONE

        # DataResourceOffset (UE5 >= 1009)
        if is_ue5_file and ue5_version >= UE5_DATA_RESOURCES:
            f.write(struct.pack(endian_fmt + 'i', -1))

        # TotalHeaderSize trailer (UE5 < 1016)
        if is_ue5_file and ue5_version < UE5_PACKAGE_SAVED_HASH:
            total_header_size_pos = f.tell()
            f.write(struct.pack(endian_fmt + 'i', 0))

        # === 名称表 ===
        name_offset = f.tell()

        # Name hashes: UE4 >= 502 AND UE5 files
        emit_name_hashes = (not is_ue5_file and ue4_version >= NAME_HASHES_SERIALIZED_VERSION) or is_ue5_file

        for name in names:
            # FString 格式：长度 + UTF-8 数据 + null 终止符
            name_bytes = name.encode('utf-8') + b'\x00'
            f.write(struct.pack(endian_fmt + 'i', len(name_bytes)))
            f.write(name_bytes)

            # Emit hash bytes for UE4 >= 502 and UE5
            if emit_name_hashes:
                f.write(struct.pack(endian_fmt + 'HH', 0, 0))  # 4 bytes hash

        # === 导入表 ===
        import_offset = f.tell()
        for class_package_idx, class_name_idx, outer_index, object_name_idx in imports:
            f.write(struct.pack(endian_fmt + 'I', class_package_idx))  # ClassPackage index
            f.write(struct.pack(endian_fmt + 'I', 0))  # Number
            f.write(struct.pack(endian_fmt + 'I', class_name_idx))  # ClassName index
            f.write(struct.pack(endian_fmt + 'I', 0))  # Number
            f.write(struct.pack(endian_fmt + 'i', outer_index))  # OuterIndex
            f.write(struct.pack(endian_fmt + 'I', object_name_idx))  # ObjectName index
            f.write(struct.pack(endian_fmt + 'I', 0))  # Number

        # === 导出表 ===
        export_offset = f.tell()
        for class_index, super_index, outer_index, object_name_idx, flags, serial_size, serial_offset in exports:
            f.write(struct.pack(endian_fmt + 'i', class_index))  # ClassIndex
            f.write(struct.pack(endian_fmt + 'i', super_index))  # SuperIndex
            # Phase 6: TemplateIndex (UE4 >= 506)
            if ue4_version >= 506 or is_ue5_file:
                f.write(struct.pack(endian_fmt + 'i', 0))  # TemplateIndex (default 0)
            f.write(struct.pack(endian_fmt + 'i', outer_index))  # OuterIndex
            f.write(struct.pack(endian_fmt + 'I', object_name_idx))  # ObjectName index
            f.write(struct.pack(endian_fmt + 'I', 0))  # Number
            f.write(struct.pack(endian_fmt + 'I', flags))  # ObjectFlags
            # SerialSize/Offset: UE4 >= 508 uses i64, otherwise i32
            if ue4_version >= 508 or is_ue5_file:
                f.write(struct.pack(endian_fmt + 'q', serial_size))  # SerialSize (i64)
                f.write(struct.pack(endian_fmt + 'q', serial_offset))  # SerialOffset (i64)
            else:
                f.write(struct.pack(endian_fmt + 'i', serial_size))  # SerialSize (i32)
                f.write(struct.pack(endian_fmt + 'i', serial_offset))  # SerialOffset (i32)
            # Phase 6: bool flags (always present in modern files)
            f.write(struct.pack(endian_fmt + 'B', 0))  # bForcedExport
            f.write(struct.pack(endian_fmt + 'B', 0))  # bNotForClient
            f.write(struct.pack(endian_fmt + 'B', 0))  # bNotForServer
            # Phase 6: PackageGuid (UE5 < 1010)
            if is_ue5_file and ue5_version < 1010:
                f.write(b'\x00' * 16)  # FGuid (16 bytes, read but not stored)
            # Phase 6: bIsInheritedInstance (UE5 >= 1011)
            if is_ue5_file and ue5_version >= 1011:
                f.write(struct.pack(endian_fmt + 'B', 0))  # bIsInheritedInstance
            # Phase 6: PackageFlags
            f.write(struct.pack(endian_fmt + 'I', 0))  # PackageFlags
            # Phase 6: bGeneratePublicHash (UE5 >= 1015)
            if is_ue5_file and ue5_version >= 1015:
                f.write(struct.pack(endian_fmt + 'B', 0))  # bGeneratePublicHash
            # UE5+ 脚本序列化字段（CR-02 fix: check legacy_version <= -8, NOT ue5_version >= 0）
            if is_ue5_file:
                f.write(struct.pack(endian_fmt + 'q', 0))  # ScriptSerialSize
                f.write(struct.pack(endian_fmt + 'q', 0))  # ScriptSerialOffset

        # === 更新偏移 ===
        total_header_size = f.tell()

        # 回写名称表偏移（always needed for modern files）
        f.seek(name_offset_pos)
        f.write(struct.pack(endian_fmt + 'i', name_offset))

        # 回写导入表偏移
        f.seek(import_offset_pos)
        f.write(struct.pack(endian_fmt + 'i', import_offset))

        # 回写导出表偏移
        f.seek(export_offset_pos)
        f.write(struct.pack(endian_fmt + 'i', export_offset))

        # 回写 TotalHeaderSize
        f.seek(total_header_size_pos)
        f.write(struct.pack(endian_fmt + 'i', total_header_size))

    return path


def cleanup_test_file(path: str):
    """清理临时测试文件"""
    if os.path.exists(path):
        os.remove(path)


# ============================================================================
# 测试函数
# ============================================================================

def test_package_summary_valid():
    """
    测试有效 UE5 uasset 文件头解析（CORE-01）。

    验证：魔术标签、版本号正确读取。
    """
    path = create_test_uasset(
        tag=PACKAGE_FILE_TAG,
        legacy_version=-8,
        ue5_version=UE5_VERSION_MIN
    )

    try:
        result = parse_uasset(path)

        assert result.is_success, f"Parse failed: {result.errors}"
        assert result.summary is not None
        assert result.summary.tag == PACKAGE_FILE_TAG
        assert result.summary.legacy_file_version == -8
        assert result.summary.file_version_ue5 == UE5_VERSION_MIN
    finally:
        cleanup_test_file(path)


def test_byte_swapping_detection():
    """
    测试字节序检测（CORE-02/D-11）。

    验证：交换字节序文件正确解析。
    使用 use_big_endian=True 创建大端序文件，
    魔术标签为 PACKAGE_FILE_TAG_SWAPPED 表示字节交换。
    """
    path = create_test_uasset(
        tag=PACKAGE_FILE_TAG_SWAPPED,
        legacy_version=-8,
        ue5_version=UE5_VERSION_MIN,
        use_big_endian=True
    )

    try:
        result = parse_uasset(path)

        # 字节交换文件应成功解析（tag 被转换为正确值）
        assert result.is_success, f"Parse failed: {result.errors}"
        assert result.summary is not None
        # 解析后 tag 应为正确值（0x9E2A83C1）
        assert result.summary.tag == PACKAGE_FILE_TAG
    finally:
        cleanup_test_file(path)


def test_byte_swapping_string_content():
    """
    Test that UTF-8 strings are NOT corrupted by byte swapping (CR-01 fix).

    Validates:
    - NameMap content is correct in byte-swapped files
    - String bytes are NOT reversed (UTF-8 is byte-order independent)
    """
    # Create byte-swapped file with specific names
    names = ["Alice", "Bob", "Charlie"]
    path = create_test_uasset(
        tag=PACKAGE_FILE_TAG_SWAPPED,
        legacy_version=-8,
        ue5_version=UE5_VERSION_MIN,
        names=names,
        use_big_endian=True
    )

    try:
        result = parse_uasset(path)

        assert result.is_success, f"Parse failed: {result.errors}"
        # Verify NameMap content is correct (not reversed garbage)
        assert len(result.name_map) == len(names) + 1  # "None" + names
        assert result.name_map[0] == "None"
        assert result.name_map[1] == "Alice"  # NOT "ecilA\x00"
        assert result.name_map[2] == "Bob"    # NOT "boB\x00"
        assert result.name_map[3] == "Charlie"
    finally:
        cleanup_test_file(path)


def test_name_table_extraction():
    """
    测试名称表提取（CORE-03）。

    验证：NameMap 正确读取。
    create_test_uasset 会自动在名称表开头添加 "None"。
    """
    names = ["TestName", "AnotherName", "TestClass"]
    path = create_test_uasset(names=names)

    try:
        result = parse_uasset(path)

        assert result.is_success, f"Parse failed: {result.errors}"
        # 名称表包含 "None" + names
        assert len(result.name_map) == len(names) + 1
        # 检查名称内容
        assert result.name_map[0] == "None"  # UE FName 约定
        assert result.name_map[1] == "TestName"
        assert result.name_map[2] == "AnotherName"
    finally:
        cleanup_test_file(path)


def test_import_map():
    """
    测试导入表解析（CORE-04）。

    验证：ImportMap 正确读取。
    """
    # 导入表条目：(class_package_idx, class_name_idx, outer_index, object_name_idx)
    # 使用名称表索引（默认包含 ["None", "TestName", "AnotherName", "TestClass", "TestPackage"])
    imports = [
        (4, 3, 0, 1),  # TestPackage, TestClass, outer=0, TestName
    ]

    path = create_test_uasset(imports=imports)

    try:
        result = parse_uasset(path)

        assert result.is_success, f"Parse failed: {result.errors}"
        assert len(result.import_map) == 1
        import_entry = result.import_map[0]
        assert import_entry.class_package == "TestPackage"
        assert import_entry.class_name == "TestClass"
        assert import_entry.object_name == "TestName"
        assert import_entry.outer_index.index == 0
    finally:
        cleanup_test_file(path)


def test_export_map():
    """
    测试导出表解析（CORE-05）。

    验证：ExportMap 正确读取。
    """
    # 导出表条目：(class_index, super_index, outer_index, object_name_idx, flags, serial_size, serial_offset)
    exports = [
        (-1, 0, 0, 1, 0, 100, 200),  # class_index=-1（导入表索引0），object_name=TestName
    ]

    path = create_test_uasset(exports=exports)

    try:
        result = parse_uasset(path)

        assert result.is_success, f"Parse failed: {result.errors}"
        assert len(result.export_map) == 1
        export_entry = result.export_map[0]
        assert export_entry.object_name == "TestName"
        assert export_entry.class_index.index == -1
        assert export_entry.serial_size == 100
        assert export_entry.serial_offset == 200
    finally:
        cleanup_test_file(path)


def test_asset_class_identification():
    """
    测试资产类型识别（CORE-06）。

    验证：get_asset_class 从 class_index 获取类名。
    """
    # 创建导入表条目（类名）
    imports = [
        (4, 3, 0, 3),  # TestPackage, TestClass, outer=0, TestClass
    ]

    # 创建导出表条目（class_index 指向导入表）
    exports = [
        (-1, 0, 0, 1, 0, 100, 200),  # class_index=-1（导入表索引0）
    ]

    path = create_test_uasset(imports=imports, exports=exports)

    try:
        result = parse_uasset(path)

        assert result.is_success, f"Parse failed: {result.errors}"

        # 获取资产类名
        export = result.export_map[0]
        class_name = get_asset_class(export, result.import_map, result.export_map)

        assert class_name == "TestClass"
    finally:
        cleanup_test_file(path)


def test_unsupported_legacy_version():
    """
    测试不支持版本错误处理（CORE-08/D-04）。

    验证：legacy_version=-1 返回清晰错误。
    """
    path = create_test_uasset(legacy_version=-1)

    try:
        result = parse_uasset(path)

        assert not result.is_success
        assert len(result.errors) > 0
        assert "Unsupported legacy version" in result.errors[0]
    finally:
        cleanup_test_file(path)


def test_invalid_tag():
    """
    测试无效魔术标签错误处理（CORE-08）。

    验证：无效 tag 返回清晰错误。
    """
    path = create_test_uasset(tag=0xDEADBEEF)

    try:
        result = parse_uasset(path)

        assert not result.is_success
        assert len(result.errors) > 0
        assert "Invalid package tag" in result.errors[0]
    finally:
        cleanup_test_file(path)


def test_low_ue5_version():
    """
    测试低 UE5 版本处理（CORE-08/D-04）。

    UE5_VERSION_MIN 已改为 0，接受真实 UE5 文件（版本 521-522）。
    验证：ue5_version=500 被接受，解析成功。
    """
    path = create_test_uasset(ue5_version=500)

    try:
        result = parse_uasset(path)

        assert result.is_success
        assert result.summary.file_version_ue5 == 500
    finally:
        cleanup_test_file(path)


def test_package_index_properties():
    """
    测试 PackageIndex 属性方法（D-07）。

    验证：is_import、is_export、is_null 属性正确。
    """
    # 正数：导出
    export_idx = PackageIndex(1)
    assert export_idx.is_export
    assert not export_idx.is_import
    assert not export_idx.is_null
    assert export_idx.to_export_index() == 0

    # 负数：导入
    import_idx = PackageIndex(-1)
    assert import_idx.is_import
    assert not import_idx.is_export
    assert not import_idx.is_null
    assert import_idx.to_import_index() == 0

    # 零：空
    null_idx = PackageIndex(0)
    assert null_idx.is_null
    assert not null_idx.is_import
    assert not null_idx.is_export


def test_farchive_boundary_validation():
    """
    测试 FArchive 边界验证（D-14）。

    验证：超出文件大小的 seek 抛出 ParseError。
    """
    # 创建小文件
    fd, path = tempfile.mkstemp(suffix='.uasset')
    os.write(fd, b'\x00' * 10)  # 10 bytes
    os.close(fd)

    try:
        archive = FArchive(path)

        # 正常 seek
        archive.seek(5)
        assert archive.tell() == 5

        # 超出边界 seek
        with pytest.raises(ParseError) as exc_info:
            archive.seek(100)

        assert "exceeds file size" in str(exc_info.value)

        archive.close()
    finally:
        cleanup_test_file(path)


def test_farchive_read_boundary():
    """
    测试 FArchive 读取边界验证（D-14）。

    验证：读取超出剩余字节抛出 ParseError。
    """
    # 创建小文件
    fd, path = tempfile.mkstemp(suffix='.uasset')
    os.write(fd, b'\x00' * 10)  # 10 bytes
    os.close(fd)

    try:
        archive = FArchive(path)

        # 定位到末尾附近
        archive.seek(8)

        # 读取超出剩余字节
        with pytest.raises(ParseError) as exc_info:
            archive.read(10)

        assert "Cannot read" in str(exc_info.value)

        archive.close()
    finally:
        cleanup_test_file(path)


def test_farchive_type_specific_byte_swapping():
    """
    Test that type-specific read methods correctly swap bytes (CR-01).

    Validates:
    - read_i32/read_u32/read_i64/read_u64/read_f32 use '>' format when byte_swapping=True
    - Numeric values are correctly interpreted from big-endian files
    """
    fd, path = tempfile.mkstemp(suffix='.uasset')
    # Write big-endian values (need swapping to be interpreted correctly)
    os.write(fd, struct.pack('>i', -7))        # -7 as big-endian int32
    os.write(fd, struct.pack('>I', 0x9E2A83C1)) # PACKAGE_FILE_TAG as big-endian uint32
    os.write(fd, struct.pack('>q', 1000))      # 1000 as big-endian int64
    os.write(fd, struct.pack('>Q', 0xFFFFFFFFFFFFFFFF)) # max uint64 as big-endian
    os.write(fd, struct.pack('>f', 3.14159))   # float as big-endian
    os.close(fd)

    try:
        archive = FArchive(path)
        archive.set_byte_swapping(True)

        # Test read_i32 - should interpret big-endian bytes correctly
        assert archive.read_i32() == -7, "read_i32 failed to swap bytes"

        # Test read_u32 - should interpret big-endian bytes correctly
        assert archive.read_u32() == 0x9E2A83C1, "read_u32 failed to swap bytes"

        # Test read_i64 - should interpret big-endian bytes correctly
        assert archive.read_i64() == 1000, "read_i64 failed to swap bytes"

        # Test read_u64 - should interpret big-endian bytes correctly
        assert archive.read_u64() == 0xFFFFFFFFFFFFFFFF, "read_u64 failed to swap bytes"

        # Test read_f32 - should interpret big-endian bytes correctly
        fval = archive.read_f32()
        assert abs(fval - 3.14159) < 0.0001, f"read_f32 failed to swap bytes: {fval}"

        archive.close()
    finally:
        cleanup_test_file(path)


def test_farchive_raw_bytes_no_reversal():
    """
    Test that FArchive.read() does NOT reverse raw bytes when byte_swapping=True (CR-01).

    Validates:
    - Raw byte reads return original bytes (no reversal)
    - UTF-8 string data is NOT corrupted
    - Byte swapping only affects numeric type methods (read_i32, etc.)

    This test catches the bug: if read() reverses all multi-byte data,
    GUIDs, SavedHash, and UTF-8 strings would be corrupted.
    """
    fd, path = tempfile.mkstemp(suffix='.uasset')
    # Write big-endian int (needs swapping) + raw UTF-8 bytes (should NOT swap)
    os.write(fd, struct.pack('>I', 0x12345678) + b'TestName')
    os.close(fd)

    try:
        archive = FArchive(path)
        archive.set_byte_swapping(True)

        # Read 4 raw bytes - should NOT be reversed
        raw_bytes = archive.read(4)
        assert raw_bytes == b'\x12\x34\x56\x78', f"Raw bytes were reversed: {raw_bytes.hex()}"

        # Read UTF-8 string bytes - should NOT be reversed
        string_bytes = archive.read(8)
        assert string_bytes == b'TestName', f"UTF-8 bytes were reversed: {string_bytes}"

        archive.close()
    finally:
        cleanup_test_file(path)


def test_legacy_minus_seven_ue4_521():
    """
    Test parsing file similar to Lyra Character_Default.uasset (01-05 gap closure).

    Validates:
    - legacy=-7, UE4=521 files parse correctly
    - NameOffset is valid (not garbage from missing PackageName)
    - PackageName field correctly read
    - Inline names branch NOT triggered for legacy=-7

    This test catches the bugs fixed in 01-05:
    - Missing PackageName FString field
    - Incorrect inline names condition for legacy=-7
    """
    names = ["TestName", "TestClass", "TestPackage"]
    path = create_test_uasset(
        legacy_version=-7,  # Lyra uses -7
        ue4_version=521,    # Lyra uses UE4 version 521
        ue5_version=0,      # No UE5 version for legacy=-7
        names=names
    )

    try:
        result = parse_uasset(path)

        assert result.is_success, f"Parse failed: {result.errors}"
        assert result.summary is not None
        assert result.summary.legacy_file_version == -7
        assert result.summary.file_version_ue4 == 521
        # Verify NameOffset is valid (within file size)
        assert result.summary.name_offset < result.summary.total_header_size
        # Verify NameMap populated
        assert len(result.name_map) == len(names) + 1  # "None" + names
        assert result.name_map[0] == "None"
        assert result.name_map[1] == "TestName"
        # Verify PackageName read correctly (added in 01-05)
        assert result.summary.package_name == "None"
    finally:
        cleanup_test_file(path)


def test_package_name_field_reading():
    """
    Test that PackageName FString is correctly read (01-05 Task 1).

    Validates:
    - PackageName FString field exists in PackageFileSummary
    - PackageName is FString (read_fstring), not FName
    - PackageName read from correct position (after TotalHeaderSize)
    """
    path = create_test_uasset(
        legacy_version=-8,
        ue5_version=UE5_VERSION_MIN
    )

    try:
        result = parse_uasset(path)

        assert result.is_success, f"Parse failed: {result.errors}"
        assert result.summary is not None
        # PackageName field should exist (default "None" for synthetic files)
        assert hasattr(result.summary, 'package_name')
        assert result.summary.package_name == "None"
    finally:
        cleanup_test_file(path)


def test_parse_result_structure():
    """
    测试 ParseResult 结构（D-15）。

    验证：ParseResult 包含所有必需字段。
    """
    result = ParseResult()

    assert result.summary is None
    assert result.name_map == []
    assert result.import_map == []
    assert result.export_map == []
    assert result.errors == []
    assert result.is_success == False


def test_saved_hash_ue5_package_saved_hash_version():
    """
    Test SavedHash and early TotalHeaderSize parsing for UE5 >= PACKAGE_SAVED_HASH (1016).

    Validates:
    - Parser correctly reads 20-byte SavedHash for UE5 >= 1016 files
    - TotalHeaderSize is read early (before CustomVersions) for UE5 >= 1016
    - saved_hash field populated in PackageFileSummary

    Strategy: Use baseline test with UE5 < 1016 to verify saved_hash is empty,
    then test UE5 >= 1016 SavedHash reading.
    """
    # First verify UE5 < 1016 still works (baseline) - saved_hash should be empty
    path_baseline = create_test_uasset(
        legacy_version=-8,
        ue5_version=1015,  # < PACKAGE_SAVED_HASH (1016)
        names=["TestName"]
    )

    try:
        result_baseline = parse_uasset(path_baseline)
        assert result_baseline.is_success, f"Baseline parse failed: {result_baseline.errors}"
        assert result_baseline.summary.file_version_ue5 == 1015
        assert result_baseline.summary.saved_hash == b''  # Should be empty for < 1016
        assert len(result_baseline.name_map) == 2  # "None" + "TestName"
    finally:
        cleanup_test_file(path_baseline)

    # Now test UE5 >= 1016 SavedHash reading
    path_ue5_1016 = create_test_uasset(
        legacy_version=-8,
        ue5_version=1016,  # >= PACKAGE_SAVED_HASH
        names=["TestName"]
    )

    try:
        result_ue5_1016 = parse_uasset(path_ue5_1016)
        assert result_ue5_1016.is_success, f"Parse failed: {result_ue5_1016.errors}"
        assert result_ue5_1016.summary.file_version_ue5 == 1016
        # SavedHash should be 20 bytes (from fixture's placeholder zeros)
        assert len(result_ue5_1016.summary.saved_hash) == 20
        assert result_ue5_1016.summary.total_header_size > 0
    finally:
        cleanup_test_file(path_ue5_1016)


def test_ue4_export_no_script_serialization():
    """
    Test that UE4 files (legacy > -8) do NOT read script_serial fields (CR-02 fix).

    Validates:
    - UE4 files skip script_serial_size/script_serial_offset
    - Export parsing works correctly for legacy=-7 files
    - script_serial fields should be 0 (not read from file)
    """
    # Create UE4-style file (legacy=-7, NOT UE5)
    exports = [
        (-1, 0, 0, 1, 0, 100, 200),  # class=-1, name_idx=1
    ]

    path = create_test_uasset(
        legacy_version=-7,  # UE4 file (NOT UE5)
        ue4_version=522,    # Real UE4 version
        ue5_version=0,      # No UE5 version for legacy=-7
        exports=exports
    )

    try:
        result = parse_uasset(path)

        assert result.is_success, f"Parse failed: {result.errors}"
        assert len(result.export_map) == 1
        export = result.export_map[0]
        # For UE4 files, script_serial fields should be 0 (not read)
        assert export.script_serial_size == 0, f"UE4 file should not have script_serial_size: {export.script_serial_size}"
        assert export.script_serial_offset == 0, f"UE4 file should not have script_serial_offset: {export.script_serial_offset}"
        # Basic fields should be correct
        assert export.serial_size == 100
        assert export.serial_offset == 200
    finally:
        cleanup_test_file(path)


def test_name_count_bounds_validation():
    """
    Test that excessive name_count raises ParseError (WR-01 fix).

    Validates:
    - Parser rejects files with name_count > MAX_NAME_COUNT
    - Error message contains "exceeds maximum"
    """
    import struct
    fd, path = tempfile.mkstemp(suffix='.uasset')

    # Minimal header with huge name_count (WR-01 test)
    # Use UE5 version 500 (< 1004) to avoid SavedHash reading
    header = struct.pack('<I', PACKAGE_FILE_TAG)  # Tag
    header += struct.pack('<i', -8)  # LegacyFileVersion
    header += struct.pack('<i', 864)  # LegacyUE3Version
    header += struct.pack('<i', 0)  # UE4 version
    header += struct.pack('<i', 500)  # UE5 version (< 1004, no SavedHash)
    header += struct.pack('<i', 0)  # Licensee
    header += struct.pack('<I', 0)  # CustomVersions count
    header += struct.pack('<i', 5) + b'None\x00'  # PackageName
    header += struct.pack('<I', 0)  # PackageFlags
    header += struct.pack('<i', 20_000_000)  # name_count > MAX

    os.write(fd, header)
    os.close(fd)

    try:
        result = parse_uasset(path)
        assert not result.is_success
        assert "exceeds maximum" in result.errors[0]
    finally:
        cleanup_test_file(path)


def test_export_count_bounds_validation():
    """
    Test that excessive export_count raises ParseError (WR-01 fix).

    Validates:
    - Parser rejects files with export_count > MAX_EXPORT_COUNT
    - Error message contains "exceeds maximum"
    """
    fd, path = tempfile.mkstemp(suffix='.uasset')

    # Use UE5 version 1015 (< 1016) to avoid SavedHash reading
    # Follow correct UE field order: ExportCount BEFORE ImportCount
    header = struct.pack('<I', PACKAGE_FILE_TAG)
    header += struct.pack('<i', -8)  # LegacyFileVersion
    header += struct.pack('<i', 864)  # LegacyUE3Version
    header += struct.pack('<i', 0)    # FileVersionUE4
    header += struct.pack('<i', 1015)  # FileVersionUE5 (< 1016, no SavedHash)
    header += struct.pack('<i', 0)    # FileVersionLicensee
    header += struct.pack('<I', 0)    # CustomVersions count
    header += struct.pack('<i', 5) + b'None\x00'  # PackageName FString
    header += struct.pack('<I', 0)    # PackageFlags
    header += struct.pack('<i', 10)   # NameCount (valid)
    header += struct.pack('<i', 500)  # NameOffset (far into padded file)
    # SoftObjectPaths (UE5>=1008)
    header += struct.pack('<i', 0)    # Count
    header += struct.pack('<i', 0)    # Offset
    # LocalizationId (uncooked UE5)
    header += struct.pack('<i', 0)    # Empty FString
    # GatherableTextData (uncooked)
    header += struct.pack('<i', 0)    # Count
    header += struct.pack('<i', 0)    # Offset
    # ExportCount, ExportOffset (Export BEFORE Import!)
    header += struct.pack('<i', 5_000_000)  # ExportCount > MAX - should fail here
    # Add lots of padding to make offsets valid and ensure parser reaches ExportCount
    header += b'\x00' * 600  # Pad file so offsets are valid

    os.write(fd, header)
    os.close(fd)

    try:
        result = parse_uasset(path)
        assert not result.is_success
        assert "exceeds maximum" in result.errors[0]
    finally:
        cleanup_test_file(path)


def test_total_header_size_position_ue4():
    """
    Test TotalHeaderSize is read BEFORE PackageName for UE4 files.

    Validates fix for 01-07 gap:
    - UE4 files (legacy=-7) read TotalHeaderSize after CustomVersions, before PackageName
    - TotalHeaderSize position enables correct PackageName reading
    - Lyra Character_Default.uasset (legacy=-7, UE4 v521) requires this fix

    UE source reference (PackageFileSummary.cpp lines 254-258):
    ```cpp
    if (Sum.GetFileVersionUE() < EUnrealEngineObjectUE5Version::PACKAGE_SAVED_HASH)
    {
        Record << SA_VALUE(TEXT("TotalHeaderSize"), Sum.TotalHeaderSize);
    }
    Record << SA_VALUE(TEXT("PackageName"), Sum.PackageName);
    ```
    """
    # Create UE4-style file (legacy=-7) with names
    names = ["TestName", "TestClass"]
    path = create_test_uasset(
        legacy_version=-7,  # UE4 file (NOT UE5)
        ue4_version=522,    # Real UE4 version
        ue5_version=0,      # No UE5 version for legacy=-7
        names=names
    )

    try:
        result = parse_uasset(path)

        assert result.is_success, f"Parse failed: {result.errors}"
        assert result.summary is not None
        # Verify TotalHeaderSize is positive (valid)
        assert result.summary.total_header_size > 0
        # Verify PackageName parsed correctly (not garbage from wrong position)
        assert result.summary.package_name == "None"
        # Verify NameOffset is valid (within total_header_size)
        assert result.summary.name_offset < result.summary.total_header_size
        # Verify NameMap populated correctly
        assert len(result.name_map) == len(names) + 1  # "None" + names
        assert result.name_map[1] == "TestName"
    finally:
        cleanup_test_file(path)


def test_ue4_total_header_size_at_correct_position():
    """
    Test parsing UE4 file with TotalHeaderSize at correct UE position.

    Creates a file manually with TotalHeaderSize BEFORE PackageName,
    matching real Lyra Character_Default.uasset structure.

    This test catches the bug: if parser reads TotalHeaderSize at wrong position,
    PackageName FString length will be garbage (like 14620 from Lyra file).

    Expected UE4 file structure (correct order per UE PackageFileSummary.cpp):
    - Tag, LegacyVersion, LegacyUE3Version, UE4Version, LicenseeVersion
    - CustomVersions (count=0 for simplicity)
    - TotalHeaderSize (at correct position)
    - PackageName FString
    - PackageFlags
    - NameCount, NameOffset
    - LocalizationId (UE4 >= 385, uncooked)
    - GatherableTextData (UE4 >= 401, uncooked)
    - ExportCount, ExportOffset (Export BEFORE Import!)
    - ImportCount, ImportOffset
    - ... rest of header
    - Name table data
    """
    import struct
    import tempfile

    fd, path = tempfile.mkstemp(suffix='.uasset')

    # Build header with TotalHeaderSize at CORRECT UE4 position
    header = struct.pack('<I', PACKAGE_FILE_TAG)  # Tag
    header += struct.pack('<i', -7)  # LegacyFileVersion (UE4)
    header += struct.pack('<i', 864)  # LegacyUE3Version
    header += struct.pack('<i', 522)  # UE4 version
    header += struct.pack('<i', 0)  # Licensee version
    header += struct.pack('<I', 0)  # CustomVersions count = 0

    # CORRECT UE4 POSITION: TotalHeaderSize BEFORE PackageName
    # We don't know the final size yet, use placeholder
    total_header_size_placeholder_pos = len(header)
    header += struct.pack('<i', 0)  # TotalHeaderSize placeholder

    # PackageName FString
    package_name_bytes = "None".encode('utf-8') + b'\x00'
    header += struct.pack('<i', len(package_name_bytes))
    header += package_name_bytes

    # PackageFlags
    header += struct.pack('<I', 0)

    # NameCount, NameOffset
    header += struct.pack('<i', 2)  # NameCount = 2 ("None", "TestName")
    name_offset_placeholder_pos = len(header)
    header += struct.pack('<i', 0)  # NameOffset placeholder

    # LocalizationId FString - UE4 uncooked files (>= 385)
    # UE4 v522 >= 385, so LocalizationId is present
    header += struct.pack('<i', 0)  # Empty LocalizationId (length=0)

    # GatherableTextData Count/Offset - UE4 uncooked files (>= 401)
    # UE4 v522 >= 401, so GatherableTextData is present
    header += struct.pack('<i', 0)  # Count = 0
    header += struct.pack('<i', 0)  # Offset = 0

    # ExportCount, ExportOffset (Export BEFORE Import - correct UE order!)
    header += struct.pack('<i', 0)
    header += struct.pack('<i', 0)

    # ImportCount, ImportOffset
    header += struct.pack('<i', 0)
    header += struct.pack('<i', 0)

    # DependsOffset
    header += struct.pack('<i', 0)

    # SoftPackageReferences (UE4 >= 382, v522 >= 382)
    header += struct.pack('<i', 0)  # Count
    header += struct.pack('<i', 0)  # Offset

    # SearchableNames (UE4 >= 508, v522 >= 508)
    header += struct.pack('<i', 0)

    # ThumbnailTableOffset
    header += struct.pack('<i', 0)

    # Legacy Guid (UE4 files always have 16 bytes Legacy Guid before PersistentGuid)
    header += b'\x00' * 16  # Legacy Guid (FGuid)

    # PersistentGuid (UE4 >= 516, v522 >= 516)
    header += b'\x00' * 16  # FGuid

    # Generations
    header += struct.pack('<i', 0)  # GenerationCount = 0

    # SavedByEngineVersion (UE4 >= 334, v522 >= 334)
    header += struct.pack('<H', 5)  # Major
    header += struct.pack('<H', 0)  # Minor
    header += struct.pack('<H', 0)  # Patch
    header += struct.pack('<I', 0)  # Changelist
    header += struct.pack('<i', 0)  # Branch FString (empty)

    # CompatibleWithEngineVersion (UE4 >= 442, v522 >= 442)
    header += struct.pack('<H', 5)  # Major
    header += struct.pack('<H', 0)  # Minor
    header += struct.pack('<H', 0)  # Patch
    header += struct.pack('<I', 0)  # Changelist
    header += struct.pack('<i', 0)  # Branch FString (empty)

    # CompressionFlags
    header += struct.pack('<I', 0)

    # CompressedChunks (TArray)
    header += struct.pack('<i', 0)  # Count = 0

    # PackageSource
    header += struct.pack('<I', 0)

    # AdditionalPackagesToCook (TArray)
    header += struct.pack('<i', 0)  # Count = 0

    # NumTextureAllocations (legacy=-7 > -7, so NOT present)

    # AssetRegistryDataOffset
    header += struct.pack('<i', 0)

    # BulkDataStartOffset (i64)
    header += struct.pack('<q', 0)

    # WorldTileInfoDataOffset (UE4 >= 223, v522 >= 223)
    header += struct.pack('<i', 0)

    # ChunkIDs (UE4 >= 277, changed to array at 341, v522 >= 341)
    header += struct.pack('<i', 0)  # Count = 0

    # PreloadDependencies (UE4 >= 505, v522 >= 505)
    header += struct.pack('<i', -1)  # Count = -1
    header += struct.pack('<i', 0)   # Offset

    # Name table data
    name_offset = len(header)
    # UE4 v522 >= 502 (VER_UE4_NAME_HASHES_SERIALIZED), so hash bytes are present
    NAME_HASHES_SERIALIZED_VERSION = 502
    emit_name_hashes = True  # UE4 v522 >= 502
    for name in ["None", "TestName"]:
        name_bytes = name.encode('utf-8') + b'\x00'
        header += struct.pack('<i', len(name_bytes))
        header += name_bytes

        # Emit hash bytes for UE4 >= 502
        if emit_name_hashes:
            # NonCasePreservingHash (uint16) + CasePreservingHash (uint16) = 4 bytes
            header += struct.pack('<H', 0)  # NonCasePreservingHash
            header += struct.pack('<H', 0)  # CasePreservingHash

    total_header_size = len(header)

    # Update placeholders
    header_bytes = bytearray(header)
    struct.pack_into('<i', header_bytes, total_header_size_placeholder_pos, total_header_size)
    struct.pack_into('<i', header_bytes, name_offset_placeholder_pos, name_offset)

    os.write(fd, bytes(header_bytes))
    os.close(fd)

    try:
        result = parse_uasset(path)

        # KEY VERIFICATION: Parser must read TotalHeaderSize from correct position
        assert result.is_success, f"Parse failed: {result.errors}"
        assert result.summary is not None
        assert result.summary.total_header_size == total_header_size
        # PackageName must be correct (not garbage from wrong TotalHeaderSize position)
        assert result.summary.package_name == "None"
        # NameOffset must be valid
        assert result.summary.name_offset == name_offset
        # NameMap must have correct entries
        assert len(result.name_map) == 2
        assert result.name_map[0] == "None"
        assert result.name_map[1] == "TestName"
    finally:
        cleanup_test_file(path)


def test_real_lyra_character_default_file():
    """
    Test parsing real Lyra Character_Default.uasset.

    Integration test validating all Phase 1 fixes together.
    - LocalizationId FString correctly read for UE4 files
    - GatherableTextData Count/Offset correctly read
    - ImportOffset/ExportOffset are valid values (not garbage)

    This is the definitive test for Phase 1 completion.
    """
    lyra_path = "UnrealProjects/LyraStarterGame/Content/Characters/Character_Default.uasset"

    # Skip if file not available
    if not os.path.exists(lyra_path):
        pytest.skip(f"Lyra test file not found: {lyra_path}")

    result = parse_uasset(lyra_path)

    assert result.is_success, f"Lyra parse failed: {result.errors}"
    assert result.summary.legacy_file_version == -7
    assert result.summary.file_version_ue4 == 521

    # Verify offsets are valid (not garbage from missing LocalizationId/GatherableTextData)
    assert result.summary.name_offset > 0
    assert result.summary.import_offset > 0
    assert result.summary.export_offset > 0
    # Get file size for validation
    file_size = os.path.getsize(lyra_path)
    assert result.summary.name_offset < file_size
    assert result.summary.import_offset < file_size
    assert result.summary.export_offset < file_size

    # Verify maps populate
    assert len(result.name_map) > 100  # ~129 expected
    assert len(result.import_map) > 10  # ~20 expected
    assert len(result.export_map) > 20  # ~35 expected

    # Verify LocalizationId - should be a GUID string
    assert len(result.summary.localization_id) > 0


def test_ue4_localization_id_field_reading():
    """
    Test LocalizationId and GatherableTextData fields are read for UE4 files.

    Validates fix for 01-08 gap:
    - UE4 files (legacy=-7) read LocalizationId FString
    - UE4 files read GatherableTextData Count/Offset
    - ImportOffset is valid (not garbage from missing fields)

    RED test: This test will fail until read_package_summary() reads these fields.
    """
    names = ["TestClass", "TestObject"]
    imports = [
        (1, 0, 0, 2),  # ClassPackage=1 (TestClass), ClassName=0 (None), ObjectName=2 (TestObject)
    ]

    path = create_test_uasset(
        legacy_version=-7,
        ue4_version=522,
        ue5_version=0,
        names=names,
        imports=imports
    )

    try:
        result = parse_uasset(path)

        assert result.is_success, f"Parse failed: {result.errors}"
        assert result.summary is not None
        # LocalizationId should be populated (empty for synthetic files)
        assert hasattr(result.summary, 'localization_id')
        assert result.summary.localization_id == ""  # Empty for synthetic files
        # GatherableTextData fields should be populated (0 for synthetic files)
        assert result.summary.gatherable_text_data_count == 0
        assert result.summary.gatherable_text_data_offset == 0
        # ImportOffset should be valid (not garbage)
        assert result.summary.import_offset > 0
        assert result.summary.import_offset < result.summary.total_header_size
        # ImportMap should populate
        assert len(result.import_map) == len(imports)
    finally:
        cleanup_test_file(path)


def test_ue4_localization_id_and_gatherable_text_data_fields():
    """
    Test LocalizationId and GatherableTextData fields exist in PackageFileSummary.

    Validates fix for 01-08 gap:
    - PackageFileSummary dataclass has localization_id field (default empty string)
    - PackageFileSummary dataclass has gatherable_text_data_count/offset fields (default 0)

    RED test: This test will fail until fields are added to dataclass.
    """
    from uasset_read import PackageFileSummary

    # Create default summary - fields should exist with correct defaults
    summary = PackageFileSummary(
        tag=PACKAGE_FILE_TAG,
        legacy_file_version=-7,
        file_version_ue4=521
    )

    # LocalizationId should exist and default to empty string
    assert hasattr(summary, 'localization_id'), "PackageFileSummary missing localization_id field"
    assert summary.localization_id == "", "localization_id should default to empty string"

    # GatherableTextData fields should exist and default to 0
    assert hasattr(summary, 'gatherable_text_data_count'), "PackageFileSummary missing gatherable_text_data_count field"
    assert summary.gatherable_text_data_count == 0, "gatherable_text_data_count should default to 0"
    assert hasattr(summary, 'gatherable_text_data_offset'), "PackageFileSummary missing gatherable_text_data_offset field"
    assert summary.gatherable_text_data_offset == 0, "gatherable_text_data_offset should default to 0"


def test_utf16_length_overflow():
    """
    Test that UTF-16 strings with extreme length raise ParseError (WR-02 fix).

    Validates:
    - Parser rejects UTF-16 strings with length > 10M bytes
    - Prevents integer overflow in -length * 2 calculation
    - Error message contains "too large"
    """
    fd, path = tempfile.mkstemp(suffix='.uasset')

    # Create a file that triggers UTF-16 read with extreme length
    # UTF-16 is indicated by negative length in FString
    # length = -2147483648 (INT_MIN) would cause -length * 2 = 4GB overflow
    # We test with a more reasonable extreme value: -5_000_001 -> 10_000_002 bytes
    header = struct.pack('<I', PACKAGE_FILE_TAG)
    header += struct.pack('<i', -8)  # LegacyFileVersion
    header += struct.pack('<i', 864)  # LegacyUE3Version
    header += struct.pack('<i', 0)   # UE4 version
    header += struct.pack('<i', 500) # UE5 version (< 1004, no SavedHash)
    header += struct.pack('<i', 0)   # Licensee
    header += struct.pack('<I', 0)   # CustomVersions count
    # PackageName FString with negative length (UTF-16 marker)
    header += struct.pack('<i', -5_000_001)  # UTF-16 length indicator (> 10M bytes)

    os.write(fd, header)
    os.close(fd)

    try:
        result = parse_uasset(path)
        assert not result.is_success
        assert "too large" in result.errors[0]
    finally:
        cleanup_test_file(path)


# ============================================================================
# pytest 配置
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])