"""N2CStruct/N2CGraph/N2CNode/N2CPin dataclass tests."""
import pytest

from uasset_read.n2c.schema import N2CPin, N2CNode, N2CGraph, N2CStruct


class TestN2CPin:
    """N2CPin dataclass tests."""

    def test_minimal_pin(self):
        pin = N2CPin(pin_name="Exec", pin_category="exec", direction="input")
        assert pin.pin_name == "Exec"
        assert pin.pin_category == "exec"
        assert pin.pin_subcategory == ""
        assert pin.direction == "input"
        assert pin.default_value is None

    def test_pin_with_optional_fields(self):
        pin = N2CPin(
            pin_name="ReturnValue",
            pin_category="object",
            pin_subcategory="Actor",
            direction="output",
            default_value="None",
        )
        assert pin.pin_subcategory == "Actor"
        assert pin.default_value == "None"

    def test_pin_to_dict(self):
        pin = N2CPin(pin_name="Exec", pin_category="exec", direction="input")
        d = pin.to_dict()
        assert d["pin_name"] == "Exec"
        assert d["pin_category"] == "exec"
        assert d["pin_subcategory"] == ""
        assert d["direction"] == "input"
        assert d["default_value"] is None

    def test_pin_to_dict_with_all_fields(self):
        pin = N2CPin(
            pin_name="Target",
            pin_category="object",
            pin_subcategory="Actor",
            direction="input",
            default_value="self",
        )
        d = pin.to_dict()
        assert d["pin_name"] == "Target"
        assert d["pin_category"] == "object"
        assert d["pin_subcategory"] == "Actor"
        assert d["direction"] == "input"
        assert d["default_value"] == "self"


class TestN2CNode:
    """N2CNode dataclass tests."""

    def test_minimal_node(self):
        node = N2CNode(id="N1", type="CallFunction", name="Print String")
        assert node.id == "N1"
        assert node.type == "CallFunction"
        assert node.name == "Print String"
        assert node.comment == ""
        assert node.pure is False
        assert node.latent is False
        assert node.input_pins == []
        assert node.output_pins == []
        assert node.extra_data == {}

    def test_node_with_pins(self):
        pin = N2CPin(pin_name="Exec", pin_category="exec", direction="input")
        node = N2CNode(
            id="N2",
            type="Event",
            name="BeginPlay",
            input_pins=[pin],
        )
        assert len(node.input_pins) == 1
        assert node.input_pins[0].pin_name == "Exec"

    def test_node_with_extra_data(self):
        node = N2CNode(
            id="N3",
            type="CallFunction",
            name="GetActorLocation",
            extra_data={"member_name": "GetActorLocation", "member_parent": "Actor"},
        )
        assert node.extra_data["member_name"] == "GetActorLocation"
        assert node.extra_data["member_parent"] == "Actor"

    def test_node_with_flags(self):
        node = N2CNode(
            id="N4",
            type="CallFunction",
            name="PureFunc",
            pure=True,
            latent=False,
        )
        assert node.pure is True
        assert node.latent is False

    def test_node_to_dict(self):
        node = N2CNode(id="N1", type="CallFunction", name="Print String")
        d = node.to_dict()
        assert d["id"] == "N1"
        assert d["type"] == "CallFunction"
        assert d["name"] == "Print String"
        assert d["comment"] == ""
        assert d["pure"] is False
        assert d["latent"] is False
        assert d["input_pins"] == []
        assert d["output_pins"] == []
        assert d["extra_data"] == {}

    def test_node_to_dict_with_content(self):
        pin = N2CPin(pin_name="Exec", pin_category="exec", direction="input")
        node = N2CNode(
            id="N1",
            type="CallFunction",
            name="Print String",
            comment="My comment",
            pure=True,
            input_pins=[pin],
            extra_data={"member_name": "PrintString"},
        )
        d = node.to_dict()
        assert d["id"] == "N1"
        assert d["type"] == "CallFunction"
        assert d["name"] == "Print String"
        assert d["comment"] == "My comment"
        assert d["pure"] is True
        assert d["input_pins"] == [{"pin_name": "Exec", "pin_category": "exec", "pin_subcategory": "", "direction": "input", "default_value": None}]
        assert d["extra_data"]["member_name"] == "PrintString"


class TestN2CGraph:
    """N2CGraph dataclass tests."""

    def test_minimal_graph(self):
        g = N2CGraph(name="EventGraph", graph_type="event", nodes=[])
        assert g.name == "EventGraph"
        assert g.graph_type == "event"
        assert g.nodes == []
        assert "execution" in g.flows
        assert "data" in g.flows

    def test_graph_to_dict(self):
        node = N2CNode(id="N1", type="Event", name="BeginPlay")
        g = N2CGraph(name="EventGraph", graph_type="event", nodes=[node])
        d = g.to_dict()
        assert d["name"] == "EventGraph"
        assert d["graph_type"] == "event"
        assert len(d["nodes"]) == 1
        assert d["nodes"][0]["id"] == "N1"
        assert d["flows"]["execution"] == []
        assert d["flows"]["data"] == {}


class TestN2CStruct:
    """N2CStruct dataclass tests."""

    def test_empty_struct(self):
        s = N2CStruct(metadata={"Name": "MyBlueprint"})
        assert s.version == "1.0.0"
        assert s.metadata == {"Name": "MyBlueprint"}
        assert s.graphs == []
        assert s.structs == []
        assert s.enums == []

    def test_to_dict_empty(self):
        s = N2CStruct(metadata={})
        d = s.to_dict()
        assert d["version"] == "1.0.0"
        assert d["metadata"] == {}
        assert d["graphs"] == []
        assert d["structs"] == []
        assert d["enums"] == []

    def test_to_dict_with_graphs(self):
        node = N2CNode(id="N1", type="Event", name="BeginPlay")
        graph = N2CGraph(name="EventGraph", graph_type="event", nodes=[node])
        s = N2CStruct(
            metadata={"Name": "BP_Test", "BlueprintType": "Blueprint"},
            graphs=[graph],
        )
        d = s.to_dict()
        assert d["version"] == "1.0.0"
        assert d["metadata"]["Name"] == "BP_Test"
        assert len(d["graphs"]) == 1
        assert d["graphs"][0]["name"] == "EventGraph"
        assert d["graphs"][0]["nodes"][0]["id"] == "N1"
        assert d["structs"] == []
        assert d["enums"] == []
