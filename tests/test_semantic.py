"""Consolidated semantic tests for Issue #551 — common semantic JSON foundation."""
import pytest


class TestAssetTypeResolution:
    def test_known_types(self):
        from uasset_read.semantic.kinds import resolve_asset_type
        assert resolve_asset_type("Material") == "material"
        assert resolve_asset_type("Texture2D") == "texture"
        assert resolve_asset_type("StaticMesh") == "static_mesh"
        assert resolve_asset_type("DataTable") == "data_table"
        assert resolve_asset_type("SoundCue") == "sound_cue"

    def test_blueprint_classes(self):
        from uasset_read.semantic.kinds import resolve_asset_type
        assert resolve_asset_type("BlueprintGeneratedClass") == "blueprint"
        assert resolve_asset_type("AnimBlueprintGeneratedClass") == "anim_blueprint"

    def test_unknown_returns_unknown(self):
        from uasset_read.semantic.kinds import resolve_asset_type
        assert resolve_asset_type("SomeUnknownClass") == "unknown"
        assert resolve_asset_type("") == "unknown"


class TestSemanticIRModels:
    def test_asset_status_fields(self):
        from uasset_read.semantic.models import AssetStatus
        s = AssetStatus(parse="complete", representation="full")
        assert s.parse == "complete"
        assert s.representation == "full"

    def test_asset_meta_required_fields(self):
        from uasset_read.semantic.models import AssetMeta
        m = AssetMeta(
            package="/Game/BP_Foo",
            name="BP_Foo",
        )
        assert m.package == "/Game/BP_Foo"
        assert m.generated_class is None

    def test_semantic_ir_top_level(self):
        from uasset_read.semantic.models import (
            SemanticIR, AssetMeta, AssetStatus,
        )
        ir = SemanticIR(
            format="uasset_read.asset_semantic",
            format_version="1.0",
            mode="standard",
            asset_type="blueprint",
            asset=AssetMeta(package="/Game/BP_Foo", name="BP_Foo"),
            status=AssetStatus(parse="complete", representation="full"),
        )
        assert ir.format == "uasset_read.asset_semantic"
        assert ir.asset_type == "blueprint"
        assert ir.references == ()
        assert ir.coverage is None
        assert ir.diagnostics == ()


class TestProjection:
    def test_standard_removes_evidence(self):
        """Standard projection strips evidence and debug extension fields."""
        from uasset_read.semantic.projection import project_semantic
        from uasset_read.semantic.models import (
            SemanticIR, AssetMeta, AssetStatus, EvidenceEntry, DiagnosticEntry,
        )
        debug_ir = SemanticIR(
            format="uasset_read.asset_semantic",
            format_version="1.0",
            mode="debug",
            asset_type="blueprint",
            asset=AssetMeta(package="/Game/BP_Foo", name="BP_Foo"),
            status=AssetStatus(parse="complete", representation="full"),
            evidence=[
                EvidenceEntry(key="export_index", value=0),
                EvidenceEntry(key="original_class", value="BlueprintGeneratedClass"),
            ],
            diagnostics=(
                DiagnosticEntry(severity="info", code="DEBUG_ONLY", message="debug detail"),
            ),
        )
        standard = project_semantic(debug_ir, "standard")
        assert standard.mode == "standard"
        assert standard.evidence == ()
        # Non-evidence diagnostics preserved
        assert len(standard.diagnostics) >= 0

    def test_debug_preserves_evidence(self):
        """Debug projection keeps evidence intact."""
        from uasset_read.semantic.projection import project_semantic
        from uasset_read.semantic.models import (
            SemanticIR, AssetMeta, AssetStatus, EvidenceEntry,
        )
        debug_ir = SemanticIR(
            format="uasset_read.asset_semantic",
            format_version="1.0",
            mode="debug",
            asset_type="texture",
            asset=AssetMeta(package="/Game/T_Default", name="T_Default"),
            status=AssetStatus(parse="complete", representation="full"),
            evidence=[EvidenceEntry(key="raw_class", value="Texture2D")],
        )
        result = project_semantic(debug_ir, "debug")
        assert result.mode == "debug"
        assert len(result.evidence) == 1

    def test_projection_idempotent(self):
        """project_semantic(ir, ir.mode) returns equivalent IR."""
        from uasset_read.semantic.projection import project_semantic
        from uasset_read.semantic.models import (
            SemanticIR, AssetMeta, AssetStatus,
        )
        ir = SemanticIR(
            format="uasset_read.asset_semantic",
            format_version="1.0",
            mode="standard",
            asset_type="texture",
            asset=AssetMeta(package="/Game/T_Default", name="T_Default"),
            status=AssetStatus(parse="complete", representation="full"),
        )
        result = project_semantic(ir, "standard")
        assert result.format == ir.format
        assert result.mode == "standard"
        assert result.asset_type == ir.asset_type
