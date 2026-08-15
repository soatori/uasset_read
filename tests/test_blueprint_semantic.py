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
