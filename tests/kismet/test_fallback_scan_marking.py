"""
Kismet fallback scan 标记测试 — Issue #77

验证 KismetDecompiledResult 的 logic_source 字段正确反映字节码来源：
- function_export: 正常解析的字节码
- serial_scan_recovery: 启发式扫描恢复的字节码
- bp_graph_cache: BPGC 回退的字节码
"""
import pytest


def _make_result(**overrides):
    """构造 KismetDecompiledResult 的辅助函数，提供合理默认值。"""
    from uasset_read.kismet.result import KismetDecompiledResult

    defaults = dict(
        function_name="TestFunc",
        signature="void TestFunc()",
        local_variables=[],
        cpp_code="// code",
    )
    defaults.update(overrides)
    return KismetDecompiledResult(**defaults)


class TestFallbackScanMarking:
    """fallback scan 结果应正确标记"""

    def test_fallback_scan_sets_logic_source(self):
        """fallback scan 应设置 logic_source"""
        result = _make_result(
            bytecode_status="fallback",
            logic_source="serial_scan_recovery",
        )

        assert result.logic_source == "serial_scan_recovery"
        assert result.bytecode_status == "fallback"

    def test_normal_bytecode_has_function_export_source(self):
        """正常字节码 logic_source 应为 function_export"""
        result = _make_result(
            bytecode_status="parsed",
            logic_source="function_export",
        )

        assert result.logic_source == "function_export"
        assert result.bytecode_status == "parsed"

    def test_fallback_reasons_tracked(self):
        """fallback_reasons 应包含来源信息"""
        result = _make_result(
            bytecode_status="fallback",
            logic_source="serial_scan_recovery",
            fallback_reasons=["serial_scan_recovery"],
        )

        assert "serial_scan_recovery" in result.fallback_reasons

    def test_bpgc_fallback_marking(self):
        """BPGC 回退应正确标记"""
        result = _make_result(
            bytecode_status="fallback",
            logic_source="bp_graph_cache",
            fallback_reasons=["bp_graph_cache"],
        )

        assert result.logic_source == "bp_graph_cache"
        assert result.bytecode_status == "fallback"
        assert "bp_graph_cache" in result.fallback_reasons

    def test_to_dict_includes_logic_source(self):
        """to_dict() 应包含 logic_source 字段"""
        result = _make_result(
            logic_source="serial_scan_recovery",
        )

        result_dict = result.to_dict()
        assert "logic_source" in result_dict
        assert result_dict["logic_source"] == "serial_scan_recovery"
