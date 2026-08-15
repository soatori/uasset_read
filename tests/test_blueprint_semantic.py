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


class TestBlueprintComponents:
    def test_component_emission_and_parent_resolution(self):
        from uasset_read.semantic.blueprint.components import emit_components
        from uasset_read.semantic.blueprint.types import TypeTable
        from uasset_read.semantic.blueprint.reporting import BlueprintReporting

        source = [
            {"name": "CollisionCylinder", "class": "CapsuleComponent"},
            {"name": "Mesh", "class": "SkeletalMeshComponent",
             "parent": "CollisionCylinder", "socket": "WeaponSocket"},
        ]
        rep = BlueprintReporting()
        comps = emit_components(source, TypeTable(), rep)
        assert comps[0]["id"] == "c0"
        assert comps[0]["origin"] == "unverified"
        assert comps[0]["type"] == {"$type": "t0"}
        assert comps[1]["parent"] == "c0"
        assert comps[1]["socket"] == "WeaponSocket"
        assert [e["scope"] for e in rep.coverage_entries()] == ["components"]

    def test_dangling_parent_diagnosed(self):
        from uasset_read.semantic.blueprint.components import emit_components
        from uasset_read.semantic.blueprint.types import TypeTable
        from uasset_read.semantic.blueprint.reporting import BlueprintReporting

        rep = BlueprintReporting()
        comps = emit_components([{"name": "Mesh", "class": "X", "parent": "Nope"}],
                                TypeTable(), rep)
        assert "parent" not in comps[0]
        assert any(d["code"] == "BP_COMPONENT_PARENT_UNRESOLVED"
                   for d in rep.diagnostics_entries("standard"))


class TestBlueprintIds:
    def test_ascii_slug_rules(self):
        from uasset_read.semantic.blueprint.ids import ascii_slug
        assert ascii_slug("EventGraph") == "EventGraph"
        assert ascii_slug("BeginPlay") == "BeginPlay"
        assert ascii_slug("My Var/Name") == "My_Var_Name"
        assert ascii_slug("123abc") == "x123abc"
        assert ascii_slug("") == "unnamed"
        assert ascii_slug("节点") == "unnamed"

    def test_id_builders(self):
        from uasset_read.semantic.blueprint.ids import graph_id, node_id, data_endpoint, exec_endpoint
        assert graph_id("EventGraph") == "blueprint://graph/EventGraph"
        assert node_id("EventGraph", "call", "SetActorLocation", 0) == \
            "blueprint://graph/EventGraph/node/call/SetActorLocation/0"
        assert data_endpoint("NewLocation", "input") == "input.NewLocation"
        assert exec_endpoint("execute") == "exec.in"
        assert exec_endpoint("then") == "exec.out"
        assert exec_endpoint("True") == "exec.true"

    def test_id_regexes_match_builders(self):
        import re
        from uasset_read.semantic.blueprint.ids import (
            GRAPH_ID_RE, NODE_ID_RE, ENDPOINT_RE,
            graph_id, node_id, data_endpoint, exec_endpoint,
        )
        assert re.fullmatch(GRAPH_ID_RE, graph_id("EventGraph"))
        assert re.fullmatch(NODE_ID_RE, node_id("Function_TakeDamage", "variable-set", "Health", 3))
        for ep in (data_endpoint("NewLocation", "input"), exec_endpoint("then")):
            assert re.fullmatch(ENDPOINT_RE, ep)


class TestBlueprintDefaults:
    def test_scalar_and_object_defaults(self):
        from uasset_read.semantic.blueprint.defaults import default_value_for
        from uasset_read.semantic.blueprint.reporting import BlueprintReporting

        class Pin:
            def __init__(self, **kw):
                self.pin_category = kw.get("pin_category", "")
                self.default_value = kw.get("default_value", "")
                self.default_object_name = kw.get("default_object_name", None)
                self.default_text_value = kw.get("default_text_value", None)
                self.linked_to = []

        rep = BlueprintReporting()
        assert default_value_for(Pin(pin_category="bool", default_value="true"), rep) is True
        assert default_value_for(Pin(pin_category="int", default_value="0"), rep) == 0
        assert default_value_for(Pin(pin_category="real", default_value="1.5"), rep) == 1.5
        assert default_value_for(Pin(pin_category="string", default_value=""), rep) == ""
        assert default_value_for(Pin(pin_category="object", default_object_name="/Game/X"), rep) == {"object": "/Game/X"}
        assert default_value_for(Pin(pin_category="text", default_text_value="Hello"), rep) == {"text": {"raw": "Hello"}}
        connected = Pin(pin_category="int", default_value="5")
        connected.linked_to = ["aa" * 16]
        assert default_value_for(connected, rep) is None


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


class TestBlueprintTypes:
    def test_primitive_categories_inline(self):
        from uasset_read.semantic.blueprint.types import TypeTable
        table = TypeTable()
        assert table.type_ref_for(category="bool") == "bool"
        assert table.type_ref_for(category="real", subcategory="double") == "double"
        assert table.type_ref_for(category="real") == "float"
        assert table.entries == {}

    def test_struct_deduplicated(self):
        from uasset_read.semantic.blueprint.types import TypeTable
        table = TypeTable()
        r1 = table.type_ref_for(category="struct", subcategory_object_name="Vector")
        r2 = table.type_ref_for(category="struct", subcategory_object_name="Vector")
        assert r1 == r2 == {"$type": "t0"}
        assert table.entries == {"t0": {"kind": "struct", "path": "Vector"}}

    def test_map_key_value_terminal(self):
        from uasset_read.semantic.blueprint.types import TypeTable
        table = TypeTable()
        ref = table.type_ref_for(category="name", container_type=3,
                                 map_key_terminal_category="struct",
                                 map_key_terminal_sub_category_object_name="Objective")
        entry = table.entries[ref["$type"]]
        assert entry["kind"] == "map"
        assert entry["key"] == "name"
        assert entry["value"] == {"$type": "t0"}
        assert table.entries["t0"] == {"kind": "struct", "path": "Objective"}

    def test_reference_and_const_modifiers(self):
        from uasset_read.semantic.blueprint.types import TypeTable
        table = TypeTable()
        ref = table.type_ref_for(category="object", subcategory_object_name="Actor",
                                 is_reference=True, is_const=True)
        entry = table.entries[ref["$type"]]
        assert entry["kind"] == "ref"
        assert entry["const"] is True
        inner = table.entries[entry["target"]["$type"]]
        assert inner == {"kind": "object", "path": "Actor"}
