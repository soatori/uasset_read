"""动画蓝图 IR 数据模型单元测试"""
import pytest
from uasset_read.models.ir import (
    AnimBlueprintIR,
    BakedStateMachineIR,
    BakedStateIR,
    BakedExitTransitionIR,
    BakedTransitionIR,
    AnimNotifyIR,
    AnimSequenceIR,
    AnimMontageIR,
)


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
