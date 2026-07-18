"""测试 ParseResult.graphs → ExportIR.graphs 输出链及 graph/parser 基本接口。"""
import pytest
from pathlib import Path

from uasset_read.graph.parser import extract_blueprint_graphs
from uasset_read.constants import PKG_Cooked

SAMPLES_DIR = Path(__file__).parent.parent / "samples"


class TestGraphOutputChain:
    """图数据输出链测试。"""

    @pytest.mark.integration
    def test_parse_result_graphs_count(self):
        """验证 ParseResult.graphs 包含图数据。"""
        from uasset_read.parse_uasset import parse_package

        path = SAMPLES_DIR / "StackOBot_BP_Drone.uasset"
        if not path.exists():
            pytest.skip("测试样本不存在")

        result = parse_package(str(path))
        # 本地样本可能只有少量图
        assert len(result.graphs) >= 1, f"应有至少 1 个图，实际: {len(result.graphs)}"

    @pytest.mark.integration
    def test_export_ir_graphs_not_empty(self):
        """验证 ExportIR.graphs 包含图数据。"""
        from uasset_read.parse_uasset import parse_package
        from uasset_read.ir_builder import build_package_ir

        path = SAMPLES_DIR / "StackOBot_BP_Drone.uasset"
        if not path.exists():
            pytest.skip("测试样本不存在")

        result = parse_package(str(path))
        ir = build_package_ir(result)

        # 找到蓝图 export（以 _C 结尾）
        bp_exports = [e for e in ir.exports if e.object_name.endswith("_C")]
        assert len(bp_exports) > 0, "应有蓝图 export"

        # 至少一个蓝图 export 应有图
        has_graphs = any(len(e.graphs) > 0 for e in bp_exports)
        assert has_graphs, "蓝图 export 应包含图数据"

    @pytest.mark.integration
    def test_json_output_contains_graphs(self):
        """验证 JSON 输出包含图数据。"""
        from uasset_read.parse_uasset import parse_package
        from uasset_read.ir_builder import build_package_ir
        from uasset_read.renderers.json_renderer import JSONRenderer
        from uasset_read.renderers.base import RenderOptions

        path = SAMPLES_DIR / "StackOBot_BP_Drone.uasset"
        if not path.exists():
            pytest.skip("测试样本不存在")

        result = parse_package(str(path))
        ir = build_package_ir(result)
        renderer = JSONRenderer()
        output = renderer.render(ir, RenderOptions(output_level="normal"))

        import json
        data = json.loads(output)

        # 检查 exports 中是否有图
        exports_with_graphs = [e for e in data.get("exports", []) if e.get("graphs")]
        assert len(exports_with_graphs) > 0, "JSON 输出应包含图数据"

    @pytest.mark.integration
    def test_markdown_output_contains_graph_sections(self):
        """验证 Markdown 输出包含图章节。"""
        from uasset_read.parse_uasset import parse_package
        from uasset_read.ir_builder import build_package_ir
        from uasset_read.renderers.markdown_renderer import MarkdownRenderer
        from uasset_read.renderers.base import RenderOptions

        path = SAMPLES_DIR / "StackOBot_BP_Drone.uasset"
        if not path.exists():
            pytest.skip("测试样本不存在")

        result = parse_package(str(path))
        ir = build_package_ir(result)
        renderer = MarkdownRenderer()
        output = renderer.render(ir, RenderOptions(output_level="normal"))

        # 检查是否有图章节
        assert "## Graph:" in output or "## Event Graph" in output, \
            "Markdown 输出应包含图章节"


# ============================================================================
# 来自 test_graph_parser.py — extract_blueprint_graphs 基本接口测试
# ============================================================================


class TestExtractBlueprintGraphsCallable:
    """extract_blueprint_graphs 应可调用。"""

    def test_callable(self):
        assert callable(extract_blueprint_graphs)


class TestExtractBlueprintGraphsCookedSkip:
    """cooked 包应跳过图解析。"""

    def _make_summary(self, flags: int):
        class FakeSummary:
            package_flags = flags
        return FakeSummary()

    def test_cooked_package_returns_empty(self):
        summary = self._make_summary(PKG_Cooked)
        result = extract_blueprint_graphs(
            archive=None,
            summary=summary,
            name_map=[],
            import_map=[],
            export_map=[],
        )
        assert result == []

    def test_non_cooked_package_not_skipped(self):
        """非 cooked 包不会因 flags 被跳过（可能因无 EdGraph export 而返回空）。"""
        summary = self._make_summary(0)
        result = extract_blueprint_graphs(
            archive=None,
            summary=summary,
            name_map=[],
            import_map=[],
            export_map=[],
        )
        assert result == []


class TestExtractBlueprintGraphsEmptyExports:
    """空 export_map 应返回空列表。"""

    def test_empty_export_map(self):
        class FakeSummary:
            package_flags = 0

        result = extract_blueprint_graphs(
            archive=None,
            summary=FakeSummary(),
            name_map=[],
            import_map=[],
            export_map=[],
        )
        assert result == []
        assert isinstance(result, list)
