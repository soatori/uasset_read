"""Test AnimNotify debug output validates against schema (#555)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from uasset_read.pipeline.core import parse_uasset_with_linker
from uasset_read.ir_builder import build_package_ir
from uasset_read.semantic.builder import build_semantic_ir
from uasset_read.semantic.projection import project_semantic
from uasset_read.semantic.render import render_semantic_json
from uasset_read.semantic.validator import validate_semantic_document


def test_animnotify_debug_validates_against_schema(samples_dir: Path):
    """AnimNotify with debug evidence validates against schema."""
    sample = samples_dir / "ABP_RifleAnimLayers.uasset"
    if not sample.exists():
        pytest.skip("Sample not found")

    result = parse_uasset_with_linker(str(sample), tolerant=True)
    ir = build_package_ir(result)
    
    semantic_ir = build_semantic_ir(ir, source_path=str(sample), mode="debug")
    projected = project_semantic(semantic_ir, "debug")
    
    json_str = render_semantic_json(projected, include_schema=False)
    json.loads(json_str)  # verify valid JSON
    
    errors = validate_semantic_document(projected)
    assert not errors, f"Debug AnimNotify should validate: {errors}"


def test_animnotify_standard_validates_against_schema(samples_dir: Path):
    """AnimNotify without evidence (standard mode) validates against schema."""
    sample = samples_dir / "ABP_RifleAnimLayers.uasset"
    if not sample.exists():
        pytest.skip("Sample not found")

    result = parse_uasset_with_linker(str(sample), tolerant=True)
    ir = build_package_ir(result)
    semantic_ir = build_semantic_ir(ir, source_path=str(sample))
    projected = project_semantic(semantic_ir, "standard")
    
    errors = validate_semantic_document(projected)
    assert not errors, f"Standard AnimNotify should validate: {errors}"
