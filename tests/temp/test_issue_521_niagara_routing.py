"""Tests for #521 Niagara routing migration.

Verifies that:
- NiagaraGraph and NiagaraScript are routed as OPAQUE_CLASS_PAYLOAD
- NiagaraNode* migrated classes are routed as OPAQUE_CLASS_PAYLOAD
- NiagaraSystem still returns OPAQUE_CLASS_PAYLOAD (no regression)
- Other Niagara classes remain SKIP_UNSUPPORTED
"""

from uasset_read.parsers.class_serialization_strategy import (
    SerializationStrategy,
    get_serialization_strategy,
)


# ── Phase 0: class routing migration ────────────────────────────────────

def test_niagara_graph_is_opaque() -> None:
    """NiagaraGraph migrated from _SKIP_CLASSES to _OPAQUE_CLASSES (#521)."""
    assert get_serialization_strategy("NiagaraGraph") == SerializationStrategy.OPAQUE_CLASS_PAYLOAD


def test_niagara_script_is_opaque() -> None:
    """NiagaraScript migrated from _SKIP_CLASSES to _OPAQUE_CLASSES (#521)."""
    assert get_serialization_strategy("NiagaraScript") == SerializationStrategy.OPAQUE_CLASS_PAYLOAD


def test_niagara_system_still_opaque() -> None:
    """NiagaraSystem remains OPAQUE_CLASS_PAYLOAD (no regression)."""
    assert get_serialization_strategy("NiagaraSystem") == SerializationStrategy.OPAQUE_CLASS_PAYLOAD


# ── Phase 4: node family routing migration ──────────────────────────────

_NIAGARA_NODE_OPAQUE_CLASSES = [
    "NiagaraNodeInput",
    "NiagaraNodeFunctionCall",
    "NiagaraNodeParameterMapGet",
    "NiagaraNodeParameterMapSet",
    "NiagaraNodeOp",
    "NiagaraNodeOutput",
    "NiagaraNodeReroute",
    "NiagaraNodeSelect",
    "NiagaraNodeStaticSwitch",
]


def test_niagara_node_input_is_opaque() -> None:
    """NiagaraNodeInput migrated to _OPAQUE_CLASSES (#521 Phase 4)."""
    assert get_serialization_strategy("NiagaraNodeInput") == SerializationStrategy.OPAQUE_CLASS_PAYLOAD


def test_niagara_node_function_call_is_opaque() -> None:
    """NiagaraNodeFunctionCall migrated to _OPAQUE_CLASSES (#521 Phase 4)."""
    assert get_serialization_strategy("NiagaraNodeFunctionCall") == SerializationStrategy.OPAQUE_CLASS_PAYLOAD


def test_niagara_node_parameter_map_get_is_opaque() -> None:
    """NiagaraNodeParameterMapGet migrated to _OPAQUE_CLASSES (#521 Phase 4)."""
    assert get_serialization_strategy("NiagaraNodeParameterMapGet") == SerializationStrategy.OPAQUE_CLASS_PAYLOAD


def test_niagara_node_parameter_map_set_is_opaque() -> None:
    """NiagaraNodeParameterMapSet migrated to _OPAQUE_CLASSES (#521 Phase 4)."""
    assert get_serialization_strategy("NiagaraNodeParameterMapSet") == SerializationStrategy.OPAQUE_CLASS_PAYLOAD


def test_niagara_node_op_is_opaque() -> None:
    """NiagaraNodeOp migrated to _OPAQUE_CLASSES (#521 Phase 4)."""
    assert get_serialization_strategy("NiagaraNodeOp") == SerializationStrategy.OPAQUE_CLASS_PAYLOAD


def test_niagara_node_output_is_opaque() -> None:
    """NiagaraNodeOutput migrated to _OPAQUE_CLASSES (#521 Phase 4)."""
    assert get_serialization_strategy("NiagaraNodeOutput") == SerializationStrategy.OPAQUE_CLASS_PAYLOAD


def test_niagara_node_reroute_is_opaque() -> None:
    """NiagaraNodeReroute migrated to _OPAQUE_CLASSES (#521 Phase 4)."""
    assert get_serialization_strategy("NiagaraNodeReroute") == SerializationStrategy.OPAQUE_CLASS_PAYLOAD


def test_niagara_node_select_is_opaque() -> None:
    """NiagaraNodeSelect migrated to _OPAQUE_CLASSES (#521 Phase 4)."""
    assert get_serialization_strategy("NiagaraNodeSelect") == SerializationStrategy.OPAQUE_CLASS_PAYLOAD


def test_niagara_node_static_switch_is_opaque() -> None:
    """NiagaraNodeStaticSwitch migrated to _OPAQUE_CLASSES (#521 Phase 4)."""
    assert get_serialization_strategy("NiagaraNodeStaticSwitch") == SerializationStrategy.OPAQUE_CLASS_PAYLOAD


def test_unmigrated_niagara_node_still_skip() -> None:
    """NiagaraNode subclasses NOT in allowlist remain SKIP_UNSUPPORTED."""
    # NiagaraNodeDelay is not in the migration list
    assert get_serialization_strategy("NiagaraNodeDelay") == SerializationStrategy.SKIP_UNSUPPORTED


# ── Non-migrated classes ────────────────────────────────────────────────

def test_niagara_data_interface_still_skip() -> None:
    """NiagaraDataInterface remains SKIP_UNSUPPORTED (not migrated)."""
    assert get_serialization_strategy("NiagaraDataInterface") == SerializationStrategy.SKIP_UNSUPPORTED


def test_niagara_script_source_still_skip() -> None:
    """NiagaraScriptSource remains SKIP_UNSUPPORTED (not migrated)."""
    assert get_serialization_strategy("NiagaraScriptSource") == SerializationStrategy.SKIP_UNSUPPORTED


def test_niagara_emitter_still_skip() -> None:
    """NiagaraEmitter remains SKIP_UNSUPPORTED (not migrated)."""
    assert get_serialization_strategy("NiagaraEmitter") == SerializationStrategy.SKIP_UNSUPPORTED


def test_niagara_unknown_class_falls_through_to_tagged() -> None:
    """Unknown Niagara class not in any table gets TAGGED_PROPERTIES_ONLY."""
    assert get_serialization_strategy("NiagaraFooBar") == SerializationStrategy.TAGGED_PROPERTIES_ONLY
