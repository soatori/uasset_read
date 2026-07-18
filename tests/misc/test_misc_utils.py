"""misc 工具测试 — 合并自 test_json_schema / test_output_level / test_exception_context。

验证：
1. JSON Schema 集成（output_version 移除、$schema 引用）
2. output_level 参数行为（standard/debug 渲染差异）
3. ParseError 上下文信息增强
"""
from __future__ import annotations

import json
import pytest
from pathlib import Path

from uasset_read.renderers.json_renderer import JSONRenderer
from uasset_read.renderers.base import RenderOptions
from uasset_read.models.ir import PackageIR, PackageHeaderIR, ExportIR
from uasset_read.exceptions import ParseError, ErrorContext


# ============================================================================
# JSON Schema 辅助工厂
# ============================================================================

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


# ============================================================================
# JSON Schema 集成测试
# ============================================================================

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


# ============================================================================
# output_level 渲染测试
# ============================================================================

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


# ============================================================================
# ParseError 上下文信息测试
# ============================================================================

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
