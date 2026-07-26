"""AnimBlueprint Asset type handler

Parse UAnimBlueprintGeneratedClass animation-specific data:
- BakedStateMachines (baked state machines)
- AnimNotifies (animation notifies)
- SyncGroupNames (sync groups)
- AnimNodeData (animation node constant data)
"""

import logging
from typing import Any

from uasset_read.models.fallback import ExportParseStatus as ParseStatus
from uasset_read.models.ir import (
    AnimBlueprintIR,
    BakedStateMachineIR,
    BakedStateIR,
    BakedExitTransitionIR,
    BakedTransitionIR,
)
from uasset_read.parsers.asset_types.anim_common import (
    ensure_custom_data,
    parse_anim_notifies,
)
from uasset_read.parsers.asset_types.property_extractor import (
    build_properties_dict,
    extract_array_property,
    extract_object_ref,
    extract_property,
    parse_dict_list,
)

logger = logging.getLogger(__name__)


def _extract_int_array(data: Any, key: str) -> list[int]:
    """Extract integer array from dict, skipping non-int values."""
    arr = data.get(key, [])
    return [i for i in arr if isinstance(i, int)]


class AnimBlueprintHandler:
    """AnimBlueprint Asset type handler"""

    # Reflection registration metadata
    export_type: str = "AnimBlueprintGeneratedClass"
    priority: int = 100

    def handle(self, export: Any, context: Any) -> ParseStatus:
        """Handle AnimBlueprintGeneratedClass export

        Args:
            export: ObjectExport instance
            context: parse context

        Returns:
            ParseStatus: SUCCESS or PARTIAL
        """
        try:
            # Extract property data from export
            # ObjectExport has a properties attribute (parsed property list)
            properties_list = getattr(export, "properties", [])
            if not properties_list:
                return ParseStatus.PARTIAL

            # Convert property list to dictionary format（name -> value）
            properties = build_properties_dict(properties_list)

            # Build AnimBlueprintIR
            anim_ir = AnimBlueprintIR()

            # Extract BakedStateMachines
            anim_ir.baked_state_machines = extract_array_property(
                properties, "BakedStateMachines", self._parse_baked_state_machines
            )

            # Extract AnimNotifies
            anim_ir.anim_notifies = extract_array_property(
                properties, "AnimNotifies", parse_anim_notifies
            )

            # Extract TargetSkeleton (object reference)
            extract_object_ref(properties, "TargetSkeleton", anim_ir, "target_skeleton")

            # Extract SyncGroupNames
            anim_ir.sync_group_names = extract_array_property(
                properties, "SyncGroupNames", self._parse_sync_group_names
            )

            # Extract simple properties
            extract_property(
                properties, "GraphAssetPlayerInformation", anim_ir, "graph_asset_player_info"
            )
            extract_property(
                properties, "GraphBlendOptions", anim_ir, "graph_blend_options"
            )
            extract_property(properties, "AnimNodeData", anim_ir, "anim_node_data")

            # Store in export custom data
            ensure_custom_data(export)["anim_blueprint"] = anim_ir

            return ParseStatus.SUCCESS

        except (KeyError, TypeError, ValueError) as e:
            logger.warning("AnimBlueprint parse error: %s", e)
            return ParseStatus.PARTIAL

    def _parse_baked_state_machines(self, data: Any) -> list[BakedStateMachineIR]:
        """Parse baked state machine array"""

        def _parse_machine(machine_data: dict) -> BakedStateMachineIR:
            machine = BakedStateMachineIR(
                machine_name=machine_data.get("MachineName", ""),
                initial_state=machine_data.get("InitialState", 0),
            )
            states_data = machine_data.get("States", [])
            if isinstance(states_data, list):
                machine.states = self._parse_baked_states(states_data)
            transitions_data = machine_data.get("Transitions", [])
            if isinstance(transitions_data, list):
                machine.transitions = self._parse_baked_transitions(transitions_data)
            return machine

        if isinstance(data, dict):
            return [_parse_machine(data)]
        return parse_dict_list(data, _parse_machine)

    def _parse_baked_states(self, data: list) -> list[BakedStateIR]:
        """Parse baked state array"""

        def _parse_state(state_data: dict) -> BakedStateIR:
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
            state.player_node_indices = _extract_int_array(state_data, "PlayerNodeIndices")
            state.layer_node_indices = _extract_int_array(state_data, "LayerNodeIndices")
            transitions_data = state_data.get("Transitions", [])
            if isinstance(transitions_data, list):
                state.transitions = self._parse_baked_exit_transitions(transitions_data)
            return state

        return parse_dict_list(data, _parse_state)

    def _parse_baked_exit_transitions(self, data: list) -> list[BakedExitTransitionIR]:
        """Parse exit transition rules"""

        def _parse_transition(trans_data: dict) -> BakedExitTransitionIR:
            return BakedExitTransitionIR(
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

        return parse_dict_list(data, _parse_transition)

    def _parse_baked_transitions(self, data: list) -> list[BakedTransitionIR]:
        """Parse inter-state transitions"""

        def _parse_transition(trans_data: dict) -> BakedTransitionIR:
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
            extract_object_ref(trans_data, "CustomCurve", transition, "custom_curve")
            extract_object_ref(trans_data, "BlendProfile", transition, "blend_profile")
            return transition

        return parse_dict_list(data, _parse_transition)

    def _parse_sync_group_names(self, data: Any) -> list[str]:
        """Parse sync group names"""
        if not isinstance(data, list):
            return []
        return [name for name in data if isinstance(name, str)]
