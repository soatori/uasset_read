"""Tests for Skeleton parser parent_index correctness."""
from __future__ import annotations

from pathlib import Path

import pytest

from uasset_read.pipeline.core import parse_single


@pytest.fixture
def skeleton_sample(samples_dir: Path) -> Path:
    """Return a Skeleton .uasset sample file."""
    from tests.conftest import get_samples_by_category
    assets = get_samples_by_category(samples_dir, "skeleton")
    if not assets:
        pytest.skip("No Skeleton samples found")
    return assets[0]


def test_skeleton_parent_index_in_range(skeleton_sample: Path):
    """All parent_index values must be valid (>= -1 and < bone_count)."""
    result = parse_single(str(skeleton_sample))
    assert result is not None

    skeleton_export = None
    for export in result.export_map or []:
        class_name = str(getattr(export, "object_class", "") or "")
        if class_name == "Skeleton":
            skeleton_export = export
            break

    if skeleton_export is None:
        pytest.skip("No Skeleton export found in sample")

    handler_result = getattr(skeleton_export, "_handler_result", None)
    if handler_result is None:
        pytest.skip("No handler result on Skeleton export")

    bones = handler_result.get("bones", [])
    if not bones:
        pytest.skip("No bones in skeleton")

    bone_count = len(bones)
    for i, bone in enumerate(bones):
        parent_idx = bone.get("parent_index", -1)
        assert parent_idx >= -1, f"Bone {i}: parent_index {parent_idx} < -1"
        assert parent_idx < bone_count, f"Bone {i}: parent_index {parent_idx} >= bone_count {bone_count}"
