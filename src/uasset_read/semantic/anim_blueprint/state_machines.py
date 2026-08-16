"""State machine emission for Animation Blueprint semantic JSON."""
from __future__ import annotations

from typing import Any

from uasset_read.semantic.anim_blueprint.ids import (
    ascii_slug,
    state_machine_id,
    state_id,
)


def emit_state_machines(
    baked_state_machines: list,
    reporting,
    *,
    mode: str,
) -> list[dict]:
    """Emit baked state machines from AnimBlueprintIR.

    Args:
        baked_state_machines: List of BakedStateMachineIR objects
        reporting: AnimBlueprintReporting instance
        mode: "standard" or "debug"

    Returns:
        List of state machine dicts
    """
    machines_json: list[dict] = []
    machine_slug_counts: dict[str, int] = {}

    for machine in baked_state_machines:
        name = getattr(machine, "machine_name", "") or "StateMachine"
        slug = ascii_slug(name)
        seen = machine_slug_counts.get(slug, 0)
        machine_slug_counts[slug] = seen + 1
        if seen:
            slug = f"{slug}_{seen}"

        sm_id = state_machine_id(slug)
        initial_state = getattr(machine, "initial_state", 0)

        # Emit states
        states_json = _emit_states(
            getattr(machine, "states", []) or [], slug, reporting, mode
        )

        # Emit inter-state transitions
        transitions_json = _emit_transitions(
            getattr(machine, "transitions", []) or [], reporting, mode
        )

        sm_dict: dict = {
            "id": sm_id,
            "name": name,
            "initial_state_index": initial_state,
            "states": states_json,
            "transitions": transitions_json,
        }
        machines_json.append(sm_dict)

        reporting.coverage(
            "state_machines",
            "ok" if states_json else "partial",
            reason=f"{len(states_json)} states emitted",
            declared=len(getattr(machine, "states", []) or []),
            emitted=len(states_json),
        )

    return machines_json


def _emit_states(
    states: list,
    machine_slug: str,
    reporting,
    mode: str,
) -> list[dict]:
    """Emit baked states."""
    states_json: list[dict] = []

    for state in states:
        state_name = getattr(state, "state_name", "") or "State"
        state_slug = ascii_slug(state_name)
        sid = state_id(machine_slug, state_slug)

        state_dict: dict = {
            "id": sid,
            "name": state_name,
        }

        is_conduit = getattr(state, "b_is_a_conduit", False)
        if is_conduit:
            state_dict["is_conduit"] = True

        always_reset = getattr(state, "b_always_reset_on_entry", False)
        if always_reset:
            state_dict["always_reset_on_entry"] = True

        player_indices = getattr(state, "player_node_indices", []) or []
        if player_indices:
            state_dict["player_node_indices"] = list(player_indices)

        layer_indices = getattr(state, "layer_node_indices", []) or []
        if layer_indices:
            state_dict["layer_node_indices"] = list(layer_indices)

        # Emit exit transitions
        exit_transitions = _emit_exit_transitions(
            getattr(state, "transitions", []) or [], reporting, mode
        )
        if exit_transitions:
            state_dict["exit_transitions"] = exit_transitions

        if mode == "debug":
            state_dict["evidence"] = {
                "state_root_node_index": getattr(state, "state_root_node_index", -1),
                "entry_rule_node_index": getattr(state, "entry_rule_node_index", -1),
                "start_notify": getattr(state, "start_notify", -1),
                "end_notify": getattr(state, "end_notify", -1),
                "fully_blended_notify": getattr(state, "fully_blended_notify", -1),
            }

        states_json.append(state_dict)

    return states_json


def _emit_exit_transitions(
    transitions: list,
    reporting,
    mode: str,
) -> list[dict]:
    """Bake exit transitions from state."""
    trans_json: list[dict] = []

    for trans in transitions:
        trans_dict: dict = {}

        transition_index = getattr(trans, "transition_index", -1)
        if transition_index >= 0:
            trans_dict["transition_index"] = transition_index

        trigger_time = getattr(trans, "automatic_rule_trigger_time", 0.0)
        if trigger_time != 0.0:
            trans_dict["automatic_rule_trigger_time"] = trigger_time

        if mode == "debug":
            trans_dict["evidence"] = {
                "can_take_delegate_index": getattr(trans, "can_take_delegate_index", -1),
                "custom_result_node_index": getattr(trans, "custom_result_node_index", -1),
                "b_desired_transition_return_value": getattr(trans, "b_desired_transition_return_value", True),
                "b_automatic_remaining_time_rule": getattr(trans, "b_automatic_remaining_time_rule", False),
                "b_only_evaluate_when_active": getattr(trans, "b_only_evaluate_when_active", False),
            }

        if trans_dict:
            trans_json.append(trans_dict)

    return trans_json


def _emit_transitions(
    transitions: list,
    reporting,
    mode: str,
) -> list[dict]:
    """Emit inter-state transitions."""
    trans_json: list[dict] = []

    for trans in transitions:
        previous_state = getattr(trans, "previous_state", -1)
        next_state = getattr(trans, "next_state", -1)

        if previous_state < 0 or next_state < 0:
            continue

        trans_dict: dict = {
            "previous_state": previous_state,
            "next_state": next_state,
        }

        crossfade = getattr(trans, "crossfade_duration", 0.0)
        if crossfade != 0.0:
            trans_dict["crossfade_duration"] = crossfade

        blend_mode = getattr(trans, "blend_mode", None)
        if blend_mode is not None:
            trans_dict["blend_mode"] = blend_mode

        logic_type = getattr(trans, "logic_type", None)
        if logic_type is not None:
            trans_dict["logic_type"] = logic_type

        if mode == "debug":
            evidence: dict = {}
            min_reentry = getattr(trans, "min_time_before_reentry", 0.0)
            if min_reentry != 0.0:
                evidence["min_time_before_reentry"] = min_reentry
            start_notify = getattr(trans, "start_notify", -1)
            if start_notify >= 0:
                evidence["start_notify"] = start_notify
            end_notify = getattr(trans, "end_notify", -1)
            if end_notify >= 0:
                evidence["end_notify"] = end_notify
            interrupt_notify = getattr(trans, "interrupt_notify", -1)
            if interrupt_notify >= 0:
                evidence["interrupt_notify"] = interrupt_notify
            custom_curve = getattr(trans, "custom_curve", None)
            if custom_curve:
                evidence["custom_curve"] = custom_curve
            blend_profile = getattr(trans, "blend_profile", None)
            if blend_profile:
                evidence["blend_profile"] = blend_profile
            if evidence:
                trans_dict["evidence"] = evidence

        trans_json.append(trans_dict)

    return trans_json
