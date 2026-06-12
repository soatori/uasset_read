"""Package Summary 数据类型定义。"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List


@dataclass
class GenerationInfo:
    """FGenerationInfo 版本世代信息。"""
    export_count: int = 0
    name_count: int = 0


@dataclass
class EngineVersion:
    """FEngineVersion 引擎版本信息。"""
    major: int = 0
    minor: int = 0
    patch: int = 0
    changelist: int = 0
    branch: str = ""


@dataclass
class CustomVersion:
    """自定义版本（GUID + 版本号）。"""
    guid: str
    version: int


@dataclass
class PackageFileSummary:
    """PackageFileSummary 文件头。"""
    tag: int
    legacy_file_version: int
    file_version_ue4: int = 0
    file_version_ue5: int = 0
    file_version_licensee: int = 0
    saved_hash: bytes = field(default_factory=lambda: b'')
    total_header_size: int = 0
    custom_versions: List[CustomVersion] = field(default_factory=list)
    package_name: str = ""
    package_flags: int = 0
    name_count: int = 0
    name_offset: int = 0
    soft_object_paths_count: int = 0
    soft_object_paths_offset: int = 0
    localization_id: str = ""
    gatherable_text_data_count: int = 0
    gatherable_text_data_offset: int = 0
    export_count: int = 0
    export_offset: int = 0
    import_count: int = 0
    import_offset: int = 0
    cell_export_count: int = 0
    cell_export_offset: int = 0
    cell_import_count: int = 0
    cell_import_offset: int = 0
    metadata_offset: int = 0
    depends_offset: int = 0
    soft_package_references_count: int = 0
    soft_package_references_offset: int = 0
    searchable_names_offset: int = 0
    thumbnail_table_offset: int = 0
    import_type_hierarchies_count: int = 0
    import_type_hierarchies_offset: int = 0
    persistent_guid: str = ""
    owner_persistent_guid: str = ""  # 16 bytes GUID (UE4 519 or legacy -7/-8)
    compressed_chunks: list = field(default_factory=list)  # 已废弃，保留用于偏移对齐
    additional_packages_to_cook: List[str] = field(default_factory=list)  # 已废弃
    generations: List[GenerationInfo] = field(default_factory=list)
    saved_by_engine_version: EngineVersion = field(default_factory=EngineVersion)
    compatible_with_engine_version: EngineVersion = field(default_factory=EngineVersion)
    compression_flags: int = 0
    package_source: int = 0
    asset_registry_data_offset: int = 0
    bulk_data_start_offset: int = 0
    world_tile_info_data_offset: int = 0
    chunk_ids: List[str] = field(default_factory=list)
    preload_dependency_count: int = -1   # UE sentinel: -1 = absent
    preload_dependency_offset: int = 0
    names_referenced_from_export_data_count: int = 0
    payload_toc_offset: int = -1         # UE: INDEX_NONE = -1
    data_resource_offset: int = -1       # UE: -1 = absent
    depends_map: List[List[int]] = field(default_factory=list)
    preload_dependencies: List[int] = field(default_factory=list)

    def get_custom_version(self, guid: str, default: int = 0) -> int:
        """查找 CustomVersion 版本值。"""
        normalized_guid = guid.replace("-", "").lower()
        for cv in self.custom_versions:
            if cv.guid == normalized_guid:
                return cv.version
        return default

    @property
    def has_preload_dependencies(self) -> bool:
        """是否包含预加载依赖表（区分 absent 和 empty）。"""
        return self.preload_dependency_count >= 0

    @property
    def has_payload_toc(self) -> bool:
        """是否包含 PayloadToc（-1 = absent）。"""
        return self.payload_toc_offset >= 0

    @property
    def has_data_resources(self) -> bool:
        """是否包含 DataResource（-1 = absent）。"""
        return self.data_resource_offset >= 0
