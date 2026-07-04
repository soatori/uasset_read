"""测试 output_level 参数行为。"""
import json
import pytest
from pathlib import Path

SAMPLE_DIR = Path(r"E:\Develop\lib\Samples\FirstPerson\Content\FirstPerson\Blueprints")
SAMPLE_BP = SAMPLE_DIR / "BP_FirstPersonCharacter.uasset"


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

        has_knot = any(
            export.get("object_class") == "K2Node_Knot"
            for export in data.get("exports", [])
        )
        assert has_knot
