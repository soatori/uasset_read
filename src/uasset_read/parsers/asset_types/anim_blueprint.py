"""AnimBlueprint 资产类型处理器

解析 UAnimBlueprintGeneratedClass 的动画特有数据：
- BakedStateMachines（烘焙后的状态机）
- AnimNotifies（动画通知）
- SyncGroupNames（同步组）
- AnimNodeData（动画节点常量数据）
"""
from __future__ import annotations

from typing import Any

from uasset_read.models.fallback import ExportParseStatus as ParseStatus
from uasset_read.models.ir import (
    AnimBlueprintIR,
    AnimNotifyIR,
    BakedStateMachineIR,
    BakedStateIR,
    BakedExitTransitionIR,
    BakedTransitionIR,
)


class AnimBlueprintHandler:
    """AnimBlueprint 资产类型处理器"""

    def handle(self, export: Any, context: Any) -> ParseStatus:
        """处理 AnimBlueprintGeneratedClass export

        Args:
            export: ObjectExport 实例
            context: 解析上下文

        Returns:
            ParseStatus: SUCCESS 或 PARTIAL
        """
        try:
            # 从 export.instance（CDO）提取动画数据
            instance = getattr(export, "instance", None)
            if instance is None:
                return ParseStatus.PARTIAL

            properties = getattr(instance, "properties", {})
            if not properties:
                return ParseStatus.PARTIAL

            # 构建 AnimBlueprintIR
            anim_ir = AnimBlueprintIR()

            # 提取 BakedStateMachines
            if "BakedStateMachines" in properties:
                anim_ir.baked_state_machines = self._parse_baked_state_machines(
                    properties["BakedStateMachines"]
                )

            # 提取 AnimNotifies
            if "AnimNotifies" in properties:
                anim_ir.anim_notifies = self._parse_anim_notifies(
                    properties["AnimNotifies"]
                )

            # 提取 TargetSkeleton
            if "TargetSkeleton" in properties:
                skeleton_ref = properties["TargetSkeleton"]
                if isinstance(skeleton_ref, dict):
                    anim_ir.target_skeleton = skeleton_ref.get("object_path")

            # 提取 SyncGroupNames
            if "SyncGroupNames" in properties:
                anim_ir.sync_group_names = self._parse_sync_group_names(
                    properties["SyncGroupNames"]
                )

            # 存储到 export 的自定义数据
            if not hasattr(export, "custom_data"):
                export.custom_data = {}
            export.custom_data["anim_blueprint"] = anim_ir

            return ParseStatus.SUCCESS

        except Exception as e:
            # 记录错误但不中断解析
            if hasattr(context, "warnings"):
                context.warnings.append(f"AnimBlueprint 解析错误: {e}")
            return ParseStatus.PARTIAL

    def _parse_baked_state_machines(self, data: Any) -> list[BakedStateMachineIR]:
        """解析烘焙后的状态机数组"""
        result = []
        if not isinstance(data, (list, dict)):
            return result

        machines = data if isinstance(data, list) else [data]
        for machine_data in machines:
            if not isinstance(machine_data, dict):
                continue

            machine = BakedStateMachineIR(
                machine_name=machine_data.get("MachineName", ""),
                initial_state=machine_data.get("InitialState", 0),
            )

            # 解析 States
            states_data = machine_data.get("States", [])
            if isinstance(states_data, list):
                machine.states = self._parse_baked_states(states_data)

            # 解析 Transitions
            transitions_data = machine_data.get("Transitions", [])
            if isinstance(transitions_data, list):
                machine.transitions = self._parse_baked_transitions(transitions_data)

            result.append(machine)

        return result

    def _parse_baked_states(self, data: list) -> list[BakedStateIR]:
        """解析烘焙后的状态数组"""
        result = []
        for state_data in data:
            if not isinstance(state_data, dict):
                continue

            state = BakedStateIR(
                state_name=state_data.get("StateName", ""),
                state_root_node_index=state_data.get("StateRootNodeIndex", -1),
                entry_rule_node_index=state_data.get("EntryRuleNodeIndex", -1),
                start_notify=state_data.get("StartNotify", -1),
                end_notify=state_data.get("EndNotify", -1),
                fully_blended_notify=state_data.get("FullyBlendedNotify", -1),
                b_always_reset_on_entry=state_data.get("bAlwaysResetOnEntry", False),
                b_is_a_conduit=state_data.get("bIsAConduit", False),
            )

            # 解析 PlayerNodeIndices
            player_indices = state_data.get("PlayerNodeIndices", [])
            if isinstance(player_indices, list):
                state.player_node_indices = [
                    i for i in player_indices if isinstance(i, int)
                ]

            # 解析 LayerNodeIndices
            layer_indices = state_data.get("LayerNodeIndices", [])
            if isinstance(layer_indices, list):
                state.layer_node_indices = [
                    i for i in layer_indices if isinstance(i, int)
                ]

            # 解析退出转换
            transitions_data = state_data.get("Transitions", [])
            if isinstance(transitions_data, list):
                state.transitions = self._parse_baked_exit_transitions(transitions_data)

            result.append(state)

        return result

    def _parse_baked_exit_transitions(self, data: list) -> list[BakedExitTransitionIR]:
        """解析退出转换规则"""
        result = []
        for trans_data in data:
            if not isinstance(trans_data, dict):
                continue

            transition = BakedExitTransitionIR(
                can_take_delegate_index=trans_data.get("CanTakeDelegateIndex", -1),
                custom_result_node_index=trans_data.get("CustomResultNodeIndex", -1),
                transition_index=trans_data.get("TransitionIndex", -1),
                b_desired_transition_return_value=trans_data.get(
                    "bDesiredTransitionReturnValue", True
                ),
                b_automatic_remaining_time_rule=trans_data.get(
                    "bAutomaticRemainingTimeRule", False
                ),
                automatic_rule_trigger_time=trans_data.get(
                    "AutomaticRuleTriggerTime", 0.0
                ),
                b_only_evaluate_when_active=trans_data.get(
                    "bOnlyEvaluateWhenActive", False
                ),
            )
            result.append(transition)

        return result

    def _parse_baked_transitions(self, data: list) -> list[BakedTransitionIR]:
        """解析状态间转换"""
        result = []
        for trans_data in data:
            if not isinstance(trans_data, dict):
                continue

            transition = BakedTransitionIR(
                previous_state=trans_data.get("PreviousState", -1),
                next_state=trans_data.get("NextState", -1),
                crossfade_duration=trans_data.get("CrossfadeDuration", 0.0),
                min_time_before_reentry=trans_data.get("MinTimeBeforeReentry", 0.0),
                blend_mode=trans_data.get("BlendMode"),
                logic_type=trans_data.get("LogicType"),
                start_notify=trans_data.get("StartNotify", -1),
                end_notify=trans_data.get("EndNotify", -1),
                interrupt_notify=trans_data.get("InterruptNotify", -1),
            )

            # 解析对象引用
            custom_curve = trans_data.get("CustomCurve")
            if isinstance(custom_curve, dict):
                transition.custom_curve = custom_curve.get("object_path")

            blend_profile = trans_data.get("BlendProfile")
            if isinstance(blend_profile, dict):
                transition.blend_profile = blend_profile.get("object_path")

            result.append(transition)

        return result

    def _parse_anim_notifies(self, data: Any) -> list[AnimNotifyIR]:
        """解析动画通知数组"""
        result = []
        if not isinstance(data, list):
            return result

        for notify_data in data:
            if not isinstance(notify_data, dict):
                continue

            notify = AnimNotifyIR(
                notify_name=notify_data.get("NotifyName", ""),
                trigger_time_offset=notify_data.get("TriggerTimeOffset", 0.0),
                end_trigger_time_offset=notify_data.get("EndTriggerTimeOffset", 0.0),
                trigger_weight_threshold=notify_data.get("TriggerWeightThreshold", 0.0),
                duration=notify_data.get("Duration", 0.0),
                notify_class=notify_data.get("NotifyClass"),
                notify_state_class=notify_data.get("NotifyStateClass"),
                montage_tick_type=notify_data.get("MontageTickType"),
                notify_trigger_chance=notify_data.get("NotifyTriggerChance", 1.0),
                notify_filter_type=notify_data.get("NotifyFilterType"),
                notify_filter_lod=notify_data.get("NotifyFilterLOD", 0),
                b_converted_from_branching_point=notify_data.get(
                    "bConvertedFromBranchingPoint", False
                ),
                track_index=notify_data.get("TrackIndex", 0),
            )

            # 解析对象引用
            linked_montage = notify_data.get("LinkedMontage")
            if isinstance(linked_montage, dict):
                notify.linked_montage = linked_montage.get("object_path")

            linked_sequence = notify_data.get("LinkedSequence")
            if isinstance(linked_sequence, dict):
                notify.linked_sequence = linked_sequence.get("object_path")

            result.append(notify)

        return result

    def _parse_sync_group_names(self, data: Any) -> list[str]:
        """解析同步组名称"""
        if not isinstance(data, list):
            return []
        return [name for name in data if isinstance(name, str)]
