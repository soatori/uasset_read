"""Roundtrip tests for to_n2c_json / from_n2c_json."""
import pytest

from uasset_read.models.core import UEdGraph, UEdGraphNode, UEdGraphPin, FEdGraphPinType
from uasset_read.n2c.schema import N2CStruct, N2CGraph, N2CNode, N2CPin


def _make_call_function_node(guid="guid-001", pos_x=0, pos_y=0, has_exec=True):
    """Create a mock K2Node_CallFunction node."""
    node = UEdGraphNode(
        node_guid=guid,
        class_name="K2Node_CallFunction",
        node_pos_x=pos_x,
        node_pos_y=pos_y,
        node_comment="",
    )
    node.node_data = type('MockNodeData', (), {
        'function_reference': type('MockFR', (), {
            'member_name': 'PrintString',
            'member_parent': 'KismetSystemLibrary',
        })(),
    })()
    if has_exec:
        node.pins.append(UEdGraphPin(
            pin_id=f"{guid}-exec-in",
            pin_name="execute",
            direction=0,
            pin_type=FEdGraphPinType(pin_category="exec"),
        ))
        node.pins.append(UEdGraphPin(
            pin_id=f"{guid}-exec-out",
            pin_name="then",
            direction=1,
            pin_type=FEdGraphPinType(pin_category="exec"),
        ))
    node.pins.append(UEdGraphPin(
        pin_id=f"{guid}-in-string",
        pin_name="InString",
        direction=0,
        pin_type=FEdGraphPinType(pin_category="string"),
    ))
    if not has_exec:
        # Pure function: only output pins
        node.pins.append(UEdGraphPin(
            pin_id=f"{guid}-return",
            pin_name="ReturnValue",
            direction=1,
            pin_type=FEdGraphPinType(pin_category="object", pin_subcategory="Actor"),
        ))
    return node


def _make_event_node(guid="guid-event", event_name="ReceiveBeginPlay"):
    """Create a mock K2Node_Event node."""
    node = UEdGraphNode(
        node_guid=guid,
        class_name="K2Node_Event",
        node_pos_x=-300,
        node_pos_y=0,
        node_comment="",
    )
    node.node_data = type('MockNodeData', (), {
        'event_reference': type('MockER', (), {
            'member_name': event_name,
            'member_parent': None,
        })(),
    })()
    node.pins.append(UEdGraphPin(
        pin_id=f"{guid}-exec-out",
        pin_name="then",
        direction=1,
        pin_type=FEdGraphPinType(pin_category="exec"),
    ))
    return node


def _make_knot_node(guid="guid-knot"):
    """Create a mock K2Node_Knot node (should be excluded)."""
    node = UEdGraphNode(
        node_guid=guid,
        class_name="K2Node_Knot",
        node_pos_x=0,
        node_pos_y=0,
        node_comment="",
    )
    node.pins.append(UEdGraphPin(
        pin_id=f"{guid}-input",
        pin_name="InputPin",
        direction=0,
        pin_type=FEdGraphPinType(pin_category="exec"),
    ))
    node.pins.append(UEdGraphPin(
        pin_id=f"{guid}-output",
        pin_name="OutputPin",
        direction=1,
        pin_type=FEdGraphPinType(pin_category="exec"),
    ))
    return node


def _make_if_then_else_node(guid="guid-branch"):
    """Create a mock K2Node_IfThenElse node."""
    node = UEdGraphNode(
        node_guid=guid,
        class_name="K2Node_IfThenElse",
        node_pos_x=200,
        node_pos_y=0,
        node_comment="",
    )
    node.pins.append(UEdGraphPin(
        pin_id=f"{guid}-exec-in",
        pin_name="execute",
        direction=0,
        pin_type=FEdGraphPinType(pin_category="exec"),
    ))
    node.pins.append(UEdGraphPin(
        pin_id=f"{guid}-condition",
        pin_name="Condition",
        direction=0,
        pin_type=FEdGraphPinType(pin_category="bool"),
    ))
    node.pins.append(UEdGraphPin(
        pin_id=f"{guid}-true",
        pin_name="True",
        direction=1,
        pin_type=FEdGraphPinType(pin_category="exec"),
    ))
    node.pins.append(UEdGraphPin(
        pin_id=f"{guid}-false",
        pin_name="False",
        direction=1,
        pin_type=FEdGraphPinType(pin_category="exec"),
    ))
    return node


def _make_variable_get_node(guid="guid-varget", var_name="MyVar"):
    """Create a mock K2Node_VariableGet node."""
    node = UEdGraphNode(
        node_guid=guid,
        class_name="K2Node_VariableGet",
        node_pos_x=100,
        node_pos_y=100,
        node_comment="",
    )
    node.node_data = type('MockNodeData', (), {
        'variable_reference': type('MockVR', (), {
            'member_name': var_name,
            'member_parent': None,
        })(),
    })()
    node.pins.append(UEdGraphPin(
        pin_id=f"{guid}-return",
        pin_name=var_name,
        direction=1,
        pin_type=FEdGraphPinType(pin_category="int"),
    ))
    return node


def _make_simple_graph():
    """Create a simple EventGraph with Event -> CallFunction (wired exec)."""
    event = _make_event_node("guid-event")
    call = _make_call_function_node("guid-call")
    # Wire exec output from Event to exec input of CallFunction
    event.pins[0].linked_to_raw = [{"pin_id": "guid-call-exec-in", "pin_guid": "guid-call-exec-in"}]
    graph = UEdGraph(graph_name="EventGraph", graph_class="EdGraph")
    graph.nodes.append(event)
    graph.nodes.append(call)
    return graph


class TestToN2CJson:
    """Tests for to_n2c_json() conversion."""

    def test_to_n2c_json_empty_graph(self):
        """Empty graph returns valid N2CStruct dict with all top-level keys."""
        from uasset_read.n2c import to_n2c_json
        graph = UEdGraph(graph_name="EmptyGraph", graph_class="EdGraph")
        result = to_n2c_json(graphs=[graph])
        assert "version" in result
        assert "metadata" in result
        assert "graphs" in result
        assert "structs" in result
        assert "enums" in result
        assert result["version"] == "1.0.0"
        assert len(result["graphs"]) == 1
        assert result["graphs"][0]["nodes"] == []

    def test_to_n2c_json_short_ids(self):
        """Node IDs are short format (N1, N2, ...)."""
        from uasset_read.n2c import to_n2c_json
        graph = _make_simple_graph()
        result = to_n2c_json(graphs=[graph])
        node_ids = [n["id"] for n in result["graphs"][0]["nodes"]]
        for nid in node_ids:
            assert nid.startswith("N"), f"Expected short ID, got {nid}"

    def test_to_n2c_json_excludes_knots(self):
        """Knot nodes are not present in output."""
        from uasset_read.n2c import to_n2c_json
        graph = UEdGraph(graph_name="EventGraph", graph_class="EdGraph")
        graph.nodes.append(_make_event_node())
        graph.nodes.append(_make_knot_node())
        graph.nodes.append(_make_call_function_node())
        result = to_n2c_json(graphs=[graph])
        node_types = [n["type"] for n in result["graphs"][0]["nodes"]]
        assert "Knot" not in node_types
        # Should have Event and CallFunction
        assert len(result["graphs"][0]["nodes"]) == 2

    def test_to_n2c_json_semantic_types(self):
        """Node type field uses semantic type, not raw class_name."""
        from uasset_read.n2c import to_n2c_json
        graph = _make_simple_graph()
        result = to_n2c_json(graphs=[graph])
        types = {n["id"]: n["type"] for n in result["graphs"][0]["nodes"]}
        # Check that at least one is a semantic type (not raw K2Node_*)
        for tid, ttype in types.items():
            assert not ttype.startswith("K2Node_"), f"Raw class_name found: {ttype}"

    def test_to_n2c_json_callfunction_extra_data(self):
        """CallFunction nodes have member_name, member_parent in extra_data."""
        from uasset_read.n2c import to_n2c_json
        graph = UEdGraph(graph_name="EventGraph", graph_class="EdGraph")
        graph.nodes.append(_make_call_function_node())
        result = to_n2c_json(graphs=[graph])
        cf_nodes = [n for n in result["graphs"][0]["nodes"] if n["type"] == "CallFunction"]
        assert len(cf_nodes) == 1
        assert cf_nodes[0]["extra_data"].get("member_name") == "PrintString"

    def test_to_n2c_json_execution_flows_chain_format(self):
        """Execution flows contain chain strings like 'N1->N2'."""
        from uasset_read.n2c import to_n2c_json
        graph = _make_simple_graph()
        result = to_n2c_json(graphs=[graph])
        exec_flows = result["graphs"][0]["flows"]["execution"]
        # Should have at least one chain string
        has_chain = any(isinstance(f, str) and "->" in f for f in exec_flows)
        assert has_chain, f"Expected chain format in execution flows, got {exec_flows}"

    def test_to_n2c_json_data_flows_compact(self):
        """Data flows contain compact mapping like {'N1.P0': 'N2.P1'}."""
        from uasset_read.n2c import to_n2c_json
        graph = UEdGraph(graph_name="EventGraph", graph_class="EdGraph")
        src = _make_call_function_node("guid-src", has_exec=False)  # Pure function with output
        tgt = _make_call_function_node("guid-tgt")
        # Connect output to input via pin
        src.pins[-1].linked_to_raw = [{"pin_id": "guid-tgt-in-string", "pin_guid": "guid-tgt-in-string"}]
        graph.nodes.append(src)
        graph.nodes.append(tgt)
        result = to_n2c_json(graphs=[graph])
        data_flows = result["graphs"][0]["flows"]["data"]
        # Should have compact format keys
        for key in data_flows:
            assert "." in key, f"Expected compact format, got key: {key}"

    def test_to_n2c_json_metadata_from_result(self):
        """When result provided, metadata is extracted."""
        from uasset_read.n2c import to_n2c_json
        from uasset_read.models.result import ParseResult
        from uasset_read.models.blueprint import BlueprintMetadata

        summary = type('MockSummary', (), {'package_name': 'BP_Test'})()
        bp = BlueprintMetadata(
            is_blueprint=True,
            parent_class="Actor",
        )
        result_obj = type('MockResult', (), {
            'summary': summary,
            'blueprint': bp,
            'graphs': [],
        })()
        result = to_n2c_json(result=result_obj)
        assert result["metadata"]["Name"] == "BP_Test"
        assert result["metadata"]["BlueprintClass"] == "Actor"


class TestFromN2CJson:
    """Tests for from_n2c_json() reconstruction."""

    def test_from_n2c_json_basic(self):
        """from_n2c_json reconstructs N2CStruct instance."""
        from uasset_read.n2c import from_n2c_json
        data = {
            "version": "1.0.0",
            "metadata": {"Name": "Test"},
            "graphs": [],
            "structs": [],
            "enums": [],
        }
        struct = from_n2c_json(data)
        assert isinstance(struct, N2CStruct)
        assert struct.version == "1.0.0"
        assert struct.metadata == {"Name": "Test"}

    def test_from_n2c_json_with_nodes(self):
        """from_n2c_json reconstructs nodes with pins."""
        from uasset_read.n2c import from_n2c_json
        data = {
            "version": "1.0.0",
            "metadata": {},
            "graphs": [{
                "name": "EventGraph",
                "graph_type": "event",
                "nodes": [{
                    "id": "N1",
                    "type": "Event",
                    "name": "BeginPlay",
                    "comment": "Start",
                    "pure": False,
                    "latent": False,
                    "input_pins": [],
                    "output_pins": [{"pin_name": "then", "pin_category": "exec", "pin_subcategory": "", "direction": "output"}],
                    "extra_data": {"event_name": "ReceiveBeginPlay"},
                }],
                "flows": {"execution": [], "data": {}},
            }],
            "structs": [],
            "enums": [],
        }
        struct = from_n2c_json(data)
        assert isinstance(struct, N2CStruct)
        assert len(struct.graphs) == 1
        assert len(struct.graphs[0].nodes) == 1
        node = struct.graphs[0].nodes[0]
        assert isinstance(node, N2CNode)
        assert node.id == "N1"
        assert node.type == "Event"
        assert len(node.output_pins) == 1
        assert isinstance(node.output_pins[0], N2CPin)
        assert node.output_pins[0].pin_name == "then"

    def test_from_n2c_json_roundtrip(self):
        """to_n2c_json -> from_n2c_json -> to_dict produces identical output."""
        from uasset_read.n2c import to_n2c_json, from_n2c_json
        graph = _make_simple_graph()
        original = to_n2c_json(graphs=[graph])
        reconstructed = from_n2c_json(original)
        rebuilt = reconstructed.to_dict()
        assert rebuilt == original

    def test_from_n2c_json_invalid_raises(self):
        """from_n2c_json raises ValueError on invalid input."""
        from uasset_read.n2c import from_n2c_json
        with pytest.raises(ValueError):
            from_n2c_json({"invalid": "data"})

    def test_from_n2c_json_missing_optional_defaults(self):
        """Missing optional fields use defaults."""
        from uasset_read.n2c import from_n2c_json
        data = {
            "version": "1.0.0",
            "metadata": {},
            "graphs": [{
                "name": "EventGraph",
                "graph_type": "event",
                "nodes": [{"id": "N1", "type": "Event", "name": "BP"}],
            }],
            "structs": [],
            "enums": [],
        }
        struct = from_n2c_json(data)
        node = struct.graphs[0].nodes[0]
        assert node.comment == ""
        assert node.pure is False
        assert node.latent is False
        assert node.extra_data == {}

    def test_from_n2c_json_extra_data_preserved(self):
        """extra_data dict is correctly reconstructed."""
        from uasset_read.n2c import from_n2c_json
        data = {
            "version": "1.0.0",
            "metadata": {},
            "graphs": [{
                "name": "EventGraph",
                "graph_type": "event",
                "nodes": [{
                    "id": "N1",
                    "type": "CallFunction",
                    "name": "Test",
                    "extra_data": {"member_name": "Foo", "member_parent": "Bar"},
                }],
            }],
            "structs": [],
            "enums": [],
        }
        struct = from_n2c_json(data)
        node = struct.graphs[0].nodes[0]
        assert node.extra_data == {"member_name": "Foo", "member_parent": "Bar"}
