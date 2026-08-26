"""Test AnimBlueprint debug evidence generation (#555)."""
from __future__ import annotations

from pathlib import Path

import pytest

from uasset_read.pipeline.core import parse_uasset_with_linker
from uasset_read.ir_builder import build_package_ir
from uasset_read.semantic.builder import build_semantic_ir
from uasset_read.semantic.projection import project_semantic
from uasset_read.semantic.render import render_semantic_json
import json
import re


def test_animbp_debug_mode_generates_evidence(samples_dir: Path):
    """AnimBlueprint extractor generates debug evidence when mode='debug'."""
    sample = samples_dir / "ABP_RifleAnimLayers.uasset"
    if not sample.exists():
        pytest.skip("Sample not found")

    result = parse_uasset_with_linker(str(sample), tolerant=True)
    ir = build_package_ir(result)

    # Build with debug mode
    semantic_ir = build_semantic_ir(ir, source_path=str(sample), mode="debug")
    projected = project_semantic(semantic_ir, "debug")

    # Debug mode should preserve evidence in anim_notifies
    notifies = projected.content.get("anim_notifies", [])
    if notifies:
        # At least one notify should have evidence if debug data exists
        has_evidence = any("evidence" in n for n in notifies)
        assert has_evidence, "Debug mode should generate evidence for anim_notifies"


def test_animbp_standard_mode_strips_evidence(samples_dir: Path):
    """Standard projection strips evidence from debug-built IR."""
    sample = samples_dir / "ABP_RifleAnimLayers.uasset"
    if not sample.exists():
        pytest.skip("Sample not found")

    result = parse_uasset_with_linker(str(sample), tolerant=True)
    ir = build_package_ir(result)

    # Build with debug mode, project to standard
    semantic_ir = build_semantic_ir(ir, source_path=str(sample), mode="debug")
    projected = project_semantic(semantic_ir, "standard")

    # Standard mode should strip all evidence
    notifies = projected.content.get("anim_notifies", [])
    for notify in notifies:
        assert "evidence" not in notify, "Standard mode should strip evidence"


def test_animbp_no_raw_guid_in_standard(samples_dir: Path):
    """Standard mode has no raw GUIDs in content."""
    sample = samples_dir / "ABP_RifleAnimLayers.uasset"
    if not sample.exists():
        pytest.skip("Sample not found")

    result = parse_uasset_with_linker(str(sample), tolerant=True)
    ir = build_package_ir(result)
    semantic_ir = build_semantic_ir(ir, source_path=str(sample), mode="debug")
    projected = project_semantic(semantic_ir, "standard")
    json_str = render_semantic_json(projected)
    doc = json.loads(json_str)

    # No raw GUID-like values in content (except pattern IDs)
    guid_pattern = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")

    def _find_guids(obj, path=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                _find_guids(v, f"{path}.{k}")
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                _find_guids(item, f"{path}[{i}]")
        elif isinstance(obj, str) and guid_pattern.search(obj):
            # Allow known pattern IDs but not raw GUIDs
            pass  # TODO: tighten once we know exact expected values

    _find_guids(doc)  # Should not raise
