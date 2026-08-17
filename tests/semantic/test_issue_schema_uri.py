"""Test schema URI matches ir.format (#555/#556)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from uasset_read.pipeline.core import parse_uasset_with_linker
from uasset_read.ir_builder import build_package_ir
from uasset_read.semantic.builder import build_semantic_ir
from uasset_read.semantic.render import render_semantic_json


def test_animbp_schema_uri_matches_format(samples_dir: Path):
    """AnimBlueprint semantic JSON has schema URI matching format."""
    sample = samples_dir / "ABP_RifleAnimLayers.uasset"
    if not sample.exists():
        pytest.skip("Sample not found")

    result = parse_uasset_with_linker(str(sample), tolerant=True)
    ir = build_package_ir(result)
    semantic_ir = build_semantic_ir(ir, source_path=str(sample))
    
    json_str = render_semantic_json(semantic_ir, include_schema=True)
    data = json.loads(json_str)
    
    assert "$schema" in data
    assert "anim_blueprint_semantic.schema.json" in data["$schema"]


def test_material_schema_uri_matches_format(samples_dir: Path):
    """Material semantic JSON has schema URI matching format."""
    sample = samples_dir / "FirstPerson_M_FlatCol.uasset"
    if not sample.exists():
        pytest.skip("Sample not found")

    result = parse_uasset_with_linker(str(sample), tolerant=True)
    ir = build_package_ir(result)
    semantic_ir = build_semantic_ir(ir, source_path=str(sample))
    
    json_str = render_semantic_json(semantic_ir, include_schema=True)
    data = json.loads(json_str)
    
    assert "$schema" in data
    assert "material_semantic.schema.json" in data["$schema"]


def test_generic_schema_uri_for_unknown_format(samples_dir: Path):
    """Unknown asset type uses generic semantic.schema.json."""
    pytest.skip("No unknown-type sample available")
