"""兼容性抽测验证 — 确认固定种子抽测脚本的验收标准。

此测试运行 compat_check.py 脚本的内部逻辑（不依赖 subprocess），
验证核心抽测管线的正确性。
"""
from __future__ import annotations

import json
import os

import pytest

from scripts.compat_check import (
    discover_assets,
    select_assets,
    run_single_check,
    build_summary,
    DEFAULT_SAMPLE_ROOT,
    DEFAULT_SEED,
    DEFAULT_COUNT,
)


_has_sample_root = os.path.isdir(DEFAULT_SAMPLE_ROOT)


@pytest.fixture(scope="module")
def all_assets() -> list[str]:
    if not _has_sample_root:
        pytest.skip("Sample root not available")
    return discover_assets(DEFAULT_SAMPLE_ROOT)


@pytest.fixture(scope="module")
def selected_assets(all_assets: list[str]) -> list[str]:
    return select_assets(all_assets, DEFAULT_COUNT, DEFAULT_SEED)


class TestAssetDiscovery:
    """资产发现基础验证。"""

    def test_discover_assets_finds_files(self, all_assets):
        assert len(all_assets) > 100, f"Expected >100 assets, got {len(all_assets)}"

    def test_all_discovered_are_uasset(self, all_assets):
        for asset in all_assets[:50]:  # 检查前 50 个
            assert asset.endswith(".uasset"), f"Non-uasset found: {asset}"

    def test_select_assets_deterministic(self, all_assets):
        """相同种子应产生相同选择。"""
        a = select_assets(all_assets, 10, seed=42)
        b = select_assets(all_assets, 10, seed=42)
        assert a == b

    def test_select_assets_count(self, all_assets):
        selected = select_assets(all_assets, DEFAULT_COUNT, DEFAULT_SEED)
        assert len(selected) == DEFAULT_COUNT


@pytest.mark.integration
@pytest.mark.skipif(not _has_sample_root, reason="Sample root not available")
class TestSingleAssetCheck:
    """单资产检测验证。"""

    def test_known_good_asset_returns_valid_json(self):
        """已知良好的资产应返回合法 JSON。"""
        asset = os.path.join(
            DEFAULT_SAMPLE_ROOT,
            r"FirstPerson\Content\LevelPrototyping\Meshes\SM_Cube.uasset",
        )
        if not os.path.isfile(asset):
            pytest.skip("Test asset not found")

        report = run_single_check(asset, timeout=30)
        assert report.is_valid_json, f"Invalid JSON: {report.error_message}"
        assert report.status in ("success", "partial", "failed"), f"Unexpected status: {report.status}"

    def test_timeout_field_is_set(self):
        """超时时应正确标记。"""
        # 使用一个不存在的文件来测试 subprocess_error 路径
        report = run_single_check("nonexistent.uasset", timeout=5)
        assert report.status in ("failed", "subprocess_error", "empty_output")


@pytest.mark.integration
@pytest.mark.skipif(not _has_sample_root, reason="Sample root not available")
class TestCompatSummary:
    """汇总统计验证。"""

    def test_build_summary_with_mock_results(self):
        """使用模拟数据验证汇总计算。"""
        from scripts.compat_check import AssetReport

        results = [
            AssetReport("a.uasset", "a", 0, "success", True, 0, "", 0.3),
            AssetReport("b.uasset", "b", 0, "success", True, 2, "linker", 0.5),
            AssetReport("c.uasset", "c", 1, "failed", True, 5, "name_table", 1.0),
        ]
        summary = build_summary(results)

        assert summary["total"] == 3
        assert summary["success"] == 2
        assert summary["failed"] == 1
        assert summary["timeout"] == 0
        assert summary["valid_json_count"] == 3
        assert summary["failure_stages"] == {"name_table": 1}

    def test_build_summary_empty(self):
        summary = build_summary([])
        assert summary["total"] == 0
        assert summary["success_rate"] == "N/A"
