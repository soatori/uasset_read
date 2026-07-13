"""
parse_uasset.py 覆盖率补充测试

覆盖以下关键路径：
- _should_use_lightweight_tolerant_parse 轻量模式检测
- _build_lightweight_graphs 轻量图提取
- _build_lightweight_function_graphs 轻量函数图提取
- _extract_kismet_decompiled 字节码提取
- _post_process 后处理
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from dataclasses import dataclass, field
from typing import List, Optional

from uasset_read.parse_uasset import (
    _should_use_lightweight_tolerant_parse,
    _build_lightweight_graphs,
    _build_lightweight_function_graphs,
    _post_process,
)
from uasset_read.parse_post_process import (
    _extract_kismet_decompiled,
)
from uasset_read.models.result import ParseResult
from uasset_read.constants import LIGHTWEIGHT_TOLERANT_PARSE_THRESHOLD


# ===========================================================================
# 辅助数据类
# ===========================================================================

@dataclass
class MockSummary:
    """模拟 PackageFileSummary。"""
    export_count: int = 0
    package_name: str = "/Game/Test"
    file_version_ue5: int = 0
    total_export_count: int = 0
    total_import_count: int = 0
    package_flags: int = 0
    version: int = 522
    soft_object_paths_count: int = 0
    soft_object_paths_offset: int = 0
    depends_map_count: int = 0
    depends_map_offset: int = 0
    preload_dependency_count: int = 0
    preload_dependency_offset: int = 0


@dataclass
class MockExport:
    """模拟 ObjectExport。"""
    object_name: str = "TestExport"
    class_index: MagicMock = field(default_factory=lambda: MagicMock())
    serial_offset: int = 0
    serial_size: int = 100


@dataclass
class MockImport:
    """模拟 ObjectImport。"""
    object_name: str = "TestImport"
    class_package: str = "/Engine/Core"
    class_name: str = "Object"


# ===========================================================================
# _should_use_lightweight_tolerant_parse 测试
# ===========================================================================

class TestShouldUseLightweightTolerantParse:
    """_should_use_lightweight_tolerant_parse 轻量模式检测单元测试。"""

    def test_force_full_parse_returns_false(self):
        """force_full_parse=True 时返回 False。"""
        result = ParseResult()
        result.summary = MockSummary(export_count=1000)

        assert _should_use_lightweight_tolerant_parse(
            result, tolerant=True, force_full_parse=True
        ) is False

    def test_not_tolerant_returns_false(self):
        """tolerant=False 时返回 False。"""
        result = ParseResult()
        result.summary = MockSummary(export_count=1000)

        assert _should_use_lightweight_tolerant_parse(
            result, tolerant=False, force_full_parse=False
        ) is False

    def test_no_summary_returns_false(self):
        """summary 为 None 时返回 False。"""
        result = ParseResult()
        result.summary = None

        assert _should_use_lightweight_tolerant_parse(
            result, tolerant=True, force_full_parse=False
        ) is False

    def test_below_threshold_returns_false(self):
        """export_count 低于阈值时返回 False。"""
        result = ParseResult()
        result.summary = MockSummary(export_count=LIGHTWEIGHT_TOLERANT_PARSE_THRESHOLD)

        assert _should_use_lightweight_tolerant_parse(
            result, tolerant=True, force_full_parse=False
        ) is False

    def test_above_threshold_returns_true(self):
        """export_count 超过阈值时返回 True。"""
        result = ParseResult()
        result.summary = MockSummary(export_count=LIGHTWEIGHT_TOLERANT_PARSE_THRESHOLD + 1)

        assert _should_use_lightweight_tolerant_parse(
            result, tolerant=True, force_full_parse=False
        ) is True

    def test_custom_threshold(self):
        """自定义阈值。"""
        result = ParseResult()
        result.summary = MockSummary(export_count=50)

        # 自定义阈值 100
        assert _should_use_lightweight_tolerant_parse(
            result, tolerant=True, lightweight_threshold=100
        ) is False

        # 自定义阈值 30
        assert _should_use_lightweight_tolerant_parse(
            result, tolerant=True, lightweight_threshold=30
        ) is True


# ===========================================================================
# _build_lightweight_graphs 测试
# ===========================================================================

class TestBuildLightweightGraphs:
    """_build_lightweight_graphs 轻量图提取单元测试。"""

    def test_empty_export_map(self):
        """空 export_map — 返回空列表。"""
        result = ParseResult()
        result.export_map = []
        result.import_map = []

        graphs = _build_lightweight_graphs(result)
        assert graphs == []

    def test_empty_import_map(self):
        """空 import_map — 返回空列表。"""
        result = ParseResult()
        result.export_map = [MockExport(object_name="Test")]
        result.import_map = []

        graphs = _build_lightweight_graphs(result)
        assert graphs == []

    def test_no_edgraph_exports(self):
        """无 EdGraph 类型导出 — 返回空列表。"""
        result = ParseResult()
        export = MockExport(object_name="TestComponent")
        result.export_map = [export]
        result.import_map = [MockImport()]

        with patch('uasset_read.serializers.object_resources.get_asset_class', return_value="BlueprintGeneratedClass"):
            graphs = _build_lightweight_graphs(result)
            assert graphs == []

    def test_edgraph_export(self):
        """EdGraph 类型导出 — 创建最小化图。"""
        result = ParseResult()
        export = MockExport(object_name="EventGraph")
        result.export_map = [export]
        result.import_map = [MockImport()]

        with patch('uasset_read.serializers.object_resources.get_asset_class', return_value="EdGraph"):
            graphs = _build_lightweight_graphs(result)
            assert len(graphs) == 1
            assert graphs[0].graph_name == "EventGraph"
            assert graphs[0].graph_class == "EdGraph"
            assert graphs[0].nodes == []

    def test_uberedgraph_export(self):
        """UberEdGraph 类型导出 — 创建最小化图。"""
        result = ParseResult()
        export = MockExport(object_name="UberGraphPages")
        result.export_map = [export]
        result.import_map = [MockImport()]

        with patch('uasset_read.serializers.object_resources.get_asset_class', return_value="UberEdGraph"):
            graphs = _build_lightweight_graphs(result)
            assert len(graphs) == 1
            assert graphs[0].graph_name == "UberGraphPages"
            assert graphs[0].graph_class == "UberEdGraph"
            assert graphs[0].nodes == []

    def test_multiple_edgraph_exports(self):
        """多个 EdGraph 导出 — 创建多个图。"""
        result = ParseResult()
        export1 = MockExport(object_name="EventGraph")
        export2 = MockExport(object_name="AnimGraph")
        result.export_map = [export1, export2]
        result.import_map = [MockImport()]

        with patch('uasset_read.serializers.object_resources.get_asset_class', return_value="EdGraph"):
            graphs = _build_lightweight_graphs(result)
            assert len(graphs) == 2
            names = {g.graph_name for g in graphs}
            assert "EventGraph" in names
            assert "AnimGraph" in names

    def test_export_without_name(self):
        """导出无名称 — 跳过。"""
        result = ParseResult()
        export = MockExport(object_name="")
        result.export_map = [export]
        result.import_map = [MockImport()]

        with patch('uasset_read.serializers.object_resources.get_asset_class', return_value="EdGraph"):
            graphs = _build_lightweight_graphs(result)
            assert graphs == []

    def test_mixed_export_types(self):
        """混合类型导出 — 仅提取 EdGraph/UberEdGraph。"""
        result = ParseResult()
        export1 = MockExport(object_name="EventGraph")
        export2 = MockExport(object_name="TestComponent")
        export3 = MockExport(object_name="UberGraphPages")
        result.export_map = [export1, export2, export3]
        result.import_map = [MockImport()]

        def mock_get_class(exp, imp, exps):
            if exp.object_name in ("EventGraph",):
                return "EdGraph"
            if exp.object_name == "UberGraphPages":
                return "UberEdGraph"
            return "BlueprintGeneratedClass"

        with patch('uasset_read.serializers.object_resources.get_asset_class', side_effect=mock_get_class):
            graphs = _build_lightweight_graphs(result)
            assert len(graphs) == 2
            names = {g.graph_name for g in graphs}
            assert "EventGraph" in names
            assert "UberGraphPages" in names


# ===========================================================================
# _build_lightweight_function_graphs 测试
# ===========================================================================

class TestBuildLightweightFunctionGraphs:
    """_build_lightweight_function_graphs 轻量函数图提取单元测试。"""

    def test_empty_export_map(self):
        """空 export_map — 返回空列表。"""
        entries = _build_lightweight_function_graphs([])
        assert entries == []

    def test_none_export_map(self):
        """None export_map — 返回空列表。"""
        entries = _build_lightweight_function_graphs(None)
        assert entries == []

    def test_blueprint_class_export(self):
        """蓝图类导出（_C 后缀）— 跳过。"""
        export = MockExport(object_name="TestBlueprint_C")
        entries = _build_lightweight_function_graphs([export])
        assert entries == []

    def test_default_object_export(self):
        """默认对象导出（Default__ 前缀）— 跳过。"""
        export = MockExport(object_name="Default__TestBlueprint")
        entries = _build_lightweight_function_graphs([export])
        assert entries == []

    def test_event_graph_export(self):
        """EventGraph 导出 — 跳过。"""
        export = MockExport(object_name="EventGraph")
        entries = _build_lightweight_function_graphs([export])
        assert entries == []

    def test_uber_graph_pages_export(self):
        """UberGraphPages 导出 — 跳过。"""
        export = MockExport(object_name="UberGraphPages")
        entries = _build_lightweight_function_graphs([export])
        assert entries == []

    def test_simple_construction_script_export(self):
        """SimpleConstructionScript 导出 — 跳过。"""
        export = MockExport(object_name="SimpleConstructionScript")
        entries = _build_lightweight_function_graphs([export])
        assert entries == []

    def test_normal_function_export(self):
        """普通函数导出 — 创建条目。"""
        export = MockExport(object_name="MyFunction")
        entries = _build_lightweight_function_graphs([export])
        assert len(entries) == 1
        assert entries[0]["function_name"] == "MyFunction"
        assert entries[0]["graph_source"] == "export_map"
        assert entries[0]["fallback_reason"] == "lightweight_tolerant_parse"

    def test_multiple_function_exports(self):
        """多个函数导出 — 创建多个条目。"""
        exports = [
            MockExport(object_name="Function1"),
            MockExport(object_name="Function2"),
            MockExport(object_name="Function3"),
        ]
        entries = _build_lightweight_function_graphs(exports)
        assert len(entries) == 3
        names = {e["function_name"] for e in entries}
        assert "Function1" in names
        assert "Function2" in names
        assert "Function3" in names

    def test_max_entries_limit(self):
        """超过 64 个条目限制 — 只取前 64 个。"""
        exports = [MockExport(object_name=f"Function{i}") for i in range(100)]
        entries = _build_lightweight_function_graphs(exports)
        assert len(entries) == 64

    def test_empty_name_export(self):
        """空名称导出 — 跳过。"""
        export = MockExport(object_name="")
        entries = _build_lightweight_function_graphs([export])
        assert entries == []


# ===========================================================================
# _extract_kismet_decompiled 测试
# ===========================================================================

class TestExtractKismetDecompiled:
    """_extract_kismet_decompiled 字节码提取单元测试。"""

    def test_no_ustruct_exports(self):
        """无 UStruct 导出 — 返回空列表。"""
        archive = MagicMock()
        summary = MockSummary()
        name_map = ["Test"]
        import_map = []
        export_map = [MockExport(object_name="TestExport")]

        with patch('uasset_read.serializers.object_resources.resolve_class_name', return_value="TestComponent"):
            result = _extract_kismet_decompiled(
                "/Game/Test", archive, summary, name_map, import_map, export_map
            )
            assert result == []

    def test_ustruct_export_success(self):
        """UStruct 导出成功 — 返回结果。"""
        archive = MagicMock()
        summary = MockSummary()
        name_map = ["Test"]
        import_map = []
        export = MockExport(object_name="MyFunction")
        export_map = [export]

        mock_result = MagicMock()
        mock_result.function_name = "MyFunction"

        with patch('uasset_read.serializers.object_resources.resolve_class_name', return_value="UserDefinedEnum"):
            with patch('uasset_read.kismet.bytecode_extractor.USTRUCT_TYPES', {"UserDefinedEnum"}):
                with patch('uasset_read.kismet.pipeline.decompile_single_function', return_value=mock_result):
                    with patch('uasset_read.kismet.bytecode_extractor.reset_bpgc_cache'):
                        result = _extract_kismet_decompiled(
                            "/Game/Test", archive, summary, name_map, import_map, export_map
                        )
                        assert len(result) == 1
                        assert result[0].function_name == "MyFunction"

    def test_ustruct_export_failure_tolerant(self):
        """UStruct 导出失败 — 容错模式返回空列表。"""
        archive = MagicMock()
        summary = MockSummary()
        name_map = ["Test"]
        import_map = []
        export = MockExport(object_name="MyFunction")
        export_map = [export]

        with patch('uasset_read.serializers.object_resources.resolve_class_name', return_value="UserDefinedEnum"):
            with patch('uasset_read.kismet.bytecode_extractor.USTRUCT_TYPES', {"UserDefinedEnum"}):
                with patch('uasset_read.kismet.pipeline.decompile_single_function', side_effect=OSError("Test error")):
                    with patch('uasset_read.kismet.bytecode_extractor.reset_bpgc_cache'):
                        # tolerant=True (default)
                        result = _extract_kismet_decompiled(
                            "/Game/Test", archive, summary, name_map, import_map, export_map
                        )
                        assert result == []

    def test_ustruct_export_returns_none(self):
        """UStruct 导出返回 None — 跳过。"""
        archive = MagicMock()
        summary = MockSummary()
        name_map = ["Test"]
        import_map = []
        export = MockExport(object_name="MyFunction")
        export_map = [export]

        with patch('uasset_read.serializers.object_resources.resolve_class_name', return_value="UserDefinedEnum"):
            with patch('uasset_read.kismet.bytecode_extractor.USTRUCT_TYPES', {"UserDefinedEnum"}):
                with patch('uasset_read.kismet.pipeline.decompile_single_function', return_value=None):
                    with patch('uasset_read.kismet.bytecode_extractor.reset_bpgc_cache'):
                        result = _extract_kismet_decompiled(
                            "/Game/Test", archive, summary, name_map, import_map, export_map
                        )
                        assert result == []


# ===========================================================================
# _post_process 测试
# ===========================================================================

class TestPostProcess:
    """_post_process 后处理单元测试。"""

    def test_basic_post_process(self):
        """基本后处理 — 无蓝图导出。"""
        archive = MagicMock()
        summary = MockSummary()
        name_map = ["Test"]
        import_map = []
        export_map = []
        result = ParseResult()

        # 简化测试 - 只验证函数可以被调用
        try:
            _post_process(
                "/Game/Test", archive, summary, name_map, import_map, export_map,
                result, tolerant=True
            )
            # 如果没有抛异常，测试通过
            assert True
        except Exception:
            # 容错模式下应该不会抛异常
            assert False, "_post_process raised an exception in tolerant mode"

    def test_post_process_with_linker(self):
        """后处理 — 带 linker。"""
        archive = MagicMock()
        summary = MockSummary()
        name_map = ["Test"]
        import_map = []
        export_map = []
        result = ParseResult()
        linker = MagicMock()

        try:
            _post_process(
                "/Game/Test", archive, summary, name_map, import_map, export_map,
                result, tolerant=True, linker=linker
            )
            assert True
        except Exception:
            assert False, "_post_process raised an exception in tolerant mode"


# ===========================================================================
# ParseResult 边界测试
# ===========================================================================

class TestParseResultEdgeCases:
    """ParseResult 边界情况测试。"""

    def test_parse_result_defaults(self):
        """ParseResult 默认值 — 所有字段初始化正确。"""
        result = ParseResult()
        assert result.summary is None
        assert result.name_map == []
        assert result.export_map == []
        assert result.import_map == []
        assert result.linker is None
        assert result.graphs == []
        assert result.decompiled_functions == []
        assert result.metadata == {}
        assert result.mmap_used is False
        assert result.mmap_warning is None

    def test_parse_result_with_diagnostics(self):
        """ParseResult 带诊断信息。"""
        result = ParseResult()
        diag = MagicMock()
        result.diagnostics = [diag]
        assert len(result.diagnostics) == 1

    def test_parse_result_status_model(self):
        """ParseResult 状态模型 — success/partial/failed。"""
        # 空结果状态为 failed
        result = ParseResult()
        assert result.status == "failed"

        # 有数据但 is_success=False 时状态为 partial（非 success）
        result.name_map = ["Test"]
        assert result.status == "partial"

        # 有错误时状态为 partial
        result.errors = ["Test error"]
        assert result.status == "partial"

        # is_success=True 且无错误时状态为 success
        result2 = ParseResult()
        result2.is_success = True
        result2.name_map = ["Test"]
        assert result2.status == "success"
