from __future__ import annotations

import gc
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
DEFAULT_SAMPLE_ROOT = Path(r"E:\Develop\lib\Samples")

# ---------------------------------------------------------------------------
# 内存安全常量
# ---------------------------------------------------------------------------
MAX_PARSE_FILE_SIZE = 50 * 1024 * 1024   # 50MB — 超过此大小的文件跳过解析
MAX_ASSET_COUNT = 200                     # all_assets 最多返回的文件数
PARSE_TIMEOUT = 120                       # 单次解析超时（秒）


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
    assets = sorted(
        p for p in sample_root.rglob("*")
        if p.is_file() and p.suffix.lower() in {".uasset", ".umap"}
    )
    if len(assets) > MAX_ASSET_COUNT:
        assets = assets[:MAX_ASSET_COUNT]
    if not assets:
        pytest.fail(f"No .uasset/.umap files found under {sample_root}")
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
    """文件过大时跳过测试，防止 OOM。"""
    if path.stat().st_size > max_size:
        size_mb = path.stat().st_size / 1024 / 1024
        limit_mb = max_size / 1024 / 1024
        pytest.skip(f"asset too large: {size_mb:.1f}MB > {limit_mb}MB")


def cleanup_after_parse() -> None:
    """解析后强制 GC 回收，减少循环引用导致的内存残留。"""
    gc.collect()
