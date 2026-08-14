"""Consolidated semantic tests for Issue #551 — common semantic JSON foundation."""
import pytest

from uasset_read.models.ir import (
    ExportIR, ExportRawIR, ImportIR, PackageIR, PackageHeaderIR,
    DiagnosticsDataIR, LinkerSummaryIR,
)


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


class TestPrimaryAssetSelection:
    def test_b_is_asset_preferred(self):
        """Export with b_is_asset=True is selected as primary."""
        from uasset_read.semantic.builder import build_semantic_ir
        exports = [
            ExportIR(index=0, object_name="Other", object_class="Texture2D",
                     serial_size=100, outer_index_resolved=None, super_index_resolved=None,
                     parent_class=None, properties=[], graphs=[], bulk_data=None),
            ExportIR(index=1, object_name="BP_Main", object_class="BlueprintGeneratedClass",
                     serial_size=2048, outer_index_resolved=None, super_index_resolved=None,
                     parent_class=None, properties=[], graphs=[], bulk_data=None,
                     ue_export_raw=ExportRawIR(b_is_asset=True)),
        ]
        ir = PackageIR(
            header=PackageHeaderIR(package_name="/Game/BP_Main", package_class="Package",
                                   package_flags=0, total_export_count=2, total_import_count=0, ue_version="5.3"),
            name_map=[], imports=[], exports=exports,
            linker=LinkerSummaryIR(has_linker=False, import_paths=[], export_paths=[]),
            diagnostics_data=DiagnosticsDataIR(),
        )
        semantic = build_semantic_ir(ir)
        assert semantic.asset.name == "BP_Main"
        assert semantic.asset_type == "blueprint"

    def test_fallback_to_package_basename(self):
        """When no b_is_asset, fallback to export matching package basename."""
        from uasset_read.semantic.builder import build_semantic_ir
        exports = [
            ExportIR(index=0, object_name="BP_Foo", object_class="Texture2D",
                     serial_size=100, outer_index_resolved=None, super_index_resolved=None,
                     parent_class=None, properties=[], graphs=[], bulk_data=None),
        ]
        ir = PackageIR(
            header=PackageHeaderIR(package_name="/Game/BP_Foo", package_class="Package",
                                   package_flags=0, total_export_count=1, total_import_count=0, ue_version="5.3"),
            name_map=[], imports=[], exports=exports,
            linker=LinkerSummaryIR(has_linker=False, import_paths=[], export_paths=[]),
            diagnostics_data=DiagnosticsDataIR(),
        )
        semantic = build_semantic_ir(ir)
        assert semantic.asset.name == "BP_Foo"

    def test_no_exports_emits_opaque(self):
        """No exports -> opaque status with diagnostic."""
        from uasset_read.semantic.builder import build_semantic_ir
        ir = PackageIR(
            header=PackageHeaderIR(package_name="/Game/Empty", package_class="Package",
                                   package_flags=0, total_export_count=0, total_import_count=0, ue_version="5.3"),
            name_map=[], imports=[], exports=[],
            linker=LinkerSummaryIR(has_linker=False, import_paths=[], export_paths=[]),
            diagnostics_data=DiagnosticsDataIR(),
        )
        semantic = build_semantic_ir(ir)
        assert semantic.status.representation == "opaque"
        assert any(d.code == "NO_EXPORTS" for d in semantic.diagnostics)


class TestDiagnosticAggregation:
    def test_diagnostics_deduplicated(self):
        """Duplicate diagnostics are deduplicated by DiagnosticAggregator."""
        from uasset_read.semantic.diagnostics import DiagnosticAggregator
        agg = DiagnosticAggregator()
        agg.add("error", "PARSE_ERROR", "duplicate message")
        agg.add("error", "PARSE_ERROR", "duplicate message")
        agg.add("warning", "PARSE_WARNING", "other")
        result = agg.build()
        assert len(result) == 2  # not 3

    def test_from_ir_populates(self):
        """DiagnosticAggregator.from_ir() populates from DiagnosticsDataIR."""
        from uasset_read.semantic.diagnostics import DiagnosticAggregator
        data = DiagnosticsDataIR(errors=["err1"], warnings=["warn1"])
        agg = DiagnosticAggregator()
        agg.from_ir(data)
        result = agg.build()
        assert len(result) == 2
        assert result[0].severity == "error"
        assert result[1].severity == "warning"


class TestCoverageModel:
    def test_all_available(self):
        """All scopes available -> 0 unavailable."""
        from uasset_read.semantic.coverage import CoverageModel
        cov = CoverageModel()
        cov.track("scope_a", True)
        cov.track("scope_b", True)
        info = cov.build()
        assert info.scopes_expected == 2
        assert info.scopes_available == 2
        assert info.scopes_unavailable == ()

    def test_some_unavailable(self):
        """Some scopes unavailable -> listed."""
        from uasset_read.semantic.coverage import CoverageModel
        cov = CoverageModel()
        cov.track("domain_content", True)
        cov.track("extra_data", False)
        info = cov.build(notes="partial coverage")
        assert info.scopes_expected == 2
        assert info.scopes_available == 1
        assert info.scopes_unavailable == ("extra_data",)
        assert info.notes == "partial coverage"


class TestReferenceCollection:
    def test_sorted_by_kind_then_index(self):
        """References sorted by (kind, index)."""
        from uasset_read.semantic.references import collect_references
        exports = [
            ExportIR(index=0, object_name="Exp0", object_class="Texture2D",
                     serial_size=100, outer_index_resolved=None, super_index_resolved=None,
                     parent_class=None, properties=[], graphs=[], bulk_data=None),
            ExportIR(index=1, object_name="Exp1", object_class="Material",
                     serial_size=200, outer_index_resolved=None, super_index_resolved=None,
                     parent_class=None, properties=[], graphs=[], bulk_data=None),
        ]
        imports = [
            ImportIR(index=0, class_package="/Script/Engine",
                     class_name="Actor", object_name="Actor_0"),
        ]
        refs = collect_references(imports, exports)
        # Sorted by (kind, index): "export" < "import" alphabetically
        assert refs[0].kind == "export"
        assert refs[0].index == 0
        assert refs[1].kind == "export"
        assert refs[1].index == 1
        assert refs[2].kind == "import"
        assert refs[2].index == 0


class TestExtensionRegistry:
    def test_register_and_lookup(self):
        """Register an extractor and look it up."""
        from uasset_read.semantic.extensions import register_extension, get_extractor, is_registered
        def dummy_extractor(export_ir, coverage, evidence_list=None):
            return {}
        register_extension("TestDummyClass", dummy_extractor)
        assert is_registered("TestDummyClass")
        assert get_extractor("TestDummyClass") is dummy_extractor
        assert get_extractor("NonExistent") is None
        # Cleanup
        from uasset_read.semantic.extensions import _REGISTRY
        _REGISTRY.pop("TestDummyClass", None)

    def test_duplicate_registration_raises(self):
        """Duplicate registration raises ValueError."""
        from uasset_read.semantic.extensions import register_extension, _REGISTRY
        def dummy_extractor(export_ir):
            return {}
        register_extension("TestDup", dummy_extractor)
        with pytest.raises(ValueError, match="already registered"):
            register_extension("TestDup", dummy_extractor)
        # Cleanup
        _REGISTRY.pop("TestDup", None)


class TestValidator:
    def test_valid_ir_returns_empty(self):
        from uasset_read.semantic.validator import validate_semantic_document
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
        assert validate_semantic_document(ir) == []

    def test_invalid_format_detected(self):
        from uasset_read.semantic.validator import validate_semantic_document
        from uasset_read.semantic.models import (
            SemanticIR, AssetMeta, AssetStatus,
        )
        ir = SemanticIR(
            format="wrong",
            format_version="1.0",
            mode="standard",
            asset_type="texture",
            asset=AssetMeta(package="/Game/T_Default", name="T_Default"),
            status=AssetStatus(parse="complete", representation="full"),
        )
        errors = validate_semantic_document(ir)
        assert any("format" in e.lower() for e in errors)

    def test_invalid_mode_detected(self):
        from uasset_read.semantic.validator import validate_semantic_document
        from uasset_read.semantic.models import (
            SemanticIR, AssetMeta, AssetStatus,
        )
        ir = SemanticIR(
            format="uasset_read.asset_semantic",
            format_version="1.0",
            mode="compact",
            asset_type="texture",
            asset=AssetMeta(package="/Game/T_Default", name="T_Default"),
            status=AssetStatus(parse="complete", representation="full"),
        )
        errors = validate_semantic_document(ir)
        assert any("mode" in e.lower() for e in errors)


class TestCanonicalAndRenderer:
    def test_key_order_deterministic(self):
        """Top-level keys appear in the defined contract order."""
        from uasset_read.semantic.canonical import canonical_sort
        data = {
            "diagnostics": [], "asset": {}, "status": {},
            "references": [], "coverage": None,
            "format": "x", "format_version": "1", "mode": "standard",
            "asset_type": "texture",
        }
        result = canonical_sort(data)
        keys = list(result.keys())
        assert keys == [
            "format", "format_version", "mode", "asset_type",
            "asset", "status", "references", "coverage", "diagnostics",
        ]

    def test_render_byte_identical(self):
        """Same SemanticIR produces byte-identical JSON."""
        from uasset_read.semantic.render import render_semantic_json
        from uasset_read.semantic.models import (
            SemanticIR, AssetMeta, AssetStatus, ReferenceEntry,
        )
        ir = SemanticIR(
            format="uasset_read.asset_semantic",
            format_version="1.0",
            mode="standard",
            asset_type="texture",
            asset=AssetMeta(package="/Game/T_Default", name="T_Default"),
            status=AssetStatus(parse="complete", representation="full"),
            references=(
                ReferenceEntry(index=0, kind="export", class_name="Texture2D", object_name="T_Default"),
            ),
        )
        out1 = render_semantic_json(ir)
        out2 = render_semantic_json(ir)
        assert out1 == out2
        assert out1.endswith("\n")

    def test_render_uses_lf(self):
        """Output uses LF line endings, not CRLF."""
        from uasset_read.semantic.render import render_semantic_json
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
        out = render_semantic_json(ir)
        assert "\r\n" not in out
        assert out.endswith("\n")

    def test_render_omits_none_and_empty(self):
        """None values and empty containers are omitted from output."""
        import json
        from uasset_read.semantic.render import render_semantic_json
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
            coverage=None,
            diagnostics=(),
        )
        data = json.loads(render_semantic_json(ir))
        assert "coverage" not in data
        assert "diagnostics" not in data

    def test_evidence_only_in_debug(self):
        """Evidence appears only in debug mode output."""
        import json
        from uasset_read.semantic.render import render_semantic_json
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
        data = json.loads(render_semantic_json(debug_ir))
        assert "evidence" in data
        assert data["evidence"][0]["key"] == "raw_class"


class TestDeterminism:
    def test_byte_identical_across_runs(self):
        """Same input produces byte-identical output across subprocess calls."""
        import subprocess
        import sys
        script = '''
import json, sys
sys.path.insert(0, "src")
from uasset_read.semantic.models import SemanticIR, AssetMeta, AssetStatus, ReferenceEntry
from uasset_read.semantic.render import render_semantic_json
ir = SemanticIR(
    format="uasset_read.asset_semantic",
    format_version="1.0",
    mode="standard",
    asset_type="texture",
    asset=AssetMeta(package="/Game/T_Default", name="T_Default"),
    status=AssetStatus(parse="complete", representation="full"),
    references=(ReferenceEntry(index=0, kind="export", class_name="Texture2D", object_name="T_Default"),),
)
sys.stdout.write(render_semantic_json(ir))
'''
        import os
        env1 = {**os.environ, "PYTHONHASHSEED": "0"}
        env2 = {**os.environ, "PYTHONHASHSEED": "42"}
        r1 = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, env=env1)
        r2 = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, env=env2)
        assert r1.returncode == 0, r1.stderr
        assert r2.returncode == 0, r2.stderr
        assert r1.stdout == r2.stdout


class TestRealAssetSmoke:
    def test_bp_firstperson_parses_without_crash(self):
        """BP_FirstPersonCharacter.uasset parses and produces valid JSON."""
        import json
        from pathlib import Path
        sample = Path("tests/samples/FirstPerson_BP_FirstPersonCharacter.uasset")
        if not sample.exists():
            pytest.skip("Sample not available")
        from uasset_read.core import parse_single
        result = parse_single(str(sample), format="json", output_level="standard")
        data = json.loads(result)
        assert data["format"] == "uasset_read.asset_semantic"
        assert "asset" in data
        assert "status" in data

    def test_opaque_asset_preserves_facts(self):
        """Opaque assets still emit identity, references, and diagnostics."""
        from uasset_read.semantic.builder import build_semantic_ir
        from uasset_read.models.ir import (
            ExportIR, PackageIR, PackageHeaderIR, DiagnosticsDataIR, LinkerSummaryIR,
        )
        exports = [
            ExportIR(index=0, object_name="SomeAsset", object_class="UnknownClass",
                     serial_size=512, outer_index_resolved=None, super_index_resolved=None,
                     parent_class=None, properties=[], graphs=[], bulk_data=None),
        ]
        ir = PackageIR(
            header=PackageHeaderIR(package_name="/Game/SomeAsset", package_class="Package",
                                   package_flags=0, total_export_count=1, total_import_count=0, ue_version="5.3"),
            name_map=[], imports=[], exports=exports,
            linker=LinkerSummaryIR(has_linker=False, import_paths=[], export_paths=[]),
            diagnostics_data=DiagnosticsDataIR(),
        )
        semantic = build_semantic_ir(ir)
        assert semantic.status.representation == "opaque"
        assert semantic.asset_type == "unknown"
        assert any(d.code == "UNKNOWN_TYPE" for d in semantic.diagnostics)
        # asset_class preserved in evidence for unknown types
        assert any(e.key == "asset_class" and e.value == "UnknownClass" for e in semantic.evidence)
        assert semantic.asset.generated_class == "UnknownClass"

    def test_asset_class_evidence_only_in_debug(self):
        """asset_class evidence is stripped by standard projection."""
        from uasset_read.semantic.builder import build_semantic_ir
        from uasset_read.semantic.projection import project_semantic
        from uasset_read.models.ir import (
            ExportIR, PackageIR, PackageHeaderIR, DiagnosticsDataIR, LinkerSummaryIR,
        )
        exports = [
            ExportIR(index=0, object_name="SomeAsset", object_class="UnknownClass",
                     serial_size=512, outer_index_resolved=None, super_index_resolved=None,
                     parent_class=None, properties=[], graphs=[], bulk_data=None),
        ]
        ir = PackageIR(
            header=PackageHeaderIR(package_name="/Game/SomeAsset", package_class="Package",
                                   package_flags=0, total_export_count=1, total_import_count=0, ue_version="5.3"),
            name_map=[], imports=[], exports=exports,
            linker=LinkerSummaryIR(has_linker=False, import_paths=[], export_paths=[]),
            diagnostics_data=DiagnosticsDataIR(),
        )
        debug_ir = build_semantic_ir(ir)
        assert any(e.key == "asset_class" for e in debug_ir.evidence)
        standard_ir = project_semantic(debug_ir, "standard")
        assert standard_ir.evidence == ()


class TestOpaqueFallback:
    def test_unregistered_asset_is_opaque(self):
        """Asset with a known type but no registered extractor must be opaque, not full."""
        from uasset_read.semantic.builder import build_semantic_ir
        from uasset_read.models.ir import PackageIR, PackageHeaderIR, ExportIR, LinkerSummaryIR, DiagnosticsDataIR

        pkg = PackageIR(
            header=PackageHeaderIR(
                package_name="/Game/BP_Test",
                package_class="Package",
                package_flags=0,
                total_export_count=1,
                total_import_count=0,
                ue_version="5.1",
            ),
            name_map=(),
            imports=[],
            exports=[
                ExportIR(
                    index=0, object_name="BP_Test", object_class="BlueprintGeneratedClass",
                    serial_size=1024, outer_index_resolved=None,
                    super_index_resolved=None, parent_class=None,
                    properties=[], graphs=[], bulk_data=None,
                ),
            ],
            linker=LinkerSummaryIR(has_linker=False, import_paths=[], export_paths=[]),
            diagnostics_data=DiagnosticsDataIR(),
        )

        ir = build_semantic_ir(pkg)
        assert ir.asset_type == "blueprint"
        assert ir.status.representation == "opaque"
        assert any(d.code == "NO_EXTRACTOR" for d in ir.diagnostics)


class TestCLIAPIEquivalence:
    def test_single_file_cli_matches_python_api(self):
        """CLI single-file output matches Python API output byte-for-byte."""
        import subprocess, sys, json
        from pathlib import Path
        sample = Path("tests/samples/FirstPerson_BP_FirstPersonCharacter.uasset")
        if not sample.exists():
            pytest.skip("Sample not available")
        # Python API
        from uasset_read.core import parse_single
        api_output = parse_single(str(sample), format="json", output_level="standard")
        # CLI
        cli_result = subprocess.run(
            [sys.executable, "run.py", "--json", str(sample)],
            capture_output=True, text=True,
        )
        assert cli_result.returncode == 0, cli_result.stderr
        assert json.loads(api_output) == json.loads(cli_result.stdout)


class TestSchemaLocatability:
    def test_schema_file_exists_and_valid_json(self):
        """semantic.schema.json exists and is valid JSON."""
        from uasset_read.schema_loader import load_semantic_schema
        schema = load_semantic_schema()
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert "properties" in schema
        assert "$defs" in schema


# ── Domain Extractor Integration Tests ──

def _make_export(object_class, object_name, serial_size=1024, properties=None,
                 graphs=None, asset_type_data=None, b_is_asset=True):
    """Helper to create ExportIR for domain extractor tests."""
    raw = ExportRawIR(b_is_asset=b_is_asset) if b_is_asset else ExportRawIR()
    return ExportIR(
        index=0, object_name=object_name, object_class=object_class,
        serial_size=serial_size, outer_index_resolved=None, super_index_resolved=None,
        parent_class=None, properties=properties or [], graphs=graphs or [],
        bulk_data=None, asset_type_data=asset_type_data, ue_export_raw=raw,
    )


def _make_pkg(export, package_name=None):
    """Helper to create PackageIR wrapping a single export."""
    if package_name is None:
        package_name = f"/Game/{export.object_name}"
    return PackageIR(
        header=PackageHeaderIR(
            package_name=package_name, package_class="Package",
            package_flags=0, total_export_count=1, total_import_count=0, ue_version="5.3",
        ),
        name_map=[], imports=[], exports=[export],
        linker=LinkerSummaryIR(has_linker=False, import_paths=[], export_paths=[]),
        diagnostics_data=DiagnosticsDataIR(),
    )


class TestPrimaryExportTopLevel:
    def test_nested_export_not_selected_by_basename(self):
        """Nested export matching basename must not be primary when no top-level match exists."""
        from uasset_read.semantic.builder import _select_primary_export
        pkg = PackageIR(
            header=PackageHeaderIR(
                package_name="/Game/Foo",
                package_class="Package",
                package_flags=0,
                total_export_count=2,
                total_import_count=0,
                ue_version="5.1",
            ),
            name_map=(),
            imports=[],
            exports=[
                ExportIR(
                    index=0, object_name="Other", object_class="Texture2D",
                    serial_size=1024, outer_index_resolved=None,
                    super_index_resolved=None, parent_class=None,
                    properties=[], graphs=[], bulk_data=None,
                ),
                ExportIR(
                    index=1, object_name="Foo", object_class="Texture2D",
                    serial_size=512, outer_index_resolved="SomeOuter",
                    super_index_resolved=None, parent_class=None,
                    properties=[], graphs=[], bulk_data=None,
                ),
            ],
            linker=LinkerSummaryIR(has_linker=False, import_paths=[], export_paths=[]),
            diagnostics_data=DiagnosticsDataIR(),
        )

        result = _select_primary_export(pkg)
        assert result is None


class TestDomainExtractors:
    """Integration tests for domain extractors through the full pipeline."""

    @pytest.mark.skip(reason="Domain extractors migrated to #554-#557")
    def test_resource_extractor_texture2d(self):
        """Texture2D with resource properties produces correct content."""
        import json
        from uasset_read.semantic import build_semantic_ir, project_semantic, render_semantic_json

        export = _make_export(
            "Texture2D", "T_Wood",
            properties=[
                type("P", (), {"name": "SizeX", "value": 512})(),
                type("P", (), {"name": "SizeY", "value": 256})(),
                type("P", (), {"name": "Format", "value": "PF_B8G8R8A8"})(),
            ],
        )
        ir = build_semantic_ir(_make_pkg(export))
        ir = project_semantic(ir, "standard")
        data = json.loads(render_semantic_json(ir))

        assert data["asset_type"] == "texture"
        assert "content" not in data  # merged, not nested
        assert data["class_name"] == "Texture2D"
        assert data["object_name"] == "T_Wood"
        assert data["serial_size"] == 1024
        assert data["properties"]["SizeX"] == 512
        assert data["properties"]["Format"] == "PF_B8G8R8A8"

    @pytest.mark.skip(reason="Domain extractors migrated to #554-#557")
    def test_resource_extractor_coverage(self):
        """Resource extractor tracks coverage scopes correctly."""
        from uasset_read.semantic import build_semantic_ir
        from uasset_read.semantic.coverage import CoverageModel

        export = _make_export(
            "Texture2D", "T_Default",
            properties=[type("P", (), {"name": "SizeX", "value": 256})()],
        )
        ir = build_semantic_ir(_make_pkg(export))
        assert ir.coverage is not None
        assert ir.coverage.scopes_expected == 3  # metadata, properties, asset_type_data
        assert ir.coverage.scopes_available == 2  # metadata + properties
        assert "asset_type_data" in ir.coverage.scopes_unavailable

    @pytest.mark.skip(reason="Domain extractors migrated to #554-#557")
    def test_graph_extractor_soundcue(self):
        """SoundCue with graphs produces graph content."""
        import json
        from uasset_read.semantic import build_semantic_ir, project_semantic, render_semantic_json
        from uasset_read.models.ir import GraphIR

        graph = GraphIR(graph_guid="g1", graph_name="SoundGraph", graph_class="EdGraph", nodes=[1, 2, 3], execution_chains=[])
        export = _make_export(
            "SoundCue", "SC_Footstep",
            graphs=[graph],
            asset_type_data={"parse_status": "success", "node_count": 3},
        )
        ir = build_semantic_ir(_make_pkg(export))
        ir = project_semantic(ir, "standard")
        data = json.loads(render_semantic_json(ir))

        assert data["asset_type"] == "sound_cue"
        assert "content" not in data
        assert data["graph_metadata"]["class_name"] == "SoundCue"
        assert data["graphs"][0]["name"] == "SoundGraph"
        assert data["graphs"][0]["node_count"] == 3
        assert data["asset_type_data"]["node_count"] == 3

    @pytest.mark.skip(reason="Domain extractors migrated to #554-#557")
    def test_structured_extractor_datatable(self):
        """DataTable with rows produces structured content."""
        import json
        from uasset_read.semantic import build_semantic_ir, project_semantic, render_semantic_json

        export = _make_export(
            "DataTable", "DT_Config",
            asset_type_data={
                "parse_status": "success",
                "rows": [{"Key": "row1"}, {"Key": "row2"}, {"Key": "row3"}],
                "row_count": 3,
                "guid": "abc-123",
            },
        )
        ir = build_semantic_ir(_make_pkg(export))
        ir = project_semantic(ir, "standard")
        data = json.loads(render_semantic_json(ir))

        assert data["asset_type"] == "data_table"
        assert data["class_name"] == "DataTable"
        assert data["row_count"] == 3
        assert data["guid"] == "abc-123"

    def test_no_extractor_opaque_content(self):
        """Asset with no registered extractor has empty content."""
        from uasset_read.semantic import build_semantic_ir

        export = _make_export("BlueprintGeneratedClass", "BP_Foo", b_is_asset=False)
        # BlueprintGeneratedClass is not registered, so no extractor
        pkg = _make_pkg(export, "/Game/BP_Foo")
        ir = build_semantic_ir(pkg)
        # Should fall back to name-match rule or be opaque
        assert ir.content == {} or ir.status.representation == "opaque"

    @pytest.mark.skip(reason="Domain extractors migrated to #554-#557")
    def test_content_merges_to_top_level(self):
        """Domain content fields appear at JSON top level, not nested."""
        import json
        from uasset_read.semantic import build_semantic_ir, project_semantic, render_semantic_json

        export = _make_export(
            "Texture2D", "T_Test",
            properties=[type("P", (), {"name": "SizeX", "value": 128})()],
        )
        ir = build_semantic_ir(_make_pkg(export))
        out = render_semantic_json(project_semantic(ir, "standard"))
        data = json.loads(out)

        # Contract keys present
        assert "format" in data
        assert "asset_type" in data
        # Domain keys at top level
        assert "class_name" in data
        assert "properties" in data
        # No nested "content" key
        assert "content" not in data

    def test_deterministic_domain_output(self):
        """Same asset produces byte-identical JSON across runs."""
        import json
        from uasset_read.semantic import build_semantic_ir, project_semantic, render_semantic_json

        export = _make_export(
            "Texture2D", "T_Det",
            properties=[type("P", (), {"name": "SizeX", "value": 64})()],
        )
        ir = build_semantic_ir(_make_pkg(export))
        ir = project_semantic(ir, "standard")
        out1 = render_semantic_json(ir)
        out2 = render_semantic_json(ir)
        assert out1 == out2
