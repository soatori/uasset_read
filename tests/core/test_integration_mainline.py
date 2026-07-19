"""集成测试主线 — 合并自 test_integration_core.py、test_integration_types.py。

覆盖：核心集成、类型集成。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from uasset_read.parse_uasset import parse_package, parse_uasset_with_linker
from uasset_read.renderers import list_formats
from uasset_read.renderers.base import RenderOptions
from uasset_read.renderers.json_renderer import JSONRenderer
from uasset_read.renderers.markdown_renderer import MarkdownRenderer
from uasset_read.ir_builder import build_package_ir

pytestmark = pytest.mark.integration


# ============================================================================
# 1. 基础解析验证
# ============================================================================

LOCAL_SAMPLE_ROOT = Path(__file__).parent.parent / "samples"
ASSET_PATH = LOCAL_SAMPLE_ROOT / "StackOBot_BP_Drone.uasset"


@pytest.fixture(scope="module")
def bp_result():
    """解析 StackOBot_BP_Drone 资产。"""
    if not ASSET_PATH.exists():
        pytest.skip(f"资产不存在: {ASSET_PATH}")
    return parse_uasset_with_linker(str(ASSET_PATH), tolerant=True)


class TestBasicParsing:
    """基础解析验证。"""

    def test_parse_succeeds(self, bp_result):
        """解析器应成功解析（status != failed）。"""
        assert bp_result.status != "failed", f"解析失败: {bp_result.errors}"

    def test_has_summary(self, bp_result):
        """应有摘要信息。"""
        assert bp_result.summary is not None

    def test_has_graphs(self, bp_result):
        """应有至少 1 个图。"""
        assert len(bp_result.graphs) >= 1


# ============================================================================
# 2. 端到端 JSON 渲染
# ============================================================================

_REAL_BLUEPRINT = str(LOCAL_SAMPLE_ROOT / "FirstPerson_BP_FirstPersonGameMode.uasset")
_has_real_asset = os.path.isfile(_REAL_BLUEPRINT)


@pytest.mark.regression
@pytest.mark.skipif(not _has_real_asset, reason="真实资产不可用")
class TestRealAssetJsonRendering:
    """验证真实蓝图的 JSON 输出字段正确。"""

    def test_json_package_name(self):
        """JSON 输出应包含有效 package_name。"""
        from uasset_read.core import parse_single
        output = parse_single(_REAL_BLUEPRINT, format="json", tolerant=True)
        data = json.loads(output)
        assert data["summary"]["package_name"] is not None
        assert len(data["summary"]["package_name"]) > 0

    def test_json_export_count_positive(self):
        """JSON 输出应有至少 1 个 export。"""
        from uasset_read.core import parse_single
        output = parse_single(_REAL_BLUEPRINT, format="json", tolerant=True)
        data = json.loads(output)
        assert data["summary"]["total_export_count"] >= 1


# ============================================================================
# 3. 本地样本 JSON/Markdown 渲染
# ============================================================================

LOCAL_SAMPLES = [
    "FirstPerson_BP_FirstPersonGameMode.uasset",
    "StackOBot_BP_Drone.uasset",
    "StackOBot_M_BotBase.uasset",
]


@pytest.mark.parametrize("filename", LOCAL_SAMPLES)
class TestLocalSampleRendering:
    """验证本地样本在 JSON 和 Markdown 格式下不崩溃。"""

    def test_json_renderer_produces_valid_json(self, filename):
        path = LOCAL_SAMPLE_ROOT / filename
        if not path.exists():
            pytest.skip(f"样本不存在: {path}")
        result = parse_package(str(path))
        ir = build_package_ir(result)
        renderer = JSONRenderer()
        output = renderer.render(ir, RenderOptions())
        parsed = json.loads(output)
        assert "summary" in parsed

    def test_markdown_renderer_produces_output(self, filename):
        path = LOCAL_SAMPLE_ROOT / filename
        if not path.exists():
            pytest.skip(f"样本不存在: {path}")
        result = parse_package(str(path))
        ir = build_package_ir(result)
        renderer = MarkdownRenderer()
        output = renderer.render(ir, RenderOptions())
        assert isinstance(output, str)
        assert len(output) > 0


# ============================================================================
# 4. 截断文件诊断
# ============================================================================

@pytest.fixture
def truncated_file(tmp_path):
    """创建截断的 .uasset 文件（< 64 字节）。"""
    path = tmp_path / "truncated.uasset"
    data = b"\xC1\x83\x2A\x9E" + b"\x00" * 32
    path.write_bytes(data)
    return str(path)


@pytest.mark.regression
class TestTruncatedFileDiagnostics:
    """验证截断文件返回结构化诊断，不抛 AttributeError。"""

    def test_truncated_linker_returns_diagnostics(self, truncated_file):
        result = parse_uasset_with_linker(truncated_file, tolerant=True)
        assert not result.is_success
        assert len(result.diagnostics) > 0

    def test_truncated_json_format_no_crash(self, truncated_file):
        """截断文件通过 parse_single(json) 应返回结构化错误。"""
        from uasset_read.core import parse_single
        output = parse_single(truncated_file, format="json", tolerant=True)
        data = json.loads(output)
        assert "status" in data
        assert data.get("status", {}).get("status") == "failed"


# ============================================================================
# 5. 状态模型集成
# ============================================================================

_SAMPLES_DIR = Path("E:/Develop/lib/Samples")
_has_samples_dir = _SAMPLES_DIR.exists()


def _get_test_asset():
    """获取第一个可用的测试 .uasset 文件。"""
    if not _has_samples_dir:
        pytest.skip("测试资产目录不存在")
    uasset_files = list(_SAMPLES_DIR.glob("**/*.uasset"))[:1]
    if not uasset_files:
        pytest.skip("未找到测试资产")
    return uasset_files[0]


class TestStatusModelIntegration:
    """状态模型集成测试。"""

    def test_json_output_status_format(self):
        """验证 JSON 输出状态格式正确。"""
        from uasset_read.core import parse_single
        asset_path = _get_test_asset()
        output = parse_single(str(asset_path), format="json")
        data = json.loads(output)
        assert "status" in data
        assert data["status"]["status"] in ["success", "partial", "failed"]

    def test_ir_status_preserved(self):
        """验证 IR 构建后状态信息保留。"""
        asset_path = _get_test_asset()
        result = parse_package(str(asset_path), tolerant=True)
        ir = build_package_ir(result)
        assert ir.status in ["success", "partial", "failed"]
