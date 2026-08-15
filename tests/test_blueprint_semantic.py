"""Blueprint semantic JSON (#554) tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

SAMPLES_DIR = Path(__file__).resolve().parents[1] / "tests" / "samples"


def _sample(name: str) -> Path:
    path = SAMPLES_DIR / name
    if not path.exists():
        pytest.skip(f"Sample not found: {name}")
    return path


class TestPinGuidResearchFixtures:
    """Pins the research-gate findings (docs/designs/issue-554-pin-guid-research.md)."""

    def test_firstperson_character_pin_identity_fields(self):
        from uasset_read.parse_uasset import parse_uasset

        result = parse_uasset(str(_sample("FirstPerson_BP_FirstPersonCharacter.uasset")), tolerant=True)
        pins = 0
        pin_ids: set[str] = set()
        split_parents = 0
        linked = 0
        for export in result.export_map or []:
            for graph in getattr(export, "graphs", None) or []:
                stack = [graph]
                while stack:
                    g = stack.pop()
                    for node in g.nodes or []:
                        for pin in node.pins or []:
                            pins += 1
                            if getattr(pin, "pin_id", ""):
                                pin_ids.add(pin.pin_id)
                            if getattr(pin, "sub_pins", None):
                                split_parents += 1
                            if getattr(pin, "linked_to_raw", None):
                                linked += 1
                    stack.extend(g.subgraphs or [])
        assert pins > 100
        assert len(pin_ids) > 50
        assert split_parents > 0  # struct split pins present (research counter-example)
        assert linked > 0

    def test_linkedto_refs_resolve_to_pin_ids(self):
        from uasset_read.parse_uasset import parse_uasset

        result = parse_uasset(str(_sample("FirstPerson_BP_FirstPersonCharacter.uasset")), tolerant=True)
        index: set[str] = set()
        pins = []
        for export in result.export_map or []:
            for graph in getattr(export, "graphs", None) or []:
                stack = [graph]
                while stack:
                    g = stack.pop()
                    for node in g.nodes or []:
                        for pin in node.pins or []:
                            if getattr(pin, "pin_id", ""):
                                index.add(pin.pin_id)
                            pins.append(pin)
                    stack.extend(g.subgraphs or [])
        resolved = unresolved = 0
        for pin in pins:
            for ref in pin.linked_to_raw or []:
                guid = ref.get("pin_guid") if isinstance(ref, dict) else None
                if guid and guid in index:
                    resolved += 1
                else:
                    unresolved += 1
        assert resolved > 0
        # Research finding: a bounded number of dangling refs may exist;
        # they must never produce authoritative edges.
        assert unresolved <= resolved


class TestPinIRIdentityFields:
    def test_pin_ir_carries_self_id_and_relations(self):
        from uasset_read.parse_uasset import parse_uasset
        from uasset_read.ir_builder import build_package_ir

        result = parse_uasset(str(_sample("FirstPerson_BP_FirstPersonCharacter.uasset")), tolerant=True)
        pkg = build_package_ir(result)
        pin_ids: list[str] = []
        parent_refs = sub_refs = 0
        for export in pkg.exports:
            for graph in export.graphs:
                stack = [graph]
                while stack:
                    g = stack.pop()
                    for node in g.nodes:
                        for pin in node.pins:
                            if pin.pin_guid:
                                pin_ids.append(pin.pin_guid)
                            if pin.parent_pin_guid:
                                parent_refs += 1
                            if pin.sub_pin_guids:
                                sub_refs += 1
                    stack.extend(g.subgraphs)
        assert len(pin_ids) > 50
        assert len(set(pin_ids)) > 30  # majority of PinIds are unique
        assert parent_refs > 0 and sub_refs > 0   # split-pin tree preserved


class TestDomainFormatPlumbing:
    def _package_ir(self, export):
        from uasset_read.models.ir import PackageIR, PackageHeaderIR, DiagnosticsDataIR, LinkerSummaryIR
        header = PackageHeaderIR(
            package_name="/Game/BP_Fake", package_class="Package", package_flags=0,
            total_export_count=1, total_import_count=0, ue_version="5.4.0",
        )
        pkg = PackageIR(header=header, name_map=(), imports=[], exports=[export],
                        linker=LinkerSummaryIR(has_linker=False, import_paths=[], export_paths=[]))
        pkg.diagnostics_data = DiagnosticsDataIR(status="success", errors=None, warnings=None)
        return pkg

    def _fake_export(self):
        from uasset_read.models.ir import ExportIR
        return ExportIR(
            index=0, object_name="BP_Fake", object_class="Blueprint",
            serial_size=0, outer_index_resolved=None, super_index_resolved=None,
            parent_class=None, properties=[], graphs=[], bulk_data=None,
        )

    def _build(self, monkeypatch, content, domain_format=None, domain_version=None):
        from uasset_read.semantic import extensions
        from uasset_read.semantic.builder import build_semantic_ir

        def extractor(package_ir, export_ir, cov, evidence):
            return content

        monkeypatch.setattr(extensions, "_REGISTRY", {"Blueprint": extractor})
        monkeypatch.setattr(
            extensions, "_DOMAIN_FORMATS",
            {"Blueprint": (domain_format, domain_version)} if domain_format else {})
        return build_semantic_ir(self._package_ir(self._fake_export()), source_path="BP_Fake.uasset")

    def test_domain_format_stamped(self, monkeypatch):
        ir = self._build(monkeypatch, {"graphs": []},
                         domain_format="uasset_read.blueprint_semantic", domain_version="1.0.0")
        assert ir.format == "uasset_read.blueprint_semantic"
        assert ir.format_version == "1.0.0"

    def test_collision_guard_raises(self, monkeypatch):
        from uasset_read.semantic.render import render_semantic_json
        ir = self._build(monkeypatch, {"format": "evil"})
        with pytest.raises(ValueError, match="collides"):
            render_semantic_json(ir)

    def test_domain_coverage_override(self, monkeypatch):
        from uasset_read.semantic.render import render_semantic_json
        ir = self._build(
            monkeypatch,
            {"references": [], "coverage": [{"scope": "graphs", "status": "partial"}],
             "diagnostics": [{"code": "BP_TEST", "scope": "asset", "severity": "info",
                              "effect": "none", "count": 1}]},
            domain_format="uasset_read.blueprint_semantic", domain_version="1.0.0")
        doc = json.loads(render_semantic_json(ir))
        assert doc["coverage"] == [{"scope": "graphs", "status": "partial"}]
        assert "references" not in doc  # empty list stripped by renderer
