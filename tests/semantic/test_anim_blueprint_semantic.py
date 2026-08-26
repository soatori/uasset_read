"""AnimBlueprint semantic extractor tests.

Tests the AnimBlueprint domain extractor with real AnimBP samples.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from uasset_read.pipeline.core import parse_uasset_with_linker
from uasset_read.ir_builder import build_package_ir
from uasset_read.semantic.builder import build_semantic_ir
from uasset_read.semantic.models import SemanticIR
from uasset_read.semantic.projection import project_semantic
from uasset_read.semantic.render import render_semantic_json
from types import SimpleNamespace


# ABP_RifleAnimLayers parses cleanly; ALS_AnimBP has corrupted class names
# and resolves to "unknown" — tested separately with relaxed assertions.
_CLEAN_ANIMBP = ["ABP_RifleAnimLayers.uasset"]
_ALL_ANIMBP = ["ABP_RifleAnimLayers.uasset", "ALS_AnimBP.uasset"]


def _build_semantic(samples_dir: Path, filename: str) -> SemanticIR:
    """Parse and build SemanticIR for a sample."""
    sample = samples_dir / filename
    result = parse_uasset_with_linker(str(sample), tolerant=True)
    ir = build_package_ir(result)
    return build_semantic_ir(ir, source_path=str(sample))


class TestAnimBlueprintSemanticExtraction:
    """AnimBlueprint semantic extractor output validation."""

    @pytest.mark.parametrize(
        "filename",
        _CLEAN_ANIMBP,
        ids=[s.split(".")[0] for s in _CLEAN_ANIMBP],
    )
    def test_animbp_has_semantic_ir(self, samples_dir: Path, filename: str):
        """Clean AnimBlueprint sample produces a valid SemanticIR with correct type."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_semantic(samples_dir, filename)
        assert semantic is not None
        assert semantic.asset_type == "anim_blueprint"
        assert semantic.asset.name != "unknown"

    @pytest.mark.parametrize(
        "filename",
        _ALL_ANIMBP,
        ids=[s.split(".")[0] for s in _ALL_ANIMBP],
    )
    def test_animbp_produces_valid_ir(self, samples_dir: Path, filename: str):
        """All AnimBP samples produce a valid SemanticIR (type may be unknown)."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_semantic(samples_dir, filename)
        assert semantic is not None
        assert semantic.asset_type in ("anim_blueprint", "unknown")

    @pytest.mark.parametrize(
        "filename",
        _ALL_ANIMBP,
        ids=[s.split(".")[0] for s in _ALL_ANIMBP],
    )
    def test_animbp_status_valid(self, samples_dir: Path, filename: str):
        """AnimBlueprint SemanticIR has valid status fields."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_semantic(samples_dir, filename)
        assert semantic.status.parse in ("complete", "partial", "failed")
        assert semantic.status.representation in ("full", "partial", "opaque")

    @pytest.mark.parametrize(
        "filename",
        _ALL_ANIMBP,
        ids=[s.split(".")[0] for s in _ALL_ANIMBP],
    )
    def test_animbp_has_content_when_not_opaque(self, samples_dir: Path, filename: str):
        """AnimBlueprint SemanticIR has non-empty content when not opaque."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_semantic(samples_dir, filename)
        if semantic.status.representation != "opaque":
            assert semantic.content, f"{filename}: content is empty"

    @pytest.mark.parametrize(
        "filename",
        _ALL_ANIMBP,
        ids=[s.split(".")[0] for s in _ALL_ANIMBP],
    )
    def test_animbp_has_references_or_domain_format(self, samples_dir: Path, filename: str):
        """AnimBlueprint SemanticIR has references or uses domain format (which owns them)."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_semantic(samples_dir, filename)
        # Domain formats own references internally, so top-level may be empty
        if semantic.format != "uasset_read.asset_semantic":
            # Domain format — references are in content
            assert isinstance(semantic.references, tuple)
        else:
            assert len(semantic.references) > 0


class TestAnimBlueprintDomainFormat:
    """AnimBlueprint domain format specifics."""

    def test_animbp_format_field(self, samples_dir: Path):
        """AnimBlueprint domain format is set."""
        if not (samples_dir / "ABP_RifleAnimLayers.uasset").exists():
            pytest.skip("Sample not found")

        semantic = _build_semantic(samples_dir, "ABP_RifleAnimLayers.uasset")
        assert semantic.format is not None
        assert semantic.format_version is not None

    def test_animbp_asset_meta(self, samples_dir: Path):
        """AnimBlueprint SemanticIR has correct asset metadata."""
        if not (samples_dir / "ABP_RifleAnimLayers.uasset").exists():
            pytest.skip("Sample not found")

        semantic = _build_semantic(samples_dir, "ABP_RifleAnimLayers.uasset")
        assert semantic.asset.package
        assert semantic.asset.name


class TestSyntheticAnimBlueprintIR:
    """Tests with minimal synthetic IR to verify data pipeline."""

    def _make_synthetic_package_ir(self):
        """Build a minimal PackageIR with AnimBlueprint + AnimBlueprintGeneratedClass."""
        # AnimGraphNode_UnknownPlugin node
        unknown_node = SimpleNamespace(
            node_class="AnimGraphNode_UnknownPlugin",
            class_name="AnimGraphNode_UnknownPlugin",
            node_guid="guid-unknown",
            pins=[],
        )

        # AnimGraphNode_SequencePlayer node with FPoseLink output pin
        seq_pin_out = SimpleNamespace(
            pin_guid="pin-seq-out",
            pin_name="Pose",
            pin_category="struct",
            pin_subcategory="FPoseLink",
            pin_subcategory_object_name="",
            direction=None,  # will be set below
            orphaned=False,
            orphaned_pin=False,
            not_connectable=False,
            sub_pin_guids=None,
            parent_pin_guid="",
        )
        # Mark as output
        seq_pin_out.direction = 0  # EGPD_Output

        seq_node = SimpleNamespace(
            node_class="AnimGraphNode_SequencePlayer",
            class_name="AnimGraphNode_SequencePlayer",
            node_guid="guid-seq",
            pins=[seq_pin_out],
        )

        # AnimGraphNode_Root node with FPoseLink input pin
        root_pin_in = SimpleNamespace(
            pin_guid="pin-root-in",
            pin_name="Result",
            pin_category="struct",
            pin_subcategory="FPoseLink",
            pin_subcategory_object_name="",
            direction=1,  # EGPD_Input
            orphaned=False,
            orphaned_pin=False,
            not_connectable=False,
            sub_pin_guids=None,
            parent_pin_guid="",
        )
        root_node = SimpleNamespace(
            node_class="AnimGraphNode_Root",
            class_name="AnimGraphNode_Root",
            node_guid="guid-root",
            pins=[root_pin_in],
        )

        # Graph
        graph = SimpleNamespace(
            graph_name="AnimGraph",
            graph_class="AnimGraph",
            graph_guid="graph-guid-1",
            nodes=[seq_node, root_node, unknown_node],
            subgraphs=[],
        )

        # Baked state machine
        state1 = SimpleNamespace(
            state_name="Idle",
            b_is_a_conduit=False,
            b_always_reset_on_entry=False,
            player_node_indices=[0],
            layer_node_indices=[],
            transitions=[],
            state_root_node_index=0,
            entry_rule_node_index=-1,
            start_notify=-1,
            end_notify=-1,
            fully_blended_notify=-1,
        )
        state2 = SimpleNamespace(
            state_name="Run",
            b_is_a_conduit=False,
            b_always_reset_on_entry=False,
            player_node_indices=[1],
            layer_node_indices=[],
            transitions=[],
            state_root_node_index=1,
            entry_rule_node_index=-1,
            start_notify=-1,
            end_notify=-1,
            fully_blended_notify=-1,
        )
        transition = SimpleNamespace(
            previous_state=0,
            next_state=1,
            crossfade_duration=0.2,
            blend_mode=None,
            logic_type=None,
        )
        baked_sm = SimpleNamespace(
            machine_name="Locomotion",
            initial_state=0,
            states=[state1, state2],
            transitions=[transition],
        )

        # Anim notify
        notify = SimpleNamespace(
            notify_name="Footstep",
            trigger_time_offset=0.0,
            duration=0.0,
            notify_class=None,
            notify_state_class=None,
            track_index=0,
            end_trigger_time_offset=0.0,
            trigger_weight_threshold=0.0,
            montage_tick_type=None,
            notify_trigger_chance=1.0,
            notify_filter_type=None,
            notify_filter_lod=0,
            b_converted_from_branching_point=False,
            linked_montage=None,
            linked_sequence=None,
        )

        # AnimBlueprintIR
        anim_bp_ir = SimpleNamespace(
            baked_state_machines=[baked_sm],
            anim_notifies=[notify],
            sync_group_names=["Locomotion"],
            target_skeleton=None,
        )

        # AnimBlueprintGeneratedClass export (has the anim data)
        gen_class_export = SimpleNamespace(
            object_name="TestABP_C",
            object_class="AnimBlueprintGeneratedClass",
            index=1,
            b_is_asset=False,
            outer_index_resolved=None,
            parse_status="success",
            fallback_reason=None,
            anim_blueprint=anim_bp_ir,
            graphs=[],
            variables=None,
        )

        # AnimBlueprint primary export (no anim data)
        primary_export = SimpleNamespace(
            object_name="TestABP",
            object_class="AnimBlueprint",
            index=0,
            b_is_asset=True,
            outer_index_resolved=None,
            parse_status="success",
            fallback_reason=None,
            anim_blueprint=None,  # data is on generated class
            graphs=[graph],
            variables=None,
        )

        # Package IR
        header = SimpleNamespace(
            package_name="/Game/TestABP",
            saved_by_engine_version="5.3.0",
        )
        blueprint = SimpleNamespace(
            parent_class="",
            interfaces=[],
            components=[],
            functions=[],
        )
        package_ir = SimpleNamespace(
            header=header,
            exports=[primary_export, gen_class_export],
            imports=[],
            variables=[],
            blueprint=blueprint,
            diagnostics_data=None,
        )
        return package_ir

    def test_state_machine_extracted_from_generated_class(self):
        """State machines are found even when data is on generated class export."""
        from uasset_read.semantic.builder import build_semantic_ir
        pkg = self._make_synthetic_package_ir()
        ir = build_semantic_ir(pkg, source_path="/fake/TestABP.uasset")
        assert ir.format == "uasset_read.anim_blueprint_semantic"
        content = ir.content
        assert content["state_machines"][0]["name"] == "Locomotion"

    def test_anim_notify_extracted(self):
        """Anim notifies are extracted from generated class."""
        from uasset_read.semantic.builder import build_semantic_ir
        pkg = self._make_synthetic_package_ir()
        ir = build_semantic_ir(pkg, source_path="/fake/TestABP.uasset")
        assert ir.content["anim_notifies"][0]["name"] == "Footstep"

    def test_sync_groups_extracted(self):
        """Sync groups are extracted from generated class."""
        from uasset_read.semantic.builder import build_semantic_ir
        pkg = self._make_synthetic_package_ir()
        ir = build_semantic_ir(pkg, source_path="/fake/TestABP.uasset")
        assert ir.content["sync_groups"] == ["Locomotion"]

    def test_anim_graph_node_recognized(self):
        """AnimGraphNode_SequencePlayer is recognized as sequence_player."""
        from uasset_read.semantic.builder import build_semantic_ir
        pkg = self._make_synthetic_package_ir()
        ir = build_semantic_ir(pkg, source_path="/fake/TestABP.uasset")
        nodes = ir.content["graphs"][0]["nodes"]
        seq_node = next(n for n in nodes if n["kind"] == "sequence_player")
        assert seq_node is not None

    def test_unknown_node_is_opaque(self):
        """Unknown plugin node has opaque status."""
        from uasset_read.semantic.builder import build_semantic_ir
        pkg = self._make_synthetic_package_ir()
        ir = build_semantic_ir(pkg, source_path="/fake/TestABP.uasset")
        nodes = ir.content["graphs"][0]["nodes"]
        unknown = next(n for n in nodes if n.get("status") == "opaque")
        assert unknown["source_type"] == "AnimGraphNode_UnknownPlugin"

    def test_opaque_diagnostic_emitted(self):
        """Unknown nodes produce ABP_NODE_UNRECOGNIZED diagnostic."""
        from uasset_read.semantic.builder import build_semantic_ir
        pkg = self._make_synthetic_package_ir()
        ir = build_semantic_ir(pkg, source_path="/fake/TestABP.uasset")
        diag_codes = [d.code for d in ir.diagnostics]
        assert "ABP_NODE_UNRECOGNIZED" in diag_codes

    def test_pose_flow_has_edges(self):
        """Pose flow edges connect output pose to input pose."""
        from uasset_read.semantic.builder import build_semantic_ir
        pkg = self._make_synthetic_package_ir()
        ir = build_semantic_ir(pkg, source_path="/fake/TestABP.uasset")
        graph = ir.content["graphs"][0]
        pose_flow = graph.get("pose_flow", {})
        edges = pose_flow.get("edges", [])
        assert len(edges) >= 1
        edge = edges[0]
        assert edge["from"]["pose_pin"].startswith("pose.output.")
        assert edge["to"]["pose_pin"].startswith("pose.input.")

    def test_representation_partial_with_opaque_nodes(self):
        """Representation is partial when opaque nodes exist."""
        from uasset_read.semantic.builder import build_semantic_ir
        pkg = self._make_synthetic_package_ir()
        ir = build_semantic_ir(pkg, source_path="/fake/TestABP.uasset")
        assert ir.status.representation == "partial"
