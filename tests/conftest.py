"""Shared test fixtures — manifest and path helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

SAMPLES_DIR = Path(__file__).parent / "samples"


@pytest.fixture
def samples_dir() -> Path:
    return SAMPLES_DIR


@pytest.fixture
def sample_path():
    """ABP_RifleAnimLayers — 10 exports, 2 asset roles."""
    return str(SAMPLES_DIR / "ABP_RifleAnimLayers.uasset")


@pytest.fixture
def multi_asset_sample():
    """ALS_AnimBP — 3395 exports, 2 asset roles."""
    return str(SAMPLES_DIR / "ALS_AnimBP.uasset")
