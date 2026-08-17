"""Test Material preserves diagnostics and references (#556)."""
from __future__ import annotations

from pathlib import Path

import pytest

from uasset_read.pipeline.core import parse_uasset_with_linker
from uasset_read.ir_builder import build_package_ir
from uasset_read.semantic.builder import build_semantic_ir


def test_material_preserves_diagnostics(samples_dir: Path):
    """Material semantic IR preserves parser diagnostics from envelope."""
    sample = samples_dir / "FirstPerson_M_FlatCol.uasset"
    if not sample.exists():
        pytest.skip("Sample not found")

    result = parse_uasset_with_linker(str(sample), tolerant=True)
    ir = build_package_ir(result)
    semantic_ir = build_semantic_ir(ir, source_path=str(sample))

    # Material format owns diagnostics in content, but envelope should also have them
    # when there are actual diagnostics
    if ir.diagnostics_data and (ir.diagnostics_data.errors or ir.diagnostics_data.warnings):
        # Envelope diagnostics should not be empty when there are actual diagnostics
        assert semantic_ir.diagnostics, "Material should preserve envelope diagnostics"


def test_material_preserves_references(samples_dir: Path):
    """Material semantic IR preserves import/export references from envelope."""
    sample = samples_dir / "FirstPerson_M_FlatCol.uasset"
    if not sample.exists():
        pytest.skip("Sample not found")

    result = parse_uasset_with_linker(str(sample), tolerant=True)
    ir = build_package_ir(result)
    semantic_ir = build_semantic_ir(ir, source_path=str(sample))

    # Material format owns references in content, but envelope should also have them
    if ir.imports or ir.exports:
        # Envelope references should not be empty when there are imports/exports
        assert semantic_ir.references, "Material should preserve envelope references"


def test_material_content_no_hardcoded_empty_arrays(samples_dir: Path):
    """Material content dict does not hardcode empty references/diagnostics."""
    sample = samples_dir / "FirstPerson_M_FlatCol.uasset"
    if not sample.exists():
        pytest.skip("Sample not found")

    result = parse_uasset_with_linker(str(sample), tolerant=True)
    ir = build_package_ir(result)
    semantic_ir = build_semantic_ir(ir, source_path=str(sample))

    # Content should not have hardcoded empty arrays that override envelope
    content = semantic_ir.content
    # If references/diagnostics are in content, they should have actual data
    if "references" in content:
        assert content["references"] != [], "Material content should not hardcode empty references"
    if "diagnostics" in content:
        assert content["diagnostics"] != [], "Material content should not hardcode empty diagnostics"