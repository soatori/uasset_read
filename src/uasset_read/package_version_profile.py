"""
PackageVersionProfile — 版本特性配置，区分 UE4/UE5 序列化差异。

核心职责：
- 封装引擎家族（ue4 / ue5）和版本阈值
- 提供字段存在性判断（legacy_file_version, file_version_ue5, saved_hash, etc.）
- 提供 PropertyTag 格式、SoftObjectPath 模式、ObjectExport 布局判断
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PackageVersionProfile:
    """版本特性配置文件。

    Attributes:
        engine_family: "ue4" | "ue5"
        legacy_file_version: LegacyFileVersion 字段值（-6, -7, -8, -9）
        file_version_ue4: FileVersionUE4 字段值
        file_version_ue5: FileVersionUE5 字段值（UE4 资产为 0）
        property_tag_format: "legacy_fname_type" (UE4) | "ue5_property_type_name" (UE5)
        soft_object_path_mode: "inline" (UE4) | "header_indexed" (UE5.1+)
        object_export_layout: "ue4" | "ue5"
    """

    engine_family: str  # "ue4" | "ue5"
    legacy_file_version: int = 0
    file_version_ue4: int = 0
    file_version_ue5: int = 0
    property_tag_format: str = "legacy_fname_type"
    soft_object_path_mode: str = "inline"
    object_export_layout: str = "ue4"

    # ---- 字段存在性标志 ----
    has_file_version_ue5: bool = False
    has_saved_hash: bool = False
    has_soft_object_paths: bool = False
    has_cell_exports: bool = False
    has_metadata_offset: bool = False
    has_import_type_hierarchies: bool = False
    has_names_referenced_from_export: bool = False
    has_payload_toc: bool = False
    has_data_resource_offset: bool = False
    has_owner_persistent_guid: bool = False

    @property
    def is_ue4(self) -> bool:
        return self.engine_family == "ue4"

    @property
    def is_ue5(self) -> bool:
        return self.engine_family == "ue5"


def build_version_profile(
    legacy_file_version: int,
    file_version_ue4: int,
    file_version_ue5: int,
) -> PackageVersionProfile:
    """根据文件头版本字段构建版本特性配置。

    Args:
        legacy_file_version: LegacyFileVersion 值
        file_version_ue4: FileVersionUE4 值
        file_version_ue5: FileVersionUE5 值（UE4 资产为 0）

    Returns:
        PackageVersionProfile 实例
    """
    # 确定引擎家族
    if file_version_ue5 > 0 or legacy_file_version <= -8:
        engine_family = "ue5"
    else:
        engine_family = "ue4"

    # UE5 常量引用
    from uasset_read.constants import (
        UE5_ADD_SOFTOBJECTPATH_LIST,
        UE5_PACKAGE_SAVED_HASH,
        UE5_VERSE_CELLS,
        UE5_METADATA_SERIALIZATION_OFFSET,
        UE5_IMPORT_TYPE_HIERARCHIES,
        UE5_NAMES_REFERENCED_FROM_EXPORT_DATA,
        UE5_PAYLOAD_TOC,
        UE5_DATA_RESOURCES,
        UE5_PROPERTY_TAG_COMPLETE_TYPE_NAME,
    )
    from uasset_read.constants import (
        UE4_NON_OUTER_PACKAGE_IMPORT,
        UE4_ADDED_PACKAGE_OWNER,
    )

    # 判断字段存在性
    has_file_version_ue5 = legacy_file_version <= -8
    has_saved_hash = file_version_ue5 >= UE5_PACKAGE_SAVED_HASH if has_file_version_ue5 else False
    has_soft_object_paths = file_version_ue5 >= UE5_ADD_SOFTOBJECTPATH_LIST if has_file_version_ue5 else False
    has_cell_exports = file_version_ue5 >= UE5_VERSE_CELLS if has_file_version_ue5 else False
    has_metadata_offset = file_version_ue5 >= UE5_METADATA_SERIALIZATION_OFFSET if has_file_version_ue5 else False
    has_import_type_hierarchies = file_version_ue5 >= UE5_IMPORT_TYPE_HIERARCHIES if has_file_version_ue5 else False
    has_names_referenced_from_export = file_version_ue5 >= UE5_NAMES_REFERENCED_FROM_EXPORT_DATA if has_file_version_ue5 else True  # UE5 始终存在
    has_payload_toc = file_version_ue5 >= UE5_PAYLOAD_TOC if has_file_version_ue5 else True  # UE5 始终存在
    has_data_resource_offset = file_version_ue5 >= UE5_DATA_RESOURCES if has_file_version_ue5 else False
    has_owner_persistent_guid = file_version_ue4 >= UE4_ADDED_PACKAGE_OWNER or (legacy_file_version in (-8, -7))

    # PropertyTag 格式
    if has_file_version_ue5 and file_version_ue5 >= UE5_PROPERTY_TAG_COMPLETE_TYPE_NAME:
        property_tag_format = "ue5_property_type_name"
    else:
        property_tag_format = "legacy_fname_type"

    # SoftObjectPath 模式
    if has_soft_object_paths:
        soft_object_path_mode = "header_indexed"
    else:
        soft_object_path_mode = "inline"

    # ObjectExport 布局
    if engine_family == "ue5":
        object_export_layout = "ue5"
    else:
        object_export_layout = "ue4"

    return PackageVersionProfile(
        engine_family=engine_family,
        legacy_file_version=legacy_file_version,
        file_version_ue4=file_version_ue4,
        file_version_ue5=file_version_ue5,
        property_tag_format=property_tag_format,
        soft_object_path_mode=soft_object_path_mode,
        object_export_layout=object_export_layout,
        has_file_version_ue5=has_file_version_ue5,
        has_saved_hash=has_saved_hash,
        has_soft_object_paths=has_soft_object_paths,
        has_cell_exports=has_cell_exports,
        has_metadata_offset=has_metadata_offset,
        has_import_type_hierarchies=has_import_type_hierarchies,
        has_names_referenced_from_export=has_names_referenced_from_export,
        has_payload_toc=has_payload_toc,
        has_data_resource_offset=has_data_resource_offset,
        has_owner_persistent_guid=has_owner_persistent_guid,
    )
