"""测试 ParseResult.graphs → ExportIR.graphs 输出链。"""
import pytest
from pathlib import Path

SAMPLES_DIR = Path(__file__).parent / "samples"


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
        """Verify semantic JSON output is valid for assets with graphs."""
        from uasset_read.parse_uasset import parse_package
        from uasset_read.ir_builder import build_package_ir
        from uasset_read.semantic.builder import build_semantic_ir
        from uasset_read.semantic.projection import project_semantic
        from uasset_read.semantic.render import render_semantic_json

        path = SAMPLES_DIR / "StackOBot_BP_Drone.uasset"
        if not path.exists():
            pytest.skip("test sample not found")

        result = parse_package(str(path))
        ir = build_package_ir(result)
        semantic_ir = build_semantic_ir(ir)
        semantic_ir = project_semantic(semantic_ir, "standard")
        output = render_semantic_json(semantic_ir)

        import json
        data = json.loads(output)
        # Blueprint assets route through the blueprint semantic extractor,
        # producing blueprint_semantic format.
        assert data["format"] in ("uasset_read.asset_semantic", "uasset_read.blueprint_semantic")

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
        output = renderer.render(ir, RenderOptions(output_level="standard"))

        # 检查是否有图章节
        assert "## Graph:" in output or "## Event Graph" in output, \
            "Markdown 输出应包含图章节"
