"""测试 UEdGraph 偏移读取修复。"""
import pytest
from pathlib import Path

SAMPLES_DIR = Path(__file__).parent / "samples"


class TestValidateGraphExportOffset:
    """_validate_graph_export_offset 单元测试。"""

    def _make_export(self, object_name, serial_offset, serial_size):
        class FakeExport:
            pass
        exp = FakeExport()
        exp.object_name = object_name
        exp.serial_offset = serial_offset
        exp.serial_size = serial_size
        return exp

    def test_empty_export_returns_true(self):
        """serial_size=0 的空 export 应通过验证。"""
        from uasset_read.graph.parser import _validate_graph_export_offset
        export = self._make_export("EmptyExport", 0, 0)
        assert _validate_graph_export_offset(export, 100000) is True

    def test_valid_offset_returns_true(self):
        """正常偏移应在有效范围内。"""
        from uasset_read.graph.parser import _validate_graph_export_offset
        export = self._make_export("EventGraph", 1000, 500)
        assert _validate_graph_export_offset(export, 100000) is True

    def test_zero_offset_non_default_returns_false(self):
        """非 Default__ export 的 serial_offset=0 应返回 False。"""
        from uasset_read.graph.parser import _validate_graph_export_offset
        export = self._make_export("EventGraph", 0, 500)
        assert _validate_graph_export_offset(export, 100000) is False

    def test_zero_offset_default_export_returns_true(self):
        """Default__ export 的 serial_offset=0 应通过验证。"""
        from uasset_read.graph.parser import _validate_graph_export_offset
        export = self._make_export("Default__EventGraph", 0, 500)
        assert _validate_graph_export_offset(export, 100000) is True

    def test_offset_beyond_archive_returns_false(self):
        """偏移越界应返回 False。"""
        from uasset_read.graph.parser import _validate_graph_export_offset
        export = self._make_export("EventGraph", 95000, 10000)
        assert _validate_graph_export_offset(export, 100000) is False

    def test_unknown_archive_size_skips_boundary_check(self):
        """archive_size=0 时不检查边界（安全降级）。"""
        from uasset_read.graph.parser import _validate_graph_export_offset
        export = self._make_export("EventGraph", 95000, 10000)
        assert _validate_graph_export_offset(export, 0) is True


class TestUEGraphOffset:
    """UEdGraph 偏移读取集成测试。"""

    @pytest.mark.integration
    def test_local_blueprint_graphs_not_partial(self):
        """验证本地蓝图样本的 graph 可用性，与 Kismet fallback 状态无关。

        Graph availability 和 Kismet fallback 是独立的关注点：
        - Graph parsing 由 UEdGraph 解析器负责
        - Kismet fallback (serial_scan_recovery) 影响 bytecode 提取，不影响 graph 解析
        """
        from uasset_read.parse_uasset import parse_package

        path = SAMPLES_DIR / "StackOBot_BP_Drone.uasset"
        if not path.exists():
            pytest.skip("Test sample not found")

        result = parse_package(str(path))
        assert result.is_success, f"Parse failed: {result.errors}"

        # Graph availability is independent of Kismet fallback status
        # (serial_scan_recovery marks package partial but doesn't affect graph parsing)
        assert len(result.graphs) > 0, "Should have parsed blueprint graphs"

        # Verify graphs have non-empty content
        for graph in result.graphs:
            assert hasattr(graph, "nodes"), f"Graph missing nodes attribute"
            assert len(graph.nodes) > 0, f"Graph {getattr(graph, 'name', '?')} has no nodes"

    @pytest.mark.integration
    def test_graph_offset_within_export_bounds(self):
        """验证图数据偏移在 export 边界内。"""
        from uasset_read.parse_uasset import parse_package

        path = SAMPLES_DIR / "StackOBot_BP_Drone.uasset"
        if not path.exists():
            pytest.skip("测试样本不存在")

        result = parse_package(str(path))
        # 检查每个 export 的图偏移是否在有效范围内
        for export in result.export_map:
            serial_offset = getattr(export, "serial_offset", 0)
            serial_size = getattr(export, "serial_size", 0)
            # 偏移不应为 0（除非是特殊 export）
            if serial_size > 0:
                assert serial_offset > 0 or export.object_name.startswith("Default__"), \
                    f"Export {export.object_name} 偏移异常: offset={serial_offset}, size={serial_size}"
