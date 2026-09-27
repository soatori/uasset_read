"""Task 6: owner-aware Blueprint graph IR."""

from tests.fixtures import parse_sample, sample_path
from uasset_read.archive import SourceInfo
from uasset_read.models.analysis import BlueprintNode, BlueprintPin, NodeId, PinLinkRef
from uasset_read.models.document import PackageDocument
from uasset_read.models.object_model import ObjectRecord
from uasset_read.parsers.blueprint.graph import BlueprintGraphDecoder, resolve_pin_links
from uasset_read.sources import MemorySource


def test_graph_identity_includes_owner_for_duplicate_guids():
    first = NodeId(owner_object_id="export:0", node_export_id="export:9")
    second = NodeId(owner_object_id="export:1", node_export_id="export:9")
    assert first != second
    assert str(first) == "export:0/export:9"


def _node(node_id: NodeId) -> BlueprintNode:
    pin = BlueprintPin(
        id="same-pin",
        name="exec",
        direction="output",
        category="exec",
        subcategory="",
        default_value=None,
        default_object_ref=None,
        default_text=None,
        sub_pin_ids=[],
        parent_pin_id=None,
        reference_pass_through_pin_id=None,
        linked=[],
        owner_node_id=node_id,
        raw_region=None,
        is_const=False,
    )
    return BlueprintNode(
        id=node_id,
        guid="same",
        class_name="SyntheticNode",
        title="SyntheticNode",
        metadata=None,
        pins=[pin],
        raw_region=None,
    )


def test_duplicate_pin_guid_resolves_by_owner():
    left = _node(NodeId("export:0", "export:9"))
    right = _node(NodeId("export:1", "export:10"))
    ref = PinLinkRef(
        from_node_id=left.id,
        from_pin_guid="same-pin",
        to_owner_node_id=right.id,
        to_pin_guid="same-pin",
    )
    result = resolve_pin_links([left, right], [ref])
    assert result.links[0].to_node_id == right.id
    assert result.links[0].raw_ref == ref
    assert not result.diagnostics


def test_stackobot_graph_names_and_kinds(stackobot_document, stackobot_source):
    obj = next(o for o in stackobot_document.objects if o.id == "export:0")
    graphs = {g.name: g for g in BlueprintGraphDecoder().decode(obj, stackobot_document, source=stackobot_source)}
    assert set(graphs) == {"EventGraph", "UserConstructionScript"}
    assert graphs["EventGraph"].kind == "event_graph"
    assert graphs["UserConstructionScript"].kind == "construction_script"
    assert len(graphs["EventGraph"].nodes) == 14


def test_selected_owner_uses_same_graph_dependency_closure_as_full_decode():
    full = parse_sample("StackOBot_BP_Drone.uasset", depth="decode")
    selected = parse_sample(
        "StackOBot_BP_Drone.uasset",
        depth="decode",
        object_ids=["export:0"],
    )
    full_owner = next(obj for obj in full.objects if obj.id == "export:0")
    selected_owner = next(obj for obj in selected.objects if obj.id == "export:0")
    assert (full_owner.semantic or {}).get("graphs") == (selected_owner.semantic or {}).get("graphs")


def test_source_read_falls_back_to_document_package_path():
    path = sample_path("StackOBot_BP_Drone.uasset")
    obj = ObjectRecord(id="export:0", table_index=0, name="BP_Drone")
    document = PackageDocument(
        objects=[obj],
        source=SourceInfo(kind="loose", name=path.name, size=path.stat().st_size, path=str(path)),
    )
    graphs = BlueprintGraphDecoder().decode(obj, document, source=MemorySource(b"\x00"))
    assert sorted(g.name for g in graphs) == ["EventGraph", "UserConstructionScript"]


def test_source_read_without_package_path_is_explicit():
    obj = ObjectRecord(id="export:0", table_index=0, name="BP_Drone")
    document = PackageDocument(objects=[obj])
    graphs = BlueprintGraphDecoder().decode(obj, document, source=MemorySource(b"\x00"))
    assert graphs == []
    assert [d.code for d in document.diagnostics] == ["graph_package_path_unresolved"]


def test_source_read_not_requested_stays_silent():
    obj = ObjectRecord(id="export:0", table_index=0, name="BP_Drone")
    document = PackageDocument(objects=[obj])
    assert BlueprintGraphDecoder().decode(obj, document) == []
    assert document.diagnostics == []
