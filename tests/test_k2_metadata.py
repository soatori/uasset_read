"""Task 6: version-gated K2 node metadata — identity must be non-empty."""

from uasset_read.models.analysis import K2NodeMetadata
from uasset_read.parsers.blueprint.graph import BlueprintGraphDecoder

# Node types that must carry non-empty member identity when present in a
# sample. K2Node_IfThenElse is a pure branch node (no FMemberReference) and
# only asserts metadata attachment.
IDENTITY_FIELD_FOR_CLASS = {
    "K2Node_CallFunction": "function_name",
    "K2Node_Event": "event_name",
    "K2Node_VariableGet": "variable_name",
    "K2Node_VariableSet": "variable_name",
    "K2Node_CustomEvent": "event_name",
}
_METADATA_ONLY_CLASSES = frozenset({"K2Node_IfThenElse"})


def _identity_nodes(document, source):
    """All K2 identity-relevant nodes decoded from both attached and source graphs."""
    return [
        node
        for obj in document.objects
        for graph in BlueprintGraphDecoder().decode(obj, document, source=source)
        for node in graph.nodes
        if node.class_name in IDENTITY_FIELD_FOR_CLASS or node.class_name in _METADATA_ONLY_CLASSES
    ]


def _assert_identity(node) -> None:
    assert node.metadata is not None, f"{node.class_name} must carry metadata"
    field_name = IDENTITY_FIELD_FOR_CLASS.get(node.class_name)
    if field_name is None:
        return
    value = getattr(node.metadata, field_name, None)
    assert value, (
        f"{node.class_name} {node.id}: metadata.{field_name} must be non-empty, "
        f"got metadata={node.metadata!r}"
    )


def test_ue58_k2_event_identity_is_non_empty(ue58_blueprint_document, ue58_source):
    """UE5.8 sample: K2Node_Event nodes expose Receive* from EventReference."""
    nodes = [
        n
        for n in _identity_nodes(ue58_blueprint_document, ue58_source)
        if n.class_name == "K2Node_Event"
    ]
    assert nodes, "UE5.8 sample must decode K2Node_Event nodes"
    for node in nodes:
        _assert_identity(node)
        assert node.metadata.event_name.startswith("Receive"), node.metadata.event_name


def test_ue58_k2_metadata_is_not_only_an_allowlisted_tag(
    ue58_blueprint_document, ue58_source
):
    nodes = [
        node
        for obj in ue58_blueprint_document.objects
        for graph in BlueprintGraphDecoder().decode(obj, ue58_blueprint_document, source=ue58_source)
        for node in graph.nodes
        if node.class_name
        in {
            "K2Node_CallFunction",
            "K2Node_Event",
            "K2Node_VariableGet",
            "K2Node_VariableSet",
        }
    ]
    assert nodes
    assert all(node.metadata is not None for node in nodes)
    for node in nodes:
        _assert_identity(node)


def test_stackobot_k2_call_function_identity_is_non_empty(stackobot_document, stackobot_source):
    """StackOBot sample: K2Node_CallFunction nodes expose FunctionReference.MemberName."""
    nodes = [
        n
        for n in _identity_nodes(stackobot_document, stackobot_source)
        if n.class_name == "K2Node_CallFunction"
    ]
    assert nodes, "StackOBot sample must decode K2Node_CallFunction nodes"
    for node in nodes:
        _assert_identity(node)
        assert node.metadata.function_name in {
            "AddMovementInput",
            "BreakVector2D",
            "GetActorForwardVector",
            "GetActorRightVector",
            "AddControllerYawInput",
            "AddControllerPitchInput",
        }


def test_identity_matrix_covers_six_k2_node_types(ue58_blueprint_document, ue58_source, stackobot_document, stackobot_source):
    """Inventory + identity matrix over the six reviewed K2 node types.

    Types absent from today's samples are recorded (count == 0) so a future
    sample flip is visible; present types must yield non-empty identity.
    """
    wanted = set(IDENTITY_FIELD_FOR_CLASS) | _METADATA_ONLY_CLASSES
    counts = {name: 0 for name in sorted(wanted)}
    for document, source in (
        (ue58_blueprint_document, ue58_source),
        (stackobot_document, stackobot_source),
    ):
        for node in _identity_nodes(document, source):
            counts[node.class_name] = counts.get(node.class_name, 0) + 1
            _assert_identity(node)
    # Present types across the two samples (Events + IfThenElse + CallFunction).
    assert counts["K2Node_Event"] > 0
    assert counts["K2Node_CallFunction"] > 0
    # VariableGet / VariableSet / CustomEvent: zero on today's samples only.
    assert counts["K2Node_VariableGet"] == 0, "unexpected sample flip: VariableGet appeared"
    assert counts["K2Node_VariableSet"] == 0, "unexpected sample flip: VariableSet appeared"
    assert counts["K2Node_CustomEvent"] == 0, "unexpected sample flip: CustomEvent appeared"


def test_k2_metadata_unknown_variant_record_is_ranged_and_unresolved():
    from uasset_read.models.byte_ranges import opaque_region

    metadata = K2NodeMetadata(
        node_class="K2Node_Event",
        opaque_properties=[opaque_region(10, 4, "unsupported_k2_variant")],
    )
    assert metadata.opaque_properties
    assert all(item.size > 0 for item in metadata.opaque_properties)
