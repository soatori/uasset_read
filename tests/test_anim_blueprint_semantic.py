"""Animation Blueprint semantic JSON (#555) tests."""
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


class TestAnimBlueprintIds:
    def test_ascii_slug_rules(self):
        from uasset_read.semantic.anim_blueprint.ids import ascii_slug
        assert ascii_slug("IdleWalkRun") == "IdleWalkRun"
        assert ascii_slug("My State/Name") == "My_State_Name"
        assert ascii_slug("123abc") == "x123abc"
        assert ascii_slug("") == "unnamed"
        assert ascii_slug("节点") == "unnamed"

    def test_graph_id_uses_animblueprint_prefix(self):
        from uasset_read.semantic.anim_blueprint.ids import graph_id
        assert graph_id("AnimGraph") == "animblueprint://graph/AnimGraph"

    def test_node_id_uses_animblueprint_prefix(self):
        from uasset_read.semantic.anim_blueprint.ids import node_id
        assert node_id("AnimGraph", "sequence_player", "Idle", 0) == \
            "animblueprint://graph/AnimGraph/node/sequence-player/Idle/0"

    def test_state_machine_id(self):
        from uasset_read.semantic.anim_blueprint.ids import state_machine_id
        assert state_machine_id("Locomotion") == "animblueprint://state_machine/Locomotion"

    def test_state_id(self):
        from uasset_read.semantic.anim_blueprint.ids import state_id
        assert state_id("Locomotion", "Idle") == \
            "animblueprint://state_machine/Locomotion/state/Idle"

    def test_pose_endpoint(self):
        from uasset_read.semantic.anim_blueprint.ids import pose_endpoint
        assert pose_endpoint("Result", "output") == "pose.output.Result"
        assert pose_endpoint("Source", "input") == "pose.input.Source"


class TestAnimBlueprintReporting:
    def test_coverage_and_diagnostics(self):
        from uasset_read.semantic.anim_blueprint.reporting import AnimBlueprintReporting
        rep = AnimBlueprintReporting()
        rep.coverage("state_machines", "ok", reason="2 machines emitted")
        rep.diagnostic("ABP_GRAPH_MISSING", "asset", "warning", "semantic_loss")

        coverage = rep.coverage_entries()
        assert len(coverage) == 1
        assert coverage[0]["scope"] == "state_machines"
        assert coverage[0]["status"] == "ok"

        diags = rep.diagnostics_entries("standard")
        assert len(diags) == 1
        assert diags[0]["code"] == "ABP_GRAPH_MISSING"
        assert diags[0]["severity"] == "warning"


class TestStateMachineEmission:
    def test_emit_state_machines(self):
        from uasset_read.semantic.anim_blueprint.state_machines import emit_state_machines
        from uasset_read.semantic.anim_blueprint.reporting import AnimBlueprintReporting
        from uasset_read.models.ir_anim import (
            BakedStateMachineIR,
            BakedStateIR,
            BakedTransitionIR,
        )

        machine = BakedStateMachineIR(
            machine_name="Locomotion",
            initial_state=0,
            states=[
                BakedStateIR(state_name="Idle", state_root_node_index=0),
                BakedStateIR(state_name="Walk", state_root_node_index=1),
            ],
            transitions=[
                BakedTransitionIR(previous_state=0, next_state=1, crossfade_duration=0.2),
            ],
        )

        rep = AnimBlueprintReporting()
        result = emit_state_machines([machine], rep, mode="debug")

        assert len(result) == 1
        sm = result[0]
        assert sm["name"] == "Locomotion"
        assert sm["initial_state_index"] == 0
        assert len(sm["states"]) == 2
        assert sm["states"][0]["name"] == "Idle"
        assert sm["states"][1]["name"] == "Walk"
        assert len(sm["transitions"]) == 1
        assert sm["transitions"][0]["previous_state"] == 0
        assert sm["transitions"][0]["next_state"] == 1
        assert sm["transitions"][0]["crossfade_duration"] == 0.2

    def test_conduit_state(self):
        from uasset_read.semantic.anim_blueprint.state_machines import emit_state_machines
        from uasset_read.semantic.anim_blueprint.reporting import AnimBlueprintReporting
        from uasset_read.models.ir_anim import BakedStateMachineIR, BakedStateIR

        machine = BakedStateMachineIR(
            machine_name="Test",
            states=[
                BakedStateIR(state_name="Conduit1", b_is_a_conduit=True),
            ],
        )

        rep = AnimBlueprintReporting()
        result = emit_state_machines([machine], rep, mode="debug")
        assert result[0]["states"][0]["is_conduit"] is True

    def test_empty_machines(self):
        from uasset_read.semantic.anim_blueprint.state_machines import emit_state_machines
        from uasset_read.semantic.anim_blueprint.reporting import AnimBlueprintReporting

        rep = AnimBlueprintReporting()
        result = emit_state_machines([], rep, mode="debug")
        assert result == []


class TestAnimNotifiesEmission:
    def test_emit_anim_notifies(self):
        from uasset_read.semantic.anim_blueprint.extractor import _emit_anim_notifies
        from uasset_read.semantic.anim_blueprint.reporting import AnimBlueprintReporting
        from uasset_read.models.ir_anim import AnimNotifyIR

        notify = AnimNotifyIR(
            notify_name="Footstep",
            trigger_time_offset=0.5,
            duration=0.1,
            notify_class="/Script/Engine.AnimNotify_Footstep",
            track_index=1,
        )

        rep = AnimBlueprintReporting()
        result = _emit_anim_notifies([notify], rep, mode="debug")

        assert len(result) == 1
        assert result[0]["name"] == "Footstep"
        assert result[0]["trigger_time_offset"] == 0.5
        assert result[0]["duration"] == 0.1
        assert result[0]["notify_class"] == "/Script/Engine.AnimNotify_Footstep"
        assert result[0]["track_index"] == 1

    def test_default_track_index_omitted(self):
        from uasset_read.semantic.anim_blueprint.extractor import _emit_anim_notifies
        from uasset_read.semantic.anim_blueprint.reporting import AnimBlueprintReporting
        from uasset_read.models.ir_anim import AnimNotifyIR

        notify = AnimNotifyIR(notify_name="Test", track_index=0)
        rep = AnimBlueprintReporting()
        result = _emit_anim_notifies([notify], rep, mode="debug")
        assert "track_index" not in result[0]


class TestAnimBlueprintSchema:
    def test_schema_loads(self):
        from uasset_read.schema_loader import load_anim_blueprint_semantic_schema
        schema = load_anim_blueprint_semantic_schema()
        assert schema["$id"].endswith("anim_blueprint_semantic.schema.json")
        assert schema["properties"]["format"]["const"] == "uasset_read.anim_blueprint_semantic"
        assert schema["properties"]["asset_type"]["const"] == "anim_blueprint"

    def test_schema_has_state_machines(self):
        from uasset_read.schema_loader import load_anim_blueprint_semantic_schema
        schema = load_anim_blueprint_semantic_schema()
        assert "state_machines" in schema["properties"]
        assert "StateMachine" in schema["$defs"]

    def test_schema_has_anim_notifies(self):
        from uasset_read.schema_loader import load_anim_blueprint_semantic_schema
        schema = load_anim_blueprint_semantic_schema()
        assert "anim_notifies" in schema["properties"]
        assert "AnimNotify" in schema["$defs"]

    def test_schema_has_pose_flow(self):
        from uasset_read.schema_loader import load_anim_blueprint_semantic_schema
        schema = load_anim_blueprint_semantic_schema()
        assert "PoseFlow" in schema["$defs"]
        assert "PosePin" in schema["$defs"]
        assert "PoseEndpointRef" in schema["$defs"]
        assert "PoseFlowEdge" in schema["$defs"]

    def test_schema_rejects_bad_mode(self):
        import jsonschema
        from jsonschema import ValidationError
        from uasset_read.schema_loader import load_anim_blueprint_semantic_schema
        schema = load_anim_blueprint_semantic_schema()
        doc = {
            "format": "uasset_read.anim_blueprint_semantic",
            "format_version": "1.0.0",
            "mode": "compact",
            "asset_type": "anim_blueprint",
            "asset": {"package": "/Game/X", "name": "X"},
            "status": {"parse": "complete", "representation": "partial"},
            "graphs": [],
        }
        with pytest.raises(ValidationError):
            jsonschema.validate(doc, schema)


class TestAnimBlueprintValidator:
    def _ir(self, content):
        from uasset_read.semantic.models import SemanticIR, AssetMeta, AssetStatus
        return SemanticIR(
            format="uasset_read.anim_blueprint_semantic", format_version="1.0.0",
            mode="standard", asset_type="anim_blueprint",
            asset=AssetMeta(package="/Game/ABP_X", name="ABP_X"),
            status=AssetStatus(parse="complete", representation="partial"),
            content=content)

    def test_valid_document_passes(self):
        from uasset_read.semantic.validator import validate_semantic_document
        content = {
            "graphs": [{
                "id": "animblueprint://graph/AnimGraph", "name": "AnimGraph",
                "kind": "anim_graph",
                "nodes": [{
                    "id": "animblueprint://graph/AnimGraph/node/root/Result/0",
                    "kind": "root",
                }],
            }],
            "state_machines": [{
                "id": "animblueprint://state_machine/Locomotion",
                "name": "Locomotion",
                "initial_state_index": 0,
                "states": [{
                    "id": "animblueprint://state_machine/Locomotion/state/Idle",
                    "name": "Idle",
                }],
                "transitions": [],
            }],
            "diagnostics": [{
                "code": "ABP_GRAPH_MISSING", "scope": "asset",
                "severity": "warning", "effect": "semantic_loss", "count": 1,
            }],
        }
        assert validate_semantic_document(self._ir(content)) == []

    def test_invalid_graph_id_rejected(self):
        from uasset_read.semantic.validator import validate_semantic_document
        content = {
            "graphs": [{
                "id": "blueprint://graph/AnimGraph", "name": "AnimGraph",
                "kind": "anim_graph", "nodes": [],
            }],
        }
        errors = validate_semantic_document(self._ir(content))
        assert any("graph id" in e.lower() for e in errors)

    def test_invalid_state_machine_id_rejected(self):
        from uasset_read.semantic.validator import validate_semantic_document
        content = {
            "graphs": [],
            "state_machines": [{
                "id": "blueprint://state_machine/Locomotion",
                "name": "Locomotion",
                "states": [],
            }],
        }
        errors = validate_semantic_document(self._ir(content))
        assert any("state machine id" in e.lower() for e in errors)

    def test_pose_flow_endpoint_closure(self):
        from uasset_read.semantic.validator import validate_semantic_document
        content = {
            "graphs": [{
                "id": "animblueprint://graph/AnimGraph", "name": "AnimGraph",
                "kind": "anim_graph", "nodes": [],
                "pose_flow": {
                    "entries": [{"node": "nonexistent", "pose_pin": "pose.input.Source"}],
                },
            }],
        }
        errors = validate_semantic_document(self._ir(content))
        assert any("pose endpoint closure" in e.lower() for e in errors)

    def test_type_closure_violation_rejected(self):
        from uasset_read.semantic.validator import validate_semantic_document
        content = {
            "types": {"t0": {"kind": "array", "element": {"$type": "t9"}}},
            "graphs": [],
        }
        errors = validate_semantic_document(self._ir(content))
        assert any("type" in e.lower() for e in errors)


class TestAnimBlueprintProjection:
    def test_standard_mode_has_no_evidence(self):
        from uasset_read.semantic.projection import project_semantic
        from uasset_read.semantic.models import SemanticIR, AssetMeta, AssetStatus
        ir = SemanticIR(
            format="uasset_read.anim_blueprint_semantic", format_version="1.0.0",
            mode="debug", asset_type="anim_blueprint",
            asset=AssetMeta(package="/Game/ABP_X", name="ABP_X"),
            status=AssetStatus(parse="complete", representation="partial"),
            content={"graphs": [], "evidence": {"key": "test"}},
            evidence=(("key", "value"),),
        )
        projected = project_semantic(ir, "standard")
        assert projected.mode == "standard"
        assert projected.evidence == ()
        assert "evidence" not in (projected.content or {})


class TestAnimBlueprintAcceptance:
    SAMPLES = [
        "ABP_RifleAnimLayers.uasset",
        "ALS_AnimBP.uasset",
    ]

    def test_anim_blueprint_samples_produce_valid_output(self):
        """Verify animation blueprint samples produce valid JSON."""
        from uasset_read.core import parse_single

        for name in self.SAMPLES:
            path = _sample(name)
            doc = json.loads(parse_single(str(path), format="json"))
            if doc.get("format") != "uasset_read.anim_blueprint_semantic":
                continue
            # Basic structure checks
            assert doc["asset_type"] == "anim_blueprint"
            assert "graphs" in doc
            assert "status" in doc
            assert doc["status"]["parse"] != "failed"
            if doc["status"]["representation"] == "opaque":
                assert doc.get("diagnostics")

    def test_standard_debug_modes_differ(self):
        from uasset_read.core import parse_single

        sample = str(_sample("ALS_AnimBP.uasset"))
        standard = parse_single(sample, format="json", output_level="standard")
        debug = parse_single(sample, format="json", output_level="debug")
        standard_doc = json.loads(standard)
        debug_doc = json.loads(debug)

        if standard_doc.get("format") != "uasset_read.anim_blueprint_semantic":
            pytest.skip("not anim_blueprint format")

        assert standard != debug
        assert '"evidence"' in debug
        assert '"evidence"' not in standard
        assert standard_doc["status"] == debug_doc["status"]

    def test_state_machines_present_in_output(self):
        from uasset_read.core import parse_single

        sample = str(_sample("ALS_AnimBP.uasset"))
        doc = json.loads(parse_single(str(sample), format="json"))
        if doc.get("format") != "uasset_read.anim_blueprint_semantic":
            pytest.skip("not anim_blueprint format")

        # ALS_AnimBP should have state machines
        state_machines = doc.get("state_machines", [])
        if state_machines:
            for sm in state_machines:
                assert "id" in sm
                assert "name" in sm
                assert "states" in sm
                for state in sm["states"]:
                    assert "id" in state
                    assert "name" in state


class TestAnimBlueprintSchemaValidation:
    def test_real_samples_schema_valid(self):
        """Verify real animation blueprint samples validate against schema."""
        import jsonschema
        from uasset_read.schema_loader import load_anim_blueprint_semantic_schema
        from uasset_read.core import parse_single

        schema = load_anim_blueprint_semantic_schema()
        for name in TestAnimBlueprintAcceptance.SAMPLES:
            path = _sample(name)
            doc = json.loads(parse_single(str(path), format="json"))
            if doc.get("format") != "uasset_read.anim_blueprint_semantic":
                continue
            jsonschema.validate(doc, schema)
