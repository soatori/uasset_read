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


class TestBlueprintVariables:
    def _variable(self):
        from uasset_read.models.ir import VariableIR
        return VariableIR(name="Health", type="float", default_value="100.0",
                          guid="ab" * 16, property_flags=0,
                          flags_labels=["EditAnywhere", "BlueprintVisible", "RepNotify"],
                          is_replicated=True, replication_condition=0,
                          rep_notify_func="OnRep_Health")

    def test_variable_emission(self):
        from uasset_read.semantic.blueprint.variables import emit_variables
        from uasset_read.semantic.blueprint.types import TypeTable
        from uasset_read.semantic.blueprint.reporting import BlueprintReporting

        rep = BlueprintReporting()
        variables_json = emit_variables([self._variable()], TypeTable(), rep)
        var = variables_json[0]
        assert var["name"] == "Health"
        assert var["type"] == "float"
        assert var["default"] == 100.0
        assert var["flags"] == ["BlueprintVisible", "EditAnywhere", "RepNotify"]
        assert var["identity"] == "ab" * 16
        assert var["replication"] == {"condition": "always", "notify": "OnRep_Health"}
        assert [e["scope"] for e in rep.coverage_entries()] == ["variables"]

    def test_empty_default_not_confirmed(self):
        from uasset_read.models.ir import VariableIR
        from uasset_read.semantic.blueprint.variables import emit_variables
        from uasset_read.semantic.blueprint.types import TypeTable
        from uasset_read.semantic.blueprint.reporting import BlueprintReporting

        var = VariableIR(name="Note", type="string", default_value="")
        emitted = emit_variables([var], TypeTable(), BlueprintReporting())
        assert "default" not in emitted[0]

    def test_declaration_index_references_only(self):
        from uasset_read.semantic.blueprint.variables import emit_declaration
        decl = emit_declaration(variable_names=["Health"], component_ids=["c0"],
                                functions=[{"name": "TakeDamage", "graph": None}],
                                parent_class="/Script/Engine.Character",
                                interfaces=["/Game/IF_Damageable"])
        assert decl["parent_class"] == "/Script/Engine.Character"
        assert decl["variables"] == ["Health"]
        assert decl["components"] == ["c0"]
        assert decl["functions"] == [{"name": "TakeDamage"}]
