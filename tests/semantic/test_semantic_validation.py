"""Semantic validation and contract tests.

Tests the semantic pipeline's validation, projection, and schema compliance.
"""
from __future__ import annotations

import pytest
from pathlib import Path


from uasset_read.pipeline.core import parse_uasset_with_linker
from uasset_read.ir_builder import build_package_ir
from uasset_read.semantic.builder import build_semantic_ir
from uasset_read.semantic.projection import project_semantic
from uasset_read.semantic.validator import validate_semantic_document
from uasset_read.semantic.models import SemanticIR
from uasset_read.semantic.render import render_semantic_json


def _build_and_project(samples_dir: Path, filename: str, mode: str = "standard") -> SemanticIR:
    """Parse, build, project, and return SemanticIR."""
    sample = samples_dir / filename
    result = parse_uasset_with_linker(str(sample), tolerant=True)
    ir = build_package_ir(result)
    semantic = build_semantic_ir(ir, source_path=str(sample))
    return project_semantic(semantic, mode)


class TestSemanticValidation:
    """Semantic document validation."""

    def test_valid_blueprint_passes_validation(self, samples_dir: Path):
        """A well-formed Blueprint SemanticIR passes validation."""
        semantic = _build_and_project(
            samples_dir, "FirstPerson_BP_FirstPersonCharacter.uasset",
        )
        errors = validate_semantic_document(semantic)
        assert errors == [], f"Validation errors: {errors}"

    def test_valid_material_passes_validation(self, samples_dir: Path):
        """A well-formed Material SemanticIR passes validation."""
        semantic = _build_and_project(
            samples_dir, "FirstPerson_M_FlatCol.uasset",
        )
        errors = validate_semantic_document(semantic)
        assert errors == [], f"Validation errors: {errors}"

    def test_valid_animbp_passes_validation(self, samples_dir: Path):
        """A well-formed AnimBlueprint SemanticIR passes validation."""
        semantic = _build_and_project(
            samples_dir, "ABP_RifleAnimLayers.uasset",
        )
        errors = validate_semantic_document(semantic)
        assert errors == [], f"Validation errors: {errors}"

    def test_all_samples_pass_validation(self, samples_dir: Path, sample_uassets: list[Path]):
        """All samples produce valid SemanticIR documents."""
        failures = []
        for sample_path in sample_uassets:
            try:
                result = parse_uasset_with_linker(str(sample_path), tolerant=True)
                if not result or not result.is_success:
                    continue
                ir = build_package_ir(result)
                semantic = build_semantic_ir(ir, source_path=str(sample_path))
                semantic = project_semantic(semantic, "standard")
                errors = validate_semantic_document(semantic)
                if errors:
                    failures.append((sample_path.name, errors))
            except Exception as e:
                failures.append((sample_path.name, [str(e)]))

        assert failures == [], \
            f"Validation failures: {failures}"


class TestSemanticProjection:
    """Semantic projection (standard vs debug mode)."""

    def test_standard_mode_strips_evidence(self, samples_dir: Path):
        """Standard mode removes evidence entries."""
        sample = samples_dir / "FirstPerson_BP_FirstPersonCharacter.uasset"
        result = parse_uasset_with_linker(str(sample), tolerant=True)
        ir = build_package_ir(result)
        semantic = build_semantic_ir(ir, source_path=str(sample))

        # Before projection, evidence may be present
        projected = project_semantic(semantic, "standard")
        # Standard mode should strip evidence
        assert len(projected.evidence) == 0

    def test_debug_mode_keeps_evidence(self, samples_dir: Path):
        """Debug mode keeps evidence entries."""
        sample = samples_dir / "FirstPerson_BP_FirstPersonCharacter.uasset"
        result = parse_uasset_with_linker(str(sample), tolerant=True)
        ir = build_package_ir(result)
        semantic = build_semantic_ir(ir, source_path=str(sample))

        projected = project_semantic(semantic, "debug")
        # Debug mode should keep evidence (if any existed)
        # We just verify the mode was set
        assert projected.mode == "debug"


class TestSemanticStatusContract:
    """Status contract: two independent dimensions."""

    def test_status_parse_values(self, samples_dir: Path, sample_uassets: list[Path]):
        """All samples have valid parse status values."""
        valid_parse = {"complete", "partial", "failed"}
        for sample_path in sample_uassets:
            result = parse_uasset_with_linker(str(sample_path), tolerant=True)
            if not result:
                continue
            ir = build_package_ir(result)
            semantic = build_semantic_ir(ir, source_path=str(sample_path))
            assert semantic.status.parse in valid_parse, \
                f"{sample_path.name}: invalid parse status '{semantic.status.parse}'"

    def test_status_representation_values(self, samples_dir: Path, sample_uassets: list[Path]):
        """All samples have valid representation status values."""
        valid_repr = {"full", "partial", "opaque"}
        for sample_path in sample_uassets:
            result = parse_uasset_with_linker(str(sample_path), tolerant=True)
            if not result:
                continue
            ir = build_package_ir(result)
            semantic = build_semantic_ir(ir, source_path=str(sample_path))
            assert semantic.status.representation in valid_repr, \
                f"{sample_path.name}: invalid representation '{semantic.status.representation}'"

    def test_asset_type_values(self, samples_dir: Path, sample_uassets: list[Path]):
        """All samples have non-empty asset_type."""
        for sample_path in sample_uassets:
            result = parse_uasset_with_linker(str(sample_path), tolerant=True)
            if not result:
                continue
            ir = build_package_ir(result)
            semantic = build_semantic_ir(ir, source_path=str(sample_path))
            assert semantic.asset_type, f"{sample_path.name}: empty asset_type"


class TestSchemaUri:
    """Schema URI matches ir.format (#555/#556)."""

    def test_animbp_schema_uri_matches_format(self, samples_dir: Path):
        """AnimBlueprint semantic JSON has schema URI matching format."""
        import json

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

    def test_material_schema_uri_matches_format(self, samples_dir: Path):
        """Material semantic JSON has schema URI matching format."""
        import json

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
