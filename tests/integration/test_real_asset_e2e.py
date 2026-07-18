"""真实资产端到端测试 — 验证 parse_single() 高层入口和诊断传递。

覆盖 Gap Report P0-1 验收标准：
- json / markdown 不抛异常
- 截断文件返回诊断结果
- linker 诊断在 JSON 输出中可见
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from uasset_read.core import parse_single
from uasset_read.parse_uasset import parse_uasset_with_linker

# 本地样本资产路径
_LOCAL_SAMPLE_ROOT = Path(__file__).parent.parent / "samples"
_REAL_BLUEPRINT = str(_LOCAL_SAMPLE_ROOT / "FirstPerson_BP_FirstPersonGameMode.uasset")

_has_real_asset = os.path.isfile(_REAL_BLUEPRINT)


@pytest.fixture
def truncated_file(tmp_path):
    """创建截断的 .uasset 文件（< 64 字节，触发 MIN_UASSET_SIZE 检测）。"""
    path = tmp_path / "truncated.uasset"
    # UE4 magic + 填充至 36 字节（< MIN_UASSET_SIZE=64）
    data = b"\xC1\x83\x2A\x9E" + b"\x00" * 32
    path.write_bytes(data)
    return str(path)


# ---------------------------------------------------------------------------
# P0-1 验收：高层入口不崩溃
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.regression
@pytest.mark.skipif(not _has_real_asset, reason="真实资产不可用")
class TestRealAssetHighLevelFormats:
    """验证真实蓝图的 json / markdown 输出不崩溃。"""

    def test_json_format_does_not_crash(self):
        output = parse_single(_REAL_BLUEPRINT, format="json", tolerant=True)
        assert output
        data = json.loads(output)
        # JSON 顶层键包含 status 和 summary
        assert "status" in data or "summary" in data

    def test_markdown_format_does_not_crash(self):
        output = parse_single(_REAL_BLUEPRINT, format="markdown", tolerant=True)
        assert output
        assert "FirstPerson" in output


# ---------------------------------------------------------------------------
# P0-1 验收：截断文件返回结构化诊断
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.regression
class TestTruncatedFileLinkerDiagnostics:
    """验证截断文件通过 linker 入口返回诊断，不抛 AttributeError。"""

    def test_truncated_linker_returns_diagnostics(self, truncated_file):
        result = parse_uasset_with_linker(truncated_file, tolerant=True)
        assert not result.is_success
        assert len(result.diagnostics) > 0

    def test_truncated_linker_no_attribute_error(self, truncated_file):
        """关键：不应抛出 AttributeError: LinkerParseResult has no attribute diagnostics。"""
        try:
            result = parse_uasset_with_linker(truncated_file, tolerant=True)
            assert not result.is_success
        except AttributeError as e:
            if "diagnostics" in str(e):
                pytest.fail(f"LinkerParseResult 仍缺少 diagnostics 字段: {e}")
            raise

    def test_truncated_json_format_no_crash(self, truncated_file):
        """截断文件通过 parse_single(json) 应返回结构化错误，不是抛异常。"""
        # Tolerant 模式下，截断文件应返回含 status.failed 的 JSON 结果
        output = parse_single(truncated_file, format="json", tolerant=True)
        assert output
        data = json.loads(output)
        # 验证返回了结构化错误结果
        assert "status" in data
        assert data.get("status", {}).get("status") == "failed"

    def test_truncated_diagnostics_contain_kind(self, truncated_file):
        """诊断应该有 kind 字段标识类型。"""
        result = parse_uasset_with_linker(truncated_file, tolerant=True)
        assert len(result.diagnostics) > 0
        d = result.diagnostics[0]
        assert hasattr(d, "kind")
        assert d.kind == "truncated_file"


# ---------------------------------------------------------------------------
# P0-1 验收：linker 诊断在 JSON 输出中可见
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.regression
@pytest.mark.skipif(not _has_real_asset, reason="真实资产不可用")
class TestLinkerDiagnosticsRemovedFromJson:
    """验证 JSON 输出包含 diagnostics 字段（用于调试）。"""

    def test_real_asset_json_has_diagnostics_field(self):
        """JSON 输出应包含 diagnostics 字段（如有诊断数据）。"""
        output = parse_single(_REAL_BLUEPRINT, format="json", tolerant=True)
        data = json.loads(output)
        if data.get("diagnostics"):
            assert isinstance(data["diagnostics"], list), "diagnostics 应为列表"
            assert len(data["diagnostics"]) > 0, "diagnostics 不应为空列表"

    def test_real_asset_json_no_linker_field(self):
        """精简后 JSON 输出不应包含 linker 字段。"""
        output = parse_single(_REAL_BLUEPRINT, format="json", tolerant=True)
        data = json.loads(output)
        assert "linker" not in data, (
            "linker 字段已从 JSON 输出中移除，不应出现"
        )


# ---------------------------------------------------------------------------
# 辅助：LinkerParseResult 字段完整性
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestLinkerParseResultFieldCompleteness:
    """验证 LinkerParseResult 与 ParseResult 的关键字段一致。"""

    def test_linker_result_has_diagnostics_field(self):
        from uasset_read.link.result import LinkerParseResult
        result = LinkerParseResult()
        assert hasattr(result, "diagnostics")
        assert isinstance(result.diagnostics, list)
        assert len(result.diagnostics) == 0

    def test_linker_result_diagnostics_extendable(self):
        from uasset_read.link.result import LinkerParseResult
        result = LinkerParseResult()
        result.diagnostics.extend([])
        assert result.diagnostics == []


# ---------------------------------------------------------------------------
# 状态模型集成测试（合并自 test_status_model_integration.py）
# ---------------------------------------------------------------------------

def _get_test_asset():
    """获取第一个可用的测试 .uasset 文件。"""
    test_assets = Path("E:/Develop/lib/Samples")
    if not test_assets.exists():
        pytest.skip("测试资产目录不存在")

    uasset_files = list(test_assets.glob("**/*.uasset"))[:1]
    if not uasset_files:
        pytest.skip("未找到测试资产")

    return uasset_files[0]


class TestStatusModelIntegration:
    """状态模型集成测试。"""

    def test_json_output_status_format(self):
        """验证 JSON 输出状态格式正确"""
        from uasset_read.core import parse_single

        asset_path = _get_test_asset()

        # parse_single 返回格式化字符串（JSON 格式）
        output = parse_single(str(asset_path), format="json")
        data = json.loads(output)

        # 验证顶层状态
        assert "status" in data, "JSON 输出缺少 status 字段"
        assert data["status"]["status"] in ["success", "partial", "failed"], \
            f"无效的状态值: {data['status']['status']}"

        # 验证 export 状态
        for export in data.get("exports", []):
            if "parse_status" in export:
                valid_statuses = [
                    "success", "partial", "failed", "opaque", "skipped",
                    "partial_metadata", "opaque_unversioned", "fallback", "metadata"
                ]
                assert export["parse_status"] in valid_statuses, \
                    f"无效的 export 状态: {export['parse_status']}"

    def test_markdown_output_status_section(self):
        """验证 Markdown 输出状态部分正确"""
        from uasset_read.core import parse_single
        from uasset_read.parse_uasset import parse_package

        asset_path = _get_test_asset()

        # 获取 ParseResult 以检查 status
        result = parse_package(str(asset_path), tolerant=True)

        # 生成 Markdown 输出
        output = parse_single(str(asset_path), format="markdown")

        # 如果不是 success，应该有 Status 部分
        if result.status != "success":
            assert "## Status" in output or "Status" in output, \
                "非 success 状态下 Markdown 输出应包含 Status 部分"
            assert "**PARTIAL**" in output or "**FAILED**" in output, \
                "非 success 状态下应有 PARTIAL 或 FAILED 标记"

    def test_status_values_in_result(self):
        """验证 ParseResult.status 字段值合法"""
        from uasset_read.parse_uasset import parse_package

        asset_path = _get_test_asset()

        result = parse_package(str(asset_path), tolerant=True)

        valid_statuses = ["success", "partial", "failed"]
        assert result.status in valid_statuses, \
            f"无效的 ParseResult.status: {result.status}"

    def test_ir_status_preserved(self):
        """验证 IR 构建后状态信息保留"""
        from uasset_read.parse_uasset import parse_package
        from uasset_read.ir_builder import build_package_ir

        asset_path = _get_test_asset()

        result = parse_package(str(asset_path), tolerant=True)
        ir = build_package_ir(result)

        # IR 应该保留原始状态信息
        valid_statuses = ["success", "partial", "failed"]
        assert ir.status in valid_statuses, \
            f"无效的 IR status: {ir.status}"
