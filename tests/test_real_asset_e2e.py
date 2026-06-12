"""真实资产端到端测试 — 验证 parse_single() 高层入口和诊断传递。

覆盖 Gap Report P0-1 验收标准：
- json / markdown 不抛异常
- 截断文件返回诊断结果
- linker 诊断在 JSON 输出中可见
"""
from __future__ import annotations

import json
import os

import pytest

from uasset_read.core import parse_single
from uasset_read.parse_uasset import parse_uasset_with_linker

# 真实蓝图资产路径
_REAL_BLUEPRINT = os.path.join(
    os.environ.get("UE_ASSET_ROOT", r"E:\Develop\lib\UnrealEngine\Samples"),
    "FirstPerson", "Content", "FirstPerson", "Blueprints",
    "BP_FirstPersonCharacter.uasset",
)

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
        assert "BP_FirstPersonCharacter" in output


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
class TestLinkerDiagnosticsInOutput:
    """验证 linker 诊断最终出现在 JSON 输出中。"""

    def test_real_asset_json_has_diagnostics(self):
        """真实蓝图 JSON 输出应包含 linker 诊断（4 条 PackageIndex 越界）。"""
        output = parse_single(_REAL_BLUEPRINT, format="json", tolerant=True)
        data = json.loads(output)
        assert "diagnostics" in data
        assert isinstance(data["diagnostics"], list)
        assert len(data["diagnostics"]) >= 4  # 4 条 PackageIndex 65280 越界

    def test_real_asset_diagnostics_have_correct_module(self):
        """诊断应包含来自 linker 模块的 PackageIndex 越界诊断。"""
        output = parse_single(_REAL_BLUEPRINT, format="json", tolerant=True)
        data = json.loads(output)
        # 验证存在至少 4 条来自 linker 的 PackageIndex 诊断
        linker_pkg_diagnostics = [
            d for d in data["diagnostics"]
            if d["module"] == "linker" and d["field"] == "PackageIndex"
        ]
        assert len(linker_pkg_diagnostics) >= 4, (
            f"期望至少 4 条来自 linker 的 PackageIndex 诊断，实际只有 {len(linker_pkg_diagnostics)} 条"
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
