"""动画蓝图相关单元测试（合并）

合并自以下文件：
- test_anim_blueprint_skip.py
- test_anim_blueprint_strategy.py
- test_anim_graph_types.py
- test_anim_ir_builder.py
- test_anim_ir_models.py
"""
import pytest
from unittest.mock import MagicMock

from uasset_read.parsers.class_specific_skip import SKIP_CLASS_NAMES
from uasset_read.parsers.class_serialization_strategy import (
    get_serialization_strategy,
    SerializationStrategy,
    _SKIP_CLASSES,
)
from uasset_read.ir_builder import _build_export_ir, _build_graph_ir
from uasset_read.models.ir import (
    AnimBlueprintIR,
    AnimMontageIR,
    AnimNotifyIR,
    AnimSequenceIR,
    BakedExitTransitionIR,
    BakedStateIR,
    BakedStateMachineIR,
    BakedTransitionIR,
)


# ============================================================
# 跳过列表测试（原 test_anim_blueprint_skip.py）
# ============================================================

def test_anim_blueprint_generated_class_not_skipped():
    """AnimBlueprintGeneratedClass 应该从跳过列表中移除"""
    assert "AnimBlueprintGeneratedClass" not in SKIP_CLASS_NAMES


def test_anim_blueprint_extension_still_skipped():
    """AnimBlueprintExtension 应该在 class_serialization_strategy 的跳过列表中（自定义序列化）"""
    assert "AnimBlueprintExtension" in _SKIP_CLASSES


# ============================================================
# 序列化策略测试（原 test_anim_blueprint_strategy.py）
# ============================================================

def test_anim_blueprint_strategy():
    """AnimBlueprintGeneratedClass 应该使用 TAGGED_PROPERTIES_ONLY"""
    strategy = get_serialization_strategy("AnimBlueprintGeneratedClass")
    assert strategy == SerializationStrategy.TAGGED_PROPERTIES_ONLY


# ============================================================
# 图类型识别测试（原 test_anim_graph_types.py）
# ============================================================

GRAPH_CASES = [
    ("UAnimationStateMachineGraph", "state_machine"),
    ("UAnimationStateGraph", "state"),
    ("UAnimationTransitionGraph", "transition"),
    ("UAnimationConduitGraph", "conduit"),
    ("UAnimationGraph", "animation"),
]


@pytest.mark.parametrize("graph_class,expected_type", GRAPH_CASES,
                         ids=[c[0].removeprefix("U") for c in GRAPH_CASES])
def test_animation_graph_type_recognition(graph_class, expected_type):
    """应正确识别动画图类型"""
    graph = MagicMock()
    graph.graph_class = graph_class
    graph.graph_name = f"Test{graph_class.removeprefix('U')}"
    graph.graph_guid = "00000000-0000-0000-0000-000000000001"
    graph.nodes = []
    graph.execution_chains = []
    graph.subgraphs = []

    result = _build_graph_ir(graph)
    assert result.graph_type == expected_type


# ============================================================
# IR Builder 测试（原 test_anim_ir_builder.py）
# ============================================================

class TestAnimIRBuilder:
    def test_anim_blueprint_ir_attached(self):
        """AnimBlueprintIR 应该附加到 ExportIR"""
        export = MagicMock()
        export.object_name = "TestAnimBP"
        export.class_index = MagicMock()
        export.class_index.index = 0
        export.super_index = MagicMock()
        export.super_index.index = -1
        export.outer_index = MagicMock()
        export.outer_index.index = -1
        export.template_index = MagicMock()
        export.template_index.index = -1
        export.object_flags = 0
        export.serial_size = 100
        export.serial_offset = 0
        export.package_flags = 0
        export.b_forced_export = False
        export.b_not_for_client = False
        export.b_not_for_server = False
        export.b_is_inherited_instance = False
        export.b_not_always_loaded_for_editor_game = True
        export.b_is_asset = True
        export.b_generate_public_hash = False
        export.script_serialization_start_offset = 0
        export.properties = []
        export.graphs = []
        export.bulk_data_header = None
        export._asset_type_data = None
        export.parse_status = "success"
        export.fallback_reason = None
        export.error_message = None
        export.custom_data = {
            "anim_blueprint": AnimBlueprintIR(
                baked_state_machines=[BakedStateMachineIR(machine_name="Locomotion")]
            )
        }

        result = MagicMock()
        result.blueprint = None
        result.import_map = []
        result.export_map = []

        ir = _build_export_ir(0, export, result)
        assert hasattr(ir, "anim_blueprint")
        assert ir.anim_blueprint is not None
        assert len(ir.anim_blueprint.baked_state_machines) == 1
        assert ir.anim_blueprint.baked_state_machines[0].machine_name == "Locomotion"

    def test_anim_sequence_ir_attached(self):
        """AnimSequenceIR 应该附加到 ExportIR"""
        export = MagicMock()
        export.object_name = "TestAnimSeq"
        export.class_index = MagicMock()
        export.class_index.index = 0
        export.super_index = MagicMock()
        export.super_index.index = -1
        export.outer_index = MagicMock()
        export.outer_index.index = -1
        export.template_index = MagicMock()
        export.template_index.index = -1
        export.object_flags = 0
        export.serial_size = 100
        export.serial_offset = 0
        export.package_flags = 0
        export.b_forced_export = False
        export.b_not_for_client = False
        export.b_not_for_server = False
        export.b_is_inherited_instance = False
        export.b_not_always_loaded_for_editor_game = True
        export.b_is_asset = True
        export.b_generate_public_hash = False
        export.script_serialization_start_offset = 0
        export.properties = []
        export.graphs = []
        export.bulk_data_header = None
        export._asset_type_data = None
        export.parse_status = "success"
        export.fallback_reason = None
        export.error_message = None
        export.custom_data = {
            "anim_sequence": AnimSequenceIR(
                target_skeleton="/Game/Skeletons/SK_Hero",
                sequence_length=10.0,
            )
        }

        result = MagicMock()
        result.blueprint = None
        result.import_map = []
        result.export_map = []

        ir = _build_export_ir(0, export, result)
        assert hasattr(ir, "anim_sequence")
        assert ir.anim_sequence is not None
        assert ir.anim_sequence.target_skeleton == "/Game/Skeletons/SK_Hero"

    def test_anim_montage_ir_attached(self):
        """AnimMontageIR 应该附加到 ExportIR"""
        export = MagicMock()
        export.object_name = "TestAnimMontage"
        export.class_index = MagicMock()
        export.class_index.index = 0
        export.super_index = MagicMock()
        export.super_index.index = -1
        export.outer_index = MagicMock()
        export.outer_index.index = -1
        export.template_index = MagicMock()
        export.template_index.index = -1
        export.object_flags = 0
        export.serial_size = 100
        export.serial_offset = 0
        export.package_flags = 0
        export.b_forced_export = False
        export.b_not_for_client = False
        export.b_not_for_server = False
        export.b_is_inherited_instance = False
        export.b_not_always_loaded_for_editor_game = True
        export.b_is_asset = True
        export.b_generate_public_hash = False
        export.script_serialization_start_offset = 0
        export.properties = []
        export.graphs = []
        export.bulk_data_header = None
        export._asset_type_data = None
        export.parse_status = "success"
        export.fallback_reason = None
        export.error_message = None
        export.custom_data = {
            "anim_montage": AnimMontageIR(
                sync_group="DefaultSlot",
                rate_scale=1.5,
                composite_sections=[{"section_name": "Section1", "next_section_name": "Section2"}],
                slot_anim_tracks=[{"slot_node_name": "DefaultSlot"}],
                branching_point_markers=[{"notify_index": 0, "trigger_time": 0.5}],
                blend_in_option="Linear",
                blend_out_option="Linear",
                float_curve_names=["Curve1", "Curve2"],
            )
        }

        result = MagicMock()
        result.blueprint = None
        result.import_map = []
        result.export_map = []

        ir = _build_export_ir(0, export, result)
        assert hasattr(ir, "anim_montage")
        assert ir.anim_montage is not None
        assert ir.anim_montage.sync_group == "DefaultSlot"
        assert ir.anim_montage.rate_scale == 1.5
        assert len(ir.anim_montage.composite_sections) == 1
        assert ir.anim_montage.composite_sections[0]["section_name"] == "Section1"
        assert len(ir.anim_montage.slot_anim_tracks) == 1
        assert ir.anim_montage.slot_anim_tracks[0]["slot_node_name"] == "DefaultSlot"
        assert len(ir.anim_montage.branching_point_markers) == 1
        assert ir.anim_montage.branching_point_markers[0]["trigger_time"] == 0.5
        assert ir.anim_montage.blend_in_option == "Linear"
        assert ir.anim_montage.blend_out_option == "Linear"
        assert len(ir.anim_montage.float_curve_names) == 2
        assert ir.anim_montage.float_curve_names == ["Curve1", "Curve2"]


# ============================================================
# IR 数据模型测试（原 test_anim_ir_models.py）
# ============================================================

class TestAnimNotifyIR:
    def test_default_values(self):
        notify = AnimNotifyIR(notify_name="TestNotify")
        assert notify.notify_name == "TestNotify"
        assert notify.trigger_time_offset == 0.0
        assert notify.duration == 0.0
        assert notify.notify_class is None
        assert notify.track_index == 0

    def test_with_values(self):
        notify = AnimNotifyIR(
            notify_name="PlaySound",
            trigger_time_offset=0.5,
            duration=1.0,
            notify_class="AN_Footstep",
            track_index=2,
        )
        assert notify.notify_name == "PlaySound"
        assert notify.trigger_time_offset == 0.5
        assert notify.duration == 1.0
        assert notify.notify_class == "AN_Footstep"
        assert notify.track_index == 2


class TestBakedStateIR:
    def test_default_values(self):
        state = BakedStateIR(state_name="Idle")
        assert state.state_name == "Idle"
        assert state.state_root_node_index == -1
        assert state.player_node_indices == []
        assert state.b_is_a_conduit is False
        assert state.transitions == []


class TestBakedTransitionIR:
    def test_default_values(self):
        transition = BakedTransitionIR()
        assert transition.previous_state == -1
        assert transition.next_state == -1
        assert transition.crossfade_duration == 0.0
        assert transition.blend_mode is None


class TestBakedStateMachineIR:
    def test_default_values(self):
        sm = BakedStateMachineIR(machine_name="Locomotion")
        assert sm.machine_name == "Locomotion"
        assert sm.initial_state == 0
        assert sm.states == []
        assert sm.transitions == []


class TestAnimBlueprintIR:
    def test_default_values(self):
        ir = AnimBlueprintIR()
        assert ir.target_skeleton is None
        assert ir.baked_state_machines == []
        assert ir.anim_notifies == []
        assert ir.sync_group_names == []


class TestAnimSequenceIR:
    def test_default_values(self):
        ir = AnimSequenceIR()
        assert ir.target_skeleton is None
        assert ir.additive_anim_type is None
        assert ir.sequence_length == 0.0
        assert ir.notifies == []
        assert ir.has_compressed_data is False

    def test_with_notifies(self):
        ir = AnimSequenceIR(
            notifies=[
                AnimNotifyIR(notify_name="TestNotify"),
            ]
        )
        assert len(ir.notifies) == 1
        assert ir.notifies[0].notify_name == "TestNotify"


class TestAnimMontageIR:
    def test_default_values(self):
        ir = AnimMontageIR()
        assert ir.blend_mode_in is None
        assert ir.blend_mode_out is None
        assert ir.rate_scale == 1.0
        assert ir.notifies == []
        assert ir.composite_sections == []
