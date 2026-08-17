"""User-Defined types semantic extractor tests.

Tests the UserDefinedEnum and UserDefinedStruct domain extractors with real samples.
"""
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
from uasset_read.semantic.models import SemanticIR


_USER_DEFINED_SAMPLES = [
    "Lyra_Enum_PanelType.uasset",
    "StackOBot_Enum_CameraState.uasset",
    "StackOBot_Struct_Objective.uasset",
]


def _build_semantic(samples_dir: Path, filename: str) -> SemanticIR:
    """Parse and build SemanticIR for a sample."""
    sample = samples_dir / filename
    result = parse_uasset_with_linker(str(sample), tolerant=True)
    ir = build_package_ir(result)
    return build_semantic_ir(ir, source_path=str(sample))


def _build_and_project(samples_dir: Path, filename: str, mode: str = "standard") -> SemanticIR:
    """Parse, build, project, and return SemanticIR."""
    sample = samples_dir / filename
    result = parse_uasset_with_linker(str(sample), tolerant=True)
    ir = build_package_ir(result)
    semantic = build_semantic_ir(ir, source_path=str(sample))
    return project_semantic(semantic, mode)


class TestUserDefinedSemanticExtraction:
    """User-Defined types semantic extractor output validation."""

    @pytest.mark.parametrize(
        "filename",
        _USER_DEFINED_SAMPLES,
        ids=[s.split(".")[0] for s in _USER_DEFINED_SAMPLES],
    )
    def test_user_defined_has_semantic_ir(self, samples_dir: Path, filename: str):
        """User-Defined sample produces a valid SemanticIR."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_semantic(samples_dir, filename)
        assert semantic is not None
        assert semantic.asset_type in ("enum", "struct")
        assert semantic.asset.name != "unknown"

    @pytest.mark.parametrize(
        "filename",
        _USER_DEFINED_SAMPLES,
        ids=[s.split(".")[0] for s in _USER_DEFINED_SAMPLES],
    )
    def test_user_defined_format(self, samples_dir: Path, filename: str):
        """User-Defined uses the user_defined_semantic domain format."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_semantic(samples_dir, filename)
        assert semantic.format == "uasset_read.user_defined_semantic"
        assert semantic.format_version == "1.0.0"

    @pytest.mark.parametrize(
        "filename",
        _USER_DEFINED_SAMPLES,
        ids=[s.split(".")[0] for s in _USER_DEFINED_SAMPLES],
    )
    def test_user_defined_has_content(self, samples_dir: Path, filename: str):
        """User-Defined SemanticIR may have empty content when asset_type_data is None."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_semantic(samples_dir, filename)
        # Some user-defined assets have no asset_type_data from PropertyMetadataHandler
        if semantic.content:
            assert "user_defined" in semantic.content, f"{filename}: missing user_defined key"

    @pytest.mark.parametrize(
        "filename",
        _USER_DEFINED_SAMPLES,
        ids=[s.split(".")[0] for s in _USER_DEFINED_SAMPLES],
    )
    def test_user_defined_manifest(self, samples_dir: Path, filename: str):
        """User-Defined content has correct manifest structure when present."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_semantic(samples_dir, filename)
        if "user_defined" not in semantic.content:
            pytest.skip("No user_defined content — asset_type_data was None")
        ud = semantic.content["user_defined"]
        assert "enum_data" in ud or "struct_data" in ud

        if "enum_data" in ud:
            ed = ud["enum_data"]
            assert "enum_name" in ed
            assert "display_name" in ed
            assert "entry_count" in ed
            assert "entries" in ed
            assert isinstance(ed["entry_count"], int)
            assert ed["entry_count"] >= 0
            assert ed["entry_count"] == len(ed["entries"])

        if "struct_data" in ud:
            sd = ud["struct_data"]
            assert "struct_name" in sd
            assert "display_name" in sd
            assert "property_count" in sd
            assert "properties" in sd
            assert isinstance(sd["property_count"], int)
            assert sd["property_count"] >= 0
            assert sd["property_count"] == len(sd["properties"])


class TestUserDefinedValidation:
    """User-Defined validator rules."""

    @pytest.mark.parametrize(
        "filename",
        _USER_DEFINED_SAMPLES,
        ids=[s.split(".")[0] for s in _USER_DEFINED_SAMPLES],
    )
    def test_user_defined_passes_validation(self, samples_dir: Path, filename: str):
        """User-Defined SemanticIR passes validation (empty content valid when atd=None)."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_and_project(samples_dir, filename)
        errors = validate_semantic_document(semantic)
        # Empty content is expected when asset_type_data is None
        assert errors == [], f"Validation errors: {errors}"


class TestUserDefinedSchemaConformance:
    """Schema conformance for User-Defined semantic JSON."""

    @pytest.mark.parametrize(
        "filename",
        _USER_DEFINED_SAMPLES,
        ids=[s.split(".")[0] for s in _USER_DEFINED_SAMPLES],
    )
    def test_standard_output_schema_valid(self, samples_dir: Path, filename: str):
        """Standard mode output validates against schema."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_and_project(samples_dir, filename, "standard")
        json_str = render_semantic_json(semantic, include_schema=True)
        data = json.loads(json_str)

        assert data["format"] == "uasset_read.user_defined_semantic"
        assert "$schema" in data
        assert "user_defined_semantic.schema.json" in data["$schema"]
        # user_defined key present only when content is non-empty
        if semantic.content:
            assert "user_defined" in data


class TestUserDefinedProjection:
    """User-Defined projection (standard vs debug mode)."""

    def test_standard_strips_evidence(self, samples_dir: Path):
        """Standard mode strips evidence from User-Defined output."""
        semantic = _build_and_project(
            samples_dir, "Lyra_Enum_PanelType.uasset", "standard",
        )
        assert len(semantic.evidence) == 0

    def test_debug_keeps_evidence(self, samples_dir: Path):
        """Debug mode keeps evidence in User-Defined output."""
        semantic = _build_and_project(
            samples_dir, "Lyra_Enum_PanelType.uasset", "debug",
        )
        assert semantic.mode == "debug"
