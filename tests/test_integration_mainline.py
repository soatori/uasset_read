"""集成测试主线 — 合并自 test_integration_core.py、test_integration_types.py。

覆盖：核心集成。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from uasset_read.parse_uasset import parse_package, parse_uasset_with_linker
from uasset_read.renderers.json_renderer import JSONRenderer
from uasset_read.renderers.base import RenderOptions
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
    def test_parse_succeeds(self, bp_result):
        """解析器应成功解析（status != failed）。"""
        assert bp_result.status != "failed", f"解析失败: {bp_result.errors}"

    def test_has_graphs(self, bp_result):
        """应有至少 1 个图。"""
        assert len(bp_result.graphs) >= 1


# ============================================================================
# 2. 截断文件诊断
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
    def test_truncated_linker_returns_diagnostics(self, truncated_file):
        result = parse_uasset_with_linker(truncated_file, tolerant=True)
        assert not result.is_success
        assert len(result.diagnostics) > 0


# ============================================================================
# 3. 状态模型集成
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
    def test_ir_status_preserved(self):
        """验证 IR 构建后状态信息保留。"""
        asset_path = _get_test_asset()
        result = parse_package(str(asset_path), tolerant=True)
        ir = build_package_ir(result)
        assert ir.diagnostics_data.status in ["success", "partial", "failed"]
