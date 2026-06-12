"""Object Resources 读取函数 — read_import_map, read_export_map, read_soft_object_paths。"""
from __future__ import annotations

import logging
from typing import List, Dict, Optional, Set

from uasset_read.archive import FArchive
from uasset_read.serializers.package_summary import PackageFileSummary
from uasset_read.constants import (
    PKG_FilterEditorOnly,
    MAX_IMPORT_COUNT, MAX_EXPORT_COUNT,
    UE5_REMOVE_OBJECT_EXPORT_PACKAGE_GUID, UE5_TRACK_OBJECT_EXPORT_IS_INHERITED,
    UE5_OPTIONAL_RESOURCES, UE5_SCRIPT_SERIALIZATION_OFFSET,
    UE5_ADD_SOFTOBJECTPATH_LIST,
    UE4_NON_OUTER_PACKAGE_IMPORT, UE4_LOAD_FOR_EDITOR_GAME,
    UE4_COOKED_ASSETS_IN_EDITOR_SUPPORT, UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS,
    UE4_TemplateIndex_IN_COOKED_EXPORTS, UE4_64BIT_EXPORTMAP_SERIALSIZES,
)
from uasset_read.exceptions import ParseError, ErrorContext
from .models import PackageIndex, ObjectImport, ObjectExport

logger = logging.getLogger(__name__)


def read_import_map(
    archive: FArchive,
    summary: PackageFileSummary,
    name_map: List[str]
) -> List[ObjectImport]:
    """读取导入表。"""
    # CR-05: 验证 import_count 范围
    if summary.import_count < 0:
        raise ParseError(f"负数导入计数: {summary.import_count}")
    if summary.import_count > MAX_IMPORT_COUNT:
        raise ParseError(f"导入计数 {summary.import_count} 超过最大值 {MAX_IMPORT_COUNT}")

    archive.seek(summary.import_offset)

    is_filter_editor_only = (summary.package_flags & PKG_FilterEditorOnly) != 0

    # UE4 version used for version gating (high value for UE5 assets)
    file_version = summary.file_version_ue4

    import_map: List[ObjectImport] = []
    for _ in range(summary.import_count):
        class_package = archive.read_name(name_map)
        class_name = archive.read_name(name_map)
        outer_index = PackageIndex(archive.read_i32())
        object_name = archive.read_name(name_map)

        # PackageName: VER_UE4_NON_OUTER_PACKAGE_IMPORT && !FilterEditorOnly
        # UE5 WITH_EDITORONLY_DATA: only present when file_version >= 519 and not filter-editor-only
        package_name: Optional[str] = None
        if file_version >= UE4_NON_OUTER_PACKAGE_IMPORT and not is_filter_editor_only:
            package_name = archive.read_name(name_map)

        # bImportOptional: UE5 >= 1003 (OPTIONAL_RESOURCES)
        b_import_optional = False
        if summary.file_version_ue5 >= UE5_OPTIONAL_RESOURCES:
            b_import_optional = archive.read_bool()

        import_map.append(ObjectImport(
            class_package=class_package, class_name=class_name,
            outer_index=outer_index, object_name=object_name,
            package_name=package_name, b_import_optional=b_import_optional
        ))
    return import_map


def read_soft_object_paths(
    archive: FArchive,
    summary: PackageFileSummary,
    name_map: List[str]
) -> List[Dict]:
    """读取 SoftObjectPaths 数组（UE5.7 专用）。"""
    if summary.soft_object_paths_count <= 0 or summary.soft_object_paths_offset <= 0:
        return []

    archive.seek(summary.soft_object_paths_offset)
    soft_refs = []
    for _ in range(summary.soft_object_paths_count):
        # UE5 >= 1007 format: double FName
        package_name = archive.read_name(name_map)
        asset_name = archive.read_name(name_map)
        asset_path = f"{package_name}.{asset_name}" if asset_name else package_name
        sub_path = archive.read_fstring()
        soft_refs.append({"asset_path": asset_path, "sub_path": sub_path})
    return soft_refs


def read_export_map(
    archive: FArchive,
    summary: PackageFileSummary,
    name_map: List[str]
) -> List[ObjectExport]:
    """读取导出表。"""
    # CR-05: 验证 export_count 范围
    if summary.export_count < 0:
        raise ParseError(f"负数导出计数: {summary.export_count}")
    if summary.export_count > MAX_EXPORT_COUNT:
        raise ParseError(f"导出计数 {summary.export_count} 超过最大值 {MAX_EXPORT_COUNT}")

    archive.seek(summary.export_offset)

    # UE4/UE5 version used for version gating
    file_version = summary.file_version_ue4

    export_map: List[ObjectExport] = []

    for export_idx in range(summary.export_count):
        object_name = ""
        try:
            class_index = PackageIndex(archive.read_i32())
            super_index = PackageIndex(archive.read_i32())

            # TemplateIndex: VER_UE4_TemplateIndex_IN_COOKED_EXPORTS (507)
            template_index = PackageIndex(0)
            if file_version >= UE4_TemplateIndex_IN_COOKED_EXPORTS:
                template_index = PackageIndex(archive.read_i32())

            outer_index = PackageIndex(archive.read_i32())
            object_name = archive.read_name(name_map)
            object_flags = archive.read_u32()

            # SerialSize/Offset: i32 before VER_UE4_64BIT_EXPORTMAP_SERIALSIZES (510), i64 after
            if file_version < UE4_64BIT_EXPORTMAP_SERIALSIZES:
                serial_size = archive.read_i32()
                serial_offset = archive.read_i32()
            else:
                serial_size = archive.read_i64()
                serial_offset = archive.read_i64()

            # CR-05: 验证 serial_size/serial_offset 非负
            # Tolerant: 负数时设为 0 并记录 warning，后续属性解析会因 size=0 被跳过
            if serial_size < 0:
                logger.warning(
                    "Export #%d serial_size 为负数: %d, 设为 0",
                    export_idx, serial_size,
                )
                serial_size = 0

            if serial_offset < 0:
                logger.warning(
                    "Export #%d serial_offset 为负数: %d, 跳过该 export",
                    export_idx, serial_offset,
                )
                serial_offset = 0
                serial_size = 0

            # bool flags (always present)
            b_forced_export = archive.read_bool()
            b_not_for_client = archive.read_bool()
            b_not_for_server = archive.read_bool()

            # PackageGuid: removed in UE5 1005
            package_guid = ""
            if summary.file_version_ue5 < UE5_REMOVE_OBJECT_EXPORT_PACKAGE_GUID:
                guid_bytes = archive.read(16)
                package_guid = guid_bytes.hex()

            # bIsInheritedInstance: UE5 >= 1006
            b_is_inherited_instance = False
            if summary.file_version_ue5 >= UE5_TRACK_OBJECT_EXPORT_IS_INHERITED:
                b_is_inherited_instance = archive.read_bool()

            package_flags = archive.read_u32()

            # bNotAlwaysLoadedForEditorGame: VER_UE4_LOAD_FOR_EDITOR_GAME (364)
            b_not_always_loaded_for_editor_game = True
            if file_version >= UE4_LOAD_FOR_EDITOR_GAME:
                b_not_always_loaded_for_editor_game = archive.read_bool()

            # bIsAsset: VER_UE4_COOKED_ASSETS_IN_EDITOR_SUPPORT (484)
            b_is_asset = False
            if file_version >= UE4_COOKED_ASSETS_IN_EDITOR_SUPPORT:
                b_is_asset = archive.read_bool()

            # bGeneratePublicHash: UE5 >= 1003 (OPTIONAL_RESOURCES)
            b_generate_public_hash = False
            if summary.file_version_ue5 >= UE5_OPTIONAL_RESOURCES:
                b_generate_public_hash = archive.read_bool()

            # Dependency arrays: VER_UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS (506)
            first_export_dependency = -1
            serialization_before_serialization_deps = 0
            create_before_serialization_deps = 0
            serialization_before_create_deps = 0
            create_before_create_deps = 0
            if file_version >= UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS:
                first_export_dependency = archive.read_i32()
                serialization_before_serialization_deps = archive.read_i32()
                create_before_serialization_deps = archive.read_i32()
                serialization_before_create_deps = archive.read_i32()
                create_before_create_deps = archive.read_i32()

            # ScriptSerialization offsets (UE5 >= 1010, only for versioned properties)
            script_serialization_start_offset = 0
            script_serialization_end_offset = 0
            from uasset_read.constants import PKG_UnversionedProperties
            uses_unversioned = (summary.package_flags & PKG_UnversionedProperties) != 0
            if (
                not uses_unversioned
                and summary.file_version_ue5 >= UE5_SCRIPT_SERIALIZATION_OFFSET
            ):
                script_serialization_start_offset = archive.read_i64()
                script_serialization_end_offset = archive.read_i64()
                # CR-05: 验证非负（Tolerant: 负数时设为 0 并记录 warning）
                if script_serialization_start_offset < 0:
                    logger.warning(
                        "Export #%d ScriptSerializationStartOffset 为负数: %d, 设为 0",
                        export_idx, script_serialization_start_offset,
                    )
                    script_serialization_start_offset = 0
                if script_serialization_end_offset < 0:
                    logger.warning(
                        "Export #%d ScriptSerializationEndOffset 为负数: %d, 设为 0",
                        export_idx, script_serialization_end_offset,
                    )
                    script_serialization_end_offset = 0

            export_map.append(ObjectExport(
                class_index=class_index, super_index=super_index,
                template_index=template_index, outer_index=outer_index,
                object_name=object_name, object_flags=object_flags,
                serial_size=serial_size, serial_offset=serial_offset,
                b_forced_export=b_forced_export,
                b_not_for_client=b_not_for_client,
                b_not_for_server=b_not_for_server,
                b_is_inherited_instance=b_is_inherited_instance,
                package_flags=package_flags,
                b_not_always_loaded_for_editor_game=b_not_always_loaded_for_editor_game,
                b_is_asset=b_is_asset,
                b_generate_public_hash=b_generate_public_hash,
                script_serialization_end_offset=script_serialization_end_offset,
                script_serialization_start_offset=script_serialization_start_offset,
                first_export_dependency=first_export_dependency,
                serialization_before_serialization_dependencies=serialization_before_serialization_deps,
                create_before_serialization_dependencies=create_before_serialization_deps,
                serialization_before_create_dependencies=serialization_before_create_deps,
                create_before_create_dependencies=create_before_create_deps,
                guid=package_guid,
            ))
        except Exception as e:
            context = ErrorContext(
                offset=archive.tell(), phase="export_map", operation="read_export",
                context_name=object_name, export_index=export_idx
            )
            raise ParseError(
                f"导出表解析失败（导出 #{export_idx}）：{str(e)}",
                partial_result={"export_map": export_map},
                context=context
            )
    return export_map
