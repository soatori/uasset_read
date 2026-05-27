from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

SAMPLE_ASSET = Path(
    r"E:\Develop\lib\UnrealEngine\Samples\FirstPerson\Content\FirstPerson\Blueprints\BP_FirstPersonCharacter.uasset"
)


@lru_cache(maxsize=1)
def _parse_sample_asset():
    from uasset_read import parse_uasset_with_linker

    return parse_uasset_with_linker(str(SAMPLE_ASSET), tolerant=True)


@pytest.fixture(scope="session")
def sample_result():
    if not SAMPLE_ASSET.exists():
        pytest.skip(f"sample asset not found: {SAMPLE_ASSET}")
    return _parse_sample_asset()
