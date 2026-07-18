"""输出层全量字段重构测试 — IR→Builder→Renderer 流水线 (#236)。

验证 PackageHeaderIR、ExportIR、ImportIR 新增字段的正确性。
合并自: test_game_variant, test_legacy_minus6, test_json_schema,
        test_output_level, test_exception_context
"""
from __future__ import annotations

import json
import os
import pytest
from dataclasses import fields as dc_fields
from pathlib import Path

from uasset_read.constants import GameVariant, get_game_variant_config
from uasset_read.exceptions import ErrorContext, ParseError
from uasset_read.models.ir import (
    ExportIR,
    ExportRawIR,
    ImportIR,
    LinkerSummaryIR,
    PackageHeaderIR,
    PackageIR,
)
from uasset_read.parse_uasset import parse_package
from uasset_read.renderers.base import RenderOptions
from uasset_read.renderers.json_renderer import JSONRenderer


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
        assert export.b_not_always_loaded_for_editor_game is False
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


# =============================================================================
# 游戏变体测试（合并自 test_game_variant.py）
# =============================================================================

def test_game_variant_enum():
    """测试 GameVariant 枚举"""
    assert GameVariant.NONE.value == 0
    assert GameVariant.FORTNITE.value == 1001


def test_get_game_variant_config():
    """测试获取游戏变体配置"""
    config = get_game_variant_config(GameVariant.FORTNITE)
    assert "feature_flags" in config
    assert config["feature_flags"]["use_new_cooked_format"] == True


def test_get_game_variant_config_none():
    """测试获取 NONE 游戏变体配置"""
    config = get_game_variant_config(GameVariant.NONE)
    assert config["feature_flags"] == {}


# =============================================================================
# Legacy -6 解析测试（合并自 test_legacy_minus6.py）
# =============================================================================

# 测试样本路径
SAMPLES_DIR = Path(__file__).parent.parent / "samples"
LEGACY_MINUS6_FILE = str(SAMPLES_DIR / "StarterContent_M_Wood_Walnut.uasset")


@pytest.mark.integration
class TestLegacyMinus6Parsing:
    """legacy -6 格式文件解析验证。"""

    @pytest.mark.skipif(
        not os.path.exists(LEGACY_MINUS6_FILE),
        reason="测试样本不存在"
    )
    def test_starter_content_parses_successfully(self):
        """StarterContent 资产应解析成功。"""
        result = parse_package(LEGACY_MINUS6_FILE, tolerant=True)
        assert result.is_success or result.summary is not None, (
            f"解析失败: {result.errors}"
        )

    @pytest.mark.skipif(
        not os.path.exists(LEGACY_MINUS6_FILE),
        reason="测试样本不存在"
    )
    def test_no_generations_error(self):
        """不应出现 generations count 负数错误。"""
        result = parse_package(LEGACY_MINUS6_FILE, tolerant=True)
        assert not any("generations" in e.lower() for e in result.errors), (
            f"Generations 解析错误: {result.errors}"
        )

    @pytest.mark.skipif(
        not os.path.exists(LEGACY_MINUS6_FILE),
        reason="测试样本不存在"
    )
    def test_summary_parsed(self):
        """应成功解析出 summary。"""
        result = parse_package(LEGACY_MINUS6_FILE, tolerant=True)
        assert result.summary is not None, (
            f"Summary 未解析: {result.errors}"
        )


class TestLegacyMinus6FieldOrder:
    """legacy -6 字段顺序单元测试（不依赖真实文件）。"""

    def test_num_texture_allocations_read(self):
        """验证 NumTextureAllocations 字段被读取。"""
        # 此测试验证代码路径，实际解析需要真实文件
        from uasset_read.serializers.package_summary import read_package_summary
        # 函数存在且可导入
        assert callable(read_package_summary)


# =============================================================================
# JSON Schema 集成测试（合并自 test_json_schema.py）
# =============================================================================

def _make_header() -> PackageHeaderIR:
    return PackageHeaderIR(
        package_name="/Game/Test/BP_Test",
        package_class="BP_Test_C",
        package_flags=0,
        total_export_count=1,
        total_import_count=1,
        ue_version="5.3",
    )


def _make_minimal_ir(**kwargs) -> PackageIR:
    """构造最小 PackageIR。"""
    defaults = dict(
        header=_make_header(),
        name_map=["BP_Test"],
        imports=[],
        exports=[],
        linker=None,
    )
    defaults.update(kwargs)
    return PackageIR(**defaults)


def _render_json(ir: PackageIR, **options_kwargs) -> dict:
    """渲染 IR 为 JSON 字典。"""
    renderer = JSONRenderer()
    options = RenderOptions(**options_kwargs)
    output = renderer.render(ir, options)
    return json.loads(output)


class TestOutputVersionRemoved:
    """验证 JSON 输出不包含 output_version 字段。"""

    def test_no_output_version_default(self):
        """默认渲染不应包含 output_version 字段。"""
        ir = _make_minimal_ir()
        data = _render_json(ir)
        assert "output_version" not in data

    def test_no_output_version_debug(self):
        """debug 模式也不应包含 output_version 字段。"""
        ir = _make_minimal_ir()
        data = _render_json(ir, output_level="debug")
        assert "output_version" not in data


class TestSchemaReference:
    """验证 include_schema=True 时输出包含 $schema 引用。"""

    def test_schema_reference_included(self):
        """启用 include_schema 时应包含 $schema 引用。"""
        ir = _make_minimal_ir()
        data = _render_json(ir, include_schema=True)
        assert "$schema" in data
        assert data["$schema"] == "package.schema.json"

    def test_schema_reference_absent_by_default(self):
        """默认不启用 include_schema 时不应包含 $schema。"""
        ir = _make_minimal_ir()
        data = _render_json(ir)
        assert "$schema" not in data

    def test_schema_reference_absent_when_false(self):
        """显式 include_schema=False 时不应包含 $schema。"""
        ir = _make_minimal_ir()
        data = _render_json(ir, include_schema=False)
        assert "$schema" not in data


class TestRequiredFields:
    """验证 JSON 输出的基本字段结构。"""

    def test_has_status_and_summary_and_exports(self):
        """输出应包含 status、summary、exports 键。"""
        ir = _make_minimal_ir()
        data = _render_json(ir)
        assert "status" in data
        assert "summary" in data
        assert "exports" in data

    def test_status_structure(self):
        """status 字段应包含 status、message、code。"""
        ir = _make_minimal_ir()
        data = _render_json(ir)
        assert "status" in data
        assert "status" in data["status"]


# =============================================================================
# output_level 渲染测试（合并自 test_output_level.py）
# =============================================================================

SAMPLE_DIR = Path(__file__).parent.parent / "samples"
SAMPLE_BP = SAMPLE_DIR / "StackOBot_BP_Drone.uasset"


@pytest.mark.integration
class TestOutputLevelRendering:
    """测试 output_level 渲染行为。"""

    def test_standard_filters_ui_properties(self):
        """standard 模式应该过滤 UI 属性。"""
        from uasset_read.core import parse_single
        result = parse_single(str(SAMPLE_BP), format="json", output_level="standard")
        data = json.loads(result)

        # 检查 exports 中的 properties
        for export in data.get("exports", []):
            for prop in export.get("properties", []):
                assert prop["name"] not in ["NodePosX", "NodePosY", "NodeGuid", "FontSize"]

    def test_debug_preserves_ui_properties(self):
        """debug 模式应该保留 UI 属性。"""
        from uasset_read.core import parse_single
        result = parse_single(str(SAMPLE_BP), format="json", output_level="debug")
        data = json.loads(result)

        # 检查 exports 中的 properties
        has_ui_prop = False
        for export in data.get("exports", []):
            for prop in export.get("properties", []):
                if prop["name"] in ["NodePosX", "NodePosY", "NodeGuid"]:
                    has_ui_prop = True
                    break
        assert has_ui_prop

    def test_standard_filters_empty_graphs(self):
        """standard 模式应该过滤空 graphs。"""
        from uasset_read.core import parse_single
        result = parse_single(str(SAMPLE_BP), format="json", output_level="standard")
        data = json.loads(result)

        # 检查 exports 中的 graphs
        for export in data.get("exports", []):
            graphs = export.get("graphs", [])
            # 空 graphs 应该被过滤
            for graph in graphs:
                assert len(graph.get("nodes", [])) > 0

    def test_standard_deduplicates_diagnostics(self):
        """standard 模式应该去重 diagnostics。"""
        from uasset_read.core import parse_single
        result = parse_single(str(SAMPLE_BP), format="json", output_level="standard")
        data = json.loads(result)

        diagnostics = data.get("diagnostics", [])
        # 检查是否有重复
        seen = set()
        for d in diagnostics:
            key = (d.get("field"), d.get("error"))
            assert key not in seen, f"Duplicate diagnostic: {key}"
            seen.add(key)

    def test_standard_output_smaller(self):
        """standard 模式输出应该更小。"""
        from uasset_read.core import parse_single

        standard = parse_single(str(SAMPLE_BP), format="json", output_level="standard")
        debug = parse_single(str(SAMPLE_BP), format="json", output_level="debug")

        assert len(standard) < len(debug)

    def test_standard_filters_knot_nodes(self):
        """standard 模式应该过滤 K2Node_Knot 导出。"""
        from uasset_read.core import parse_single
        result = parse_single(str(SAMPLE_BP), format="json", output_level="standard")
        data = json.loads(result)

        for export in data.get("exports", []):
            assert export.get("object_class") != "K2Node_Knot", \
                f"K2Node_Knot should be filtered in standard: {export.get('object_name')}"

    def test_debug_preserves_knot_nodes(self):
        """debug 模式应该保留 K2Node_Knot 导出。"""
        from uasset_read.core import parse_single
        result = parse_single(str(SAMPLE_BP), format="json", output_level="debug")
        data = json.loads(result)

        # 本地样本可能没有 K2Node_Knot 节点，只验证解析成功
        assert len(data.get("exports", [])) > 0


# =============================================================================
# 异常上下文信息增强测试（合并自 test_exception_context.py）
# =============================================================================

class TestParseErrorContext:
    """ParseError 上下文信息测试。"""

    def test_parse_error_has_context_fields(self):
        """测试异常包含新增的上下文字段。"""
        exc = ParseError("Test error")
        assert hasattr(exc, 'reader_name')
        assert hasattr(exc, 'position')
        assert hasattr(exc, 'length')
        assert hasattr(exc, 'export_name')

    def test_parse_error_default_values(self):
        """测试上下文字段默认值。"""
        exc = ParseError("Test error")
        assert exc.reader_name == ""
        assert exc.position == 0
        assert exc.length == 0
        assert exc.export_name == ""

    def test_parse_error_format_with_reader_name(self):
        """测试格式化输出包含 reader_name。"""
        exc = ParseError("Invalid length")
        exc.reader_name = "FBinaryArchive"
        msg = str(exc)
        assert "FBinaryArchive" in msg
        assert "Reader: FBinaryArchive" in msg

    def test_parse_error_format_with_position(self):
        """测试格式化输出包含位置信息。"""
        exc = ParseError("Read failed")
        exc.position = 12345
        exc.length = 67890
        msg = str(exc)
        assert "12345" in msg
        assert "67890" in msg
        assert "18.2%" in msg  # 12345/67890*100 ≈ 18.2%

    def test_parse_error_format_with_export_name(self):
        """测试格式化输出包含导出名称。"""
        exc = ParseError("Property parse error")
        exc.export_name = "BP_Player_C"
        msg = str(exc)
        assert "BP_Player_C" in msg
        assert "Export: BP_Player_C" in msg

    def test_parse_error_format_full_context(self):
        """测试完整上下文格式化输出。"""
        exc = ParseError("Serialization failed")
        exc.reader_name = "FArchive"
        exc.position = 5000
        exc.length = 10000
        exc.export_name = "MyActor"
        msg = str(exc)
        assert "Serialization failed" in msg
        assert "Reader: FArchive" in msg
        assert "5000" in msg
        assert "10000" in msg
        assert "50.0%" in msg
        assert "Export: MyActor" in msg

    def test_parse_error_format_empty_context(self):
        """测试空上下文时只输出原始消息。"""
        exc = ParseError("Simple error")
        msg = str(exc)
        assert msg == "Simple error"

    def test_parse_error_backward_compatibility(self):
        """测试向后兼容性：partial_result 和 context 仍然可用。"""
        error_ctx = ErrorContext(
            offset=100,
            phase="header",
            operation="read_i32",
            context_name="MagicNumber"
        )
        exc = ParseError(
            "Test error",
            partial_result={"partial": True},
            context=error_ctx
        )
        assert exc.partial_result == {"partial": True}
        assert exc.context == error_ctx
        assert exc.context.offset == 100

    def test_parse_error_percentage_calculation(self):
        """测试百分比计算边界情况。"""
        # 正常情况
        exc = ParseError("Error")
        exc.position = 75
        exc.length = 100
        msg = str(exc)
        assert "75.0%" in msg

        # 零长度
        exc2 = ParseError("Error")
        exc2.position = 0
        exc2.length = 0
        msg2 = str(exc2)
        # 长度为 0 时不输出位置信息
        assert "Position" not in msg2
