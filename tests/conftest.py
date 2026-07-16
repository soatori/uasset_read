from __future__ import annotations

import gc
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from uasset_read.memory_safety import (
    LARGE_FILE_THRESHOLD,
    MAX_ASSET_COUNT,
    get_memory_stats,
)


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
DEFAULT_SAMPLE_ROOT = ROOT / "tests" / "samples"

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
    """Collect a bounded set of sample assets."""
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
        print(f"[MemorySafety] {large_count} large files use size-tier resource limits")

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
    """Compatibility helper; file size no longer causes tests to skip."""
    if not path.is_file():
        pytest.skip(f"asset not found: {path}")


def asset_path(sample_root: Path, relative_path: str) -> Path:
    """Build full asset path from sample_root and relative path."""
    full_path = sample_root / relative_path
    if not full_path.is_file():
        pytest.skip(f"Asset not found: {full_path}")
    return full_path


# Common asset relative paths (using local samples)
ASSET_TEXTURE_BRICK = "StarterContent_M_Wood_Walnut.uasset"
ASSET_MATERIAL_ROCK = "IntroToUnreal_M_Plastic.uasset"
ASSET_MESH_CHAIR = "StackOBot_M_BotBase.uasset"
ASSET_MESH_MANNY = "CiciToon_SK_Mannequin.uasset"
ASSET_BLUEPRINT_FIRST_PERSON = "FirstPerson_BP_FirstPersonGameMode.uasset"
ASSET_BLUEPRINT_THIRD_PERSON = "StackOBot_BP_Drone.uasset"


# ---------------------------------------------------------------------------
# pytest hooks
# ---------------------------------------------------------------------------

def pytest_runtest_teardown(item):
    """Run one cyclic-GC pass after each test."""
    gc.collect()


def pytest_sessionfinish(session, exitstatus):
    """Print final process/system memory statistics."""
    stats = get_memory_stats()
    print(
        f"\n[MemorySafety] Final memory: process RSS={stats.process_rss_mb:.0f}MB, "
        f"system {stats.usage_percent*100:.1f}% used, {stats.available_mb:.0f}MB available"
    )


@pytest.fixture(autouse=True)
def clean_global_state():
    """每个测试前清理全局注册表状态，防止测试间状态泄漏"""
    from uasset_read.renderers import RENDERER_REGISTRY

    original_renderers = RENDERER_REGISTRY.copy()

    yield

    # 恢复状态
    RENDERER_REGISTRY.clear()
    RENDERER_REGISTRY.update(original_renderers)
