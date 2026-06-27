from __future__ import annotations

import gc
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable

import pytest

# 导入内存安全模块
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from uasset_read.memory_safety import (
    MemoryGuard,
    check_memory_pressure,
    cleanup_after_parse as _cleanup_after_parse,
    emergency_cleanup,
    force_gc,
    get_memory_stats,
    should_skip_file,
    check_process_rss_limit,
    MAX_PARSE_FILE_SIZE,
    MAX_ASSET_COUNT,
    PARSE_TIMEOUT,
    MEMORY_CRITICAL_WATERMARK,
    PROCESS_RSS_CRITICAL_MB,
    PROCESS_RSS_HIGH_WATERMARK_MB,
)


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
DEFAULT_SAMPLE_ROOT = Path(r"E:\Develop\lib\Samples")

# ---------------------------------------------------------------------------
# 内存安全常量（从 memory_safety 模块导入）
# ---------------------------------------------------------------------------
# 保留向后兼容的本地别名
MAX_PARSE_FILE_SIZE_LOCAL = MAX_PARSE_FILE_SIZE
MAX_ASSET_COUNT_LOCAL = MAX_ASSET_COUNT


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--sample-root",
        default=os.environ.get("UE_SAMPLE_ROOT", str(DEFAULT_SAMPLE_ROOT)),
        help="Root directory containing Unreal Engine sample assets.",
    )
    parser.addoption(
        "--allow-missing-assets",
        action="store_true",
        default=False,
        help="Skip asset-backed tests when the sample root is missing.",
    )


@pytest.fixture(scope="session")
def sample_root(pytestconfig: pytest.Config) -> Path:
    root = Path(pytestconfig.getoption("--sample-root"))
    if root.exists():
        return root
    message = (
        f"UE sample root not found: {root}. "
        "Set UE_SAMPLE_ROOT, pass --sample-root, or use --allow-missing-assets."
    )
    if pytestconfig.getoption("--allow-missing-assets"):
        pytest.skip(message)
    pytest.fail(message)


@pytest.fixture(scope="session")
def all_assets(sample_root: Path) -> list[Path]:
    """收集所有资产文件，自动过滤大文件防止 OOM。"""
    all_files = sorted(
        p for p in sample_root.rglob("*")
        if p.is_file() and p.suffix.lower() in {".uasset", ".umap"}
    )

    # 过滤大文件，防止内存溢出
    assets = []
    skipped_large = 0
    for p in all_files:
        should_skip, reason = should_skip_file(p)
        if should_skip:
            skipped_large += 1
            continue
        assets.append(p)

    # 限制总数
    if len(assets) > MAX_ASSET_COUNT:
        assets = assets[:MAX_ASSET_COUNT]

    if skipped_large > 0:
        print(f"\n[MemorySafety] Skipped {skipped_large} large files to prevent OOM")

    if not assets:
        pytest.fail(f"No .uasset/.umap files found under {sample_root}")

    # 检查内存状态
    stats = get_memory_stats()
    print(
        f"\n[MemorySafety] Memory: process RSS={stats.process_rss_mb:.0f}MB, "
        f"system {stats.used_mb:.0f}MB used, {stats.available_mb:.0f}MB available ({stats.usage_percent*100:.1f}%)"
    )

    return assets


@pytest.fixture(scope="session")
def representative_asset(all_assets: list[Path]) -> Path:
    preferred = [
        "BP_FirstPersonCharacter.uasset",
        "BP_ThirdPersonCharacter.uasset",
        "SKM_Manny.uasset",
    ]
    by_name = {p.name: p for p in all_assets}
    for name in preferred:
        if name in by_name:
            return by_name[name]
    return all_assets[0]


@pytest.fixture(scope="session")
def blueprint_asset(all_assets: list[Path], representative_asset: Path) -> Path:
    preferred = {
        "BP_FirstPersonCharacter.uasset",
        "BP_ThirdPersonCharacter.uasset",
        "ABP_Manny.uasset",
        "ABP_Manny_Combat.uasset",
    }
    for asset in all_assets:
        if asset.name in preferred:
            return asset
    for asset in all_assets:
        lowered = asset.name.lower()
        if lowered.startswith("bp_") or "blueprint" in str(asset).lower():
            return asset
    return representative_asset


def python_env() -> dict[str, str]:
    env = os.environ.copy()
    pythonpath = str(SRC_DIR)
    if env.get("PYTHONPATH"):
        pythonpath = pythonpath + os.pathsep + env["PYTHONPATH"]
    env["PYTHONPATH"] = pythonpath
    return env


def run_python(args: Iterable[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        env=python_env(),
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def parse_json_output(output: str) -> dict:
    return json.loads(output)


# ---------------------------------------------------------------------------
# 内存安全辅助
# ---------------------------------------------------------------------------

def skip_if_too_large(path: Path, max_size: int = MAX_PARSE_FILE_SIZE) -> None:
    """文件过大时跳过测试，防止 OOM。

    使用 memory_safety 模块的完整检查逻辑。
    """
    should_skip, reason = should_skip_file(path)
    if should_skip:
        pytest.skip(f"asset too large: {reason}")


def check_memory_before_test() -> None:
    """测试开始前检查内存状态（系统级 + 进程级），必要时跳过测试。"""
    # 检查进程 RSS（更直接的 OOM 指标）
    rss_warning = check_process_rss_limit()
    if rss_warning:
        pytest.skip(f"[MemorySafety] {rss_warning}")

    stats = get_memory_stats()
    if stats.usage_percent > MEMORY_CRITICAL_WATERMARK:
        pytest.skip(
            f"[MemorySafety] System memory critical: {stats.usage_percent*100:.1f}% used, "
            f"process RSS {stats.process_rss_mb:.0f}MB"
        )


# ---------------------------------------------------------------------------
# pytest hooks — 内存监控
# ---------------------------------------------------------------------------

def pytest_runtest_setup(item):
    """每个测试开始前检查内存状态。"""
    check_memory_before_test()


def pytest_runtest_teardown(item):
    """每个测试结束后清理内存。"""
    _cleanup_after_parse()


def pytest_sessionfinish(session, exitstatus):
    """测试会话结束时输出内存统计。"""
    stats = get_memory_stats()
    print(
        f"\n[MemorySafety] Final memory: process RSS={stats.process_rss_mb:.0f}MB, "
        f"system {stats.usage_percent*100:.1f}% used, {stats.available_mb:.0f}MB available"
    )
