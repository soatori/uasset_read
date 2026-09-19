"""Task 6: version-gated K2 node metadata."""

from uasset_read.models.analysis import K2NodeMetadata
from uasset_read.parsers.blueprint.graph import BlueprintGraphDecoder


def test_ue58_k2_reference_metadata_is_not_only_an_allowlisted_tag(
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


def test_k2_metadata_unknown_variant_record_is_ranged_and_unresolved():
    from uasset_read.models.byte_ranges import opaque_region

    metadata = K2NodeMetadata(
        node_class="K2Node_Event",
        opaque_properties=[opaque_region(10, 4, "unsupported_k2_variant")],
    )
    assert metadata.opaque_properties
    assert all(item.size > 0 for item in metadata.opaque_properties)
