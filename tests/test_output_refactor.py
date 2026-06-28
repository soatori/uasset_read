"""输出层全量字段重构测试 — IR→Builder→Renderer 流水线 (#236)。

验证 PackageHeaderIR、ExportIR、ImportIR 新增字段的正确性。
"""
from __future__ import annotations

import pytest
from dataclasses import fields as dc_fields

from uasset_read.models.ir import (
    PackageHeaderIR,
    ExportIR,
    ImportIR,
    ExportRawIR,
    PackageIR,
    LinkerSummaryIR,
)


# =============================================================================
# PackageHeaderIR 字段完整性测试
# =============================================================================

class TestPackageHeaderIRFields:
    """PackageHeaderIR 应包含与 UE PackageFileSummary 完全对齐的字段集。"""

    def test_has_all_file_version_fields(self):
        header = PackageHeaderIR(
            package_name="", package_class="", package_flags=0,
            total_export_count=0, total_import_count=0, ue_version="5.x",
        )
        assert header.file_version_ue4 == 0
        assert header.file_version_ue5 == 0
        assert header.file_version_licensee == 0

    def test_has_all_header_size_fields(self):
        header = PackageHeaderIR(
            package_name="", package_class="", package_flags=0,
            total_export_count=0, total_import_count=0, ue_version="5.x",
        )
        assert header.total_header_size == 0
        assert header.custom_versions == []
        assert header.folder_name == ""

    def test_has_name_table_fields(self):
        header = PackageHeaderIR(
            package_name="", package_class="", package_flags=0,
            total_export_count=0, total_import_count=0, ue_version="5.x",
        )
        assert header.name_count == 0
        assert header.name_offset == 0

    def test_has_soft_object_paths_fields(self):
        header = PackageHeaderIR(
            package_name="", package_class="", package_flags=0,
            total_export_count=0, total_import_count=0, ue_version="5.x",
        )
        assert header.soft_object_paths_count == 0
        assert header.soft_object_paths_offset == 0

    def test_has_localization_fields(self):
        header = PackageHeaderIR(
            package_name="", package_class="", package_flags=0,
            total_export_count=0, total_import_count=0, ue_version="5.x",
        )
        assert header.localization_id == ""
        assert header.gatherable_text_data_count == 0
        assert header.gatherable_text_data_offset == 0

    def test_has_export_import_table_fields(self):
        header = PackageHeaderIR(
            package_name="", package_class="", package_flags=0,
            total_export_count=0, total_import_count=0, ue_version="5.x",
        )
        assert header.export_count == 0
        assert header.export_offset == 0
        assert header.import_count == 0
        assert header.import_offset == 0

    def test_has_metadata_depends_fields(self):
        header = PackageHeaderIR(
            package_name="", package_class="", package_flags=0,
            total_export_count=0, total_import_count=0, ue_version="5.x",
        )
        assert header.metadata_offset == 0
        assert header.depends_offset == 0

    def test_has_soft_package_references_fields(self):
        header = PackageHeaderIR(
            package_name="", package_class="", package_flags=0,
            total_export_count=0, total_import_count=0, ue_version="5.x",
        )
        assert header.soft_package_references_count == 0
        assert header.soft_package_references_offset == 0

    def test_has_searchable_names_thumbnail_fields(self):
        header = PackageHeaderIR(
            package_name="", package_class="", package_flags=0,
            total_export_count=0, total_import_count=0, ue_version="5.x",
        )
        assert header.searchable_names_offset == 0
        assert header.thumbnail_table_offset == 0

    def test_has_import_type_hierarchies_fields(self):
        header = PackageHeaderIR(
            package_name="", package_class="", package_flags=0,
            total_export_count=0, total_import_count=0, ue_version="5.x",
        )
        assert header.import_type_hierarchies_count == 0
        assert header.import_type_hierarchies_offset == 0

    def test_has_persistent_guid_and_generations(self):
        header = PackageHeaderIR(
            package_name="", package_class="", package_flags=0,
            total_export_count=0, total_import_count=0, ue_version="5.x",
        )
        assert header.persistent_guid == "00000000000000000000000000000000"
        assert header.generations == []

    def test_has_engine_version_fields(self):
        header = PackageHeaderIR(
            package_name="", package_class="", package_flags=0,
            total_export_count=0, total_import_count=0, ue_version="5.x",
        )
        assert header.saved_by_engine_version == ""
        assert header.compatible_with_engine_version == ""

    def test_has_compression_source_fields(self):
        header = PackageHeaderIR(
            package_name="", package_class="", package_flags=0,
            total_export_count=0, total_import_count=0, ue_version="5.x",
        )
        assert header.compression_flags == 0
        assert header.package_source == 0

    def test_has_bulk_data_world_tile_fields(self):
        header = PackageHeaderIR(
            package_name="", package_class="", package_flags=0,
            total_export_count=0, total_import_count=0, ue_version="5.x",
        )
        assert header.bulk_data_start_offset == 0
        assert header.world_tile_info_data_offset == 0
        assert header.chunk_ids == []

    def test_has_preload_dependency_fields(self):
        header = PackageHeaderIR(
            package_name="", package_class="", package_flags=0,
            total_export_count=0, total_import_count=0, ue_version="5.x",
        )
        assert header.preload_dependency_count == 0
        assert header.preload_dependency_offset == 0

    def test_has晚期_fields(self):
        header = PackageHeaderIR(
            package_name="", package_class="", package_flags=0,
            total_export_count=0, total_import_count=0, ue_version="5.x",
        )
        assert header.names_referenced_from_export_data_count == 0
        assert header.payload_toc_offset == 0
        assert header.data_resource_offset == 0

    def test_custom_versions_with_data(self):
        header = PackageHeaderIR(
            package_name="", package_class="", package_flags=0,
            total_export_count=0, total_import_count=0, ue_version="5.x",
            custom_versions=[
                {"guid": "abc123", "version": 1},
                {"guid": "def456", "version": 2},
            ],
        )
        assert len(header.custom_versions) == 2
        assert header.custom_versions[0]["guid"] == "abc123"
        assert header.custom_versions[1]["version"] == 2

    def test_generations_with_data(self):
        header = PackageHeaderIR(
            package_name="", package_class="", package_flags=0,
            total_export_count=0, total_import_count=0, ue_version="5.x",
            generations=[
                {"export_count": 10, "name_count": 5},
                {"export_count": 20, "name_count": 8},
            ],
        )
        assert len(header.generations) == 2
        assert header.generations[0]["export_count"] == 10

    def test_total_field_count(self):
        """PackageHeaderIR 应至少有 35 个字段（核心 + 新增）。"""
        header_fields = dc_fields(PackageHeaderIR)
        assert len(header_fields) >= 35


# =============================================================================
# ExportIR 新增直接字段测试
# =============================================================================

class TestExportIRDirectFields:
    """ExportIR 应包含从 ExportRawIR 提升的直接访问字段。"""

    def _make_export(self, **kwargs) -> ExportIR:
        defaults = dict(
            index=0, object_name="Test", object_class="Actor",
            serial_size=100, outer_index_resolved=None,
            super_index_resolved=None, parent_class=None,
            properties=[], graphs=[], bulk_data=None,
        )
        defaults.update(kwargs)
        return ExportIR(**defaults)

    def test_has_template_index(self):
        export = self._make_export(template_index=42)
        assert export.template_index == 42

    def test_has_object_flags(self):
        export = self._make_export(object_flags=0x00000040)
        assert export.object_flags == 0x00000040

    def test_has_package_flags(self):
        export = self._make_export(package_flags=1)
        assert export.package_flags == 1

    def test_has_b_forced_export(self):
        export = self._make_export(b_forced_export=True)
        assert export.b_forced_export is True

    def test_has_b_not_for_client(self):
        export = self._make_export(b_not_for_client=True)
        assert export.b_not_for_client is True

    def test_has_b_not_for_server(self):
        export = self._make_export(b_not_for_server=True)
        assert export.b_not_for_server is True

    def test_has_b_is_asset(self):
        export = self._make_export(b_is_asset=True)
        assert export.b_is_asset is True

    def test_has_b_generate_public_hash(self):
        export = self._make_export(b_generate_public_hash=True)
        assert export.b_generate_public_hash is True

    def test_has_b_not_always_loaded_for_editor_game(self):
        export = self._make_export(b_not_always_loaded_for_editor_game=False)
        assert export.b_not_always_loaded_for_editor_game is False

    def test_has_guid(self):
        export = self._make_export(guid="abc123def456")
        assert export.guid == "abc123def456"

    def test_defaults_are_sensible(self):
        export = self._make_export()
        assert export.template_index == 0
        assert export.object_flags == 0
        assert export.package_flags == 0
        assert export.b_forced_export is False
        assert export.b_not_for_client is False
        assert export.b_not_for_server is False
        assert export.b_is_asset is False
        assert export.b_generate_public_hash is False
        assert export.b_not_always_loaded_for_editor_game is True
        assert export.guid == ""

    def test_direct_fields_coexist_with_ue_export_raw(self):
        """直接字段与 ue_export_raw 共存，值应一致。"""
        raw = ExportRawIR(
            template_index=7, object_flags=0x10, package_flags=2,
            b_forced_export=True, b_not_for_client=True, b_not_for_server=False,
            b_is_asset=True, b_generate_public_hash=False,
            b_not_always_loaded_for_editor_game=True, guid="xyz",
        )
        export = self._make_export(
            template_index=raw.template_index,
            object_flags=raw.object_flags,
            package_flags=raw.package_flags,
            b_forced_export=raw.b_forced_export,
            b_not_for_client=raw.b_not_for_client,
            b_not_for_server=raw.b_not_for_server,
            b_is_asset=raw.b_is_asset,
            b_generate_public_hash=raw.b_generate_public_hash,
            b_not_always_loaded_for_editor_game=raw.b_not_always_loaded_for_editor_game,
            guid=raw.guid,
            ue_export_raw=raw,
        )
        assert export.template_index == export.ue_export_raw.template_index
        assert export.object_flags == export.ue_export_raw.object_flags
        assert export.guid == export.ue_export_raw.guid


# =============================================================================
# ImportIR 新增字段测试
# =============================================================================

class TestImportIRFields:
    """ImportIR 应包含 outer_index_resolved、package_name、b_import_optional。"""

    def test_has_outer_index_resolved(self):
        imp = ImportIR(index=0, class_package="Core", class_name="Object",
                       object_name="Test", outer_index_resolved="/Game/Map")
        assert imp.outer_index_resolved == "/Game/Map"

    def test_has_package_name(self):
        imp = ImportIR(index=0, class_package="Core", class_name="Object",
                       object_name="Test", package_name="/Engine/Engine")
        assert imp.package_name == "/Engine/Engine"

    def test_has_b_import_optional(self):
        imp = ImportIR(index=0, class_package="Core", class_name="Object",
                       object_name="Test", b_import_optional=True)
        assert imp.b_import_optional is True

    def test_defaults(self):
        imp = ImportIR(index=0, class_package="", class_name="",
                       object_name="")
        assert imp.outer_index_resolved is None
        assert imp.package_name == ""
        assert imp.b_import_optional is False

    def test_total_field_count(self):
        """ImportIR 应至少有 9 个字段。"""
        imp_fields = dc_fields(ImportIR)
        assert len(imp_fields) >= 9


# =============================================================================
# IR Builder 集成测试
# =============================================================================

class TestIRBuilderHeaderPopulation:
    """验证 _build_header 正确从 summary 提取所有字段。"""

    def test_header_populates_file_versions(self):
        from unittest.mock import MagicMock
        from uasset_read.ir_builder import _build_header

        summary = MagicMock()
        summary.package_name = "TestPkg"
        summary.package_class = None
        summary.package_flags = 0
        summary.export_count = 5
        summary.import_count = 3
        summary.file_version_ue4 = 522
        summary.file_version_ue5 = 1000
        summary.file_version_licensee = 0
        summary.saved_hash = b'\x00' * 20
        summary.total_header_size = 512
        summary.custom_versions = []
        summary.folder_name = ""
        summary.name_count = 10
        summary.name_offset = 256
        summary.soft_object_paths_count = 0
        summary.soft_object_paths_offset = 0
        summary.localization_id = ""
        summary.gatherable_text_data_count = 0
        summary.gatherable_text_data_offset = 0
        summary.export_offset = 1024
        summary.import_offset = 768
        summary.metadata_offset = 0
        summary.depends_offset = 2048
        summary.soft_package_references_count = 0
        summary.soft_package_references_offset = 0
        summary.searchable_names_offset = 0
        summary.thumbnail_table_offset = 0
        summary.import_type_hierarchies_count = 0
        summary.import_type_hierarchies_offset = 0
        summary.persistent_guid = "abc123"
        summary.generations = []
        summary.saved_by_engine_version = MagicMock(major=5, minor=4, patch=0, changelist=0, branch="++UE5+Release-5.4")
        summary.compatible_with_engine_version = MagicMock(major=5, minor=4, patch=0, changelist=0, branch="++UE5+Main")
        summary.compression_flags = 0
        summary.package_source = 12345
        summary.bulk_data_start_offset = 0
        summary.world_tile_info_data_offset = 0
        summary.chunk_ids = []
        summary.preload_dependency_count = 0
        summary.preload_dependency_offset = 0
        summary.names_referenced_from_export_data_count = 0
        summary.payload_toc_offset = 0
        summary.data_resource_offset = 0

        result = MagicMock()
        result.summary = summary
        result.version_container = MagicMock()
        result.version_container.is_ue5 = True
        result.version_container.get_ue_version_string.return_value = "5.4.0-0"

        header = _build_header(result)
        assert header.file_version_ue4 == 522
        assert header.file_version_ue5 == 1000
        assert header.total_header_size == 512
        assert header.name_count == 10
        assert header.name_offset == 256
        assert header.export_offset == 1024
        assert header.import_offset == 768
        assert header.depends_offset == 2048
        assert header.persistent_guid == "abc123"
        assert header.package_source == 12345

    def test_header_engine_version_string(self):
        from unittest.mock import MagicMock
        from uasset_read.ir_builder import _build_header

        summary = MagicMock()
        summary.package_name = ""
        summary.package_class = None
        summary.package_flags = 0
        summary.export_count = 0
        summary.import_count = 0
        summary.saved_hash = b''
        summary.file_version_ue4 = 0
        summary.file_version_ue5 = 0
        summary.file_version_licensee = 0
        summary.total_header_size = 0
        summary.custom_versions = []
        summary.folder_name = ""
        summary.name_count = 0
        summary.name_offset = 0
        summary.soft_object_paths_count = 0
        summary.soft_object_paths_offset = 0
        summary.localization_id = ""
        summary.gatherable_text_data_count = 0
        summary.gatherable_text_data_offset = 0
        summary.export_offset = 0
        summary.import_offset = 0
        summary.metadata_offset = 0
        summary.depends_offset = 0
        summary.soft_package_references_count = 0
        summary.soft_package_references_offset = 0
        summary.searchable_names_offset = 0
        summary.thumbnail_table_offset = 0
        summary.import_type_hierarchies_count = 0
        summary.import_type_hierarchies_offset = 0
        summary.persistent_guid = ""
        summary.generations = []
        summary.saved_by_engine_version = MagicMock(major=5, minor=4, patch=2, changelist=12345, branch="++UE5+Release-5.4")
        summary.compatible_with_engine_version = MagicMock(major=5, minor=4, patch=0, changelist=100, branch="++UE5+Main")
        summary.compression_flags = 0
        summary.package_source = 0
        summary.bulk_data_start_offset = 0
        summary.world_tile_info_data_offset = 0
        summary.chunk_ids = []
        summary.preload_dependency_count = 0
        summary.preload_dependency_offset = 0
        summary.names_referenced_from_export_data_count = 0
        summary.payload_toc_offset = 0
        summary.data_resource_offset = 0

        result = MagicMock()
        result.summary = summary
        result.version_container = MagicMock()
        result.version_container.is_ue5 = True
        result.version_container.get_ue_version_string.return_value = "5.4.2-12345"

        header = _build_header(result)
        assert "5.4.2" in header.saved_by_engine_version
        assert "12345" in header.saved_by_engine_version
        assert "5.4.0" in header.compatible_with_engine_version


class TestIRBuilderExportDirectFields:
    """验证 _build_export_ir 填充 ExportIR 直接字段。"""

    def test_export_direct_fields_populated(self):
        from unittest.mock import MagicMock
        from uasset_read.ir_builder import _build_export_ir

        export = MagicMock()
        export.object_name = "TestExport"
        export.serial_size = 200
        export.outer_index = MagicMock(index=-1)
        export.super_index = MagicMock(index=0)
        export.class_index = MagicMock(index=1)
        export.template_index = MagicMock(index=5)
        export.object_flags = 0x00000040
        export.package_flags = 0
        export.b_forced_export = False
        export.b_not_for_client = False
        export.b_not_for_server = False
        export.b_is_asset = True
        export.b_generate_public_hash = False
        export.b_not_always_loaded_for_editor_game = True
        export.guid = "test-guid-1234"
        export.properties = []
        export.graphs = []
        export.bulk_data_header = None
        export._asset_type_data = None
        export.parse_status = "success"
        export.fallback_reason = None
        export.error_message = None
        export.transforms = {}
        export.custom_data = {}

        result = MagicMock()
        result.linker = None
        result.import_map = []
        result.export_map = []
        result.blueprint = None

        export_ir = _build_export_ir(0, export, result)
        assert export_ir.template_index == 5
        assert export_ir.object_flags == 0x00000040
        assert export_ir.b_is_asset is True
        assert export_ir.guid == "test-guid-1234"
        assert export_ir.ue_export_raw is not None
        assert export_ir.ue_export_raw.template_index == 5
        assert export_ir.ue_export_raw.object_flags == 0x00000040


class TestIRBuilderImportFields:
    """验证 _build_imports 返回 ImportIR 对象。"""

    def test_imports_are_import_ir_objects(self):
        from unittest.mock import MagicMock
        from uasset_read.ir_builder import _build_imports

        imp = MagicMock()
        imp.class_package = "/Engine/Core"
        imp.class_name = "Object"
        imp.object_name = "TestImport"
        imp.outer_index = MagicMock(index=-1)
        imp.is_asset = False
        imp.package_flags = 0
        imp.package_name = "/Engine/Core"
        imp.b_import_optional = False

        result = MagicMock()
        result.import_map = [imp]
        result.linker = None

        imports = _build_imports(result)
        assert len(imports) == 1
        assert isinstance(imports[0], ImportIR)
        assert imports[0].class_package == "/Engine/Core"
        assert imports[0].class_name == "Object"
        assert imports[0].object_name == "TestImport"
        assert imports[0].package_name == "/Engine/Core"
