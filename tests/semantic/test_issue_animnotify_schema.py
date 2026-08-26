import json
from pathlib import Path
import pytest

from uasset_read.pipeline.core import parse_uasset_with_linker
from uasset_read.ir_builder import build_package_ir
from uasset_read.semantic.builder import build_semantic_ir
from uasset_read.semantic.projection import project_semantic
from uasset_read.semantic.render import render_semantic_json


def _load_animbp_schema():
    """Load the anim_blueprint_semantic JSON Schema."""
    schema_path = Path(__file__).resolve().parents[2] / "src" / "uasset_read" / "schemas" / "anim_blueprint_semantic.schema.json"
    with open(schema_path) as f:
        return json.load(f)


def _build_rendered_dict(samples_dir: Path, filename: str, mode: str = "standard") -> dict:
    """Parse, build, project, render, and return as dict."""
    sample = samples_dir / filename
    result = parse_uasset_with_linker(str(sample), tolerant=True)
    ir = build_package_ir(result)
    semantic_ir = build_semantic_ir(ir, source_path=str(sample), mode=mode)
    projected = project_semantic(semantic_ir, mode)
    json_str = render_semantic_json(projected, include_schema=False)
    return json.loads(json_str)


class TestAnimBlueprintSchemaValidation:
    """Validate rendered JSON against Draft 2020-12 Schema."""

    def test_schema_is_valid_draft202012(self):
        """The schema itself is valid Draft 2020-12."""
        from jsonschema import Draft202012Validator
        schema = _load_animbp_schema()
        Draft202012Validator.check_schema(schema)

    def test_standard_real_sample_validates(self, samples_dir: Path):
        """Standard projection of real ABP sample validates against schema."""
        from jsonschema import Draft202012Validator
        if not (samples_dir / "ABP_RifleAnimLayers.uasset").exists():
            pytest.skip("Sample not found")
        schema = _load_animbp_schema()
        doc = _build_rendered_dict(samples_dir, "ABP_RifleAnimLayers.uasset", "standard")
        Draft202012Validator(schema).validate(doc)

    def test_debug_real_sample_validates(self, samples_dir: Path):
        """Debug projection of real ABP sample validates against schema."""
        from jsonschema import Draft202012Validator
        if not (samples_dir / "ABP_RifleAnimLayers.uasset").exists():
            pytest.skip("Sample not found")
        schema = _load_animbp_schema()
        doc = _build_rendered_dict(samples_dir, "ABP_RifleAnimLayers.uasset", "debug")
        Draft202012Validator(schema).validate(doc)


class TestProjectionInvariants:
    """Standard/debug projection invariants."""

    def test_standard_from_debug_matches_direct(self, samples_dir: Path):
        """project_semantic(debug, standard) == build_semantic_ir(standard)."""
        if not (samples_dir / "ABP_RifleAnimLayers.uasset").exists():
            pytest.skip("Sample not found")
        sample = samples_dir / "ABP_RifleAnimLayers.uasset"
        result = parse_uasset_with_linker(str(sample), tolerant=True)
        ir = build_package_ir(result)

        direct = project_semantic(build_semantic_ir(ir, source_path=str(sample)), "standard")
        from_debug = project_semantic(build_semantic_ir(ir, source_path=str(sample), mode="debug"), "standard")

        assert render_semantic_json(direct) == render_semantic_json(from_debug)

    def test_standard_has_no_evidence(self, samples_dir: Path):
        """Standard projection contains no evidence anywhere."""
        if not (samples_dir / "ABP_RifleAnimLayers.uasset").exists():
            pytest.skip("Sample not found")
        schema = _load_animbp_schema()
        doc = _build_rendered_dict(samples_dir, "ABP_RifleAnimLayers.uasset", "standard")

        def _find_evidence(obj):
            if isinstance(obj, dict):
                if "evidence" in obj:
                    return True
                return any(_find_evidence(v) for v in obj.values())
            if isinstance(obj, list):
                return any(_find_evidence(item) for item in obj)
            return False

        assert not _find_evidence(doc), "Standard mode must not contain evidence"

    def test_no_anim_blueprint_data_in_coverage(self, samples_dir: Path):
        """Real ABP sample should not report no_anim_blueprint_data."""
        if not (samples_dir / "ABP_RifleAnimLayers.uasset").exists():
            pytest.skip("Sample not found")
        sample = samples_dir / "ABP_RifleAnimLayers.uasset"
        result = parse_uasset_with_linker(str(sample), tolerant=True)
        ir = build_package_ir(result)
        semantic = build_semantic_ir(ir, source_path=str(sample))
        coverage = semantic.content.get("coverage", [])
        assert not any(
            entry.get("reason") == "no_anim_blueprint_data"
            for entry in coverage
        ), f"Should not report no_anim_blueprint_data: {coverage}"
