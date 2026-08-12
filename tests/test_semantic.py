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
