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
    get_file_processing_strategy,
    should_wait_for_memory,
    wait_and_cleanup,
    LARGE_FILE_THRESHOLD,
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
LARGE_FILE_THRESHOLD_LOCAL = LARGE_FILE_THRESHOLD
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
    """收集所有资产文件，大文件标记为分块处理而非跳过。"""
    all_files = sorted(
        p for p in sample_root.rglob("*")
        if p.is_file() and p.suffix.lower() in {".uasset", ".umap"}
    )

    # 限制总数
    if len(all_files) > MAX_ASSET_COUNT:
        all_files = all_files[:MAX_ASSET_COUNT]

    if not all_files:
        pytest.fail(f"No .uasset/.umap files found under {sample_root}")

    # 检查内存状态
    stats = get_memory_stats()
    print(
        f"\n[MemorySafety] Memory: process RSS={stats.process_rss_mb:.0f}MB, "
        f"system {stats.used_mb:.0f}MB used, {stats.available_mb:.0f}MB available ({stats.usage_percent*100:.1f}%)"
    )

    # 统计大文件数量
    large_count = sum(1 for p in all_files if p.stat().st_size > LARGE_FILE_THRESHOLD)
    if large_count > 0:
        print(f"[MemorySafety] {large_count} large files will use chunked processing")

    return all_files


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

def skip_if_too_large(path: Path) -> None:
    """检查文件处理策略，超大文件（>100MB）跳过测试。"""
    strategy, reason = get_file_processing_strategy(path)
    if strategy == "skip":
        pytest.skip(f"asset too large: {reason}")
    # 对于 chunked/critical 策略，不跳过，让解析器处理


def check_memory_before_test() -> None:
    """测试开始前检查内存状态，内存紧张时尝试清理而非跳过。"""
    # 如果内存紧张，先尝试清理
    if should_wait_for_memory():
        print("[MemorySafety] Memory pressure detected, cleaning up...")
        wait_and_cleanup(max_wait_seconds=5)

    # 清理后检查进程 RSS
    stats = get_memory_stats()
    if stats.process_rss_mb > PROCESS_RSS_CRITICAL_MB and stats.usage_percent > MEMORY_CRITICAL_WATERMARK:
        # 只有在进程RSS和系统内存都超限时才跳过
        pytest.skip(
            f"[MemorySafety] Memory critical: process RSS {stats.process_rss_mb:.0f}MB, "
            f"system {stats.usage_percent*100:.1f}% used"
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
