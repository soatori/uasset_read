from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
DEFAULT_SAMPLE_ROOT = Path(r"E:\Develop\lib\UnrealEngine\Samples")


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
