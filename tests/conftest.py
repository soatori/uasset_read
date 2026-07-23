from __future__ import annotations

import gc
import io
import json
import os
import struct
import subprocess
import sys
from pathlib import Path
from typing import Iterable

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
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


# ---------------------------------------------------------------------------
# core 模块 fixture
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_project_logging_after_each():
    """每个测试结束后重置 project_logging 全局状态。

    parse_package() 调用 configure_project_logging() 会设置
    package_logger.propagate=False，导致后续测试的 caplog
    无法捕获日志。此 fixture 在每个测试完成后立即恢复状态，
    防止全局日志配置泄漏到其他测试模块。
    """
    yield
    from uasset_read.project_logging import _reset_logging_state_for_tests
    _reset_logging_state_for_tests()


# ---------------------------------------------------------------------------
# parsers 模块辅助类
# ---------------------------------------------------------------------------

class FakeProperty:
    """模拟属性对象"""
    def __init__(self, name: str, value):
        self.name = name
        self.value = value


class FakeExport:
    """模拟 export 对象"""
    def __init__(self, properties=None):
        if isinstance(properties, dict):
            self.properties = [FakeProperty(k, v) for k, v in properties.items()]
        elif isinstance(properties, list):
            self.properties = properties
        else:
            self.properties = []
        self.custom_data = {}


class FakeContext:
    """模拟解析上下文"""
    def __init__(self):
        self.warnings = []


class FakeArchive:
    """基于 BytesIO 的轻量 FArchive 模拟。"""
    def __init__(self, data: bytes) -> None:
        self._buf = io.BytesIO(data)

    def read(self, size: int) -> bytes:
        return self._buf.read(size)

    def read_i32(self) -> int:
        return struct.unpack("<i", self.read(4))[0]

    def read_i64(self) -> int:
        return struct.unpack("<q", self.read(8))[0]

    def read_fstring(self) -> str:
        length = self.read_i32()
        if length == 0:
            return ""
        if length > 0:
            raw = self.read(length)
            return raw[:-1].decode("utf-8", errors="replace") if raw.endswith(b"\x00") else raw.decode("utf-8", errors="replace")
        else:
            byte_count = -length * 2
            raw = self.read(byte_count)
            return raw[:-2].decode("utf-16-le", errors="replace") if raw.endswith(b"\x00\x00") else raw.decode("utf-16-le", errors="replace")

    def read_name(self, name_map=None) -> str:
        idx = self.read_i32()
        _number = self.read_i32()
        if name_map and 0 <= idx < len(name_map):
            return name_map[idx]
        return f"Name_{idx}"

    def tell(self) -> int:
        return self._buf.tell()

    def seek(self, pos: int) -> None:
        self._buf.seek(pos)

    def total_size(self) -> int:
        pos = self._buf.tell()
        self._buf.seek(0, 2)
        end = self._buf.tell()
        self._buf.seek(pos)
        return end
