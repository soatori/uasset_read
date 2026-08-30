"""Shared fixtures for contract tests."""

from __future__ import annotations

from pathlib import Path

import pytest

SAMPLES_DIR = Path(__file__).parent.parent / "samples"


@pytest.fixture
def samples_dir() -> Path:
    return SAMPLES_DIR
